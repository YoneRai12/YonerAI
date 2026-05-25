from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from .three_mode import ModeName, get_mode_capability_profile


ROUTE_PREVIEW_SCHEMA_VERSION = "three-mode-route-preview-0.3"

RouteName = Literal[
    "managed_cloud_contract_only",
    "external_official_service_required",
    "local_node_required",
    "enrolled_verified_node_required",
    "hybrid_coordination_preview",
    "self_host_local_preview",
    "disabled",
]
OperationClass = Literal["public_docs", "private_data", "pc_operation", "local_tool", "heavy_work", "dangerous", "discord_live", "deployment", "unknown"]
LocalNodeVerificationState = Literal[
    "missing",
    "present_unverified",
    "present_verified",
    "expired",
    "invalid_signature",
    "wrong_audience",
]
SessionVerificationState = Literal[
    "not_required",
    "missing",
    "unenrolled",
    "pairing_pending",
    "enrolled_unverified",
    "enrolled_verified",
    "expired",
    "revoked",
    "wrong_audience",
]

_CAPABILITY_ALIASES = {
    "public_docs": "public_ui_sync_support",
    "public_ui": "public_ui_sync_support",
    "sync": "public_ui_sync_support",
    "support": "public_ui_sync_support",
    "cloud": "cloud_orchestration",
    "orchestration": "cloud_orchestration",
    "local_node": "local_node",
    "local_model": "local_tools",
    "workspace_file_access": "private_files",
    "mock_search": "local_tools",
    "tool_boundary": "local_tools",
    "ledger": "local_tools",
    "dangerous_operation": "dangerous_operations",
    "private_files": "private_files",
    "private_file": "private_files",
    "file": "private_files",
    "files": "private_files",
    "pc": "pc_operations",
    "pc_operations": "pc_operations",
    "shell": "pc_operations",
    "command": "pc_operations",
    "local_tools": "local_tools",
    "tool": "local_tools",
    "tools": "local_tools",
    "heavy": "heavy_work",
    "heavy_work": "heavy_work",
    "dangerous": "dangerous_operations",
    "self_evolution": "self_evolution_proposals",
    "self_evolution_proposals": "self_evolution_proposals",
    "deploy": "production_deploy",
    "deployment": "production_deploy",
    "memory": "persistent_memory",
    "persistent_memory": "persistent_memory",
}


@dataclass(frozen=True)
class RoutePreviewDecision:
    schema_version: str
    mode: ModeName
    route: RouteName
    reason: str
    requested_capability: str
    operation_class: OperationClass
    approval_required: bool
    local_node_required: bool
    cloud_allowed: bool
    private_data_allowed: bool
    dangerous_operation: bool
    disabled: bool
    runtime_available_in_public_repo: bool
    public_repo_support_status: str
    implementation_owner: str
    external_official_service_required: bool
    contract_only: bool
    public_repo_execution_available: bool
    unavailable_reason: str | None
    local_node_verification_state: LocalNodeVerificationState | None
    signed_origin_verified: bool
    local_node_capability_declared: bool | None
    session_required: bool
    session_verification_state: SessionVerificationState
    session_enrolled: bool
    session_verified: bool
    session_gate_satisfied: bool
    non_claims: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["non_claims"] = list(self.non_claims)
        route_strategy = _route_strategy(self)
        payload["route_strategy"] = route_strategy
        payload["task_class"] = self.operation_class
        payload["privacy_class"] = _privacy_class_for_operation(self.operation_class)
        payload["local_provider_available"] = _local_provider_available(self)
        payload["node_posture_state"] = _node_posture_state_for_route(self.local_node_verification_state)
        payload["capability_gate"] = _capability_gate(self)
        payload["approval_state"] = "required" if self.approval_required else "not_required"
        payload["cloud_escape_reason"] = _cloud_escape_reason(self, route_strategy)
        payload["audit_requirements"] = _audit_requirements(self, route_strategy)
        payload["cloud_escape_erased_approval_audit_args_hash"] = False
        return payload


