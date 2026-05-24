from __future__ import annotations

from typing import Mapping

from .relay_status import build_relay_status_report
from .wire_contract import build_local_node_status_report


HYBRID_NODE_RELAY_CONTRACT_VERSION = "yonerai-hybrid-node-relay-contract/v0.1"


def build_hybrid_node_relay_contract_stub(env: Mapping[str, str] | None = None) -> dict[str, object]:
    node_status = build_local_node_status_report()
    relay_status = build_relay_status_report(env)
    local_node = node_status["local_node"] if isinstance(node_status.get("local_node"), dict) else {}
    session_ref = local_node.get("session_ref") if isinstance(local_node.get("session_ref"), dict) else {}
    return {
        "schema_version": HYBRID_NODE_RELAY_CONTRACT_VERSION,
        "command": "yonerai doctor",
        "ok": bool(node_status.get("ok")) and bool(relay_status.get("ok")),
        "public_repo_scope": "contract_and_local_dev_fixture",
        "official_cloud_runtime_implemented": False,
        "production_oracle_used": False,
        "production_trust_material": False,
        "network_required": False,
        "local_node": {
            "schema_version": node_status.get("schema_version"),
            "available": local_node.get("available"),
            "trust_state": local_node.get("trust_state"),
            "loopback_only": local_node.get("loopback_only"),
            "session_token_hash_only": local_node.get("session_token_hash_only"),
            "message_body_persisted": local_node.get("message_body_persisted"),
            "audit_event_schema": local_node.get("audit_event_schema"),
        },
        "relay": {
            "schema_version": relay_status.get("schema_version"),
            "mode": relay_status.get("mode"),
            "ok": relay_status.get("ok"),
            "loopback_only": _relay_flag(relay_status, "loopback_only"),
            "process_started": _relay_flag(relay_status, "process_started"),
            "health_probe_performed": _relay_flag(relay_status, "health_probe_performed"),
            "public_exposure_allowed": _relay_flag(relay_status, "public_exposure_allowed"),
            "message_body_persisted": _relay_flag(relay_status, "message_body_persisted"),
            "pairing_code_storage": _relay_flag(relay_status, "pairing_code_storage"),
            "session_token_storage": _relay_flag(relay_status, "session_token_storage"),
        },
        "session_ref": {
            "state": session_ref.get("state") if isinstance(session_ref, dict) else None,
            "signed_origin_verified": session_ref.get("signed_origin_verified") if isinstance(session_ref, dict) else None,
            "bearer_token_included": session_ref.get("bearer_token_included") if isinstance(session_ref, dict) else None,
            "bearer_token_hash_only": session_ref.get("bearer_token_hash_only") if isinstance(session_ref, dict) else None,
            "message_body_persisted": session_ref.get("message_body_persisted") if isinstance(session_ref, dict) else None,
        },
        "official_cloud_consumption_stub": {
            "contract_only": True,
            "expects_local_node_hello": True,
            "expects_capability_manifest": True,
            "expects_session_ref": True,
            "expects_relay_status": True,
            "persists_message_bodies": False,
            "stores_session_token_plaintext": False,
            "requires_production_trust_private_lane": True,
        },
        "cli_commands": [
            "yonerai node status --pretty",
            "yonerai node pair --dry-run --pretty",
            "yonerai relay status --pretty",
            "yonerai route preview <task> --use-local-node-fixture",
            "yonerai doctor --pretty",
            "yonerai demo --pretty",
        ],
        "actions_not_performed": [
            "no official cloud runtime",
            "no production Oracle",
            "no relay process start",
            "no node connector start",
            "no public tunnel",
            "no message body persistence",
            "no token output",
            "no provider key",
            "no live Discord",
            "no deploy",
        ],
    }


def _relay_flag(relay_status: Mapping[str, object], key: str) -> object:
    relay = relay_status.get("relay")
    if not isinstance(relay, Mapping):
        return None
    return relay.get(key)
