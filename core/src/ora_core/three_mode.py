from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


THREE_MODE_CAPABILITY_SURFACE_VERSION = "three-mode-capability-surface-0.2"

ModeName = Literal["official_managed_cloud", "official_hybrid_private", "full_private_self_host"]
CapabilityStatus = Literal["available", "gated", "disabled"]
PublicRepoSupportStatus = Literal[
    "contract_only",
    "local_node_contract_and_dev_simulator",
    "public_local_supported",
]
ImplementationOwner = Literal["official_private", "public_contract_plus_private_coordination", "self_host_operator"]

MODES: tuple[ModeName, ...] = (
    "official_managed_cloud",
    "official_hybrid_private",
    "full_private_self_host",
)

CAPABILITY_NAMES: tuple[str, ...] = (
    "public_ui_sync_support",
    "cloud_orchestration",
    "local_node",
    "private_files",
    "pc_operations",
    "local_tools",
    "heavy_work",
    "dangerous_operations",
    "self_evolution_proposals",
    "production_deploy",
    "persistent_memory",
)


@dataclass(frozen=True)
class ModeCapability:
    name: str
    status: CapabilityStatus
    reason: str
    public_safe: bool
    requires_approval: bool
    local_node_required: bool
    private_data_allowed: bool
    dangerous_operation: bool

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ModeCapabilityProfile:
    mode: ModeName
    posture: str
    public_repo_support_status: PublicRepoSupportStatus
    runtime_available_in_public_repo: bool
    implementation_owner: ImplementationOwner
    external_official_service: bool
    contract_only: bool
    disabled_reason: str | None
    same_user_experience: bool
    production_deploy_enabled: bool
    persistent_memory_enabled: bool
    capabilities: tuple[ModeCapability, ...]

    def capability(self, name: str) -> ModeCapability:
        for capability in self.capabilities:
            if capability.name == name:
                return capability
        raise KeyError(name)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "posture": self.posture,
            "public_repo_support_status": self.public_repo_support_status,
            "runtime_available_in_public_repo": self.runtime_available_in_public_repo,
            "implementation_owner": self.implementation_owner,
            "external_official_service": self.external_official_service,
            "contract_only": self.contract_only,
            "disabled_reason": self.disabled_reason,
            "same_user_experience": self.same_user_experience,
            "production_deploy_enabled": self.production_deploy_enabled,
            "persistent_memory_enabled": self.persistent_memory_enabled,
            "capabilities": [capability.to_public_dict() for capability in self.capabilities],
        }


def _capability(
    name: str,
    status: CapabilityStatus,
    reason: str,
    *,
    public_safe: bool,
    requires_approval: bool = False,
    local_node_required: bool = False,
    private_data_allowed: bool = False,
    dangerous_operation: bool = False,
) -> ModeCapability:
    return ModeCapability(
        name=name,
        status=status,
        reason=reason,
        public_safe=public_safe,
        requires_approval=requires_approval,
        local_node_required=local_node_required,
        private_data_allowed=private_data_allowed,
        dangerous_operation=dangerous_operation,
    )