def _classify_operation(task_text: str, requested_capability: str | None, risk_hint: str | None) -> OperationClass:
    hint = " ".join(part for part in (requested_capability or "", risk_hint or "", task_text) if part).lower()
    if any(term in hint for term in ("deploy", "deployment", "release production", "rollout")):
        return "deployment"
    if any(term in hint for term in ("discord", "live bot", "gateway")):
        return "discord_live"
    if any(term in hint for term in ("shell", "command", "run ", "execute", "pc operation", "delete", "write file")):
        return "pc_operation"
    if any(term in hint for term in ("local tool", "mcp tool", "tool execution")):
        return "local_tool"
    if any(
        term in hint
        for term in (
            "workspace_file_access",
            "workspace file",
            "private file",
            "local file",
            "my file",
            "read file",
            "private data",
        )
    ):
        return "private_data"
    if any(term in hint for term in ("heavy", "batch", "long running", "gpu")):
        return "heavy_work"
    if any(term in hint for term in ("dangerous", "destructive", "delete", "format disk")):
        return "dangerous"
    if any(term in hint for term in ("docs", "readme", "public", "summarize")):
        return "public_docs"
    return "unknown"


def _capability_for_operation(operation_class: OperationClass, requested_capability: str | None) -> str:
    if requested_capability:
        normalized = requested_capability.strip().lower().replace("-", "_").replace(".", "_")
        return _CAPABILITY_ALIASES.get(normalized, normalized)
    if operation_class == "public_docs":
        return "cloud_orchestration"
    if operation_class == "private_data":
        return "private_files"
    if operation_class == "pc_operation":
        return "pc_operations"
    if operation_class == "local_tool":
        return "local_tools"
    if operation_class == "heavy_work":
        return "heavy_work"
    if operation_class == "dangerous":
        return "dangerous_operations"
    if operation_class == "deployment":
        return "production_deploy"
    if operation_class == "discord_live":
        return "discord.gateway_live"
    return "unknown"


def _normalize_local_node_capabilities(capabilities: tuple[str, ...] | None) -> tuple[str, ...] | None:
    if capabilities is None:
        return None
    return tuple(
        _CAPABILITY_ALIASES.get(item.strip().lower().replace("-", "_").replace(".", "_"), item)
        for item in capabilities
    )


def _normalize_local_node_state(
    *,
    has_local_node: bool,
    local_node_verification_state: LocalNodeVerificationState | None,
) -> LocalNodeVerificationState | None:
    if local_node_verification_state is not None:
        return local_node_verification_state
    if not has_local_node:
        return "missing"
    return None


def _trust_state_unavailable_reason(state: LocalNodeVerificationState | None) -> str | None:
    if state == "missing":
        return "local_node_missing"
    if state == "present_unverified":
        return "unverified_node_denied"
    if state == "expired":
        return "expired_node_manifest"
    if state == "invalid_signature":
        return "invalid_node_signature"
    if state == "wrong_audience":
        return "wrong_audience_node_manifest"
    return None


def _normalize_session_state(
    *,
    require_enrolled_verified_session: bool,
    session_verification_state: SessionVerificationState | None,
) -> SessionVerificationState:
    if require_enrolled_verified_session and session_verification_state == "not_required":
        return "missing"
    if not require_enrolled_verified_session and session_verification_state is None:
        return "not_required"
    return session_verification_state or "missing"


def _session_unavailable_reason(state: SessionVerificationState) -> str | None:
    if state == "not_required" or state == "enrolled_verified":
        return None
    if state == "missing":
        return "local_node_session_required"
    if state == "unenrolled":
        return "local_node_enrollment_required"
    if state == "pairing_pending":
        return "pairing_pending"
    if state == "enrolled_unverified":
        return "session_not_verified"
    if state == "expired":
        return "session_expired"
    if state == "revoked":
        return "session_revoked"
    if state == "wrong_audience":
        return "session_wrong_audience"
    return "local_node_session_required"


def _session_enrolled(state: SessionVerificationState) -> bool:
    return state in {"enrolled_unverified", "enrolled_verified", "expired", "revoked"}


