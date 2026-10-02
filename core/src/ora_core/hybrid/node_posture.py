from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


NODE_POSTURE_SCHEMA_VERSION = "yonerai-local-node-posture/v0.1"

NodePostureState = Literal["VERIFIED", "LIMITED", "RECOVERY", "QUARANTINED", "REVOKED"]

KNOWN_POSTURE_CAPABILITIES = frozenset(
    {
        "local_model",
        "workspace_file_access",
        "mock_search",
        "tool_boundary",
        "ledger",
        "dangerous_operation",
        "dangerous_operations",
    }
)
LIMITED_POSTURE_CAPABILITIES = frozenset({"mock_search", "ledger"})
RECOVERY_POSTURE_CAPABILITIES = frozenset({"ledger"})
DANGEROUS_POSTURE_CAPABILITIES = frozenset({"dangerous_operation", "dangerous_operations"})


@dataclass(frozen=True)
class LocalNodePostureDecision:
    schema_version: str
    node_id: str
    state: NodePostureState
    manifest_verified: bool
    session_state: str
    declared_capabilities: tuple[str, ...]
    declared_extensions: tuple[str, ...]
    exposed_capabilities: tuple[str, ...]
    denied_capabilities: tuple[str, ...]
    policy_drift: bool
    manifest_drift: bool
    suspicious_behavior: bool
    revoked: bool
    production_trust_material: bool
    local_work_preview_allowed: bool
    owner_approval_required: bool
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["declared_capabilities"] = list(self.declared_capabilities)
        payload["declared_extensions"] = list(self.declared_extensions)
        payload["exposed_capabilities"] = list(self.exposed_capabilities)
        payload["denied_capabilities"] = list(self.denied_capabilities)
        payload["reasons"] = list(self.reasons)
        return payload


def evaluate_local_node_posture(
    *,
    node_id: object,
    manifest_verified: bool,
    session_state: object,
    declared_capabilities: tuple[object, ...],
    declared_extensions: tuple[object, ...] = (),
    policy_drift: bool = False,
    manifest_drift: bool = False,
    suspicious_behavior: bool = False,
    revoked: bool = False,
    production_trust_material: bool = False,
) -> LocalNodePostureDecision:
    normalized_capabilities = _normalize_names(declared_capabilities)
    normalized_extensions = _normalize_names(declared_extensions)
    unknown_capabilities = tuple(
        capability for capability in normalized_capabilities if capability not in KNOWN_POSTURE_CAPABILITIES
    )
    known_capabilities = tuple(
        capability for capability in normalized_capabilities if capability in KNOWN_POSTURE_CAPABILITIES
    )
    dangerous_capabilities = tuple(
        capability for capability in known_capabilities if capability in DANGEROUS_POSTURE_CAPABILITIES
    )
    reasons: list[str] = []
    normalized_session_state = str(session_state or "missing").strip().lower().replace("-", "_") or "missing"

    if revoked or normalized_session_state == "revoked":
        state: NodePostureState = "REVOKED"
        reasons.append("node_or_session_revoked")
    elif production_trust_material:
        state = "QUARANTINED"
        reasons.append("production_trust_material_not_allowed_public_repo")
    elif suspicious_behavior:
        state = "QUARANTINED"
        reasons.append("suspicious_behavior_detected")
    elif policy_drift or manifest_drift or normalized_session_state == "expired":
        state = "RECOVERY"
        if policy_drift:
            reasons.append("policy_drift_detected")
        if manifest_drift:
            reasons.append("manifest_drift_detected")
        if normalized_session_state == "expired":
            reasons.append("session_expired")
    elif not manifest_verified or unknown_capabilities or normalized_extensions:
        state = "LIMITED"
        if not manifest_verified:
            reasons.append("manifest_not_verified")
        if unknown_capabilities:
            reasons.append("unknown_capability_denied")
        if normalized_extensions:
            reasons.append("declared_extensions_require_review")
    else:
        state = "VERIFIED"
        reasons.append("verified_posture")

    exposed_capabilities = _exposed_capabilities(state=state, known_capabilities=known_capabilities)
    denied_capabilities = tuple(capability for capability in normalized_capabilities if capability not in exposed_capabilities)
    if dangerous_capabilities:
        reasons.append("dangerous_capability_denied_by_default")

    return LocalNodePostureDecision(
        schema_version=NODE_POSTURE_SCHEMA_VERSION,
        node_id=_safe_node_id(node_id),
        state=state,
        manifest_verified=manifest_verified,
        session_state=normalized_session_state,
        declared_capabilities=normalized_capabilities,
        declared_extensions=normalized_extensions,
        exposed_capabilities=exposed_capabilities,
        denied_capabilities=denied_capabilities,
        policy_drift=policy_drift,
        manifest_drift=manifest_drift,
        suspicious_behavior=suspicious_behavior,
        revoked=revoked or normalized_session_state == "revoked",
        production_trust_material=production_trust_material,
        local_work_preview_allowed=state == "VERIFIED",
        owner_approval_required=state != "VERIFIED" or bool(dangerous_capabilities),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _exposed_capabilities(
    *,
    state: NodePostureState,
    known_capabilities: tuple[str, ...],
) -> tuple[str, ...]:
    if state == "VERIFIED":
        allowed = set(KNOWN_POSTURE_CAPABILITIES) - set(DANGEROUS_POSTURE_CAPABILITIES)
    elif state == "LIMITED":
        allowed = set(LIMITED_POSTURE_CAPABILITIES)
    elif state == "RECOVERY":
        allowed = set(RECOVERY_POSTURE_CAPABILITIES)
    else:
        allowed = set()
    return tuple(capability for capability in known_capabilities if capability in allowed)


def _normalize_names(values: tuple[object, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(value).strip().lower().replace("-", "_").replace(".", "_")
            for value in values
            if value and str(value).strip()
        )
    )


def _safe_node_id(node_id: object) -> str:
    value = str(node_id or "").strip()
    if not value:
        return "unknown-node"
    if "\\" in value or "/" in value or ":" in value:
        return "node-id-redacted"
    return value[:80]
