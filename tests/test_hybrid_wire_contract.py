from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace


repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid.wire_contract import (  # noqa: E402
    HYBRID_WIRE_COMPATIBLE_VERSIONS,
    HYBRID_WIRE_CONTRACT_VERSION,
    assert_public_safe_wire_payload,
    build_hybrid_wire_conformance_report,
    build_local_node_capability_manifest,
    build_local_node_session_ref,
    build_local_node_status_report,
    build_node_error,
    build_official_orchestration_stub_request,
    build_official_orchestration_stub_response,
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
    assert report["compatible_versions"] == list(HYBRID_WIRE_COMPATIBLE_VERSIONS)
    assert local_node["hello"]["schema_name"] == "LocalNodeHello"
    assert local_node["heartbeat"]["schema_name"] == "LocalNodeHeartbeat"
    assert manifest["schema_name"] == "LocalNodeCapabilityManifest"
    assert session_ref["schema_name"] == "LocalNodeSessionRef"
    assert local_node["lease_id"] == session_ref["lease_id"]
    assert local_node["session_token_hash_only"] is True
    assert local_node["message_body_persisted"] is False
    assert local_node["audit_event_schema"] == "hybrid-wire-audit/v0.3"
    assert local_node["hello"]["lease_required"] is True
    assert local_node["hello"]["audit_log_required"] is True
    assert local_node["heartbeat"]["lease_id"] == session_ref["lease_id"]
    assert local_node["heartbeat"]["message_body_persisted"] is False
    assert manifest["lease_policy"] == "required_per_session"
    assert manifest["message_body_persistence"] == "forbidden"
    assert str(manifest["expires_at"]).startswith("2100-")
    assert session_ref["bearer_token_included"] is False
    assert session_ref["bearer_token_hash_only"] is True
    assert str(session_ref["expires_at"]).startswith("2100-")
    assert str(session_ref["lease_expires_at"]).startswith("2100-")
    assert session_ref["token_hash_algorithm"] == "sha256"
    assert session_ref["token_hash"].startswith("sha256:")
    assert session_ref["message_body_persisted"] is False
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
    response = build_official_orchestration_stub_response(request=request)
    report = build_pairing_dry_run_report()

    assert request.schema_name == "OfficialOrchestrationStubRequest"
    assert request.dry_run is True
    assert request.route_strategy == "hybrid"
    assert request.approval_required is True
    assert request.audit_event_required is True
    assert request.args_hash_required is True
    assert request.private_file_content_included is False
    assert request.raw_prompt_included is False
    assert request.provider_key_included is False
    assert request.official_cloud_runtime_implemented is False
    assert request.production_oracle_used is False
    assert request.network_required is False
    assert response.schema_name == "OfficialOrchestrationStubResponse"
    assert response.request_id == request.request_id
    assert response.status == "contract_stub_only"
    assert response.route_strategy == "hybrid"
    assert response.accepted_for_private_implementation is True
    assert response.public_repo_execution_available is False
    assert response.disabled_reason == "production_oracle_not_implemented_in_public_repo"
    assert response.controlled_error_schema == "LocalNodeError"
    assert response.private_file_content_included is False
    assert response.raw_prompt_included is False
    assert response.provider_key_included is False
    assert response.message_body_persisted is False
    assert response.official_cloud_runtime_implemented is False
    assert response.production_oracle_used is False
    assert response.network_required is False
    assert report["pairing_performed"] is False
    assert report["session_token_plaintext_included"] is False
    assert report["session_token_hash_only"] is True
    assert report["message_body_persisted"] is False
    assert report["official_orchestration_stub_response"]["schema_name"] == "OfficialOrchestrationStubResponse"
    assert report["official_orchestration_stub_response"]["route_strategy"] == "hybrid"
    assert report["trust_decision"]["execute_allowed"] is False


def test_public_docs_orchestration_alias_uses_cloud_contract_candidate() -> None:
    request = build_official_orchestration_stub_request(requested_capability="public_docs")

    assert request.route_strategy == "cloud_contract_candidate"
    assert request.private_file_content_included is False
    assert request.raw_prompt_included is False
    assert request.provider_key_included is False
    assert request.network_required is False


def test_local_node_error_is_public_safe_wire_schema() -> None:
    error = build_node_error(code="local_path_error", message="failed at C:\\Users\\Example\\secret.txt")
    payload = error.to_public_dict()

    assert payload["schema_name"] == "LocalNodeError"
    assert payload["public_safe"] is True
    assert payload["raw_exception_included"] is False
    assert payload["status"] == "error"
    assert str(payload["audit_event_id"]).startswith("audit-error-")
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
    invalid_manifest_expiry = evaluate_wire_request(
        manifest=build_local_node_capability_manifest(expires_at="not-a-timestamp"),
        session_ref=session,
        requested_capability="workspace_file_access",
    )
    assert invalid_manifest_expiry.state == "unverified_node"
    assert "local_node_manifest_expiry_invalid" in invalid_manifest_expiry.reasons
    expired_manifest = evaluate_wire_request(
        manifest=build_local_node_capability_manifest(expires_at="2000-01-01T00:00:00Z"),
        session_ref=session,
        requested_capability="workspace_file_access",
    )
    assert expired_manifest.state == "unverified_node"
    assert "local_node_manifest_expired" in expired_manifest.reasons
    unverified_session = evaluate_wire_request(
        manifest=manifest,
        session_ref=build_local_node_session_ref(signed_origin_verified=False),
        requested_capability="workspace_file_access",
    )
    assert unverified_session.state == "unverified_node"
    assert "local_node_session_not_verified" in unverified_session.reasons
    mismatched_session = evaluate_wire_request(
        manifest=manifest,
        session_ref=replace(session, manifest_id="different-manifest"),
        requested_capability="workspace_file_access",
    )
    assert mismatched_session.state == "unverified_node"
    assert "local_node_session_manifest_mismatch" in mismatched_session.reasons
    assert evaluate_wire_request(
        manifest=manifest,
        session_ref=build_local_node_session_ref(state="expired"),
        requested_capability="workspace_file_access",
    ).state == "expired_session"
    assert evaluate_wire_request(
        manifest=manifest,
        session_ref=build_local_node_session_ref(expires_at="2000-01-01T00:00:00Z"),
        requested_capability="workspace_file_access",
    ).state == "expired_session"
    invalid_expiry = evaluate_wire_request(
        manifest=manifest,
        session_ref=build_local_node_session_ref(expires_at="not-a-timestamp"),
        requested_capability="workspace_file_access",
    )
    assert invalid_expiry.state == "expired_session"
    assert "local_node_session_expiry_invalid" in invalid_expiry.reasons
    invalid_lease_expiry = evaluate_wire_request(
        manifest=manifest,
        session_ref=replace(session, lease_expires_at="not-a-timestamp"),
        requested_capability="workspace_file_access",
    )
    assert invalid_lease_expiry.state == "expired_session"
    assert "local_node_session_lease_expiry_invalid" in invalid_lease_expiry.reasons
    expired_lease = evaluate_wire_request(
        manifest=manifest,
        session_ref=replace(session, lease_expires_at="2000-01-01T00:00:00Z"),
        requested_capability="workspace_file_access",
    )
    assert expired_lease.state == "expired_session"
    assert "local_node_session_lease_expired" in expired_lease.reasons
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
    assert report["lease_required"] is True
    assert report["session_token_hash_only"] is True
    assert report["message_body_persisted"] is False
    assert report["audit_event_schema"] == "hybrid-wire-audit/v0.3"
    assert "OfficialOrchestrationStubRequest" in report["schemas"]
    assert "OfficialOrchestrationStubResponse" in report["schemas"]
    assert report["official_orchestration_stub"]["request"]["schema_name"] == "OfficialOrchestrationStubRequest"
    assert report["official_orchestration_stub"]["request"]["requested_capability"] == "cloud_orchestration"
    assert report["official_orchestration_stub"]["request"]["route_strategy"] == "cloud_contract_candidate"
    assert report["official_orchestration_stub"]["response"]["schema_name"] == "OfficialOrchestrationStubResponse"
    assert report["official_orchestration_stub"]["response"]["route_strategy"] == "cloud_contract_candidate"
    assert report["official_orchestration_stub"]["response"]["public_repo_execution_available"] is False
    assert report["official_orchestration_stub"]["response"]["network_required"] is False
    alignment = report["route_orchestration_alignment"]
    assert alignment["status"] == "ok"
    assert alignment["route"] == "cloud_contract_candidate"
    assert alignment["route_strategy"] == "cloud_contract_candidate"
    assert alignment["request_schema"] == "OfficialOrchestrationStubRequest"
    assert alignment["response_schema"] == "OfficialOrchestrationStubResponse"
    assert alignment["privacy_class"] == "public"
    assert alignment["cloud_contract_candidate"] is True
    assert all(alignment["checks"].values())
    assert report["node_posture_schema_version"] == "yonerai-local-node-posture/v0.1"
    assert report["extension_capability_manifest_schema_version"] == "yonerai-extension-capability-manifest/v0.2"
    assert report["required_node_posture_state_count"] == 5
    assert {item["state"] for item in report["node_posture_states"]} == {
        "VERIFIED",
        "LIMITED",
        "RECOVERY",
        "QUARANTINED",
        "REVOKED",
    }
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
    extension_statuses = {item["extension_id"]: item["status"] for item in report["extension_boundary"]}
    assert extension_statuses == {
        "local-dev-search-extension": "accepted_for_review",
        "duplicate-capability-extension": "denied",
        "overbroad-capability-extension": "denied",
        "policy-drift-extension": "policy_drift",
    }
    accepted_extension = next(
        item for item in report["extension_boundary"] if item["extension_id"] == "local-dev-search-extension"
    )
    assert accepted_extension["typed_inputs"][0]["name"] == "query"
    assert accepted_extension["typed_outputs"][0]["name"] == "result_refs"
    assert accepted_extension["owner_scope"] == "local_owner"
    assert accepted_extension["audit_event_required"] is True
    assert accepted_extension["args_hash_required"] is True
    assert accepted_extension["can_execute"] is False


def test_hybrid_wire_conformance_report_fails_when_route_alignment_drifts(monkeypatch) -> None:
    from ora_core.route_preview import preview_route

    route_decision = preview_route(
        "hard public reasoning over public API docs",
        mode="official_hybrid_private",
    ).to_public_dict()
    route_decision["route_strategy"] = "hybrid"

    monkeypatch.setattr(
        "ora_core.route_preview.preview_route",
        lambda *_args, **_kwargs: SimpleNamespace(to_public_dict=lambda: route_decision),
    )

    report = build_hybrid_wire_conformance_report()

    assert report["route_orchestration_alignment"]["status"] == "fail"
    assert report["route_orchestration_alignment"]["checks"]["route_strategy_matches_request"] is False
    assert report["ok"] is False


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
    assert envelope_payload["lease_id"] == envelope_payload["session_ref"]["lease_id"]
    assert envelope_payload["audit_summary"] == "metadata_only_no_message_body"
    assert envelope_payload["message_body_persisted"] is False
    assert result_payload["raw_result_included"] is False
    assert result_payload["audit_event_id"] == f"audit-{envelope.run_id}"
    assert result_payload["message_body_persisted"] is False
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
