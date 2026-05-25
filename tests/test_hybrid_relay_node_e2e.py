from __future__ import annotations

import json
import sys
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid.relay_node_e2e import (  # noqa: E402
    HYBRID_RELAY_NODE_E2E_SCHEMA_VERSION,
    build_local_dev_relay_node_e2e_report,
)
from ora_core.hybrid.wire_contract import assert_public_safe_wire_payload  # noqa: E402


def test_local_dev_relay_node_e2e_fixture_connects_wire_and_relay_boundaries() -> None:
    report = build_local_dev_relay_node_e2e_report({})
    serialized = json.dumps(report, sort_keys=True)

    assert report["schema_version"] == HYBRID_RELAY_NODE_E2E_SCHEMA_VERSION
    assert report["ok"] is True
    assert report["network_required"] is False
    assert report["official_cloud_runtime_implemented"] is False
    assert report["production_oracle_used"] is False
    assert report["production_trust_material"] is False
    assert report["relay"]["loopback_only"] is True
    assert report["relay"]["process_started"] is False
    assert report["relay"]["public_exposure_allowed"] is False
    assert report["relay"]["message_body_persisted"] is False
    assert report["relay"]["pairing_code_storage"] == "hash_only"
    assert report["relay"]["session_token_storage"] == "hash_only"

    node_flow = report["node_flow"]
    assert node_flow["hello"]["schema_name"] == "LocalNodeHello"
    assert node_flow["heartbeat"]["schema_name"] == "LocalNodeHeartbeat"
    assert node_flow["capability_manifest"]["schema_name"] == "LocalNodeCapabilityManifest"
    assert node_flow["session_ref"]["schema_name"] == "LocalNodeSessionRef"
    assert node_flow["session_ref"]["bearer_token_hash_only"] is True
    assert node_flow["session_ref"]["bearer_token_included"] is False
    assert node_flow["session_ref"]["message_body_persisted"] is False
    assert node_flow["trust_decision"]["state"] == "verified_test_node"
    assert node_flow["trust_decision"]["allowed_for_preview"] is True
    assert node_flow["trust_decision"]["execute_allowed"] is False

    assert "relay-node-e2e-token" not in serialized
    assert "123456" not in serialized
    assert assert_public_safe_wire_payload(report) == ()


def test_local_dev_relay_node_e2e_pairing_is_one_time_and_hash_only() -> None:
    report = build_local_dev_relay_node_e2e_report({})
    pairing = report["pairing"]

    assert pairing["pairing_code_hash_only"] is True
    assert pairing["pairing_code_plaintext_included"] is False
    assert pairing["session_token_hash_only"] is True
    assert pairing["session_token_plaintext_included"] is False
    assert pairing["first_consume"]["accepted"] is True
    assert pairing["first_consume"]["status"] == "enrolled_verified"
    assert pairing["reuse_consume"]["accepted"] is False
    assert pairing["reuse_consume"]["status"] == "pairing_code_reused"
    assert pairing["first_consume"]["session"]["session_token_hash"].startswith("sha256:")


def test_local_dev_relay_node_e2e_http_proxy_fixture_keeps_only_hashes() -> None:
    report = build_local_dev_relay_node_e2e_report({})
    proxy = report["http_proxy_fixture"]
    serialized = json.dumps(proxy, sort_keys=True)

    assert proxy["message_type"] == "http_proxy"
    assert proxy["path_category"] == "loopback_node_api_fixture"
    assert proxy["request_body_hash"].startswith("sha256:")
    assert proxy["response_body_hash"].startswith("sha256:")
    assert proxy["request_body_bytes"] > 0
    assert proxy["response_body_bytes"] > 0
    assert proxy["request_body_persisted"] is False
    assert proxy["response_body_persisted"] is False
    assert proxy["raw_body_included"] is False
    assert "local dev relay fixture" not in serialized
    assert "fixture response" not in serialized


def test_local_dev_relay_node_e2e_rejects_expired_revoked_and_unverified() -> None:
    report = build_local_dev_relay_node_e2e_report({})
    rejection_cases = report["rejection_cases"]

    assert rejection_cases["expired_session"]["state"] == "expired_session"
    assert rejection_cases["expired_session"]["allowed_for_preview"] is False
    assert rejection_cases["expired_session"]["execute_allowed"] is False
    assert rejection_cases["revoked_session"]["state"] == "revoked_session"
    assert rejection_cases["revoked_session"]["allowed_for_preview"] is False
    assert rejection_cases["unverified_node"]["state"] == "unverified_node"
    assert rejection_cases["unverified_node"]["allowed_for_preview"] is False


def test_local_dev_relay_node_e2e_blocks_non_loopback_relay_status_without_leaking_url() -> None:
    report = build_local_dev_relay_node_e2e_report(
        {
            "ORA_RELAY_HOST": "0.0.0.0",
            "ORA_RELAY_URL": "wss://relay.example.invalid",
        }
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["relay"]["ok"] is False
    assert report["relay"]["loopback_only"] is False
    assert "relay.example.invalid" not in serialized
