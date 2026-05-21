from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Literal, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

from ..three_mode import ModeName
from .envelope import (
    DEFAULT_CONTROL_PLANE_AUDIENCE,
    canonical_payload_hash,
    parse_envelope_datetime,
)
from .local_node_enrollment import (
    LocalNodeEnrollmentSession,
    evaluate_enrollment_session_capability,
)
from .local_node_manifest import (
    LOCAL_NODE_MANIFEST_ALGORITHM,
    _canonical_json,
    _private_key_from_b64,
    _public_key_from_b64,
    local_node_public_key_id,
)
from .policy import InMemoryNonceStore


LOCAL_NODE_ACTION_ENVELOPE_SCHEMA_VERSION = "yonerai-local-node-action-envelope-test/v1"

ActionVerificationStatus = Literal[
    "valid",
    "invalid_signature",
    "expired",
    "replayed_nonce",
    "session_mismatch",
    "capability_not_declared",
    "approval_required",
    "disabled_by_mode",
]

@dataclass(frozen=True)
class LocalNodeActionSignature:
    algorithm: str
    key_id: str
    signature_b64: str
    schema_version: str = LOCAL_NODE_ACTION_ENVELOPE_SCHEMA_VERSION

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LocalNodeActionEnvelope:
    action_id: str
    node_id: str
    session_id: str
    mode: ModeName
    capability: str
    audience: str
    args_hash: str
    issued_at: str
    expires_at: str
    nonce: str
    signature: LocalNodeActionSignature
    schema_version: str = LOCAL_NODE_ACTION_ENVELOPE_SCHEMA_VERSION

    def to_unsigned_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "action_id": self.action_id,
            "node_id": self.node_id,
            "session_id": self.session_id,
            "mode": self.mode,
            "capability": self.capability,
            "audience": self.audience,
            "args_hash": self.args_hash,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
        }

    def to_public_dict(self) -> dict[str, object]:
        return {
            **self.to_unsigned_public_dict(),
            "signature": self.signature.to_public_dict(),
        }


@dataclass(frozen=True)
class LocalNodeActionVerification:
    status: ActionVerificationStatus
    signature_valid: bool
    accepted_for_preview: bool
    execute_allowed: bool
    approval_required: bool
    session_bound: bool
    capability_declared: bool
    dangerous_operation: bool
    disabled_by_mode: bool
    replay_protected: bool
    production_trust_material: bool
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        return payload


def action_args_hash(args: Mapping[str, object]) -> str:
    return canonical_payload_hash(args)


def build_unsigned_local_node_action_envelope(
    *,
    action_id: str,
    node_id: str,
    session_id: str,
    mode: ModeName,
    capability: str,
    args_hash: str,
    audience: str = DEFAULT_CONTROL_PLANE_AUDIENCE,
    issued_at: str = "2026-05-21T00:00:00Z",
    expires_at: str = "2026-05-21T00:10:00Z",
    nonce: str = "test-local-node-action-nonce",
    key_id: str = "",
) -> LocalNodeActionEnvelope:
    return LocalNodeActionEnvelope(
        action_id=action_id,
        node_id=node_id,
        session_id=session_id,
        mode=mode,
        capability=capability,
        audience=audience,
        args_hash=args_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
        signature=LocalNodeActionSignature(
            algorithm=LOCAL_NODE_MANIFEST_ALGORITHM,
            key_id=key_id,
            signature_b64="",
        ),
    )


