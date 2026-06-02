from __future__ import annotations

from ora_core.official import build_status_check_report


STATUS_CONTRACT_SCHEMA_VERSION = "yonerai-official-status-contract/v0.1"


def build_official_status_contract(*, source: str = "local") -> dict[str, object]:
    """Compatibility wrapper for the legacy CLI `yonerai status` surface."""
    report = build_status_check_report(profile="operational")
    components = [
        {
            "component": "official_managed_cloud",
            "status": "external_contract_only",
            "updated_at": report.get("generated_at"),
            "incident_summary": None,
            "degraded_reason": "public repo does not include official managed cloud runtime",
            "public_repo_support_status": "contract_only",
            "network_required": False,
        },
        {
            "component": "oracle_control_plane",
            "status": "stub_local_dev_only",
            "updated_at": report.get("generated_at"),
            "incident_summary": None,
            "degraded_reason": "production Oracle control-plane is not implemented in the public repo",
            "public_repo_support_status": "contract_only",
            "network_required": False,
        },
        {
            "component": "installer_distribution",
            "status": "dry_run_manifest_verify_only",
            "updated_at": report.get("generated_at"),
            "incident_summary": None,
            "degraded_reason": "installer does not download, execute, install, or mutate PATH by default",
            "public_repo_support_status": "contract_only",
            "network_required": False,
        },
    ]
    return {
        "schema_version": STATUS_CONTRACT_SCHEMA_VERSION,
        "source": source if source in {"local", "fixture"} else "local",
        "ok": bool(report.get("ok")),
        "network_required": False,
        "production_service_called": False,
        "official_cloud_runtime_included": False,
        "oracle_control_plane_production_ready": False,
        "status_api_bridge": report,
        "components": components,
        "local_dev_control_plane": {
            "schema_version": "yonerai-local-dev-control-plane/v0.1",
            "ok": True,
            "fixture_only": True,
            "production_runtime_included": False,
        },
    }
