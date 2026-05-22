from __future__ import annotations

from dataclasses import asdict, dataclass
from ora_core.hybrid import build_local_dev_control_plane_status


STATUS_CONTRACT_SCHEMA_VERSION = "yonerai-official-status-contract/v0.1"


@dataclass(frozen=True)
class StatusComponent:
    component: str
    status: str
    updated_at: str
    incident_summary: str | None = None
    degraded_reason: str | None = None
    public_repo_support_status: str = "contract_only"
    network_required: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


def build_official_status_contract(*, source: str = "local") -> dict[str, object]:
    if source not in {"local", "fixture"}:
        source = "local"
    local_dev = build_local_dev_control_plane_status(verify_test_manifest=False)
    components = (
        StatusComponent(
            component="official_managed_cloud",
            status="external_contract_only",
            updated_at="2026-05-22T00:00:00Z",
            degraded_reason="public repo does not include official managed cloud runtime",
        ),
        StatusComponent(
            component="oracle_control_plane",
            status="stub_local_dev_only",
            updated_at="2026-05-22T00:00:00Z",
            degraded_reason="production Oracle control-plane is not implemented in the public repo",
        ),
        StatusComponent(
            component="local_node",
            status=local_dev.local_node.verification_state,
            updated_at="2026-05-22T00:00:00Z",
            degraded_reason="fixture uses non-production local-dev trust material",
        ),
        StatusComponent(
            component="provider_runtime",
            status="alpha_capability_slice",
            updated_at="2026-05-22T00:00:00Z",
            incident_summary=None,
            degraded_reason="live providers require explicit provider env opt-in",
            public_repo_support_status="runtime_alpha",
        ),
        StatusComponent(
            component="installer_distribution",
            status="dry_run_manifest_verify_only",
            updated_at="2026-05-22T00:00:00Z",
            degraded_reason="installer does not download, execute, install, or mutate PATH",
        ),
    )
    return {
        "schema_version": STATUS_CONTRACT_SCHEMA_VERSION,
        "source": source,
        "ok": True,
        "network_required": False,
        "production_service_called": False,
        "official_cloud_runtime_included": False,
        "oracle_control_plane_production_ready": False,
        "components": [component.to_public_dict() for component in components],
        "local_dev_control_plane": local_dev.to_public_dict(),
    }
