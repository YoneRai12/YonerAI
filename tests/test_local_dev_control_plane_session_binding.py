from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import sys
from pathlib import Path


NOW = datetime(2026, 5, 21, 0, 5, tzinfo=timezone.utc)


def _load_hybrid():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core import hybrid

    return hybrid


def test_missing_enrollment_and_pairing_pending_gate_hybrid_work() -> None:
    hybrid = _load_hybrid()

    missing = hybrid.evaluate_local_dev_session_binding(
        capability="local_tools",
        enrollment_state="missing_enrollment",
        now=NOW,
    )
    pending = hybrid.evaluate_local_dev_session_binding(
        capability="local_tools",
        enrollment_state="pairing_pending",
        now=NOW,
    )

    assert missing.local_work_allowed_for_preview is False
    assert missing.session_bound is False
    assert missing.reasons == ("local_node_enrollment_required",)
    assert pending.local_work_allowed_for_preview is False
    assert pending.reasons == ("pairing_pending",)


def test_enrolled_verified_session_binds_action_envelope_preview() -> None:
    hybrid = _load_hybrid()

    decision = hybrid.evaluate_local_dev_session_binding(
        capability="local_tools",
        enrollment_state="enrolled_verified",
        now=NOW,
    )

    assert decision.non_production is True
    assert decision.production_trust_material is False
    assert decision.network_required is False
    assert decision.local_node_verification_state == "present_verified"
    assert decision.enrollment_state == "enrolled_verified"
    assert decision.session_bound is True
    assert decision.local_work_allowed_for_preview is True
    assert decision.action_envelope is not None
    assert decision.action_envelope.signature_valid is True
    assert decision.action_envelope.execute_allowed is False
    assert decision.raw_args_stored is False
    assert decision.plaintext_pairing_code_stored is False


def test_unverified_expired_or_revoked_session_denies_work() -> None:
    hybrid = _load_hybrid()

    unverified = hybrid.evaluate_local_dev_session_binding(
        capability="local_tools",
        enrollment_state="enrolled_unverified",
        now=NOW,
    )
    expired = hybrid.evaluate_local_dev_session_binding(
        capability="local_tools",
        enrollment_state="expired",
        now=NOW,
    )
    revoked = hybrid.evaluate_local_dev_session_binding(
        capability="local_tools",
        enrollment_state="revoked",
        now=NOW,
    )

    assert unverified.local_work_allowed_for_preview is False
    assert unverified.session_bound is False
    assert "session_not_verified" in unverified.reasons
    assert expired.local_work_allowed_for_preview is False
    assert "session_expired" in expired.reasons
    assert revoked.local_work_allowed_for_preview is False
    assert "session_revoked" in revoked.reasons


def test_invalid_action_envelope_denies_without_raw_args_storage() -> None:
    hybrid = _load_hybrid()
    session, _signed_manifest, private_key_b64, _public_key_b64 = hybrid.build_local_dev_enrolled_session_fixture(
        capability="local_tools",
        now=NOW,
    )
    assert session is not None
    args_hash = hybrid.action_args_hash({"action": "synthetic_preview"})
    unsigned = hybrid.build_unsigned_local_node_action_envelope(
        action_id="local-dev-action",
        node_id=session.enrolled_node_id,
        session_id=session.session_id,
        mode=session.mode,
        capability="local_tools",
        args_hash=args_hash,
    )
    signed = hybrid.sign_local_node_action_envelope(unsigned, private_key_b64=private_key_b64)
    tampered = replace(signed, args_hash=hybrid.action_args_hash({"action": "tampered"}))

    decision = hybrid.evaluate_local_dev_session_binding(
        capability="local_tools",
        signed_action_envelope=tampered,
        expected_args_hash=args_hash,
        now=NOW,
    )

    assert decision.local_work_allowed_for_preview is False
    assert decision.action_envelope is not None
    assert decision.action_envelope.status == "invalid_signature"
    assert decision.action_envelope.execute_allowed is False
    assert decision.raw_args_stored is False


def test_dangerous_local_capability_requires_approval() -> None:
    hybrid = _load_hybrid()

    decision = hybrid.evaluate_local_dev_session_binding(
        capability="dangerous_operations",
        enrollment_state="enrolled_verified",
        now=NOW,
    )

    assert decision.local_work_allowed_for_preview is True
    assert decision.approval_required is True
    assert decision.action_envelope is not None
    assert decision.action_envelope.status == "approval_required"
    assert decision.action_envelope.dangerous_operation is True
    assert decision.action_envelope.execute_allowed is False