def _privacy_class_for_operation(operation_class: OperationClass) -> str:
    if operation_class == "public_docs":
        return "public"
    if operation_class == "private_data":
        return "private"
    if operation_class in {"pc_operation", "local_tool", "heavy_work"}:
        return "local_sensitive"
    if operation_class in {"dangerous", "discord_live", "deployment"}:
        return "restricted"
    return "unknown"


def _route_strategy(decision: RoutePreviewDecision) -> str:
    if decision.disabled or decision.unavailable_reason in {
        "unknown_capability",
        "capability_disabled",
        "local_node_missing",
        "unverified_node_denied",
        "expired_node_manifest",
        "invalid_node_signature",
        "wrong_audience_node_manifest",
        "local_node_capability_not_declared",
        "local_node_session_required",
        "local_node_enrollment_required",
        "pairing_pending",
        "session_not_verified",
        "session_expired",
        "session_revoked",
        "session_wrong_audience",
    }:
        return "deny"
    if decision.route in {"managed_cloud_contract_only", "external_official_service_required"}:
        return "cloud_contract_only"
    if decision.route == "hybrid_coordination_preview":
        return "hybrid"
    if decision.route == "self_host_local_preview":
        if decision.operation_class == "public_docs":
            return "local_preferred"
        return "local_only"
    return "deny"


def _local_provider_available(decision: RoutePreviewDecision) -> bool:
    return (
        decision.local_node_verification_state == "present_verified"
        and decision.session_gate_satisfied
        and not decision.disabled
    )


def _node_posture_state_for_route(state: LocalNodeVerificationState | None) -> str | None:
    if state == "present_verified":
        return "VERIFIED"
    if state == "present_unverified":
        return "LIMITED"
    if state == "expired":
        return "RECOVERY"
    if state in {"invalid_signature", "wrong_audience"}:
        return "QUARANTINED"
    if state == "missing":
        return None
    return None


def _capability_gate(decision: RoutePreviewDecision) -> str:
    if decision.unavailable_reason == "local_node_capability_not_declared":
        return "capability_not_declared"
    if decision.local_node_capability_declared is True:
        return "satisfied"
    if decision.local_node_capability_declared is False:
        return decision.unavailable_reason or "not_satisfied"
    if decision.local_node_required:
        return decision.unavailable_reason or "local_node_required"
    return "not_required"


def _cloud_escape_reason(decision: RoutePreviewDecision, route_strategy: str) -> str | None:
    if route_strategy != "cloud_contract_only":
        return None
    return decision.unavailable_reason or "official_cloud_contract_only"


def _audit_requirements(decision: RoutePreviewDecision, route_strategy: str) -> dict[str, object]:
    args_hash_required = bool(
        decision.local_node_required
        or decision.private_data_allowed
        or decision.dangerous_operation
        or decision.operation_class in {"pc_operation", "local_tool", "heavy_work", "dangerous"}
    )
    return {
        "approval_required": decision.approval_required,
        "audit_event_required": True,
        "args_hash_required": args_hash_required,
        "cloud_escape": route_strategy == "cloud_contract_only",
        "cloud_escape_preserves_approval": True,
        "cloud_escape_preserves_audit": True,
        "cloud_escape_preserves_args_hash": True,
    }


