from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import sys
from pathlib import Path


NOW = datetime(2026, 5, 21, 0, 5, tzinfo=timezone.utc)
PAIRING_CODE = "123456"


def _load_hybrid():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core import hybrid

    return hybrid


def _session_fixture(*, capabilities: tuple[str, ...] = ("local_tools", "dangerous_operations")):
    hybrid = _load_hybrid()
    private_key_b64, public_key_b64 = hybrid.generate_test_local_node_keypair()
    manifest = hybrid.build_test_local_node_manifest(capabilities=capabilities)
    signed = hybrid.sign_local_node_manifest(manifest, private_key_b64=private_key_b64)
    request = hybrid.LocalNodeEnrollmentRequest(
        node_id=manifest.identity.node_id,
        key_id=signed.signature.key_id,
        mode="official_hybrid_private",
        requested_capabilities=manifest.capabilities,
    )
    challenge = hybrid.create_pairing_challenge(request, pairing_code=PAIRING_CODE)
    pairing = hybrid.consume_pairing_code(
        challenge,
        pairing_code=PAIRING_CODE,
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=NOW,
    )
    assert pairing.session is not None
    return hybrid, private_key_b64, public_key_b64, pairing.session


def _signed_action(
    *,
    capability: str = "local_tools",
    args_hash: str | None = None,
    nonce: str = "action-nonce",
    expires_at: str = "2026-05-21T00:10:00Z",
):
    hybrid, private_key_b64, public_key_b64, session = _session_fixture()
    expected_args_hash = args_hash or hybrid.action_args_hash({"tool": "synthetic_inspection"})
    unsigned = hybrid.build_unsigned_local_node_action_envelope(
        action_id="action-1",
        node_id=session.enrolled_node_id,
        session_id=session.session_id,
        mode="official_hybrid_private",
        capability=capability,
        args_hash=expected_args_hash,
        expires_at=expires_at,
        nonce=nonce,
    )
    signed = hybrid.sign_local_node_action_envelope(unsigned, private_key_b64=private_key_b64)
    return hybrid, public_key_b64, session, signed, expected_args_hash


def test_valid_envelope_for_safe_declared_capability_is_preview_only() -> None:
    hybrid, public_key_b64, session, signed, expected_args_hash = _signed_action()

    result = hybrid.verify_local_node_action_envelope(
        signed,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=expected_args_hash,
        nonce_store=hybrid.InMemoryNonceStore(),
        mode="official_hybrid_private",
        now=NOW,
    )

    assert result.status == "approval_required"
    assert result.signature_valid is True
    assert result.accepted_for_preview is True
    assert result.execute_allowed is False
    assert result.session_bound is True
    assert result.capability_declared is True
    assert result.production_trust_material is False


def test_tampered_args_hash_is_rejected() -> None:
    hybrid, public_key_b64, session, signed, _expected_args_hash = _signed_action()

    result = hybrid.verify_local_node_action_envelope(
        signed,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=hybrid.action_args_hash({"tool": "tampered"}),
        nonce_store=hybrid.InMemoryNonceStore(),
        mode="official_hybrid_private",
        now=NOW,
    )

    assert result.status == "invalid_signature"
    assert result.signature_valid is False
    assert result.execute_allowed is False


def test_replayed_nonce_is_rejected() -> None:
    hybrid, public_key_b64, session, signed, expected_args_hash = _signed_action()
    nonce_store = hybrid.InMemoryNonceStore()

    first = hybrid.verify_local_node_action_envelope(
        signed,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=expected_args_hash,
        nonce_store=nonce_store,
        mode="official_hybrid_private",
        now=NOW,
    )
    second = hybrid.verify_local_node_action_envelope(
        signed,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=expected_args_hash,
        nonce_store=nonce_store,
        mode="official_hybrid_private",
        now=NOW,
    )

    assert first.signature_valid is True
    assert second.status == "replayed_nonce"
    assert second.execute_allowed is False