def _official_managed_cloud_profile() -> ModeCapabilityProfile:
    return ModeCapabilityProfile(
        mode="official_managed_cloud",
        posture="official_private_external_contract_only",
        public_repo_support_status="contract_only",
        runtime_available_in_public_repo=False,
        implementation_owner="official_private",
        external_official_service=True,
        contract_only=True,
        disabled_reason="official_managed_cloud_runtime_not_included_in_public_repo",
        same_user_experience=True,
        production_deploy_enabled=False,
        persistent_memory_enabled=False,
        capabilities=(
            _capability(
                "public_ui_sync_support",
                "gated",
                "Official Managed Cloud is an external/private product mode; this public repo provides contract compatibility only.",
                public_safe=True,
            ),
            _capability(
                "cloud_orchestration",
                "gated",
                "Official cloud orchestration is external/private and is not runnable from this public repository.",
                public_safe=True,
            ),
            _capability(
                "local_node",
                "disabled",
                "Managed cloud runtime is not included in this public repository; Local Node work belongs to Hybrid Private or Self-Host surfaces.",
                public_safe=True,
            ),
            _capability(
                "private_files",
                "disabled",
                "Managed cloud must not directly read private files.",
                public_safe=False,
                private_data_allowed=False,
            ),
            _capability(
                "pc_operations",
                "disabled",
                "Managed cloud must not directly perform PC operations.",
                public_safe=False,
                dangerous_operation=True,
            ),
            _capability(
                "local_tools",
                "disabled",
                "Managed cloud has no direct local tool execution path.",
                public_safe=False,
                dangerous_operation=True,
            ),
            _capability(
                "heavy_work",
                "disabled",
                "Managed cloud heavy-work execution is not included in this public repository.",
                public_safe=True,
                requires_approval=True,
            ),
            _capability(
                "dangerous_operations",
                "disabled",
                "Dangerous operations are never silently enabled from managed cloud.",
                public_safe=False,
                requires_approval=True,
                dangerous_operation=True,
            ),
            _capability(
                "self_evolution_proposals",
                "gated",
                "Only the synthetic proposal-only simulator is public here; real official-cloud observation is external/private.",
                public_safe=True,
                requires_approval=True,
            ),
            _capability(
                "production_deploy",
                "disabled",
                "Production deployment is outside the public MVP.",
                public_safe=False,
                requires_approval=True,
                dangerous_operation=True,
            ),
            _capability(
                "persistent_memory",
                "disabled",
                "Persistent memory is unavailable in the public MVP.",
                public_safe=False,
                requires_approval=True,
                private_data_allowed=True,
            ),
        ),
    )


def _official_hybrid_private_profile() -> ModeCapabilityProfile:
    return ModeCapabilityProfile(
        mode="official_hybrid_private",
        posture="official_cloud_coordination_with_local_node_gates",
        public_repo_support_status="local_node_contract_and_dev_simulator",
        runtime_available_in_public_repo=False,
        implementation_owner="public_contract_plus_private_coordination",
        external_official_service=True,
        contract_only=False,
        disabled_reason="official_cloud_coordination_is_external_private_public_repo_includes_local_node_contracts_and_dev_simulator",
        same_user_experience=True,
        production_deploy_enabled=False,
        persistent_memory_enabled=False,
        capabilities=(
            _capability(
                "public_ui_sync_support",
                "gated",
                "The public repo exposes Local Node contracts and dev-simulator compatibility; official cloud UI/sync/support remains external/private.",
                public_safe=True,
                requires_approval=True,
            ),
            _capability(
                "cloud_orchestration",
                "gated",
                "Hybrid coordination is previewed through contracts; official cloud orchestration remains external/private.",
                public_safe=True,
                requires_approval=True,
            ),
            _capability(
                "local_node",
                "gated",
                "Private and local work requires an explicit user Local Node.",
                public_safe=True,
                requires_approval=True,
                local_node_required=True,
            ),
            _capability(
                "private_files",
                "gated",
                "Private files stay behind the Local Node and require owner approval.",
                public_safe=True,
                requires_approval=True,
                local_node_required=True,
                private_data_allowed=True,
            ),
            _capability(
                "pc_operations",
                "gated",
                "PC operations require Local Node mediation and owner approval.",
                public_safe=True,
                requires_approval=True,
                local_node_required=True,
                dangerous_operation=True,
            ),
            _capability(
                "local_tools",
                "gated",
                "Local tools are Local Node mediated and deny-by-default.",
                public_safe=True,
                requires_approval=True,
                local_node_required=True,
            ),
            _capability(
                "heavy_work",
                "gated",
                "Heavy work routes through the Local Node or another approved private lane.",
                public_safe=True,
                requires_approval=True,
                local_node_required=True,
            ),
            _capability(
                "dangerous_operations",
                "gated",
                "Dangerous operations require both Local Node gating and explicit approval.",
                public_safe=True,
                requires_approval=True,
                local_node_required=True,
                dangerous_operation=True,
            ),
            _capability(
                "self_evolution_proposals",
                "gated",
                "Self-evolution is proposal-only and cannot auto-apply changes.",
                public_safe=True,
                requires_approval=True,
            ),
            _capability(
                "production_deploy",
                "disabled",
                "Production deployment remains disabled from the public MVP surface.",
                public_safe=False,
                requires_approval=True,
                dangerous_operation=True,
            ),
            _capability(
                "persistent_memory",
                "disabled",
                "Persistent memory is unavailable until a separate explicit support lane exists.",
                public_safe=False,
                requires_approval=True,
                private_data_allowed=True,
            ),
        ),
    )


