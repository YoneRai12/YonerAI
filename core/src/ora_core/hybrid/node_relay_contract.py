from __future__ import annotations

from typing import Mapping

from .relay_node_e2e import build_local_dev_relay_node_e2e_report
from .relay_status import build_relay_status_report
from .wire_contract import build_local_node_status_report


HYBRID_NODE_RELAY_CONTRACT_VERSION = "yonerai-hybrid-node-relay-contract/v0.1"


def build_hybrid_node_relay_contract_stub(env: Mapping[str, str] | None = None) -> dict[str, object]:
    node_status = build_local_node_status_report()
    relay_status = build_relay_status_report(env)
    e2e_status = build_local_dev_relay_node_e2e_report(env)
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
            "loopback_only": _section_value(relay_status, "relay", "loopback_only"),
            "process_started": _section_value(relay_status, "relay", "process_started"),
            "health_probe_performed": _section_value(relay_status, "relay", "health_probe_performed"),
            "public_exposure_allowed": _section_value(relay_status, "relay", "public_exposure_allowed"),
            "message_body_persisted": _section_value(relay_status, "relay", "message_body_persisted"),
            "pairing_code_storage": _section_value(relay_status, "relay", "pairing_code_storage"),
            "session_token_storage": _section_value(relay_status, "relay", "session_token_storage"),
        },
        "session_ref": {
            "state": session_ref.get("state") if isinstance(session_ref, dict) else None,
            "signed_origin_verified": session_ref.get("signed_origin_verified") if isinstance(session_ref, dict) else None,
            "bearer_token_included": session_ref.get("bearer_token_included") if isinstance(session_ref, dict) else None,
            "bearer_token_hash_only": session_ref.get("bearer_token_hash_only") if isinstance(session_ref, dict) else None,
            "message_body_persisted": session_ref.get("message_body_persisted") if isinstance(session_ref, dict) else None,
        },
        "local_dev_e2e": {
            "schema_version": e2e_status.get("schema_version"),
            "ok": e2e_status.get("ok"),
            "network_required": e2e_status.get("network_required"),
            "pairing_code_hash_only": _section_value(e2e_status, "pairing", "pairing_code_hash_only"),
            "session_token_hash_only": _section_value(e2e_status, "pairing", "session_token_hash_only"),
            "message_body_persisted": _proxy_body_persisted(e2e_status),
            "http_proxy_fixture_available": isinstance(e2e_status.get("http_proxy_fixture"), Mapping),
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


def _section_value(payload: Mapping[str, object], section: str, key: str) -> object:
    value = payload.get(section)
    if not isinstance(value, Mapping):
        return None
    return value.get(key)


def _proxy_body_persisted(e2e_status: Mapping[str, object]) -> bool | None:
    proxy = e2e_status.get("http_proxy_fixture")
    if not isinstance(proxy, Mapping):
        return None
    return bool(proxy.get("request_body_persisted") or proxy.get("response_body_persisted"))