def sign_local_node_action_envelope(
    envelope: LocalNodeActionEnvelope,
    *,
    private_key_b64: str,
) -> LocalNodeActionEnvelope:
    public_key_b64 = base64.b64encode(
        _private_key_from_b64(private_key_b64)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    signature = _private_key_from_b64(private_key_b64).sign(_canonical_json(envelope.to_unsigned_public_dict()))
    return replace(
        envelope,
        signature=LocalNodeActionSignature(
            algorithm=LOCAL_NODE_MANIFEST_ALGORITHM,
            key_id=local_node_public_key_id(public_key_b64),
            signature_b64=base64.b64encode(signature).decode("ascii"),
        ),
    )


def verify_local_node_action_envelope(
    envelope: LocalNodeActionEnvelope,
    *,
    session: LocalNodeEnrollmentSession,
    public_key_b64: str,
    expected_args_hash: str,
    nonce_store: InMemoryNonceStore,
    mode: ModeName,
    now: datetime | None = None,
) -> LocalNodeActionVerification:
    current = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    reasons: list[str] = []
    status: ActionVerificationStatus = "valid"
    signature_valid = False
    replay_protected = False

    if mode == "official_managed_cloud" and envelope.capability in {
        "private_files",
        "pc_operations",
        "local_tools",
        "heavy_work",
        "dangerous_operations",
    }:
        return _decision(
            status="disabled_by_mode",
            reasons=("managed_cloud_cannot_directly_route_local_node_actions",),
            disabled_by_mode=True,
        )

    if envelope.node_id != session.enrolled_node_id or envelope.session_id != session.session_id:
        return _decision(status="session_mismatch", reasons=("action_session_or_node_mismatch",))
    if envelope.mode != mode or session.mode != mode:
        return _decision(status="disabled_by_mode", reasons=("action_mode_mismatch",), disabled_by_mode=True)
    if envelope.args_hash != expected_args_hash:
        return _decision(status="invalid_signature", reasons=("args_hash_mismatch",))

    try:
        expires_at = parse_envelope_datetime(envelope.expires_at)
        issued_at = parse_envelope_datetime(envelope.issued_at)
    except ValueError:
        return _decision(status="expired", reasons=("invalid_action_timestamp",))
    if current < issued_at or current >= expires_at:
        return _decision(status="expired", reasons=("action_envelope_expired_or_not_yet_valid",))

    replay_protected = nonce_store.claim(
        issuer_node_id=envelope.node_id,
        audience=envelope.audience,
        nonce=envelope.nonce,
    )
    if not replay_protected:
        return _decision(status="replayed_nonce", reasons=("action_nonce_replayed",), replay_protected=True)

    if envelope.signature.algorithm != LOCAL_NODE_MANIFEST_ALGORITHM:
        return _decision(
            status="invalid_signature",
            reasons=("unsupported_action_signature_algorithm",),
            replay_protected=True,
        )
    expected_key_id = local_node_public_key_id(public_key_b64)
    if envelope.signature.key_id != expected_key_id or envelope.signature.key_id != session.key_id:
        return _decision(status="invalid_signature", reasons=("action_key_id_mismatch",), replay_protected=True)
    try:
        signature_raw = base64.b64decode(envelope.signature.signature_b64.encode("ascii"))
        _public_key_from_b64(public_key_b64).verify(signature_raw, _canonical_json(envelope.to_unsigned_public_dict()))
    except (InvalidSignature, ValueError):
        return _decision(status="invalid_signature", reasons=("invalid_action_signature",), replay_protected=True)
    signature_valid = True

    capability_decision = evaluate_enrollment_session_capability(
        session,
        envelope.capability,
        now=current,
    )
    if capability_decision.status == "capability_not_declared":
        return _decision(
            status="capability_not_declared",
            reasons=capability_decision.reasons,
            signature_valid=signature_valid,
            replay_protected=replay_protected,
            capability_declared=False,
        )
    if not capability_decision.allowed:
        return _decision(
            status="session_mismatch",
            reasons=capability_decision.reasons,
            signature_valid=signature_valid,
            replay_protected=replay_protected,
        )

    dangerous = envelope.capability == "dangerous_operations"
    if capability_decision.approval_required:
        return _decision(
            status="approval_required",
            reasons=("signature_verified_but_owner_approval_required",),
            signature_valid=signature_valid,
            replay_protected=replay_protected,
            approval_required=True,
            capability_declared=True,
            dangerous_operation=dangerous,
            accepted_for_preview=True,
            session_bound=True,
        )

    return _decision(
        status=status,
        reasons=("signature_verified_preview_only_no_execution",),
        signature_valid=signature_valid,
        replay_protected=replay_protected,
        approval_required=False,
        capability_declared=True,
        dangerous_operation=dangerous,
        accepted_for_preview=True,
        session_bound=True,
    )


def _decision(
    *,
    status: ActionVerificationStatus,
    reasons: tuple[str, ...],
    signature_valid: bool = False,
    accepted_for_preview: bool = False,
    execute_allowed: bool = False,
    approval_required: bool = True,
    session_bound: bool = False,
    capability_declared: bool = False,
    dangerous_operation: bool = False,
    disabled_by_mode: bool = False,
    replay_protected: bool = False,
) -> LocalNodeActionVerification:
    return LocalNodeActionVerification(
        status=status,
        signature_valid=signature_valid,
        accepted_for_preview=accepted_for_preview,
        execute_allowed=execute_allowed,
        approval_required=approval_required,
        session_bound=session_bound,
        capability_declared=capability_declared,
        dangerous_operation=dangerous_operation,
        disabled_by_mode=disabled_by_mode,
        replay_protected=replay_protected,
        production_trust_material=False,
        reasons=reasons,
    )
