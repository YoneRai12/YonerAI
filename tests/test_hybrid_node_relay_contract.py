from __future__ import annotations

import json
import sys
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid.node_relay_contract import (  # noqa: E402
    HYBRID_NODE_RELAY_CONTRACT_VERSION,
    build_hybrid_node_relay_contract_stub,
)


def test_hybrid_node_relay_contract_stub_is_public_safe_and_contract_only() -> None:
    report = build_hybrid_node_relay_contract_stub({})
    serialized = json.dumps(report, sort_keys=True)

    assert report["schema_version"] == HYBRID_NODE_RELAY_CONTRACT_VERSION
    assert report["ok"] is True
    assert report["public_repo_scope"] == "contract_and_local_dev_fixture"
    assert report["official_cloud_runtime_implemented"] is False
    assert report["production_oracle_used"] is False
    assert report["production_trust_material"] is False
    assert report["network_required"] is False
    assert report["local_node"]["session_token_hash_only"] is True
    assert report["local_node"]["message_body_persisted"] is False
    assert report["relay"]["loopback_only"] is True
    assert report["relay"]["process_started"] is False
    assert report["relay"]["public_exposure_allowed"] is False
    assert report["relay"]["message_body_persisted"] is False
    assert report["relay"]["pairing_code_storage"] == "hash_only"
    assert report["relay"]["session_token_storage"] == "hash_only"
    assert report["session_ref"]["bearer_token_included"] is False
    assert report["session_ref"]["bearer_token_hash_only"] is True
    assert report["local_dev_e2e"]["ok"] is True
    assert report["local_dev_e2e"]["network_required"] is False
    assert report["local_dev_e2e"]["transport_schema_version"] == "yonerai-local-dev-relay-transport/v0.1"
    assert report["local_dev_e2e"]["transport_mode"] == "local_dev_in_memory"
    assert report["local_dev_e2e"]["transport_loopback_only"] is True
    assert report["local_dev_e2e"]["pairing_code_hash_only"] is True
    assert report["local_dev_e2e"]["session_token_hash_only"] is True
    assert report["local_dev_e2e"]["message_body_persisted"] is False
    assert report["local_dev_e2e"]["http_proxy_fixture_available"] is True
    assert report["official_cloud_consumption_stub"]["contract_only"] is True
    assert report["official_cloud_consumption_stub"]["persists_message_bodies"] is False
    assert "token=" not in serialized.lower()
    assert "pairing_code=" not in serialized.lower()


def test_hybrid_node_relay_contract_reflects_blocked_relay_without_leaking_url() -> None:
    report = build_hybrid_node_relay_contract_stub(
        {
            "ORA_RELAY_URL": "wss://relay.example.invalid",
        }
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["relay"]["ok"] is False
    assert report["relay"]["loopback_only"] is False
    assert report["local_dev_e2e"]["ok"] is False
    assert "relay.example.invalid" not in serialized
