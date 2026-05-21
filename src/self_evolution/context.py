from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, Mapping


RouteTrustMode = Literal["official_managed_cloud", "official_hybrid_private", "full_private_self_host"]
RouteTrustRoute = Literal["cloud_only", "local_node_required", "hybrid_coordination", "self_host_local", "disabled"]
RouteTrustNodeState = Literal[
    "missing",
    "present_unverified",
    "present_verified",
    "expired",
    "invalid_signature",
    "wrong_audience",
    "not_applicable",
]

_ALLOWED_MODES = {"official_managed_cloud", "official_hybrid_private", "full_private_self_host"}
_ALLOWED_ROUTES = {"cloud_only", "local_node_required", "hybrid_coordination", "self_host_local", "disabled"}
_ALLOWED_NODE_STATES = {
    "missing",
    "present_unverified",
    "present_verified",
    "expired",
    "invalid_signature",
    "wrong_audience",
    "not_applicable",
}


@dataclass(frozen=True)
class SafeRouteTrustContext:
    mode: RouteTrustMode
    route: RouteTrustRoute
    requested_capability: str
    local_node_verification_state: RouteTrustNodeState
    approval_required: bool
    local_node_required: bool
    signed_origin_verified: bool
    trusted: bool
    production_trust_material: bool
    unavailable_reason: str | None
    diagnosis: str

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_route_trust_context(raw: Mapping[str, object] | SafeRouteTrustContext) -> SafeRouteTrustContext:
    if isinstance(raw, SafeRouteTrustContext):
        return raw

    mode = _enum_value(raw.get("mode"), allowed=_ALLOWED_MODES, fallback="official_hybrid_private")
    route = _enum_value(raw.get("route"), allowed=_ALLOWED_ROUTES, fallback="disabled")
    node_state = _enum_value(
        raw.get("local_node_verification_state"),
        allowed=_ALLOWED_NODE_STATES,
        fallback="not_applicable",
    )
    unavailable_reason = _safe_reason(raw.get("unavailable_reason"))
    return SafeRouteTrustContext(
        mode=mode,  # type: ignore[arg-type]
        route=route,  # type: ignore[arg-type]
        requested_capability=_safe_capability(raw.get("requested_capability")),
        local_node_verification_state=node_state,  # type: ignore[arg-type]
        approval_required=_as_bool(raw.get("approval_required"), default=True),
        local_node_required=_as_bool(raw.get("local_node_required"), default=False),
        signed_origin_verified=_as_bool(raw.get("signed_origin_verified"), default=False),
        trusted=False,
        production_trust_material=False,
        unavailable_reason=unavailable_reason,
        diagnosis=_diagnosis(route=route, node_state=node_state, unavailable_reason=unavailable_reason),
    )


def _enum_value(value: object, *, allowed: set[str], fallback: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return fallback


def _as_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _safe_capability(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized = value.strip().lower().replace("-", "_").replace(".", "_")
    if not normalized:
        return "unknown"
    if len(normalized) > 64:
        return "unknown"
    if not all(character.isalnum() or character == "_" for character in normalized):
        return "unknown"
    return normalized


def _safe_reason(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return "unknown"
    normalized = value.strip().lower().replace("-", "_").replace(".", "_")
    if not normalized:
        return None
    if len(normalized) > 80:
        return "unknown"
    if not all(character.isalnum() or character == "_" for character in normalized):
        return "unknown"
    return normalized


def _diagnosis(*, route: str, node_state: str, unavailable_reason: str | None) -> str:
    if unavailable_reason == "local_node_missing" or node_state == "missing":
        return "hybrid_local_node_missing"
    if unavailable_reason == "unverified_node_denied" or node_state == "present_unverified":
        return "hybrid_local_node_unverified"
    if node_state in {"expired", "invalid_signature", "wrong_audience"}:
        return f"hybrid_local_node_{node_state}"
    if unavailable_reason == "local_node_capability_not_declared":
        return "hybrid_capability_not_declared"
    if route == "hybrid_coordination":
        return "hybrid_coordination_requires_owner_approval"
    if route == "disabled":
        return "route_disabled"
    return "route_context_recorded"
