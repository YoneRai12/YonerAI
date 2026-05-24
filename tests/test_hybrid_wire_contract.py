from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid.wire_contract import (  # noqa: E402
    HYBRID_WIRE_CONTRACT_VERSION,
    assert_public_safe_wire_payload,
    build_hybrid_wire_conformance_report,
    build_local_node_capability_manifest,
    build_local_node_session_ref,
    build_local_node_status_report,
    build_node_error,
    build_official_orchestration_stub_request,
    build_pairing_dry_run_report,
    build_run_envelope,
    build_run_result,
    evaluate_wire_request,
    route_preview_inputs_from_node_status,
)


def test_local_node_fixture_conforms_to_hybrid_wire_contract() -> None:
    report = build_local_node_status_report()
    local_node = report["local_node"]
    manifest = local_node["capability_manifest"]
    session_ref = local_node["session_ref"]
    names = {capability["name"]: capability for capability in manifest["capabilities"]}

    assert report["schema_version"] == HYBRID_WIRE_CONTRACT_VERSION
    assert local_node["hello"]["schema_name"] == "LocalNodeHello"
    assert local_node["heartbeat"]["schema_name"] == "LocalNodeHeartbeat"
    assert manifest["schema_name"] == "LocalNodeCapabilityManifest"
    assert session_ref["schema_name"] == "LocalNodeSessionRef"
    assert set(names) == {
        "local_model",
        "workspace_file_access",
        "mock_search",
        "tool_boundary",
        "ledger",
        "dangerous_operation",
    }
    assert names["dangerous_operation"]["enabled"] is False
    assert names["dangerous_operation"]["approval_required"] is True
    assert local_node["production_trust_material"] is False
    assert report["official_cloud_runtime_implemented"] is False
    assert report["production_oracle_used"] is False
    assert report["network_required"] is False


def test_official_cloud_stub_request_conforms_without_implementing_cloud_runtime() -> None:
    session_ref = build_local_node_session_ref()
    request = build_official_orchestration_stub_request(session_ref=session_ref)
    report = build_pairing_dry_run_report()

    assert request.schema_name == "OfficialOrchestrationStubRequest"
    assert request.dry_run is True
    assert request.official_cloud_runtime_implemented is False
    assert request.production_oracle_used is False
    assert request.network_required is False
    assert report["pairing_performed"] is False
    assert report["trust_decision"]["execute_allowed"] is False


def test_local_node_error_is_public_safe_wire_schema() -> None:
    error = build_node_error(code="local_path_error", message="failed at C:\\Users\\Example\\secret.txt")
    payload = error.to_public_dict()

    assert payload["schema_name"] == "LocalNodeError"
    assert payload["public_safe"] is True
    assert payload["raw_exception_included"] is False
    assert assert_public_safe_wire_payload(payload) == ()
    assert "C:\\Users\\Example" not in str(payload)


def test_trust_session_rules_cover_required_denials_and_verified_test_node() -> None:
    manifest = build_local_node_capability_manifest()
    session = build_local_node_session_ref()

    assert evaluate_wire_request(
        manifest=None,
        session_ref=session,
        requested_capability="workspace_file_access",
    ).state == "missing_node"
    assert evaluate_wire_request(
        manifest=build_local_node_capability_manifest(signed_origin_verified=False),
        session_ref=session,
        requested_capability="workspace_file_access",
    ).state == "unverified_node"
    assert evaluate_wire_request(
        manifest=manifest,
        session_ref=build_local_node_session_ref(state="expired"),
        requested_capability="workspace_file_access",
    ).state == "expired_session"
    assert evaluate_wire_request(
        manifest=manifest,
        session_ref=build_local_node_session_ref(state="revoked"),
        requested_capability="workspace_file_access",
    ).state == "revoked_session"
    assert evaluate_wire_request(
        manifest=manifest,
        session_ref=session,
        requested_capability="unknown_future_capability",
    ).state == "capability_not_declared"

    mock_search = evaluate_wire_request(manifest=manifest, session_ref=session, requested_capability="mock_search")
    dangerous = evaluate_wire_request(
        manifest=manifest,
        session_ref=session,
        requested_capability="dangerous_operation",
    )

    assert mock_search.state == "verified_test_node"
    assert mock_search.allowed_for_preview is True
    assert mock_search.execute_allowed is False
    assert dangerous.state == "approval_required"
    assert dangerous.approval_required is True
    assert dangerous.execute_allowed is False
    assert "dangerous_operation_disabled_in_public_repo" in dangerous.reasons


