from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
for path in (CLIENTS_CLI,):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _fixture() -> dict[str, object]:
    path = ROOT / "docs" / "contracts" / "fixtures" / "status-snapshot-v1" / "staging-offline-worker.fixture.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_status_snapshot_schema_and_fixture_are_public_safe() -> None:
    schema = json.loads((ROOT / "docs" / "contracts" / "status_snapshot.v1.schema.json").read_text(encoding="utf-8"))
    fixture = _fixture()
    serialized = json.dumps(fixture, ensure_ascii=False, sort_keys=True).lower()

    assert schema["properties"]["schema_version"]["const"] == "yonerai.status.v1"
    assert fixture["schema_version"] == "yonerai.status.v1"
    assert fixture["private_runtime_details_included"] is False
    assert "not_production" not in {fixture["overall"]["health"], fixture["overall"]["availability"]}
    assert "arn:aws:" not in serialized
    assert "c:\\users" not in serialized
    assert "last_worker_id_hash" not in serialized
    assert "access_token" not in serialized


def test_normalize_status_snapshot_v1_keeps_worker_offline_and_provider_available() -> None:
    from yonerai_cli.services.status_snapshot_service import normalize_status_snapshot

    snapshot = normalize_status_snapshot(_fixture())
    components = {item["id"]: item for item in snapshot["components"]}

    assert components["official_execution_worker"]["health"] == "offline"
    assert components["official_execution_worker"]["availability"] == "unavailable"
    assert components["official_execution_worker"]["stale"] is True
    assert components["provider_gateway"]["health"] == "operational"
    assert components["provider_gateway"]["availability"] == "available"


def test_normalize_legacy_status_snapshot_does_not_treat_not_production_as_health() -> None:
    from yonerai_cli.services.status_snapshot_service import normalize_status_snapshot

    legacy = {
        "contract_version": "yonerai.status.feed.v0.2",
        "status": "not_production",
        "overall_status": "not_production",
        "environment": "staging",
        "generated_at": "2026-06-18T19:46:56Z",
        "status_snapshot": {
            "yonerai_api": "operational",
            "official_execution_worker": "offline",
            "worker_effective_health": "offline",
            "worker_heartbeat_stale": True,
            "worker_heartbeat_max_age_seconds": 60,
            "queue": "operational",
            "provider_gateway": "staging",
            "realtime_sync": "not_production",
            "web": "staging",
            "audit": "operational",
            "discord_bot": "not_production",
        },
    }

    snapshot = normalize_status_snapshot(legacy)

    assert snapshot["schema_version"] == "yonerai.status.v1"
    assert snapshot["overall"]["stage"] == "staging"
    assert snapshot["overall"]["health"] != "not_production"
    assert all(item["health"] != "not_production" for item in snapshot["components"])


def test_status_snapshot_rejects_private_endpoint_without_printing_it() -> None:
    from yonerai_cli.services.status_snapshot_service import StatusSnapshotError, normalize_status_snapshot

    payload = _fixture()
    payload["components"][0]["message"] = "See http://10.0.0.5/runbook"

    with pytest.raises(StatusSnapshotError) as exc:
        normalize_status_snapshot(payload)

    assert exc.value.code == "status_snapshot_private_payload_rejected"
    assert "10.0.0.5" not in exc.value.message


def test_status_snapshot_rejects_internal_hostname_without_printing_it() -> None:
    from yonerai_cli.services.status_snapshot_service import StatusSnapshotError, normalize_status_snapshot

    payload = _fixture()
    payload["components"][0]["message"] = "See https://worker.internal/runbook"

    with pytest.raises(StatusSnapshotError) as exc:
        normalize_status_snapshot(payload)

    assert exc.value.code == "status_snapshot_private_payload_rejected"
    assert "worker.internal" not in exc.value.message


def test_status_snapshot_rejects_ipv6_private_endpoint_without_printing_it() -> None:
    from yonerai_cli.services.status_snapshot_service import StatusSnapshotError, normalize_status_snapshot

    payload = _fixture()
    payload["components"][0]["message"] = "See http://[fc00::1]/status"

    with pytest.raises(StatusSnapshotError) as exc:
        normalize_status_snapshot(payload)

    assert exc.value.code == "status_snapshot_private_payload_rejected"
    assert "fc00" not in exc.value.message


def test_unknown_component_is_safe_but_not_canonical() -> None:
    from yonerai_cli.services.status_snapshot_service import normalize_status_snapshot

    payload = _fixture()
    payload["components"].append(
        {
            "id": "custom_preview",
            "health": "unknown",
            "availability": "limited",
            "stage": "preview",
            "message": "Future public component placeholder.",
            "updated_at": "2026-06-18T19:46:56Z",
            "stale": False,
            "incident_ref": None,
        }
    )

    snapshot = normalize_status_snapshot(payload)
    custom = [item for item in snapshot["components"] if item["id"] == "custom_preview"][0]

    assert custom["known_component"] is False


def test_live_mixed_envelope_drops_legacy_worker_identity() -> None:
    from yonerai_cli.services.status_snapshot_service import build_status_snapshot_report

    payload = _fixture()
    payload["status_snapshot"] = {
        "last_worker_id_hash": "abc123private",
        "queue_backend": "private_runtime_inventory",
    }

    def transport(method: str, url: str, headers: object, body: object, timeout_seconds: float) -> tuple[int, dict, dict]:
        del method, url, headers, body, timeout_seconds
        return 200, payload, {"ETag": 'W/"fixture"'}

    report = build_status_snapshot_report(source="live", transport=transport)
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is True
    assert "last_worker_id_hash" not in serialized
    assert "abc123private" not in serialized
