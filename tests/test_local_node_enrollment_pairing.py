from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import sys
from pathlib import Path


NOW = datetime(2026, 5, 21, 0, 5, tzinfo=timezone.utc)
PAIRING_CODE = "123456"


def _load_hybrid_modules():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core.hybrid import local_node_enrollment, local_node_manifest

    return local_node_enrollment, local_node_manifest


def _signed_manifest_fixture():
    enrollment, manifest_mod = _load_hybrid_modules()
    private_key_b64, public_key_b64 = manifest_mod.generate_test_local_node_keypair()
    manifest = manifest_mod.build_test_local_node_manifest()
    signed = manifest_mod.sign_local_node_manifest(manifest, private_key_b64=private_key_b64)
    request = enrollment.LocalNodeEnrollmentRequest(
        node_id=manifest.identity.node_id,
        key_id=signed.signature.key_id,
        mode="official_hybrid_private",
        requested_capabilities=manifest.capabilities,
    )
    challenge = enrollment.create_pairing_challenge(request, pairing_code=PAIRING_CODE)
    return enrollment, manifest_mod, signed, public_key_b64, challenge


def test_pairing_code_can_be_consumed_once_for_verified_session() -> None:
    enrollment, _manifest_mod, signed, public_key_b64, challenge = _signed_manifest_fixture()

    result = enrollment.consume_pairing_code(
        challenge,
        pairing_code=PAIRING_CODE,
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=NOW,
    )
    reused = enrollment.consume_pairing_code(
        result.challenge,
        pairing_code=PAIRING_CODE,
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=NOW,
    )

    assert result.accepted is True
    assert result.status == "enrolled_verified"
    assert result.session is not None
    assert result.session.enrolled_node_id == signed.manifest.identity.node_id
    assert result.session.key_id == signed.signature.key_id
    assert result.session.manifest_id == signed.manifest.manifest_id
    assert result.session.mode == "official_hybrid_private"
    assert result.session.signed_origin_verified is True
    assert result.session.trusted is False
    assert result.session.production_trust_material is False
    assert reused.accepted is False
    assert reused.status == "pairing_code_reused"


def test_pairing_code_plaintext_is_not_retained() -> None:
    enrollment, _manifest_mod, _signed, _public_key_b64, challenge = _signed_manifest_fixture()

    public_challenge = challenge.to_public_dict()

    assert public_challenge["pairing_code_hash"].startswith("sha256:")
    assert PAIRING_CODE not in repr(challenge)
    assert PAIRING_CODE not in str(asdict(challenge))
    assert PAIRING_CODE not in str(public_challenge)
    assert challenge.pairing_code_hash == enrollment.pairing_code_hash(
        challenge_id=challenge.challenge_id,
        node_id=challenge.node_id,
        pairing_code=PAIRING_CODE,
    )


def test_session_token_plaintext_is_not_retained() -> None:
    enrollment, _manifest_mod, signed, public_key_b64, challenge = _signed_manifest_fixture()
    token = "session-token-fixture"

    result = enrollment.consume_pairing_code(
        challenge,
        pairing_code=PAIRING_CODE,
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=NOW,
        session_token=token,
    )

    assert result.session is not None
    assert result.session.session_token_hash is not None
    assert result.session.session_token_hash.startswith("sha256:")
    assert token not in str(asdict(result.session))
    assert token not in str(result.session.to_public_dict())


def test_invalid_or_expired_pairing_code_is_rejected() -> None:
    enrollment, _manifest_mod, signed, public_key_b64, challenge = _signed_manifest_fixture()

    invalid = enrollment.consume_pairing_code(
        challenge,
        pairing_code="654321",
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=NOW,
    )
    expired = enrollment.consume_pairing_code(
        replace(challenge, expires_at="2026-05-21T00:01:00Z"),
        pairing_code=PAIRING_CODE,
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=NOW,
    )

    assert invalid.accepted is False
    assert invalid.status == "invalid_pairing_code"
    assert invalid.session is None
    assert expired.accepted is False
    assert expired.status == "expired_pairing_code"
    assert expired.challenge.enrollment_state == "expired"


def test_enrollment_without_verified_manifest_is_gated() -> None:
    enrollment, _manifest_mod, signed, public_key_b64, challenge = _signed_manifest_fixture()
    tampered = replace(
        signed,
        manifest=replace(
            signed.manifest,
            capabilities=signed.manifest.capabilities + ("unknown.future.capability",),
        ),
    )

    result = enrollment.consume_pairing_code(
        challenge,
        pairing_code=PAIRING_CODE,
        signed_manifest=tampered,
        public_key_b64=public_key_b64,
        now=NOW,
    )

    assert result.accepted is True
    assert result.status == "enrolled_unverified"
    assert result.session is not None
    assert result.session.capabilities == ()
    decision = enrollment.evaluate_enrollment_session_capability(
        result.session,
        "private_files",
        now=NOW,
    )
    assert decision.allowed is False
    assert decision.status == "not_verified"


def test_revoked_or_expired_session_denies_local_node_work() -> None:
    enrollment, _manifest_mod, signed, public_key_b64, challenge = _signed_manifest_fixture()
    result = enrollment.consume_pairing_code(
        challenge,
        pairing_code=PAIRING_CODE,
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=NOW,
        session_expires_at="2026-05-21T00:06:00Z",
    )
    assert result.session is not None

    revoked = enrollment.revoke_enrollment_session(result.session)
    revoked_decision = enrollment.evaluate_enrollment_session_capability(revoked, "private_files", now=NOW)
    expired_decision = enrollment.evaluate_enrollment_session_capability(
        result.session,
        "private_files",
        now=datetime(2026, 5, 21, 0, 7, tzinfo=timezone.utc),
    )

    assert revoked_decision.allowed is False
    assert revoked_decision.status == "revoked"
    assert expired_decision.allowed is False
    assert expired_decision.status == "expired"


def test_dangerous_capability_still_requires_approval() -> None:
    enrollment, _manifest_mod, signed, public_key_b64, challenge = _signed_manifest_fixture()
    result = enrollment.consume_pairing_code(
        challenge,
        pairing_code=PAIRING_CODE,
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=NOW,
    )
    assert result.session is not None

    decision = enrollment.evaluate_enrollment_session_capability(
        result.session,
        "dangerous_operations",
        now=NOW,
    )

    assert decision.allowed is True
    assert decision.status == "approval_required"
    assert decision.approval_required is True