def test_hybrid_wire_conformance_report_covers_required_states() -> None:
    report = build_hybrid_wire_conformance_report()
    states = {item["name"]: item for item in report["trust_states"]}

    assert report["ok"] is True
    assert report["test_fixture_only"] is True
    assert report["production_trust_material"] is False
    assert report["official_cloud_runtime_implemented"] is False
    assert report["network_required"] is False
    assert report["required_trust_state_count"] == len(report["required_trust_states"])
    assert set(states) == {
        "missing_node",
        "unverified_node",
        "verified_test_node",
        "expired_session",
        "revoked_session",
        "capability_not_declared",
        "approval_required",
    }
    assert states["verified_test_node"]["allowed_for_preview"] is True
    assert states["approval_required"]["approval_required"] is True
    assert all(item["execute_allowed"] is False for item in states.values())


def test_duplicate_manifest_capabilities_are_rejected_deterministically() -> None:
    manifest = build_local_node_capability_manifest()
    duplicate_manifest = replace(manifest, capabilities=manifest.capabilities + (manifest.capabilities[0],))
    decision = evaluate_wire_request(
        manifest=duplicate_manifest,
        session_ref=build_local_node_session_ref(),
        requested_capability="local_model",
    )

    assert decision.state == "unverified_node"
    assert decision.execute_allowed is False
    assert "duplicate_capability_declared" in decision.reasons


def test_wire_payloads_do_not_include_raw_prompt_secret_or_local_path() -> None:
    prompt = "read C:\\Users\\Example\\secret.txt with sk-test-placeholder and API_Key"
    envelope = build_run_envelope(capability="workspace_file_access", prompt=prompt)
    result = build_run_result(run_id=envelope.run_id, result="done from C:\\Users\\Example\\secret.txt")

    envelope_payload = envelope.to_public_dict()
    result_payload = result.to_public_dict()

    assert envelope_payload["schema_name"] == "LocalNodeRunEnvelope"
    assert result_payload["schema_name"] == "LocalNodeRunResult"
    assert envelope_payload["raw_prompt_included"] is False
    assert envelope_payload["provider_key_included"] is False
    assert envelope_payload["local_path_included"] is False
    assert result_payload["raw_result_included"] is False
    assert assert_public_safe_wire_payload(envelope_payload) == ()
    assert assert_public_safe_wire_payload(result_payload) == ()
    serialized = f"{envelope_payload} {result_payload}".lower()
    assert "c:\\users\\example" not in serialized
    assert "sk-test-placeholder" not in serialized
    assert "api_key" not in serialized


def test_public_safe_payload_checks_sensitive_keys_linux_paths_and_cycles() -> None:
    cyclic_list: list[object] = []
    payload: dict[str, object] = {
        "token": "redacted-but-forbidden-key",
        "authorization": "redacted-but-forbidden-key",
        "linux_path": "/home/example/.config/secret.txt",
        "secret_value": "private-key-placeholder",
        "loop": cyclic_list,
    }
    cyclic_list.append(payload)

    violations = assert_public_safe_wire_payload(payload)

    assert "forbidden_key:token" in violations
    assert "forbidden_key:authorization" in violations
    assert "forbidden_value:local_path" in violations
    assert "forbidden_value:secret_like" in violations


def test_route_preview_inputs_from_node_status_are_safe_fixture_only() -> None:
    report = build_local_node_status_report()
    inputs = route_preview_inputs_from_node_status(report["local_node"])

    assert inputs["has_local_node"] is True
    assert inputs["local_node_verification_state"] == "present_verified"
    assert "private_files" in inputs["local_node_capabilities"]
    assert inputs["session_verification_state"] == "enrolled_verified"
    assert inputs["require_enrolled_verified_session"] is True