def preview_route(
    task_text: str,
    *,
    mode: ModeName,
    requested_capability: str | None = None,
    has_local_node: bool = False,
    local_node_verification_state: LocalNodeVerificationState | None = None,
    local_node_capabilities: tuple[str, ...] | None = None,
    require_enrolled_verified_session: bool = False,
    session_verification_state: SessionVerificationState | None = None,
    risk_hint: str | None = None,
) -> RoutePreviewDecision:
    operation_class = _classify_operation(task_text, requested_capability, risk_hint)
    capability_name = _capability_for_operation(operation_class, requested_capability)
    if mode == "full_private_self_host" and operation_class == "public_docs" and requested_capability is None:
        capability_name = "local_tools"
    local_node_capabilities = _normalize_local_node_capabilities(local_node_capabilities)
    profile = get_mode_capability_profile(mode)
    non_claims = (
        "preview_only_no_execution",
        "no_shell_or_file_access",
        "no_provider_call",
        "no_live_discord",
        "no_production_route",
    )
    if mode == "full_private_self_host":
        non_claims = non_claims + ("self_host_owner_responsibility",)
    node_state = _normalize_local_node_state(
        has_local_node=has_local_node,
        local_node_verification_state=local_node_verification_state,
    )
    signed_origin_verified = node_state == "present_verified"
    session_state = _normalize_session_state(
        require_enrolled_verified_session=require_enrolled_verified_session,
        session_verification_state=session_verification_state,
    )
    session_verified = session_state == "enrolled_verified"
    session_gate_satisfied = not require_enrolled_verified_session or session_verified

    try:
        capability = profile.capability(capability_name)
    except KeyError:
        return RoutePreviewDecision(
            schema_version=ROUTE_PREVIEW_SCHEMA_VERSION,
            mode=mode,
            route="disabled",
            reason=f"Capability is not available in the public route-preview surface: {capability_name}",
            requested_capability=capability_name,
            operation_class=operation_class,
            approval_required=True,
            local_node_required=False,
            cloud_allowed=False,
            private_data_allowed=False,
            dangerous_operation=True,
            disabled=True,
            runtime_available_in_public_repo=profile.runtime_available_in_public_repo,
            public_repo_support_status=profile.public_repo_support_status,
            implementation_owner=profile.implementation_owner,
            external_official_service_required=profile.external_official_service,
            contract_only=profile.contract_only,
            public_repo_execution_available=False,
            unavailable_reason="unknown_capability",
            local_node_verification_state=node_state,
            signed_origin_verified=signed_origin_verified,
            local_node_capability_declared=False,
            session_required=require_enrolled_verified_session,
            session_verification_state=session_state,
            session_enrolled=_session_enrolled(session_state),
            session_verified=session_verified,
            session_gate_satisfied=session_gate_satisfied,
            non_claims=non_claims,
        )

    if capability.status == "disabled":
        return RoutePreviewDecision(
            schema_version=ROUTE_PREVIEW_SCHEMA_VERSION,
            mode=mode,
            route="disabled",
            reason=capability.reason,
            requested_capability=capability.name,
            operation_class=operation_class,
            approval_required=capability.requires_approval,
            local_node_required=capability.local_node_required,
            cloud_allowed=False,
            private_data_allowed=capability.private_data_allowed,
            dangerous_operation=capability.dangerous_operation,
            disabled=True,
            runtime_available_in_public_repo=profile.runtime_available_in_public_repo,
            public_repo_support_status=profile.public_repo_support_status,
            implementation_owner=profile.implementation_owner,
            external_official_service_required=profile.external_official_service,
            contract_only=profile.contract_only,
            public_repo_execution_available=False,
            unavailable_reason="capability_disabled",
            local_node_verification_state=node_state,
            signed_origin_verified=signed_origin_verified,
            local_node_capability_declared=None,
            session_required=require_enrolled_verified_session,
            session_verification_state=session_state,
            session_enrolled=_session_enrolled(session_state),
            session_verified=session_verified,
            session_gate_satisfied=session_gate_satisfied,
            non_claims=non_claims,
        )

    cloud_allowed = mode == "official_hybrid_private" and capability.name in {
        "public_ui_sync_support",
        "cloud_orchestration",
        "self_evolution_proposals",
    }
    local_node_required = capability.local_node_required
    if mode == "official_hybrid_private" and capability.name in {
        "private_files",
        "pc_operations",
        "local_tools",
        "heavy_work",
        "dangerous_operations",
    }:
        local_node_required = True

    if mode == "official_managed_cloud":
        route: RouteName = "managed_cloud_contract_only"
        unavailable_reason = (
            profile.disabled_reason
            or "official_managed_cloud_external_not_included"
        )
        return RoutePreviewDecision(
            schema_version=ROUTE_PREVIEW_SCHEMA_VERSION,
            mode=mode,
            route=route,
            reason=capability.reason,
            requested_capability=capability.name,
            operation_class=operation_class,
            approval_required=True,
            local_node_required=False,
            cloud_allowed=False,
            private_data_allowed=False,
            dangerous_operation=capability.dangerous_operation,
            disabled=False,
            runtime_available_in_public_repo=profile.runtime_available_in_public_repo,
            public_repo_support_status=profile.public_repo_support_status,
            implementation_owner=profile.implementation_owner,
            external_official_service_required=True,
            contract_only=True,
            public_repo_execution_available=False,
            unavailable_reason=unavailable_reason,
            local_node_verification_state=node_state,
            signed_origin_verified=signed_origin_verified,
            local_node_capability_declared=None,
            session_required=require_enrolled_verified_session,
            session_verification_state=session_state,
            session_enrolled=_session_enrolled(session_state),
            session_verified=session_verified,
            session_gate_satisfied=session_gate_satisfied,
            non_claims=non_claims + ("official_managed_cloud_runtime_not_in_public_repo",),
        )

    session_unavailable_reason = _session_unavailable_reason(session_state)
    if local_node_required and require_enrolled_verified_session and session_unavailable_reason is not None:
        return RoutePreviewDecision(
            schema_version=ROUTE_PREVIEW_SCHEMA_VERSION,
            mode=mode,
            route="enrolled_verified_node_required",
            reason=f"{capability.reason} Enrolled verified Local Node session is required before this preview can route local work.",
            requested_capability=capability.name,
            operation_class=operation_class,
            approval_required=True,
            local_node_required=True,
            cloud_allowed=cloud_allowed,
            private_data_allowed=False,
            dangerous_operation=capability.dangerous_operation,
            disabled=False,
            runtime_available_in_public_repo=profile.runtime_available_in_public_repo,
            public_repo_support_status=profile.public_repo_support_status,
            implementation_owner=profile.implementation_owner,
            external_official_service_required=profile.external_official_service,
            contract_only=profile.contract_only,
            public_repo_execution_available=False,
            unavailable_reason=session_unavailable_reason,
            local_node_verification_state=node_state,
            signed_origin_verified=signed_origin_verified,
            local_node_capability_declared=False,
            session_required=True,
            session_verification_state=session_state,
            session_enrolled=_session_enrolled(session_state),
            session_verified=session_verified,
            session_gate_satisfied=False,
            non_claims=non_claims,
        )

    trust_unavailable_reason = _trust_state_unavailable_reason(node_state)
    if local_node_required and trust_unavailable_reason is not None:
        return RoutePreviewDecision(
            schema_version=ROUTE_PREVIEW_SCHEMA_VERSION,
            mode=mode,
            route="local_node_required",
            reason=f"{capability.reason} Local Node verification state prevents this preview from routing to local work.",
            requested_capability=capability.name,
            operation_class=operation_class,
            approval_required=True,
            local_node_required=True,
            cloud_allowed=cloud_allowed,
            private_data_allowed=capability.private_data_allowed,
            dangerous_operation=capability.dangerous_operation,
            disabled=False,
            runtime_available_in_public_repo=profile.runtime_available_in_public_repo,
            public_repo_support_status=profile.public_repo_support_status,
            implementation_owner=profile.implementation_owner,
            external_official_service_required=profile.external_official_service,
            contract_only=profile.contract_only,
            public_repo_execution_available=False,
            unavailable_reason=trust_unavailable_reason,
            local_node_verification_state=node_state,
            signed_origin_verified=False,
            local_node_capability_declared=False,
            session_required=require_enrolled_verified_session,
            session_verification_state=session_state,
            session_enrolled=_session_enrolled(session_state),
            session_verified=session_verified,
            session_gate_satisfied=session_gate_satisfied,
            non_claims=non_claims,
        )

    capability_declared = None
    if local_node_required and node_state == "present_verified" and local_node_capabilities is not None:
        capability_declared = capability.name in local_node_capabilities
        if not capability_declared:
            return RoutePreviewDecision(
                schema_version=ROUTE_PREVIEW_SCHEMA_VERSION,
                mode=mode,
                route="disabled",
                reason=f"{capability.reason} Verified Local Node manifest did not declare this capability.",
                requested_capability=capability.name,
                operation_class=operation_class,
                approval_required=True,
                local_node_required=True,
                cloud_allowed=cloud_allowed,
                private_data_allowed=False,
                dangerous_operation=capability.dangerous_operation,
                disabled=True,
                runtime_available_in_public_repo=profile.runtime_available_in_public_repo,
                public_repo_support_status=profile.public_repo_support_status,
                implementation_owner=profile.implementation_owner,
                external_official_service_required=profile.external_official_service,
                contract_only=profile.contract_only,
                public_repo_execution_available=False,
                unavailable_reason="local_node_capability_not_declared",
                local_node_verification_state=node_state,
                signed_origin_verified=True,
                local_node_capability_declared=False,
                session_required=require_enrolled_verified_session,
                session_verification_state=session_state,
                session_enrolled=_session_enrolled(session_state),
                session_verified=session_verified,
                session_gate_satisfied=session_gate_satisfied,
                non_claims=non_claims,
            )

    if local_node_required and not has_local_node and node_state is None:
        return RoutePreviewDecision(
            schema_version=ROUTE_PREVIEW_SCHEMA_VERSION,
            mode=mode,
            route="local_node_required",
            reason=f"{capability.reason} Local Node availability was not provided for this preview.",
            requested_capability=capability.name,
            operation_class=operation_class,
            approval_required=True,
            local_node_required=True,
            cloud_allowed=cloud_allowed,
            private_data_allowed=capability.private_data_allowed,
            dangerous_operation=capability.dangerous_operation,
            disabled=False,
            runtime_available_in_public_repo=profile.runtime_available_in_public_repo,
            public_repo_support_status=profile.public_repo_support_status,
            implementation_owner=profile.implementation_owner,
            external_official_service_required=profile.external_official_service,
            contract_only=profile.contract_only,
            public_repo_execution_available=False,
            unavailable_reason="local_node_missing",
            local_node_verification_state="missing",
            signed_origin_verified=False,
            local_node_capability_declared=False,
            session_required=require_enrolled_verified_session,
            session_verification_state=session_state,
            session_enrolled=_session_enrolled(session_state),
            session_verified=session_verified,
            session_gate_satisfied=session_gate_satisfied,
            non_claims=non_claims,
        )

    if mode == "full_private_self_host":
        route = "self_host_local_preview"
    elif local_node_required:
        route = "hybrid_coordination_preview"
    elif cloud_allowed:
        route = "external_official_service_required"
    else:
        route = "disabled"

    disabled = route == "disabled"
    return RoutePreviewDecision(
        schema_version=ROUTE_PREVIEW_SCHEMA_VERSION,
        mode=mode,
        route=route,
        reason=capability.reason,
        requested_capability=capability.name,
        operation_class=operation_class,
        approval_required=capability.requires_approval or capability.dangerous_operation,
        local_node_required=local_node_required,
        cloud_allowed=cloud_allowed,
        private_data_allowed=capability.private_data_allowed,
        dangerous_operation=capability.dangerous_operation,
        disabled=disabled,
        runtime_available_in_public_repo=profile.runtime_available_in_public_repo,
        public_repo_support_status=profile.public_repo_support_status,
        implementation_owner=profile.implementation_owner,
        external_official_service_required=profile.external_official_service,
        contract_only=profile.contract_only,
        public_repo_execution_available=False,
        unavailable_reason="route_not_available" if disabled else None,
        local_node_verification_state=node_state,
        signed_origin_verified=signed_origin_verified,
        local_node_capability_declared=capability_declared,
        session_required=require_enrolled_verified_session,
        session_verification_state=session_state,
        session_enrolled=_session_enrolled(session_state),
        session_verified=session_verified,
        session_gate_satisfied=session_gate_satisfied,
        non_claims=non_claims,
    )
