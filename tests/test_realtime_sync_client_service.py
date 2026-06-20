from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
if str(CLIENTS_CLI) not in sys.path:
    sys.path.insert(0, str(CLIENTS_CLI))


ORIGIN = "https://api-staging.yonerai.com"
RATE_HEADERS = {
    "X-YonerAI-RateLimit-Scope": "account",
    "X-YonerAI-RateLimit-Limit": "60",
    "X-YonerAI-RateLimit-Remaining": "59",
    "X-YonerAI-RateLimit-Reset": "2026-06-20T00:00:00Z",
    "X-YonerAI-RateLimit-Reason": "within_quota",
}


def _save_session(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    from yonerai_cli.services.staging_session_service import save_staging_session

    config_path = tmp_path / "cli-config.json"
    claim = save_staging_session(
        session_token="ystg_fixture_session_1234567890",
        origin=ORIGIN,
        account={"account_ref": "public-sync-fixture-account", "email": "owner@example.com", "display_name": "Owner"},
        expires_at="2099-06-20T00:00:00Z",
        config_path=config_path,
    )
    return config_path, claim


def _event_for_account(account_id: object, **overrides: object) -> dict[str, object]:
    from yonerai_cli.services.realtime_sync_event_service import build_realtime_sync_event_fixture

    event = build_realtime_sync_event_fixture("valid")
    event["account_id"] = account_id
    event.update(overrides)
    return event


def test_golden_realtime_sync_fixtures_match_public_validator_contract() -> None:
    from yonerai_cli.services.realtime_sync_event_service import (
        GOLDEN_FIXTURE_PATH,
        build_realtime_sync_event_validation_report,
        load_realtime_sync_golden_fixtures,
    )

    raw = GOLDEN_FIXTURE_PATH.read_bytes()
    assert b"\r\n" not in raw
    golden = load_realtime_sync_golden_fixtures()

    assert golden["contract_schema_version"] == "yonerai.realtime_sync.v1"
    names = set()
    for fixture in golden["fixtures"]:
        assert isinstance(fixture, dict)
        names.add(fixture["name"])
        report = build_realtime_sync_event_validation_report(
            fixture["event"],
            linked_account_id=str(fixture["linked_account_id"]),
        )
        assert report["ok"] is (fixture["expected"] == "accept"), fixture["name"]

    assert {
        "valid-cloud-to-local",
        "forbidden-body-present",
        "forbidden-token-like-value",
        "forbidden-local-path",
        "forbidden-internal-endpoint",
        "forbidden-body-ref-traversal",
        "forbidden-body-ref-query",
        "forbidden-account-mismatch",
        "forbidden-provider-sharing-default-on",
        "forbidden-unknown-private-fields",
    } <= names


def test_listener_fetches_aws_body_only_after_valid_metadata_event(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_once_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"])
    calls: list[tuple[str, str]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        calls.append((method, url))
        assert method == "GET"
        assert url == f"{ORIGIN}/v1/conversations/conv_public_001/messages/msg_public_001"
        assert headers["Authorization"].startswith("Bearer ")
        assert body is None
        return (
            200,
            {
                "message": {
                    "conversation_id": "conv_public_001",
                    "message_id": "msg_public_001",
                    "body": "hello from web",
                    "body_safety": "public_safe_test_fixture",
                }
            },
            RATE_HEADERS,
        )

    report = build_realtime_sync_listener_once_report(
        event=event,
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["event_validated"] is True
    assert report["aws_body_fetch_performed"] is True
    assert report["body_received_from_aws"] is True
    assert report["message"]["display_text"] == "hello from web"
    assert report["message"]["body_from_firestore"] is False
    assert report["cursor_saved"] is True
    assert report["reconnect_supported"] is True
    assert report["next_reconnect_cursor"] == "cursor_public_001"
    assert calls == [("GET", f"{ORIGIN}/v1/conversations/conv_public_001/messages/msg_public_001")]
    assert "ystg_fixture_session_1234567890" not in serialized
    assert "Authorization" not in serialized
    assert str(tmp_path) not in serialized


def test_listener_deduplicates_event_before_second_body_fetch(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_once_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"])
    calls = 0

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        nonlocal calls
        calls += 1
        return (
            200,
            {
                "message": {
                    "conversation_id": "conv_public_001",
                    "message_id": "msg_public_001",
                    "body": "hello from web",
                }
            },
            RATE_HEADERS,
        )

    state_path = tmp_path / "sync-state.json"
    first = build_realtime_sync_listener_once_report(
        event=event,
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        state_path=state_path,
        transport=transport,
    )
    second = build_realtime_sync_listener_once_report(
        event=event,
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        state_path=state_path,
        transport=transport,
    )

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["duplicate_event"] is True
    assert second["body_fetch_allowed"] is False
    assert second["aws_body_fetch_performed"] is False
    assert second["next_reconnect_cursor"] == "cursor_public_001"
    assert calls == 1


def test_listener_local_only_event_never_fetches_aws_body(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_once_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"], origin="local", sync_policy="local_only")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        raise AssertionError("local_only event must not fetch AWS body")

    report = build_realtime_sync_listener_once_report(
        event=event,
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=transport,
    )

    assert report["ok"] is True
    assert report["body_fetch_allowed"] is False
    assert report["body_fetch_reason"] == "local_origin_or_local_only_never_fetches_cloud_body"
    assert report["aws_body_fetch_performed"] is False
    assert report["local_to_cloud_upload_performed"] is False
    assert report["reconnect_supported"] is True


def test_listener_rejects_private_aws_body_response_without_leaking(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_once_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"])

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return (
            200,
            {
                "message": {
                    "conversation_id": "conv_public_001",
                    "message_id": "msg_public_001",
                    "body": "accessToken must not be returned",
                }
            },
            RATE_HEADERS,
        )

    report = build_realtime_sync_listener_once_report(
        event=event,
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "sync_aws_body_private_payload_rejected"
    assert report["error"]["token_printed"] is False
    assert "accessToken" not in serialized
    assert str(tmp_path) not in serialized


def test_listener_cli_local_only_fixture_is_non_network_and_no_body_fallback(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"], origin="local", sync_policy="local_only")
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", ORIGIN)

    rc = cli.main(
        [
            "sync",
            "listener",
            "once",
            "--event-json",
            json.dumps(event),
            "--state",
            str(tmp_path / "sync-state.json"),
            "--json",
        ]
    )
    output = capsys.readouterr().out
    report = json.loads(output)

    assert rc == 0
    assert report["operation"] == "realtime_sync_listener_once"
    assert report["firestore_body_fallback_allowed"] is False
    assert report["aws_body_fetch_performed"] is False
    assert report["cursor_saved"] is True
    assert report["reconnect_supported"] is True
    assert str(tmp_path) not in output


def test_listener_poll_fetches_feed_event_then_aws_body(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_poll_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"])
    calls: list[tuple[str, str]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        calls.append((method, url))
        assert headers["Authorization"].startswith("Bearer ")
        assert body is None
        if url == f"{ORIGIN}/v1/conversations/events?limit=10":
            return (
                200,
                {
                    "schema_version": "yonerai.realtime_sync.feed.v1",
                    "metadata_only": True,
                    "redacted_preview_only": True,
                    "events": [event],
                    "next_cursor": "cursor_public_001",
                    "has_more": False,
                },
                RATE_HEADERS,
            )
        assert url == f"{ORIGIN}/v1/conversations/conv_public_001/messages/msg_public_001"
        return (
            200,
            {
                "message": {
                    "conversation_id": "conv_public_001",
                    "message_id": "msg_public_001",
                    "body": "hello from web",
                    "body_safety": "public_safe_test_fixture",
                }
            },
            RATE_HEADERS,
        )

    report = build_realtime_sync_listener_poll_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["operation"] == "realtime_sync_listener_poll"
    assert report["event_source_kind"] == "aws_account_scoped_metadata_feed"
    assert report["firestore_event_source_body_free"] is True
    assert report["events_received"] == 1
    assert report["events_processed"] == 1
    assert report["metadata_event_to_aws_body_fetch_completed"] is True
    assert report["live_web_to_cli_e2e_proven"] is False
    assert report["messages"][0]["display_text"] == "hello from web"
    assert report["messages"][0]["body_from_firestore"] is False
    assert calls == [
        ("GET", f"{ORIGIN}/v1/conversations/events?limit=10"),
        ("GET", f"{ORIGIN}/v1/conversations/conv_public_001/messages/msg_public_001"),
    ]
    assert "ystg_fixture_session_1234567890" not in serialized
    assert "Authorization" not in serialized
    assert str(tmp_path) not in serialized


def test_listener_poll_rejects_feed_with_body_projection_without_fetch(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_poll_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"])
    event["message_body"] = "body must not be projected"
    calls: list[str] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        calls.append(url)
        return 200, {"events": [event], "metadata_only": True, "redacted_preview_only": True}, RATE_HEADERS

    report = build_realtime_sync_listener_poll_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "sync_event_feed_private_payload_rejected"
    assert calls == [f"{ORIGIN}/v1/conversations/events?limit=10"]
    assert "body must not be projected" not in serialized
    assert str(tmp_path) not in serialized


def test_listener_poll_rejects_unapproved_source_path(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_poll_report

    config_path, _claim = _save_session(tmp_path)

    report = build_realtime_sync_listener_poll_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        source_path="/v1/sync/events",
        transport=lambda *_args: (_ for _ in ()).throw(AssertionError("transport must not be called")),
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "sync_event_source_not_allowed"


def test_listener_poll_session_rejection_is_controlled(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_poll_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 401, {"detail": {"code": "unknown_staging_session"}}, RATE_HEADERS

    report = build_realtime_sync_listener_poll_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_session_required"
    assert report["error"]["status_code"] == 401
    assert "ystg_fixture_session_1234567890" not in serialized


def test_listener_poll_cli_rejects_unapproved_source_path(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path, _claim = _save_session(tmp_path)
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", ORIGIN)

    rc = cli.main(
        [
            "sync",
            "listener",
            "poll",
            "--source-path",
            "/v1/sync/events",
            "--state",
            str(tmp_path / "sync-state.json"),
            "--json",
        ]
    )
    output = capsys.readouterr().out
    report = json.loads(output)

    assert rc == 1
    assert report["operation"] == "realtime_sync_listener_poll"
    assert report["error"]["code"] == "sync_event_source_not_allowed"
    assert str(tmp_path) not in output


def _firebase_token_payload(account_id: object, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_version": "yonerai.official.api.v1.skeleton",
        "firebase_auth_contract_version": "yonerai.firebase.custom_token.v1",
        "token_type": "firebase_custom_token",
        "firebase_custom_token": "firebase_custom_token_fixture_value",
        "expires_at": "2026-06-20T12:00:00Z",
        "expires_in_seconds": 900,
        "uid": account_id,
        "account_id": account_id,
        "claims": {"yonerai_staging": True},
        "firestore": {
            "project_id": "yonerai-platform-stg-2026",
            "database_id": "(default)",
            "sync_enabled": False,
            "sync_event_path_template": "/accounts/{account_id}/sync_events/{event_id}",
        },
        "google_token_returned": False,
        "refresh_token_returned": False,
        "auth_code_returned": False,
        "provider_key_returned": False,
        "production_login": False,
    }
    payload.update(overrides)
    return payload


def test_firebase_token_bridge_accepts_safe_contract_without_printing_token(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_token_report

    config_path, claim = _save_session(tmp_path)
    calls: list[tuple[str, str, Mapping[str, object] | None]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        calls.append((method, url, body))
        assert method == "POST"
        assert url == f"{ORIGIN}/v1/sync/firebase-token"
        assert headers["Authorization"].startswith("Bearer ")
        assert body == {"purpose": "realtime_sync_metadata_read"}
        return 200, _firebase_token_payload(claim["account_id"]), RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["operation"] == "realtime_sync_firebase_token"
    assert report["firebase_custom_token_received"] is True
    assert report["firebase_custom_token_printed"] is False
    assert report["firebase_custom_token_persisted"] is False
    assert report["firebase_uid_matches_account"] is True
    assert report["firestore_sync_enabled"] is False
    assert report["firestore_sync_event_path_template"] == "/accounts/{account_id}/sync_events/{event_id}"
    assert report["firestore_account_data_binding_required"] is True
    assert report["live_web_to_cli_e2e_proven"] is False
    assert "firebase_custom_token_fixture_value" not in serialized
    assert "ystg_fixture_session_1234567890" not in serialized
    assert str(tmp_path) not in serialized
    assert calls == [("POST", f"{ORIGIN}/v1/sync/firebase-token", {"purpose": "realtime_sync_metadata_read"})]


def test_firebase_token_bridge_rejects_private_token_fields(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_token_report

    config_path, claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        payload = _firebase_token_payload(claim["account_id"], google_access_token="must-not-return")
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "firebase_token_private_payload_rejected"
    assert "must-not-return" not in serialized
    assert str(tmp_path) not in serialized


def test_firebase_token_bridge_rejects_account_mismatch(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_token_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 200, _firebase_token_payload("different-account"), RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firebase_token_account_mismatch"


def test_firebase_token_bridge_rejects_enabled_sync_before_e2e(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_token_report

    config_path, claim = _save_session(tmp_path)
    payload = _firebase_token_payload(claim["account_id"])
    firestore = dict(payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    payload["firestore"] = firestore

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firebase_token_sync_flag_invalid"


def test_firebase_token_cli_missing_origin_is_controlled(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    config_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("YONERAI_STAGING_AUTH_ORIGIN", raising=False)

    rc = cli.main(["sync", "listener", "firebase-token", "--json"])
    output = capsys.readouterr().out
    report = json.loads(output)

    assert rc == 1
    assert report["operation"] == "realtime_sync_firebase_token"
    assert report["error"]["code"] == "staging_origin_not_configured"
    assert "Authorization" not in output
    assert "ystg_fixture_session_1234567890" not in output
    assert str(tmp_path) not in output


def test_listener_readiness_reports_404_as_not_ready_without_leak(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        assert method == "POST"
        assert url == f"{ORIGIN}/v1/sync/firebase-token"
        return 404, {"detail": {"code": "not_found"}}, RATE_HEADERS

    report = build_realtime_sync_listener_readiness_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["ready"] is False
    assert report["firebase_token_endpoint_checked"] is True
    assert report["firebase_token_endpoint_live"] is False
    assert report["firebase_token_endpoint_status_code"] == 404
    assert report["next_blocker"] == "private_aws_firebase_token_endpoint_not_live"
    assert "ystg_fixture_session_1234567890" not in serialized
    assert "Authorization" not in serialized
    assert str(tmp_path) not in serialized


def test_listener_readiness_treats_401_as_live_route_with_session_blocker(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 401, {"detail": {"code": "unknown_staging_session"}}, RATE_HEADERS

    report = build_realtime_sync_listener_readiness_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["ready"] is False
    assert report["firebase_token_endpoint_live"] is True
    assert report["firebase_token_endpoint_status_code"] == 401
    assert report["next_blocker"] == "staging_session_required"
    assert "ystg_fixture_session_1234567890" not in serialized


def test_listener_readiness_reports_503_as_private_runtime_blocker(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 503, {"detail": {"code": "firebase_not_configured"}}, RATE_HEADERS

    report = build_realtime_sync_listener_readiness_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["ready"] is False
    assert report["firebase_token_endpoint_live"] is True
    assert report["firebase_token_endpoint_status_code"] == 503
    assert report["next_blocker"] == "private_aws_firebase_token_endpoint_unavailable"
    assert "firebase_not_configured" not in serialized
    assert "ystg_fixture_session_1234567890" not in serialized


def test_listener_readiness_accepts_live_read_auth_but_keeps_sync_disabled(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report

    config_path, claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 200, _firebase_token_payload(claim["account_id"]), RATE_HEADERS

    report = build_realtime_sync_listener_readiness_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["ready"] is False
    assert report["firebase_token_endpoint_live"] is True
    assert report["firestore_read_auth_bridge_ready"] is True
    assert isinstance(report["firestore_sdk_dependency_available"], bool)
    assert report["firestore_client_sign_in_config_present"] is False
    assert report["firestore_sync_enabled"] is False
    assert report["firestore_sdk_listener_ready"] is False
    assert report["next_blocker"] == "firestore_sync_disabled_until_live_e2e_and_owner_flip"
    assert "firebase_custom_token_fixture_value" not in serialized
    assert "ystg_fixture_session_1234567890" not in serialized


def test_listener_readiness_reports_client_sign_in_config_without_printing_value(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report

    config_path, claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 200, _firebase_token_payload(claim["account_id"]), RATE_HEADERS

    report = build_realtime_sync_listener_readiness_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-firebase-client-config-fixture",
        },
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["ready"] is False
    assert report["firestore_read_auth_bridge_ready"] is True
    assert report["firestore_client_sign_in_config_present"] is True
    assert report["firestore_sdk_listener_ready"] is False
    assert report["next_blocker"] == "firestore_sync_disabled_until_live_e2e_and_owner_flip"
    assert "public-firebase-client-config-fixture" not in serialized
    assert "firebase_custom_token_fixture_value" not in serialized
    assert str(tmp_path) not in serialized


def test_listener_readiness_fails_closed_on_private_firebase_payload(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report

    config_path, claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 200, _firebase_token_payload(claim["account_id"], google_access_token="must-not-return"), RATE_HEADERS

    report = build_realtime_sync_listener_readiness_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["ready"] is False
    assert report["next_blocker"] == "firebase_token_contract_or_safety_violation"
    assert report["error"]["code"] == "firebase_token_private_payload_rejected"
    assert "must-not-return" not in serialized
    assert str(tmp_path) not in serialized


def test_listener_readiness_cli_reports_not_ready_without_nonzero_exit(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    config_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("YONERAI_STAGING_AUTH_ORIGIN", raising=False)

    rc = cli.main(["sync", "listener", "readiness", "--json"])
    output = capsys.readouterr().out
    report = json.loads(output)

    assert rc == 0
    assert report["operation"] == "realtime_sync_listener_readiness"
    assert report["ok"] is True
    assert report["ready"] is False
    assert report["next_blocker"] == "staging_origin_not_configured"
    assert str(tmp_path) not in output
