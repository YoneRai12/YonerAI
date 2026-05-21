from __future__ import annotations

from dataclasses import asdict, dataclass

from ..route_preview import RoutePreviewDecision, preview_route
from ..three_mode import ModeName
from .connector_fixture import (
    FIXTURE_ISSUER_NODE_ID,
    build_fixture_signature_verifier,
    build_fixture_trust_registry,
)


LOCAL_DEV_CONTROL_PLANE_PROFILE = "local_dev_control_plane"
LOCAL_DEV_CONTROL_PLANE_SCHEMA_VERSION = "local-dev-control-plane-simulator-0.1"


@dataclass(frozen=True)
class LocalDevNodeStatus:
    node_id: str
    available: bool
    non_production: bool
    capabilities: tuple[str, ...]
    requires_approval: tuple[str, ...]
    disabled: tuple[str, ...]
    trust_material: str

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        payload["requires_approval"] = list(self.requires_approval)
        payload["disabled"] = list(self.disabled)
        return payload


@dataclass(frozen=True)
class LocalDevControlPlaneStatus:
    schema_version: str
    profile: str
    official_cloud_stub_available: bool
    official_private_control_plane_ready: bool
    local_node: LocalDevNodeStatus
    production_trust_material: bool
    network_required: bool

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profile": self.profile,
            "official_cloud_stub_available": self.official_cloud_stub_available,
            "official_private_control_plane_ready": self.official_private_control_plane_ready,
            "local_node": self.local_node.to_public_dict(),
            "production_trust_material": self.production_trust_material,
            "network_required": self.network_required,
        }


def build_local_dev_control_plane_status(*, local_node_available: bool = True) -> LocalDevControlPlaneStatus:
    declared_capabilities = (
        "private_files",
        "pc_operations",
        "local_tools",
        "heavy_work",
        "dangerous_operations",
        "self_evolution_proposals",
    )
    approval_required = (
        "private_files",
        "pc_operations",
        "local_tools",
        "heavy_work",
        "dangerous_operations",
        "self_evolution_proposals",
    )
    disabled = (
        "production_deploy",
        "persistent_memory",
        "live_discord_gateway",
        "official_private_control_plane",
    )
    return LocalDevControlPlaneStatus(
        schema_version=LOCAL_DEV_CONTROL_PLANE_SCHEMA_VERSION,
        profile=LOCAL_DEV_CONTROL_PLANE_PROFILE,
        official_cloud_stub_available=True,
        official_private_control_plane_ready=False,
        local_node=LocalDevNodeStatus(
            node_id=FIXTURE_ISSUER_NODE_ID,
            available=local_node_available,
            non_production=True,
            capabilities=declared_capabilities if local_node_available else (),
            requires_approval=approval_required if local_node_available else (),
            disabled=disabled,
            trust_material="test_static_fixture_only",
        ),
        production_trust_material=False,
        network_required=False,
    )


def build_local_dev_fixture_trust_context() -> dict[str, object]:
    registry = build_fixture_trust_registry()
    verifier = build_fixture_signature_verifier()
    return {
        "profile": LOCAL_DEV_CONTROL_PLANE_PROFILE,
        "issuer_node_id": FIXTURE_ISSUER_NODE_ID,
        "production_trust_material": False,
        "signature_algorithm": "test-static-signature",
        "registry_entry_exists": registry.get(FIXTURE_ISSUER_NODE_ID) is not None,
        "verifier_class": type(verifier).__name__,
    }


def preview_route_with_local_dev_control_plane(
    task_text: str,
    *,
    mode: ModeName = "official_hybrid_private",
    requested_capability: str | None = None,
    local_node_available: bool = True,
    risk_hint: str | None = None,
) -> RoutePreviewDecision:
    status = build_local_dev_control_plane_status(local_node_available=local_node_available)
    return preview_route(
        task_text,
        mode=mode,
        requested_capability=requested_capability,
        has_local_node=status.local_node.available,
        risk_hint=risk_hint,
    )