def test_wrong_session_or_undeclared_capability_is_rejected() -> None:
    hybrid, public_key_b64, session, signed, expected_args_hash = _signed_action()
    wrong_session = replace(session, session_id="other-session")

    wrong_session_result = hybrid.verify_local_node_action_envelope(
        signed,
        session=wrong_session,
        public_key_b64=public_key_b64,
        expected_args_hash=expected_args_hash,
        nonce_store=hybrid.InMemoryNonceStore(),
        mode="official_hybrid_private",
        now=NOW,
    )
    assert wrong_session_result.status == "session_mismatch"
    assert wrong_session_result.execute_allowed is False
    # Use the original signed envelope key and session path for a clean undeclared capability check.
    hybrid2, private_key_b64, public_key_b64_2, session2 = _session_fixture(capabilities=("local_tools",))
    args_hash = hybrid2.action_args_hash({"tool": "synthetic_inspection"})
    unsigned = hybrid2.build_unsigned_local_node_action_envelope(
        action_id="action-2",
        node_id=session2.enrolled_node_id,
        session_id=session2.session_id,
        mode="official_hybrid_private",
        capability="private_files",
        args_hash=args_hash,
        nonce="action-nonce-undeclared",
    )
    signed_undeclared = hybrid2.sign_local_node_action_envelope(unsigned, private_key_b64=private_key_b64)
    undeclared_result = hybrid2.verify_local_node_action_envelope(
        signed_undeclared,
        session=session2,
        public_key_b64=public_key_b64_2,
        expected_args_hash=args_hash,
        nonce_store=hybrid2.InMemoryNonceStore(),
        mode="official_hybrid_private",
        now=NOW,
    )

    assert undeclared_result.status == "capability_not_declared"
    assert undeclared_result.execute_allowed is False


def test_wrong_audience_is_rejected() -> None:
    hybrid, public_key_b64, session, signed, expected_args_hash = _signed_action()
    wrong_audience = replace(signed, audience="wrong-audience")

    result = hybrid.verify_local_node_action_envelope(
        wrong_audience,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=expected_args_hash,
        nonce_store=hybrid.InMemoryNonceStore(),
        mode="official_hybrid_private",
        now=NOW,
    )

    assert result.status == "session_mismatch"
    assert result.reasons == ("action_audience_mismatch",)
    assert result.signature_valid is False
    assert result.execute_allowed is False


def test_expired_envelope_and_dangerous_capability_are_gated() -> None:
    hybrid, public_key_b64, session, expired, expected_args_hash = _signed_action(
        expires_at="2026-05-21T00:01:00Z",
    )
    expired_result = hybrid.verify_local_node_action_envelope(
        expired,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=expected_args_hash,
        nonce_store=hybrid.InMemoryNonceStore(),
        mode="official_hybrid_private",
        now=NOW,
    )

    hybrid2, public_key_b64_2, session2, dangerous, dangerous_args_hash = _signed_action(
        capability="dangerous_operations",
        nonce="dangerous-action",
    )
    dangerous_result = hybrid2.verify_local_node_action_envelope(
        dangerous,
        session=session2,
        public_key_b64=public_key_b64_2,
        expected_args_hash=dangerous_args_hash,
        nonce_store=hybrid2.InMemoryNonceStore(),
        mode="official_hybrid_private",
        now=NOW,
    )

    assert expired_result.status == "expired"
    assert expired_result.execute_allowed is False
    assert dangerous_result.status == "approval_required"
    assert dangerous_result.approval_required is True
    assert dangerous_result.dangerous_operation is True
    assert dangerous_result.execute_allowed is False


def test_managed_cloud_private_local_action_is_disabled() -> None:
    hybrid, public_key_b64, session, signed, expected_args_hash = _signed_action()

    result = hybrid.verify_local_node_action_envelope(
        signed,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=expected_args_hash,
        nonce_store=hybrid.InMemoryNonceStore(),
        mode="official_managed_cloud",
        now=NOW,
    )

    assert result.status == "disabled_by_mode"
    assert result.disabled_by_mode is True
    assert result.execute_allowed is False