def _full_private_self_host_profile() -> ModeCapabilityProfile:
    return ModeCapabilityProfile(
        mode="full_private_self_host",
        posture="operator_owned_local_stack_with_explicit_responsibility",
        public_repo_support_status="public_local_supported",
        runtime_available_in_public_repo=True,
        implementation_owner="self_host_operator",
        external_official_service=False,
        contract_only=False,
        disabled_reason=None,
        same_user_experience=True,
        production_deploy_enabled=False,
        persistent_memory_enabled=False,
        capabilities=(
            _capability(
                "public_ui_sync_support",
                "available",
                "The same public-safe user experience can run against a self-hosted stack.",
                public_safe=True,
            ),
            _capability(
                "cloud_orchestration",
                "disabled",
                "Official cloud orchestration is not required for full private self-host mode.",
                public_safe=True,
            ),
            _capability(
                "local_node",
                "available",
                "The operator-owned local stack acts as the local execution boundary.",
                public_safe=True,
            ),
            _capability(
                "private_files",
                "gated",
                "Private files remain owner-controlled and require explicit local policy.",
                public_safe=True,
                requires_approval=True,
                private_data_allowed=True,
            ),
            _capability(
                "pc_operations",
                "gated",
                "PC operations are possible only under owner-controlled local policy.",
                public_safe=True,
                requires_approval=True,
                dangerous_operation=True,
            ),
            _capability(
                "local_tools",
                "gated",
                "Local tools are deny-by-default unless the operator declares them.",
                public_safe=True,
                requires_approval=True,
            ),
            _capability(
                "heavy_work",
                "gated",
                "Heavy work is self-host local responsibility and remains explicit.",
                public_safe=True,
                requires_approval=True,
            ),
            _capability(
                "dangerous_operations",
                "gated",
                "Dangerous operations require owner policy and approval even in self-host mode.",
                public_safe=True,
                requires_approval=True,
                dangerous_operation=True,
            ),
            _capability(
                "self_evolution_proposals",
                "gated",
                "Self-evolution remains proposal-only without automatic mutation.",
                public_safe=True,
                requires_approval=True,
            ),
            _capability(
                "production_deploy",
                "disabled",
                "The public MVP does not enable production deployment automation.",
                public_safe=False,
                requires_approval=True,
                dangerous_operation=True,
            ),
            _capability(
                "persistent_memory",
                "disabled",
                "Persistent memory is not enabled by this public-safe status surface.",
                public_safe=False,
                requires_approval=True,
                private_data_allowed=True,
            ),
        ),
    )


_PROFILE_BUILDERS = {
    "official_managed_cloud": _official_managed_cloud_profile,
    "official_hybrid_private": _official_hybrid_private_profile,
    "full_private_self_host": _full_private_self_host_profile,
}


def get_mode_capability_profile(mode: ModeName) -> ModeCapabilityProfile:
    return _PROFILE_BUILDERS[mode]()


def build_three_mode_capability_surface() -> dict[str, object]:
    profiles = [get_mode_capability_profile(mode) for mode in MODES]
    return {
        "schema_version": THREE_MODE_CAPABILITY_SURFACE_VERSION,
        "default_action": "deny",
        "modes": {profile.mode: profile.to_public_dict() for profile in profiles},
    }
