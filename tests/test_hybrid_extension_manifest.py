from __future__ import annotations

import json
import sys
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid.extension_manifest import (  # noqa: E402
    EXTENSION_CAPABILITY_MANIFEST_SCHEMA_VERSION,
    ExtensionIOField,
    build_extension_capability_manifest,
    evaluate_extension_capability_manifest,
)
from ora_core.hybrid.wire_contract import assert_public_safe_wire_payload  # noqa: E402


def test_safe_extension_manifest_is_review_only_and_cannot_execute() -> None:
    manifest = build_extension_capability_manifest(
        extension_id="local-dev-search-extension",
        declared_capabilities=("mock_search", "ledger"),
    )
    decision = evaluate_extension_capability_manifest(manifest)
    payload = decision.to_public_dict()

    assert payload["schema_version"] == EXTENSION_CAPABILITY_MANIFEST_SCHEMA_VERSION
    assert payload["status"] == "accepted_for_review"
    assert payload["accepted_capabilities"] == ["mock_search", "ledger"]
    assert payload["typed_inputs"][0]["name"] == "query"
    assert payload["typed_outputs"][0]["name"] == "result_refs"
    assert payload["risk_tags"] == ["fixture_only", "mock", "read_only", "no_network"]
    assert payload["owner_scope"] == "local_owner"
    assert payload["owner_scope_allowed"] is True
    assert payload["audit_event_required"] is True
    assert payload["args_hash_required"] is True
    assert payload["can_execute"] is False
    assert payload["audit_required"] is True
    assert "extension_capabilities_declared_no_execution" in payload["reasons"]
    assert assert_public_safe_wire_payload(payload) == ()


def test_duplicate_extension_capability_is_denied_deterministically() -> None:
    manifest = build_extension_capability_manifest(
        extension_id="duplicate-capability-extension",
        declared_capabilities=("mock_search", "mock-search", "ledger"),
    )
    payload = evaluate_extension_capability_manifest(manifest).to_public_dict()

    assert payload["status"] == "denied"
    assert payload["accepted_capabilities"] == []
    assert payload["duplicate_capabilities"] == ["mock_search"]
    assert "duplicate_extension_capability_denied" in payload["reasons"]


def test_overbroad_and_unknown_extension_capabilities_are_denied() -> None:
    manifest = build_extension_capability_manifest(
        extension_id="overbroad-extension",
        declared_capabilities=("local_tools", "pc_operations", "future_private_capability"),
    )
    payload = evaluate_extension_capability_manifest(manifest).to_public_dict()

    assert payload["status"] == "denied"
    assert payload["accepted_capabilities"] == []
    assert payload["overbroad_capabilities"] == ["local_tools", "pc_operations"]
    assert payload["unknown_capabilities"] == ["unknown_capability_redacted"]
    assert payload["denied_capabilities"] == ["local_tools", "pc_operations", "unknown_capability_redacted"]
    assert "overbroad_extension_capability_denied" in payload["reasons"]
    assert "unknown_extension_capability_denied" in payload["reasons"]


def test_extension_manifest_redacts_unknown_capability_and_version_inputs() -> None:
    manifest = build_extension_capability_manifest(
        extension_id="unknown-extension",
        version="https://example.invalid/private-version",
        declared_capabilities=("future.private.capability",),
    )
    manifest_payload = manifest.to_public_dict()
    decision_payload = evaluate_extension_capability_manifest(manifest).to_public_dict()
    serialized = json.dumps({"manifest": manifest_payload, "decision": decision_payload}, sort_keys=True)

    assert manifest_payload["version"] == "version-redacted"
    assert manifest_payload["declared_capabilities"] == ["unknown_capability_redacted"]
    assert decision_payload["unknown_capabilities"] == ["unknown_capability_redacted"]
    assert decision_payload["denied_capabilities"] == ["unknown_capability_redacted"]
    assert "https://example.invalid/private-version" not in serialized
    assert "future.private.capability" not in serialized


