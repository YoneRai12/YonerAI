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

    from ora_core.hybrid import local_node_enrollment, local_node_manifest, session_ref

    return local_node_enrollment, local_node_manifest, session_ref


def _verified_session_fixture():
    enrollment, manifest_mod, session_ref = _load_hybrid_modules()
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
    result = enrollment.consume_pairing_code(
        challenge,
        pairing_code=PAIRING_CODE,
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=NOW,
        session_token="session-token-fixture",
    )
    assert result.session is not None
    return enrollment, session_ref, result.session


def test_session_ref_binds_verified_session_for_private_capability_preview() -> None:
    _enrollment, session_ref, session = _verified_session_fixture()

    ref = session_ref.build_local_node_session_ref(session, capability="private_files")
    decision = session_ref.validate_local_node_session_ref(
        ref,
        session=session,
        expected_mode="official_hybrid_private",
        now=NOW,
    )

    assert ref.schema_version == "yonerai-local-node-session-ref-contract/v1"
    assert ref.node_id == session.enrolled_node_id
    assert ref.session_id == session.session_id
    assert ref.key_id == session.key_id
    assert ref.manifest_id == session.manifest_id
    assert ref.production_trust_material is False
    assert "session-token-fixture" not in str(asdict(ref))
    assert decision.status == "approval_required"
    assert decision.bound is True
    assert decision.preview_usable is True
    assert decision.execute_allowed is False
    assert decision.approval_required is True


def test_session_ref_never_enables_managed_cloud_runtime() -> None:
    _enrollment, session_ref, session = _verified_session_fixture()
    ref = session_ref.build_local_node_session_ref(session, capability="private_files")

    decision = session_ref.validate_local_node_session_ref(
        ref,
        session=session,
        expected_mode="official_managed_cloud",
    )

    assert decision.status == "mode_mismatch"
    assert decision.preview_usable is False
    assert decision.execute_allowed is False
    assert decision.reasons == ("managed_cloud_session_ref_runtime_not_in_public_repo",)


def test_session_ref_rejects_revoked_and_unverified_sessions() -> None:
    enrollment, session_ref, session = _verified_session_fixture()
    ref = session_ref.build_local_node_session_ref(session, capability="private_files")

    revoked = enrollment.revoke_enrollment_session(session)
    unverified = replace(session, signed_origin_verified=False, enrollment_state="enrolled_unverified")
    revoked_decision = session_ref.validate_local_node_session_ref(
        ref,
        session=revoked,
        expected_mode="official_hybrid_private",
        now=NOW,
    )
    unverified_decision = session_ref.validate_local_node_session_ref(
        ref,
        session=unverified,
        expected_mode="official_hybrid_private",
        now=NOW,
    )

    assert revoked_decision.status == "revoked"
    assert revoked_decision.preview_usable is False
    assert unverified_decision.status == "unverified"
    assert unverified_decision.preview_usable is False


def test_session_ref_rejects_undeclared_capability() -> None:
    _enrollment, session_ref, session = _verified_session_fixture()
    ref = session_ref.build_local_node_session_ref(session, capability="unknown.future.capability")

    decision = session_ref.validate_local_node_session_ref(
        ref,
        session=session,
        expected_mode="official_hybrid_private",
        now=NOW,
    )

    assert decision.status == "capability_not_declared"
    assert decision.preview_usable is False
    assert decision.execute_allowed is False


def test_session_ref_marks_dangerous_capability_as_approval_required() -> None:
    _enrollment, session_ref, session = _verified_session_fixture()
    ref = session_ref.build_local_node_session_ref(session, capability="dangerous_operations")

    decision = session_ref.validate_local_node_session_ref(
        ref,
        session=session,
        expected_mode="official_hybrid_private",
        now=NOW,
    )

    assert ref.approval_required is True
    assert decision.status == "approval_required"
    assert decision.bound is True
    assert decision.preview_usable is True
    assert decision.execute_allowed is False
    assert decision.approval_required is True
