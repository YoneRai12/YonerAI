from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid.relay_status import (  # noqa: E402
    RELAY_STATUS_SCHEMA_VERSION,
    build_relay_status_report,
)
from src.relay.app import create_app  # noqa: E402


def test_relay_status_fixture_is_local_dev_and_non_mutating() -> None:
    report = build_relay_status_report({})
    serialized = json.dumps(report, sort_keys=True)

    assert report["schema_version"] == RELAY_STATUS_SCHEMA_VERSION
    assert report["ok"] is True
    assert report["mode"] == "local_dev_fixture"
    assert report["relay"]["host"] == "127.0.0.1"
    assert report["relay"]["loopback_only"] is True
    assert report["relay"]["process_started"] is False
    assert report["relay"]["health_probe_performed"] is False
    assert report["relay"]["quick_tunnel_enabled"] is False
    assert report["relay"]["public_exposure_allowed"] is False
    assert report["relay"]["message_body_persisted"] is False
    assert report["relay"]["pairing_code_storage"] == "hash_only"
    assert report["relay"]["session_token_storage"] == "hash_only"
    assert report["relay"]["session_token_plaintext_included"] is False
    assert report["node_connector"]["connector_started"] is False
    assert "token=" not in serialized.lower()
    assert "pairing_code=" not in serialized.lower()


def test_relay_status_redacts_non_loopback_configuration() -> None:
    report = build_relay_status_report(
        {
            "ORA_RELAY_HOST": "0.0.0.0",
            "ORA_RELAY_URL": "wss://relay.example.invalid",
            "ORA_NODE_API_BASE_URL": "https://node.example.invalid",
            "ORA_RELAY_EXPOSE_MODE": "cloudflared_quick",
        }
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["relay"]["host"] == "non_loopback_redacted"
    assert report["relay"]["configured_url_category"] == "non_loopback_blocked"
    assert report["relay"]["public_exposure_requested"] is True
    assert report["relay"]["public_exposure_allowed"] is False
    assert report["node_connector"]["node_api_base_url_category"] == "non_loopback_blocked"
    assert "relay.example.invalid" not in serialized
    assert "node.example.invalid" not in serialized


def test_relay_status_accepts_loopback_ip_range_and_auto_url_without_probe() -> None:
    report = build_relay_status_report(
        {
            "ORA_RELAY_HOST": "127.0.0.2",
            "ORA_RELAY_URL": "auto",
        }
    )

    assert report["ok"] is True
    assert report["relay"]["host"] == "127.0.0.2"
    assert report["relay"]["configured_url_category"] == "auto_unresolved_no_probe"
    assert report["relay"]["health_probe_performed"] is False
    assert report["node_connector"]["relay_url_category"] == "auto_unresolved_no_probe"


def test_relay_status_resolves_auto_url_file_before_marking_safe(tmp_path: Path) -> None:
    url_file = tmp_path / "relay-url.txt"
    url_file.write_text("https://relay.example.invalid\n", encoding="utf-8")

    report = build_relay_status_report(
        {
            "ORA_RELAY_URL": "auto",
            "ORA_RELAY_URL_FILE": str(url_file),
        }
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["relay"]["configured_url_category"] == "auto_resolved_non_loopback_blocked"
    assert report["relay"]["auto_url_resolution"] == "auto_resolved_non_loopback_blocked"
    assert report["relay"]["loopback_only"] is False
    assert report["node_connector"]["relay_url_category"] == "auto_resolved_non_loopback_blocked"
    assert "relay.example.invalid" not in serialized
    assert str(url_file) not in serialized


def test_relay_status_treats_invalid_auto_url_file_as_unreadable(tmp_path: Path) -> None:
    url_file = tmp_path / "relay-url.txt"
    url_file.write_bytes(b"\xff\xfe\xfa")

    report = build_relay_status_report(
        {
            "ORA_RELAY_URL": "auto",
            "ORA_RELAY_URL_FILE": str(url_file),
        }
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["relay"]["configured_url_category"] == "auto_resolution_unreadable"
    assert report["relay"]["auto_url_resolution"] == "auto_resolution_unreadable"
    assert report["node_connector"]["relay_url_category"] == "auto_resolution_unreadable"
    assert str(url_file) not in serialized


def test_relay_status_accepts_scheme_less_loopback_url() -> None:
    report = build_relay_status_report(
        {
            "ORA_RELAY_URL": "127.0.0.2:9010",
        }
    )

    assert report["ok"] is True
    assert report["relay"]["configured_url_category"] == "loopback"
    assert report["node_connector"]["relay_url_category"] == "loopback"


def test_relay_app_pairing_is_one_time_and_health_is_metadata_only() -> None:
    app = create_app()

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        with client.websocket_connect("/ws/node?node_id=node-1") as node_ws:
            node_ws.send_json({"type": "pair_offer", "code": "abcd1234"})
            ack = node_ws.receive_json()

            assert ack["type"] == "pair_offer_ack"
            assert ack["ok"] is True
            assert client.get("/health").json() == {"ok": True, "nodes": 1, "pairs": 1, "sessions": 0}

            paired = client.post("/api/pair", json={"code": "abcd1234"})
            assert paired.status_code == 200
            pair_body = paired.json()
            assert pair_body["ok"] is True
            assert pair_body["node_id"] == "node-1"
            assert pair_body["token"]

            reused = client.post("/api/pair", json={"code": "abcd1234"})
            assert reused.status_code == 403

            health_after = client.get("/health").json()
            assert health_after == {"ok": True, "nodes": 1, "pairs": 0, "sessions": 1}
            assert pair_body["token"] not in json.dumps(health_after)