def test_extension_manifest_distinguishes_unknown_capabilities_before_redaction() -> None:
    manifest = build_extension_capability_manifest(
        extension_id="unknown-extension",
        declared_capabilities=("future.private.one", "future.private.two"),
    )
    manifest_payload = manifest.to_public_dict()
    decision_payload = evaluate_extension_capability_manifest(manifest).to_public_dict()
    serialized = json.dumps({"manifest": manifest_payload, "decision": decision_payload}, sort_keys=True)

    assert manifest_payload["declared_capabilities"] == ["unknown_capability_redacted"]
    assert decision_payload["status"] == "denied"
    assert decision_payload["duplicate_capabilities"] == []
    assert decision_payload["unknown_capabilities"] == ["unknown_capability_redacted"]
    assert "duplicate_extension_capability_denied" not in decision_payload["reasons"]
    assert "future_private_one" not in serialized
    assert "future_private_two" not in serialized


def test_extension_manifest_denies_unsafe_risk_owner_scope_and_audit_gap() -> None:
    manifest = build_extension_capability_manifest(
        extension_id="unsafe-risk-extension",
        declared_capabilities=("mock_search",),
        risk_tags=("network", "custom_future_risk"),
        owner_scope="official_control_plane",
        audit_event_required=False,
        args_hash_required=False,
    )
    payload = evaluate_extension_capability_manifest(manifest).to_public_dict()

    assert payload["status"] == "denied"
    assert payload["accepted_capabilities"] == []
    assert payload["denied_risk_tags"] == ["network"]
    assert payload["unknown_risk_tags"] == ["custom_future_risk"]
    assert payload["owner_scope"] == "official_control_plane"
    assert payload["owner_scope_allowed"] is False
    assert "denied_extension_risk_tag" in payload["reasons"]
    assert "unknown_extension_risk_tag_denied" in payload["reasons"]
    assert "owner_scope_not_allowed" in payload["reasons"]
    assert "audit_event_required" in payload["reasons"]
    assert "args_hash_required" in payload["reasons"]


def test_extension_manifest_denies_string_boolean_audit_flags() -> None:
    manifest = build_extension_capability_manifest(
        extension_id="string-boolean-audit-extension",
        declared_capabilities=("mock_search",),
        audit_event_required="false",
        args_hash_required="0",
    )
    payload = evaluate_extension_capability_manifest(manifest).to_public_dict()

    assert payload["status"] == "denied"
    assert payload["audit_event_required"] is False
    assert payload["args_hash_required"] is False
    assert "audit_event_required" in payload["reasons"]
    assert "args_hash_required" in payload["reasons"]


def test_extension_manifest_denies_secret_or_untyped_io_fields() -> None:
    manifest = build_extension_capability_manifest(
        extension_id="secret-io-extension",
        declared_capabilities=("mock_search",),
        typed_inputs=(
            ExtensionIOField(
                name="api_token",
                type="string",
                required=True,
                sensitivity="secret",
            ),
        ),
        typed_outputs=(
            ExtensionIOField(
                name="raw_blob",
                type="bytes",
                required=True,
                sensitivity="public",
            ),
        ),
    )
    payload = evaluate_extension_capability_manifest(manifest).to_public_dict()

    assert payload["status"] == "denied"
    assert payload["accepted_capabilities"] == []
    assert "api_token:invalid_sensitivity" in payload["invalid_io_fields"]
    assert "raw_blob:invalid_type" in payload["invalid_io_fields"]
    assert "invalid_extension_io_contract_denied" in payload["reasons"]


def test_extension_policy_drift_fails_closed_with_audit_reason() -> None:
    manifest = build_extension_capability_manifest(
        extension_id="policy-drift-extension",
        declared_capabilities=("mock_search",),
    )
    payload = evaluate_extension_capability_manifest(manifest, policy_drift=True).to_public_dict()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["status"] == "policy_drift"
    assert payload["accepted_capabilities"] == []
    assert payload["policy_drift"] is True
    assert payload["can_execute"] is False
    assert "extension_policy_drift_detected" in payload["reasons"]
    assert "C:\\Users\\" not in serialized
