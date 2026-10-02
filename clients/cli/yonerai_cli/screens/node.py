from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


def format_node_status_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    local_node_value = report.get("local_node") or {}
    local_node = local_node_value if isinstance(local_node_value, dict) else {}
    manifest_value = local_node.get("capability_manifest") or {}
    manifest = manifest_value if isinstance(manifest_value, dict) else {}
    capabilities_value = manifest.get("capabilities") or []
    capabilities = capabilities_value if isinstance(capabilities_value, list) else []
    capability_rows = tuple(
        CliRow(
            str(capability.get("name")),
            "enabled" if capability.get("enabled") else "disabled",
            "ok" if capability.get("enabled") else "warn",
            note="approval required" if capability.get("approval_required") else None,
        )
        for capability in capabilities
        if isinstance(capability, dict)
    )
    sections = (
        CliSection(
            "Hybrid Wire Contract",
            (
                CliRow("schema", report.get("schema_version"), "ok"),
                CliRow("trust_state", local_node.get("trust_state"), "ok"),
                CliRow("posture_state", _node_posture_state(local_node), "ok"),
                CliRow("loopback_only", local_node.get("loopback_only"), "ok"),
                CliRow("non_production", local_node.get("non_production"), "ok"),
            ),
        ),
        CliSection(
            "Local Node fixture",
            (
                CliRow("available", local_node.get("available"), "ok" if local_node.get("available") else "warn"),
                CliRow(
                    "production_trust_material",
                    local_node.get("production_trust_material"),
                    "fail" if local_node.get("production_trust_material") else "ok",
                ),
                CliRow("network_required", report.get("network_required"), "fail" if report.get("network_required") else "ok"),
                CliRow(
                    "official_cloud_runtime",
                    "not implemented" if not report.get("official_cloud_runtime_implemented") else "implemented",
                    "ok" if not report.get("official_cloud_runtime_implemented") else "fail",
                ),
            ),
        ),
        CliSection("Capabilities", capability_rows),
        CliSection("Non-actions", tuple(CliRow("boundary", action, "ok") for action in report.get("actions_not_performed", ()))),
    )
    return render_report("YonerAI Local Node status", sections, color=color)


def format_node_pair_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    request = report.get("official_orchestration_stub_request")
    if not isinstance(request, dict):
        request = {}
    response = report.get("official_orchestration_stub_response")
    if not isinstance(response, dict):
        response = {}
    decision = report.get("trust_decision")
    if not isinstance(decision, dict):
        decision = {}
    sections = (
        CliSection(
            "Pairing dry-run",
            (
                CliRow("schema", report.get("schema_version"), "ok"),
                CliRow("dry_run", report.get("dry_run"), "ok" if report.get("dry_run") else "fail"),
                CliRow("pairing_performed", report.get("pairing_performed"), "fail" if report.get("pairing_performed") else "ok"),
                CliRow("request_schema", request.get("schema_name"), "ok"),
                CliRow("response_schema", response.get("schema_name"), "ok" if response else "warn"),
            ),
        ),
        CliSection(
            "Trust decision",
            (
                CliRow("state", decision.get("state"), _trust_decision_status(decision)),
                CliRow("requested_capability", decision.get("requested_capability"), "ok"),
                CliRow("execute_allowed", decision.get("execute_allowed"), "fail" if decision.get("execute_allowed") else "ok"),
                CliRow("approval_required", decision.get("approval_required"), "warn" if decision.get("approval_required") else "ok"),
            ),
        ),
        CliSection("Non-actions", tuple(CliRow("boundary", action, "ok") for action in report.get("actions_not_performed", ()))),
    )
    return render_report("YonerAI Local Node pairing preview", sections, color=color)


def format_relay_status_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    relay_value = report.get("relay") or {}
    relay = relay_value if isinstance(relay_value, dict) else {}
    connector_value = report.get("node_connector") or {}
    connector = connector_value if isinstance(connector_value, dict) else {}
    limits_value = report.get("limits") or {}
    limits = limits_value if isinstance(limits_value, dict) else {}
    sections = (
        CliSection(
            "Local-dev relay",
            (
                CliRow("schema", report.get("schema_version"), "ok"),
                CliRow("mode", report.get("mode"), "ok"),
                CliRow("host", relay.get("host"), "ok" if relay.get("loopback_only") else "fail"),
                CliRow("port", relay.get("port"), "ok"),
                CliRow("loopback_only", relay.get("loopback_only"), "ok" if relay.get("loopback_only") else "fail"),
                CliRow("public_exposure_requested", relay.get("public_exposure_requested"), "fail" if relay.get("public_exposure_requested") else "ok"),
                CliRow("public_exposure_allowed", relay.get("public_exposure_allowed"), "fail" if relay.get("public_exposure_allowed") else "ok"),
            ),
        ),
        CliSection(
            "Runtime boundary",
            (
                CliRow("process_started", relay.get("process_started"), "fail" if relay.get("process_started") else "ok"),
                CliRow("health_probe_performed", relay.get("health_probe_performed"), "fail" if relay.get("health_probe_performed") else "ok"),
                CliRow("quick_tunnel_enabled", relay.get("quick_tunnel_enabled"), "fail" if relay.get("quick_tunnel_enabled") else "ok"),
                CliRow("message_body_persisted", relay.get("message_body_persisted"), "fail" if relay.get("message_body_persisted") else "ok"),
                CliRow("pairing_code_storage", relay.get("pairing_code_storage"), "ok"),
                CliRow("session_token_storage", relay.get("session_token_storage"), "ok"),
            ),
        ),
        CliSection(
            "Node connector",
            (
                CliRow(
                    "relay_url_category",
                    connector.get("relay_url_category"),
                    "ok" if connector.get("relay_url_category") in {"loopback", "auto_unresolved_no_probe", "auto_resolved_loopback"} else "fail",
                ),
                CliRow(
                    "node_api_base_url_category",
                    connector.get("node_api_base_url_category"),
                    "ok" if connector.get("node_api_base_url_category") == "loopback" else "fail",
                ),
                CliRow("connector_started", connector.get("connector_started"), "fail" if connector.get("connector_started") else "ok"),
                CliRow("pairing_code_printed", connector.get("pairing_code_printed"), "fail" if connector.get("pairing_code_printed") else "ok"),
            ),
        ),
        CliSection("Limits", tuple(CliRow(key, value, "ok") for key, value in limits.items())),
        CliSection("Non-actions", tuple(CliRow("boundary", action, "ok") for action in report.get("actions_not_performed", ()))),
    )
    return render_report("YonerAI Relay local-dev status", sections, color=color)


def _node_posture_state(local_node: dict[str, Any]) -> object:
    posture = local_node.get("posture")
    if not isinstance(posture, dict):
        return "unknown"
    return posture.get("state", "unknown")


def _trust_decision_status(decision: dict[str, Any]) -> str:
    state = decision.get("state")
    if decision.get("execute_allowed"):
        return "fail"
    if state == "verified_test_node":
        return "ok"
    if state in {
        "approval_required",
        "capability_not_declared",
        "expired_session",
        "missing_node",
        "revoked_session",
        "unverified_node",
    }:
        return "warn"
    return "fail"
