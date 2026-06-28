from __future__ import annotations

import base64
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
        account={"account_id": "acct_public_sync_fixture", "email": "owner@example.com", "display_name": "Owner"},
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


def test_listener_accepts_windows_crlf_in_aws_body(tmp_path: Path) -> None:
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
                    "body": "hello from web\r\nsecond line",
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

    assert report["ok"] is True
    assert report["aws_body_fetch_performed"] is True
    assert report["message"]["display_text"] == "hello from web\r\nsecond line"
    assert report["message"]["body_from_firestore"] is False


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


def test_listener_cli_once_defaults_to_firestore_one_shot(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli
    from yonerai_cli.commands import sync as sync_command

    config_path, _claim = _save_session(tmp_path)
    captured: dict[str, object] = {}

    def fake_firestore_poll_report(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "ok": False,
            "operation": "realtime_sync_firestore_poll",
            "listener_mode": "firestore_rest_metadata_poll",
            "firestore_body_fallback_allowed": False,
            "firestore_rest_connected": False,
            "messages": [],
            "error": {"code": "fixture_stop"},
        }

    monkeypatch.setattr(sync_command, "build_realtime_sync_firestore_poll_report", fake_firestore_poll_report)

    rc = cli.main(
        [
            "sync",
            "listener",
            "once",
            "--config-path",
            str(config_path),
            "--state",
            str(tmp_path / "sync-state.json"),
            "--json",
        ]
    )
    output = capsys.readouterr().out
    report = json.loads(output)

    assert rc == 1
    assert report["operation"] == "realtime_sync_firestore_poll"
    assert report["listener_mode"] == "firestore_rest_metadata_poll"
    assert report["firestore_body_fallback_allowed"] is False
    assert captured["limit"] == 1
    assert captured["config_path"] == str(config_path)
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
        "claims": {
            "yonerai_staging": True,
            "yonerai_session_expires_at": 1781956800,
        },
        "revocation": {
            "mode": "short_ttl",
            "immediate": False,
            "max_delay_seconds": 900,
            "external_alpha_requires_session_projection": True,
        },
        "firestore": {
            "project_id": "yonerai-platform-stg-2026",
            "database_id": "(default)",
            "sync_enabled": False,
            "body_free_projection_only": True,
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


def _firebase_config_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "config_contract_version": "yonerai.firebase.public_config.v1",
        "ready": True,
        "sync_enabled": False,
        "sync_mode": "off",
        "firebase": {
            "api_key": "public-client-config-fixture",
            "auth_domain": "staging.yonerai.com",
            "project_id": "yonerai-platform-stg-2026",
            "app_id": "public-app-id-fixture",
            "messaging_sender_id": "123456789",
        },
        "firestore": {
            "project_id": "yonerai-platform-stg-2026",
            "database_id": "(default)",
            "sync_enabled": False,
            "body_free_projection_only": True,
            "sync_event_path_template": "/accounts/{account_id}/sync_events/{event_id}",
        },
        "usage_policy": _firestore_usage_policy_payload(),
    }
    payload.update(overrides)
    return payload


def _firestore_usage_policy_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "policy_version": "yonerai.firestore_usage_policy.v1",
        "sync_mode": "off",
        "account_admission_state": "closed_alpha",
        "initial_query_limit": 20,
        "absolute_query_limit": 50,
        "reconnect_cooldown_seconds": 30,
        "max_web_listeners_per_account": 1,
        "max_cli_listeners_per_account": 1,
        "custom_token_ttl_seconds": 900,
        "token_issuance_allowed": True,
        "projection_write_allowed": False,
        "kill_switch": False,
        "client_requirements": {
            "account_rooted_listener_only": True,
            "cursor_required_after_initial_page": True,
            "offset_forbidden": True,
            "collection_group_query_allowed": False,
            "client_writes_allowed": False,
            "body_fetch_source": "aws_only",
        },
        "reason_code": "sync_off_until_closed_alpha_e2e",
    }
    payload.update(overrides)
    return payload


def _firebase_config_sync_enabled_payload() -> dict[str, object]:
    payload = _firebase_config_payload(
        sync_enabled=True,
        sync_mode="staging",
        usage_policy=_firestore_usage_policy_payload(sync_mode="staging"),
    )
    firestore = dict(payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    firestore["sync_mode"] = "staging"
    payload["firestore"] = firestore
    return payload


def _firebase_config_allowlist_payload() -> dict[str, object]:
    payload = _firebase_config_payload(
        sync_enabled=True,
        sync_mode="allowlist",
        usage_policy=_firestore_usage_policy_payload(sync_mode="allowlist"),
    )
    firestore = dict(payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    firestore["sync_mode"] = "allowlist"
    payload["firestore"] = firestore
    return payload


def _firestore_value(value: object) -> dict[str, object]:
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if value is None:
        return {"nullValue": None}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {key: _firestore_value(item) for key, item in value.items()}}}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_firestore_value(item) for item in value]}}
    return {"stringValue": str(value)}


def _firestore_document(event: Mapping[str, object]) -> dict[str, object]:
    return {"name": "projects/redacted/databases/(default)/documents/accounts/redacted/sync_events/redacted", "fields": {key: _firestore_value(value) for key, value in event.items()}}


def _firestore_run_query_payload(event: Mapping[str, object]) -> list[Mapping[str, object]]:
    return [{"document": _firestore_document(event), "readTime": "2026-06-28T00:00:00Z", "transaction": "read_transaction_fixture"}]


def _assert_safe_firestore_structured_query(
    *,
    method: str,
    url: str,
    body: Mapping[str, object] | None,
    account_id: object,
    limit: int = 10,
) -> None:
    assert method == "POST"
    assert url == "https://firestore.googleapis.com/v1/projects/yonerai-platform-stg-2026/databases/(default)/documents/accounts/acct_public_sync_fixture:runQuery"
    assert body is not None
    query = body["structuredQuery"]
    assert isinstance(query, Mapping)
    assert query["from"] == [{"collectionId": "sync_events", "allDescendants": False}]
    assert query["orderBy"] == [{"field": {"fieldPath": "created_at"}, "direction": "ASCENDING"}]
    assert query["limit"] == limit
    assert "offset" not in query
    where = query["where"]
    assert isinstance(where, Mapping)
    composite = where["compositeFilter"]
    assert isinstance(composite, Mapping)
    filters = composite["filters"]
    assert isinstance(filters, list)
    assert {
        "fieldFilter": {
            "field": {"fieldPath": "account_id"},
            "op": "EQUAL",
            "value": {"stringValue": account_id},
        }
    } in filters
    assert {
        "fieldFilter": {
            "field": {"fieldPath": "body_ref.body_included"},
            "op": "EQUAL",
            "value": {"booleanValue": False},
        }
    } in filters


def _jwt_with_uid(uid: str) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode("utf-8")).decode("ascii").rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"sub": uid, "user_id": uid}).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{header}.{payload}.signature"


def test_firebase_custom_token_exchange_accepts_uid_from_id_token_payload() -> None:
    from yonerai_cli.services.realtime_sync_client_service import _exchange_firebase_custom_token

    expected_uid = "acct_public_sync_fixture"

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        assert method == "POST"
        assert "accounts:signInWithCustomToken" in url
        assert body == {"token": "firebase_custom_token_fixture_value", "returnSecureToken": True}
        return 200, {
            "kind": "identitytoolkit#VerifyCustomTokenResponse",
            "idToken": _jwt_with_uid(expected_uid),
            "refreshToken": "discarded-refresh-token-fixture",
            "expiresIn": "900",
            "isNewUser": False,
        }, {}

    id_token, local_id = _exchange_firebase_custom_token(
        "firebase_custom_token_fixture_value",
        "firebase-client-key-fixture",
        transport=transport,
        timeout_seconds=10.0,
    )

    assert id_token
    assert local_id == expected_uid


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
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            assert method == "GET"
            assert body is None
            return 200, _firebase_config_payload(), RATE_HEADERS
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
    assert report["firebase_claims_session_ref_present"] is False
    assert report["firebase_claims_session_expires_at_present"] is True
    assert report["firebase_revocation_mode"] == "short_ttl"
    assert report["firebase_revocation_immediate"] is False
    assert report["firebase_revocation_max_delay_seconds"] == 900
    assert report["firebase_immediate_firestore_read_revocation"] is False
    assert report["firebase_external_alpha_requires_session_projection"] is True
    assert report["firestore_sync_enabled"] is False
    assert report["firestore_sync_event_path_template"] == "/accounts/{account_id}/sync_events/{event_id}"
    assert report["firestore_account_data_binding_required"] is True
    assert report["live_web_to_cli_e2e_proven"] is False
    assert "firebase_custom_token_fixture_value" not in serialized
    assert "ystg_fixture_session_1234567890" not in serialized
    assert str(tmp_path) not in serialized
    assert calls == [
        ("GET", f"{ORIGIN}/v1/sync/firebase-config", None),
        ("POST", f"{ORIGIN}/v1/sync/firebase-token", {"purpose": "realtime_sync_metadata_read"}),
    ]


def test_firebase_token_bridge_checks_policy_before_requesting_custom_token(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_token_report

    config_path, _claim = _save_session(tmp_path)
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
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            payload = _firebase_config_sync_enabled_payload()
            payload["usage_policy"] = _firestore_usage_policy_payload(sync_mode="staging", token_issuance_allowed=False)
            return 200, payload, RATE_HEADERS
        raise AssertionError("Firebase custom token endpoint must not be called after token issuance is disabled")

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_usage_policy_token_issuance_disabled"
    assert calls == [("GET", f"{ORIGIN}/v1/sync/firebase-config")]


def test_firebase_config_bridge_reports_not_ready_without_printing_config(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)
    calls: list[tuple[str, str]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        calls.append((method, url))
        assert body is None
        return 200, _firebase_config_payload(
            ready=False,
            firebase={},
            firestore={},
            owner_action_required="configure_public_firebase_client",
        ), RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["operation"] == "realtime_sync_firebase_config"
    assert report["firebase_config_endpoint_live"] is True
    assert report["firebase_public_config_ready"] is False
    assert report["firebase_public_api_key_received"] is False
    assert report["firebase_public_api_key_printed"] is False
    assert report["firebase_public_api_key_persisted"] is False
    assert report["firestore_client_sign_in_config_present"] is False
    assert report["firestore_client_sign_in_config_source"] == "none"
    assert report["firestore_usage_policy_present"] is True
    assert report["firestore_usage_policy_accepted"] is True
    assert report["firestore_usage_policy_version"] == "yonerai.firestore_usage_policy.v1"
    assert report["firestore_initial_query_limit"] == 20
    assert report["firestore_absolute_query_limit"] == 50
    assert report["firestore_reconnect_cooldown_seconds"] == 30
    assert report["firestore_max_cli_listeners_per_account"] == 1
    assert report["firestore_offset_forbidden"] is True
    assert report["firestore_body_fetch_source"] == "aws_only"
    assert report["firestore_projection_write_allowed"] is False
    assert "public-client-config-fixture" not in serialized
    assert "ystg_fixture_session_1234567890" not in serialized
    assert str(tmp_path) not in serialized
    assert calls == [("GET", f"{ORIGIN}/v1/sync/firebase-config")]


def test_firebase_config_bridge_treats_sync_mode_off_as_hard_stop(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        payload = _firebase_config_payload(sync_enabled=True, sync_mode="off")
        firestore = dict(payload["firestore"])  # type: ignore[arg-type]
        firestore["sync_enabled"] = True
        firestore["sync_mode"] = "off"
        payload["firestore"] = firestore
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is True
    assert report["firestore_backend_sync_enabled"] is True
    assert report["firestore_sync_mode"] == "off"
    assert report["firestore_sync_enabled"] is False
    assert report["firestore_usage_policy_accepted"] is True


def test_firebase_config_bridge_accepts_owner_allowlist_sync_mode(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 200, _firebase_config_allowlist_payload(), RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is True
    assert report["firebase_public_config_ready"] is True
    assert report["firestore_sync_mode"] == "allowlist"
    assert report["firestore_sync_enabled"] is True
    assert report["firestore_usage_policy_accepted"] is True
    assert report["firestore_initial_query_limit"] == 20
    assert report["firestore_absolute_query_limit"] == 50
    assert report["firestore_reconnect_cooldown_seconds"] == 30
    assert report["firestore_max_cli_listeners_per_account"] == 1
    assert report["firestore_offset_forbidden"] is True
    assert report["firestore_collection_group_query_allowed"] is False
    assert report["firestore_body_fetch_source"] == "aws_only"


def test_firebase_config_bridge_keeps_allowlist_disabled_when_not_ready(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        payload = _firebase_config_allowlist_payload()
        payload["ready"] = False
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is True
    assert report["firebase_public_config_ready"] is False
    assert report["firestore_backend_sync_enabled"] is True
    assert report["firestore_sync_mode"] == "allowlist"
    assert report["firestore_sync_enabled"] is False
    assert report["ready"] is False


def test_firebase_config_bridge_rejects_permissive_usage_policy(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 200, _firebase_config_payload(usage_policy=_firestore_usage_policy_payload(initial_query_limit=100)), RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_usage_policy_too_permissive"


def test_firebase_config_bridge_rejects_usage_policy_kill_switch(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        payload = _firebase_config_sync_enabled_payload()
        payload["usage_policy"] = _firestore_usage_policy_payload(sync_mode="staging", kill_switch=True)
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_usage_policy_kill_switch_active"


def test_firebase_config_bridge_accepts_object_kill_switch_when_not_tripped(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        payload = _firebase_config_payload(
            usage_policy=_firestore_usage_policy_payload(
                kill_switch={"tripped": False, "reason": "sync_mode_off"},
            )
        )
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is True
    assert report["firestore_usage_policy_accepted"] is True
    assert report["firestore_sync_mode"] == "off"


def test_firebase_config_bridge_rejects_object_kill_switch_when_tripped(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        payload = _firebase_config_sync_enabled_payload()
        payload["usage_policy"] = _firestore_usage_policy_payload(
            sync_mode="staging",
            kill_switch={"tripped": True, "reason": "owner_smoke_disabled"},
        )
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_usage_policy_kill_switch_active"


def test_firebase_config_bridge_rejects_usage_policy_token_issuance_disabled(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        payload = _firebase_config_sync_enabled_payload()
        payload["usage_policy"] = _firestore_usage_policy_payload(sync_mode="staging", token_issuance_allowed=False)
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_usage_policy_token_issuance_disabled"


def test_firestore_poll_checks_token_policy_before_requesting_custom_token(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, _claim = _save_session(tmp_path)
    official_calls: list[tuple[str, str]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        official_calls.append((method, url))
        assert headers["Authorization"].startswith("Bearer ")
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            payload = _firebase_config_sync_enabled_payload()
            payload["usage_policy"] = _firestore_usage_policy_payload(sync_mode="staging", token_issuance_allowed=False)
            return 200, payload, RATE_HEADERS
        raise AssertionError("Firebase custom token endpoint must not be called after token issuance is disabled")

    report = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_usage_policy_token_issuance_disabled"
    assert official_calls == [("GET", f"{ORIGIN}/v1/sync/firebase-config")]


def test_firebase_config_bridge_rejects_projection_writes_while_off(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        policy = _firestore_usage_policy_payload(projection_write_allowed=True)
        return 200, _firebase_config_payload(usage_policy=policy), RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_usage_policy_invalid"


def test_firebase_config_bridge_rejects_private_payload(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_config_report

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 200, _firebase_config_payload(firebase={"api_key": "public-client-config-fixture", "client_secret": "nope"}), RATE_HEADERS

    report = build_realtime_sync_firebase_config_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "firebase_config_private_payload_rejected"
    assert "nope" not in serialized
    assert str(tmp_path) not in serialized


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
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
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


def test_firebase_token_bridge_rejects_legacy_session_ref_claim(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_token_report

    config_path, claim = _save_session(tmp_path)
    payload = _firebase_token_payload(claim["account_id"])
    claims = dict(payload["claims"])  # type: ignore[arg-type]
    claims["yonerai_session_ref"] = "session-ref-must-not-return"
    payload["claims"] = claims

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "firebase_token_private_fields"
    assert "session-ref-must-not-return" not in serialized


def test_firebase_token_bridge_rejects_immediate_revocation_claim(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_token_report

    config_path, claim = _save_session(tmp_path)
    payload = _firebase_token_payload(claim["account_id"])
    revocation = dict(payload["revocation"])  # type: ignore[arg-type]
    revocation["immediate"] = True
    payload["revocation"] = revocation

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firebase_token_revocation_invalid"


def test_firebase_token_bridge_rejects_revocation_delay_above_closed_alpha_limit(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_token_report

    config_path, claim = _save_session(tmp_path)
    payload = _firebase_token_payload(claim["account_id"])
    revocation = dict(payload["revocation"])  # type: ignore[arg-type]
    revocation["max_delay_seconds"] = 901
    payload["revocation"] = revocation

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firebase_token_revocation_invalid"


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
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
        return 200, _firebase_token_payload("different-account"), RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firebase_token_account_mismatch"


def test_firebase_token_bridge_rejects_legacy_public_ref_for_canonical_account_id(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_token_report

    raw_account_id = "acct_contract_runtime_123"
    config_path, _claim = _save_session(tmp_path)

    # Legacy Public builds stored a hashed account_ref. The current AWS contract
    # requires exact canonical account_id matching, so this must force re-login
    # rather than silently accepting a hash-derived alias.
    claim_path = config_path.with_name(f"{config_path.stem}.staging-session-claim.json")
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    claim["account_id"] = "staging-account-84c212c254ae65ca"
    claim_path.write_text(json.dumps(claim, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return 200, _firebase_token_payload(raw_account_id), RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "canonical_account_id_required"
    assert "firebase_custom_token_fixture_value" not in serialized
    assert raw_account_id not in serialized


def test_firebase_token_bridge_accepts_owner_enabled_sync_flag(tmp_path: Path) -> None:
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
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_allowlist_payload(), RATE_HEADERS
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["firestore_sync_enabled"] is True
    assert "firebase_custom_token_fixture_value" not in serialized
    assert str(tmp_path) not in serialized


def test_firebase_token_bridge_requires_body_free_projection_flag(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firebase_token_report

    config_path, claim = _save_session(tmp_path)
    payload = _firebase_token_payload(claim["account_id"])
    firestore = dict(payload["firestore"])  # type: ignore[arg-type]
    firestore["body_free_projection_only"] = False
    payload["firestore"] = firestore

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
        return 200, payload, RATE_HEADERS

    report = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "firebase_token_firestore_invalid"


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
    calls: list[tuple[str, str]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        calls.append((method, url))
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            assert method == "GET"
            return 200, _firebase_config_payload(), RATE_HEADERS
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
    assert calls == [("GET", f"{ORIGIN}/v1/sync/firebase-config"), ("POST", f"{ORIGIN}/v1/sync/firebase-token")]
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
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
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
    assert report["required_next_actions"] == (
        "run yonerai logout to clear the rejected staging session",
        "run yonerai login to get a fresh opaque YonerAI staging session",
        "rerun yonerai sync listener readiness after login succeeds",
    )
    assert "ystg_fixture_session_1234567890" not in serialized


def test_listener_readiness_rejects_legacy_public_ref_before_backend_call(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_session_service import load_staging_session_claim
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report

    config_path, _claim = _save_session(tmp_path)
    claim = load_staging_session_claim(config_path=str(config_path))
    claim["account_id"] = "staging-account-84c212c254ae65ca"
    claim_path = config_path.with_name(f"{config_path.stem}.staging-session-claim.json")
    claim_path.write_text(json.dumps(claim, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    called = False

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        nonlocal called
        called = True
        return 200, _firebase_token_payload("acct_contract_runtime_123"), RATE_HEADERS

    report = build_realtime_sync_listener_readiness_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert called is False
    assert report["ok"] is True
    assert report["ready"] is False
    assert report["official_backend_called"] is False
    assert report["firebase_token_endpoint_checked"] is False
    assert report["firebase_token_endpoint_live"] is False
    assert report["firebase_token_endpoint_status_code"] is None
    assert report["next_blocker"] == "canonical_account_id_required"
    assert report["required_next_actions"] == (
        "run yonerai logout to clear the legacy staging account_ref session",
        "run yonerai login to get a fresh opaque YonerAI staging session with canonical account_id",
        "rerun yonerai sync listener readiness after login succeeds",
    )
    assert "ystg_fixture_session_1234567890" not in serialized
    assert "acct_contract_runtime_123" not in serialized
    assert str(tmp_path) not in serialized


def test_listener_readiness_rejects_placeholder_account_id_before_backend_call(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_session_service import load_staging_session_claim
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report

    for placeholder in ("linked-staging-account", "linked staging account"):
        config_path, _claim = _save_session(tmp_path / placeholder.replace(" ", "-"))
        claim = load_staging_session_claim(config_path=str(config_path))
        claim["account_id"] = placeholder
        claim_path = config_path.with_name(f"{config_path.stem}.staging-session-claim.json")
        claim_path.write_text(json.dumps(claim, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        called = False

        def transport(
            method: str,
            url: str,
            headers: Mapping[str, str],
            body: Mapping[str, object] | None,
            timeout: float,
        ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
            nonlocal called
            called = True
            return 200, _firebase_token_payload("acct_contract_runtime_123"), RATE_HEADERS

        report = build_realtime_sync_listener_readiness_report(
            env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
            config_path=str(config_path),
            transport=transport,
        )
        serialized = json.dumps(report, sort_keys=True)

        assert called is False
        assert report["ok"] is True
        assert report["ready"] is False
        assert report["official_backend_called"] is False
        assert report["firebase_token_endpoint_checked"] is False
        assert report["firebase_token_endpoint_live"] is False
        assert report["firebase_token_endpoint_status_code"] is None
        assert report["next_blocker"] == "canonical_account_id_required"
        assert report["required_next_actions"] == (
            "run yonerai logout to clear the legacy staging account_ref session",
            "run yonerai login to get a fresh opaque YonerAI staging session with canonical account_id",
            "rerun yonerai sync listener readiness after login succeeds",
        )
        assert "acct_contract_runtime_123" not in serialized
        assert str(tmp_path) not in serialized


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
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
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


def test_listener_readiness_reports_unreachable_as_transient_blocker(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report
    from yonerai_cli.services.staging_sync_service import StagingSyncServiceError

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
        raise StagingSyncServiceError("staging_sync_unreachable", "Staging sync source is unreachable.")

    report = build_realtime_sync_listener_readiness_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["ready"] is False
    assert report["next_blocker"] == "staging_sync_unreachable"
    assert report["firebase_token_error"]["code"] == "staging_sync_unreachable"
    assert "firebase_token_contract_or_safety_violation" not in serialized
    assert "ystg_fixture_session_1234567890" not in serialized


def test_listener_readiness_checks_policy_before_requesting_custom_token(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report

    config_path, _claim = _save_session(tmp_path)
    official_calls: list[tuple[str, str]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        official_calls.append((method, url))
        assert headers["Authorization"].startswith("Bearer ")
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            payload = _firebase_config_sync_enabled_payload()
            payload["usage_policy"] = _firestore_usage_policy_payload(sync_mode="staging", token_issuance_allowed=False)
            return 200, payload, RATE_HEADERS
        raise AssertionError("Firebase custom token endpoint must not be called after token issuance is disabled")

    report = build_realtime_sync_listener_readiness_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["ready"] is False
    assert report["next_blocker"] == "firestore_usage_policy_token_issuance_disabled"
    assert report["firebase_config_error"]["code"] == "firestore_usage_policy_token_issuance_disabled"
    assert report["firebase_token_endpoint_checked"] is False
    assert report["official_backend_called"] is False
    assert official_calls == [("GET", f"{ORIGIN}/v1/sync/firebase-config")]
    assert "firebase_custom_token_fixture_value" not in serialized
    assert str(tmp_path) not in serialized


def test_listener_readiness_reports_owner_token_signing_permission_blocker(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import (
        build_realtime_sync_firebase_token_report,
        build_realtime_sync_listener_readiness_report,
    )

    config_path, _claim = _save_session(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
        return (
            503,
            {
                "detail": {
                    "code": "firebase_token_mint_dependency_blocked",
                    "owner_action_required": "grant_service_account_token_creator",
                    "token_mint_dependency_ready": False,
                }
            },
            RATE_HEADERS,
        )

    firebase = build_realtime_sync_firebase_token_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    readiness = build_realtime_sync_listener_readiness_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        config_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(readiness, sort_keys=True)

    assert firebase["ok"] is False
    assert firebase["backend_status_code"] == 503
    assert firebase["error"]["owner_action_required"] == "grant_service_account_token_creator"
    assert firebase["error"]["token_mint_dependency_ready"] is False
    assert readiness["ok"] is True
    assert readiness["ready"] is False
    assert readiness["firebase_token_endpoint_live"] is True
    assert readiness["firebase_token_endpoint_status_code"] == 503
    assert readiness["firebase_token_error"]["owner_action_required"] == "grant_service_account_token_creator"
    assert readiness["firebase_token_error"]["token_mint_dependency_ready"] is False
    assert readiness["next_blocker"] == "owner_gcp_token_signing_permission_required"
    assert readiness["firebase_custom_token_received"] is False
    assert "ystg_fixture_session_1234567890" not in serialized
    assert "Authorization" not in serialized
    assert str(tmp_path) not in serialized


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
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, _firebase_token_payload(claim["account_id"]), RATE_HEADERS
        assert url == f"{ORIGIN}/v1/sync/firebase-config"
        return 200, _firebase_config_payload(sync_enabled=False), RATE_HEADERS

    def firebase_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        assert method == "POST"
        assert url.startswith("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?")
        assert body == {"token": "firebase_custom_token_fixture_value", "returnSecureToken": True}
        assert not headers
        return 200, {"idToken": _jwt_with_uid(claim["account_id"]), "expiresIn": "900"}, {}

    report = build_realtime_sync_listener_readiness_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        transport=transport,
        firebase_rest_transport=firebase_transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["ready"] is False
    assert report["firebase_token_endpoint_live"] is True
    assert report["firestore_read_auth_bridge_ready"] is True
    assert report["linked_account"]["account_id_present"] is True
    assert report["linked_account"]["account_id_printed"] is False
    assert "account_id" not in report["linked_account"]
    assert "account_ref" not in report["linked_account"]
    assert report["firebase_account_id_matches_session"] is True
    assert report["firebase_revocation_mode"] == "short_ttl"
    assert report["firebase_revocation_immediate"] is False
    assert report["firebase_revocation_max_delay_seconds"] == 900
    assert report["firebase_external_alpha_requires_session_projection"] is True
    assert isinstance(report["firestore_sdk_dependency_available"], bool)
    assert report["firestore_client_sign_in_config_present"] is True
    assert report["firebase_config_endpoint_live"] is True
    assert report["firebase_public_config_ready"] is True
    assert report["firebase_public_api_key_received"] is True
    assert report["firestore_sync_enabled"] is False
    assert report["firestore_sdk_listener_ready"] is False
    assert report["next_blocker"] == "firestore_sync_disabled_until_live_e2e_and_owner_flip"
    assert "firebase_custom_token_fixture_value" not in serialized
    assert "account_ref" not in serialized
    assert claim["account_id"] not in serialized
    assert "ystg_fixture_session_1234567890" not in serialized


def test_firestore_poll_reads_metadata_then_fetches_body_from_aws_only(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"])
    firebase_payload = _firebase_token_payload(claim["account_id"])
    firestore = dict(firebase_payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    firebase_payload["firestore"] = firestore
    official_calls: list[tuple[str, str]] = []
    firebase_calls: list[tuple[str, str]] = []

    def official_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        official_calls.append((method, url))
        assert headers["Authorization"].startswith("Bearer ")
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, firebase_payload, RATE_HEADERS
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_allowlist_payload(), RATE_HEADERS
        assert url == f"{ORIGIN}/v1/conversations/conv_public_001/messages/msg_public_001"
        return 200, {"message": {"conversation_id": "conv_public_001", "message_id": "msg_public_001", "body": "hello via firestore"}}, RATE_HEADERS

    def firebase_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, object, Mapping[str, str]]:
        firebase_calls.append((method, url))
        if url.startswith("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?"):
            assert body == {"token": "firebase_custom_token_fixture_value", "returnSecureToken": True}
            return 200, {"idToken": "firebase_id_token_fixture", "refreshToken": "discarded", "expiresIn": "3600", "localId": claim["account_id"]}, {}
        _assert_safe_firestore_structured_query(method=method, url=url, body=body, account_id=claim["account_id"])
        assert headers["Authorization"] == "Bearer firebase_id_token_fixture"
        return 200, _firestore_run_query_payload(event), {}

    state_path = tmp_path / "sync-state.json"
    report = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=state_path,
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
    )
    serialized = json.dumps(report, sort_keys=True)
    saved_state = json.loads(state_path.read_text(encoding="utf-8"))
    conversation_state = saved_state["accounts"][claim["account_id"]]["conversations"]["conv_public_001"]

    assert report["ok"] is True
    assert report["operation"] == "realtime_sync_firestore_poll"
    assert report["firestore_sync_mode"] == "allowlist"
    assert report["firestore_rest_connected"] is True
    assert report["firestore_event_source_body_free"] is True
    assert report["events_received"] == 1
    assert report["events_processed"] == 1
    assert report["messages"][0]["display_text"] == "hello via firestore"
    assert report["messages"][0]["body_from_firestore"] is False
    assert report["metadata_event_to_aws_body_fetch_completed"] is True
    assert official_calls == [
        ("GET", f"{ORIGIN}/v1/sync/firebase-config"),
        ("POST", f"{ORIGIN}/v1/sync/firebase-token"),
        ("GET", f"{ORIGIN}/v1/conversations/conv_public_001/messages/msg_public_001"),
    ]
    assert len(firebase_calls) == 2
    assert conversation_state["cursor"] == "cursor_public_001"
    assert conversation_state["event_ids"] == ["evt_public_001"]
    assert conversation_state["idempotency_keys"] == ["sync_public_001"]
    assert saved_state["accounts"][claim["account_id"]]["last_firestore_poll_at"]
    assert "firebase_custom_token_fixture_value" not in serialized
    assert "firebase_id_token_fixture" not in serialized
    assert "public-client-key-fixture" not in serialized
    assert "ystg_fixture_session_1234567890" not in serialized
    assert str(tmp_path) not in serialized


def test_firestore_poll_reports_sanitized_read_error_diagnostic(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, claim = _save_session(tmp_path)
    firebase_payload = _firebase_token_payload(claim["account_id"])
    firestore = dict(firebase_payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    firebase_payload["firestore"] = firestore

    def official_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        assert headers["Authorization"].startswith("Bearer ")
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, firebase_payload, RATE_HEADERS
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_allowlist_payload(), RATE_HEADERS
        raise AssertionError("AWS body fetch must not run after Firestore read failure")

    def firebase_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url.startswith("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?"):
            return 200, {"idToken": "firebase_id_token_fixture", "refreshToken": "discarded", "expiresIn": "3600", "localId": claim["account_id"]}, {}
        assert url.startswith("https://firestore.googleapis.com/v1/projects/yonerai-platform-stg-2026/databases/")
        return (
            400,
            {
                "error": {
                    "code": 400,
                    "status": "FAILED_PRECONDITION",
                    "message": "index missing for account acct_public_sync_fixture; create at https://console.firebase.google.com/private",
                    "details": [{"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": [{"field": "accounts/acct_public_sync_fixture"}]}],
                }
            },
            {},
        )

    report = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
    )
    serialized = json.dumps(report, sort_keys=True)
    diagnostic = report["error"]["diagnostic"]

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_sync_event_read_failed"
    assert report["error"]["status_code"] == 400
    assert diagnostic["request_kind"] == "firestore_structured_query"
    assert diagnostic["collection"] == "sync_events"
    assert diagnostic["account_rooted"] is True
    assert diagnostic["collection_group_query"] is False
    assert diagnostic["offset_used"] is False
    assert diagnostic["account_filter_included"] is True
    assert diagnostic["body_free_filter_included"] is True
    assert diagnostic["firestore_error_code"] == 400
    assert diagnostic["firestore_error_status"] == "FAILED_PRECONDITION"
    assert diagnostic["firestore_error_detail_types"] == ["type.googleapis.com/google.rpc.BadRequest"]
    assert diagnostic["raw_firestore_message_included"] is False
    assert diagnostic["raw_firestore_path_included"] is False
    assert "console.firebase.google.com" not in serialized
    assert "acct_public_sync_fixture" not in serialized
    assert "firebase_custom_token_fixture_value" not in serialized
    assert "firebase_id_token_fixture" not in serialized
    assert "public-client-key-fixture" not in serialized
    assert str(tmp_path) not in serialized


def test_firestore_poll_diagnostic_rejects_private_detail_type_markers(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, claim = _save_session(tmp_path)
    firebase_payload = _firebase_token_payload(claim["account_id"])
    firestore = dict(firebase_payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    firebase_payload["firestore"] = firestore

    def official_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, firebase_payload, RATE_HEADERS
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_allowlist_payload(), RATE_HEADERS
        raise AssertionError("AWS body fetch must not run after Firestore read failure")

    def firebase_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url.startswith("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?"):
            return 200, {"idToken": "firebase_id_token_fixture", "refreshToken": "discarded", "expiresIn": "3600", "localId": claim["account_id"]}, {}
        return (
            400,
            {
                "error": {
                    "code": 400,
                    "status": "FAILED_PRECONDITION",
                    "message": "private path must not leak",
                    "details": [
                        {"@type": "type.googleapis.com/google.rpc.BadRequest"},
                        {"@type": "access_token"},
                        {"@type": "/home/alice/private"},
                    ],
                }
            },
            {},
        )

    report = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
    )
    serialized = json.dumps(report, sort_keys=True)
    diagnostic = report["error"]["diagnostic"]

    assert report["ok"] is False
    assert diagnostic["firestore_error_detail_types"] == ["type.googleapis.com/google.rpc.BadRequest"]
    assert "access_token" not in serialized
    assert "/home/alice/private" not in serialized
    assert "private path must not leak" not in serialized
    assert "firebase_id_token_fixture" not in serialized
    assert str(tmp_path) not in serialized


def test_firestore_poll_caps_limit_and_enforces_reconnect_cooldown(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"])
    firebase_payload = _firebase_token_payload(claim["account_id"])
    firestore = dict(firebase_payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    firebase_payload["firestore"] = firestore
    firestore_requests: list[tuple[str, str, Mapping[str, object] | None]] = []

    def official_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, firebase_payload, RATE_HEADERS
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_sync_enabled_payload(), RATE_HEADERS
        return 200, {"message": {"conversation_id": "conv_public_001", "message_id": "msg_public_001", "body": "hello via firestore"}}, RATE_HEADERS

    def firebase_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, object, Mapping[str, str]]:
        if url.startswith("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?"):
            return 200, {"idToken": "firebase_id_token_fixture", "expiresIn": "3600", "localId": claim["account_id"]}, {}
        firestore_requests.append((method, url, body))
        _assert_safe_firestore_structured_query(method=method, url=url, body=body, account_id=claim["account_id"], limit=20)
        return 200, _firestore_run_query_payload(event), {}

    state_path = tmp_path / "sync-state.json"
    first = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=state_path,
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
        limit=99,
    )
    second = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=state_path,
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
        limit=99,
    )
    serialized = json.dumps(second, sort_keys=True)

    assert first["ok"] is True
    assert first["firestore_requested_limit"] == 99
    assert first["firestore_effective_query_limit"] == 20
    assert firestore_requests[0][2]["structuredQuery"]["limit"] == 20  # type: ignore[index]
    assert second["ok"] is False
    assert second["error"]["code"] == "firestore_reconnect_cooldown_active"
    assert second["firestore_reconnect_cooldown_remaining_seconds"] > 0
    assert len(firestore_requests) == 1
    assert "firebase_id_token_fixture" not in serialized
    assert str(tmp_path) not in serialized


def test_firestore_poll_resumes_after_saved_cursor(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, claim = _save_session(tmp_path)
    state_path = tmp_path / "sync-state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "yonerai.realtime-sync-state/v0.1",
                "accounts": {
                    claim["account_id"]: {
                        "conversations": {
                            "conv_public_001": {
                                "cursor": "cursor_public_001",
                                "last_event_id": "evt_public_001",
                                "event_ids": ["evt_public_001"],
                                "idempotency_keys": ["sync_public_001"],
                            }
                        }
                    }
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    event = _event_for_account(
        claim["account_id"],
        event_id="evt_public_002",
        message_id="msg_public_002",
        cursor="cursor_public_002",
        idempotency_key="sync_public_002",
        body_ref={
            "kind": "aws_message_body",
            "href": "/v1/conversations/conv_public_001/messages/msg_public_002",
            "body_included": False,
        },
    )
    firebase_payload = _firebase_token_payload(claim["account_id"])
    firestore = dict(firebase_payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    firebase_payload["firestore"] = firestore
    firestore_requests: list[tuple[str, str, Mapping[str, object] | None]] = []

    def official_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, firebase_payload, RATE_HEADERS
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_sync_enabled_payload(), RATE_HEADERS
        assert url == f"{ORIGIN}/v1/conversations/conv_public_001/messages/msg_public_002"
        return 200, {"message": {"conversation_id": "conv_public_001", "message_id": "msg_public_002", "body": "resumed message"}}, RATE_HEADERS

    def firebase_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, object, Mapping[str, str]]:
        if url.startswith("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?"):
            return 200, {"idToken": "firebase_id_token_fixture", "expiresIn": "3600", "localId": claim["account_id"]}, {}
        firestore_requests.append((method, url, body))
        _assert_safe_firestore_structured_query(method=method, url=url, body=body, account_id=claim["account_id"])
        assert "pageToken" not in url
        return 200, _firestore_run_query_payload(event), {}

    report = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=state_path,
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
    )

    assert report["ok"] is True
    assert report["event_source_cursor"] == "cursor_public_001"
    assert report["event_source_query_included"] is True
    assert report["messages"][0]["display_text"] == "resumed message"
    assert len(firestore_requests) == 1


def test_firestore_poll_does_not_start_when_sync_flag_is_disabled(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, claim = _save_session(tmp_path)
    official_calls: list[tuple[str, str]] = []

    def official_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        official_calls.append((method, url))
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, _firebase_token_payload(claim["account_id"]), RATE_HEADERS
        assert url == f"{ORIGIN}/v1/sync/firebase-config"
        return 200, _firebase_config_payload(), RATE_HEADERS

    def firebase_transport(*_args: object) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        raise AssertionError("Firestore must not be contacted while sync is disabled")

    report = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_sync_disabled_until_live_e2e_and_owner_flip"
    assert report["firestore_rest_connected"] is False
    assert official_calls == [("GET", f"{ORIGIN}/v1/sync/firebase-config")]
    assert "firebase_custom_token_fixture_value" not in serialized
    assert "public-client-key-fixture" not in serialized
    assert str(tmp_path) not in serialized


def test_firestore_poll_does_not_start_when_allowlist_config_is_not_ready(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, _claim = _save_session(tmp_path)
    official_calls: list[tuple[str, str]] = []

    def official_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        official_calls.append((method, url))
        assert headers["Authorization"].startswith("Bearer ")
        assert url == f"{ORIGIN}/v1/sync/firebase-config"
        payload = _firebase_config_allowlist_payload()
        payload["ready"] = False
        return 200, payload, RATE_HEADERS

    def firebase_transport(*_args: object) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        raise AssertionError("Firestore must not be contacted when Firebase config ready=false")

    report = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_sync_disabled_until_live_e2e_and_owner_flip"
    assert report["firestore_sync_mode"] == "allowlist"
    assert report["firestore_sync_enabled"] is False
    assert report["firestore_rest_connected"] is False
    assert official_calls == [("GET", f"{ORIGIN}/v1/sync/firebase-config")]
    assert "firebase_custom_token_fixture_value" not in serialized
    assert "public-client-key-fixture" not in serialized
    assert str(tmp_path) not in serialized


def test_firestore_poll_rejects_body_projection_before_aws_fetch(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"])
    event["message_body"] = "body must not be projected"
    firebase_payload = _firebase_token_payload(claim["account_id"])
    firestore = dict(firebase_payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    firebase_payload["firestore"] = firestore
    official_calls: list[str] = []

    def official_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        official_calls.append(url)
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, firebase_payload, RATE_HEADERS
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_sync_enabled_payload(), RATE_HEADERS
        return 200, {"message": {"conversation_id": "conv_public_001", "message_id": "msg_public_001", "body": "should not be reached"}}, RATE_HEADERS

    def firebase_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, object, Mapping[str, str]]:
        if url.startswith("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?"):
            return 200, {"idToken": "firebase_id_token_fixture", "expiresIn": "3600", "localId": claim["account_id"]}, {}
        _assert_safe_firestore_structured_query(method=method, url=url, body=body, account_id=claim["account_id"])
        return 200, _firestore_run_query_payload(event), {}

    report = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_sync_event_rejected"
    assert official_calls == [f"{ORIGIN}/v1/sync/firebase-config", f"{ORIGIN}/v1/sync/firebase-token"]
    assert "body must not be projected" not in serialized
    assert "firebase_id_token_fixture" not in serialized
    assert str(tmp_path) not in serialized


def test_firestore_poll_rejects_legacy_documents_list_response(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account(claim["account_id"])
    firebase_payload = _firebase_token_payload(claim["account_id"])
    firestore = dict(firebase_payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    firebase_payload["firestore"] = firestore

    def official_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, firebase_payload, RATE_HEADERS
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_sync_enabled_payload(), RATE_HEADERS
        raise AssertionError("AWS body fetch must not run for legacy Firestore list response")

    def firebase_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, object, Mapping[str, str]]:
        if url.startswith("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?"):
            return 200, {"idToken": "firebase_id_token_fixture", "expiresIn": "3600", "localId": claim["account_id"]}, {}
        _assert_safe_firestore_structured_query(method=method, url=url, body=body, account_id=claim["account_id"])
        return 200, {"documents": [_firestore_document(event)]}, {}

    report = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_response_invalid"
    assert "firebase_id_token_fixture" not in serialized
    assert str(tmp_path) not in serialized


def test_firestore_poll_rejects_wrong_account_event_before_aws_fetch(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_firestore_poll_report

    config_path, claim = _save_session(tmp_path)
    event = _event_for_account("acct_other_public_fixture")
    firebase_payload = _firebase_token_payload(claim["account_id"])
    firestore = dict(firebase_payload["firestore"])  # type: ignore[arg-type]
    firestore["sync_enabled"] = True
    firebase_payload["firestore"] = firestore

    def official_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, firebase_payload, RATE_HEADERS
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_sync_enabled_payload(), RATE_HEADERS
        raise AssertionError("AWS body fetch must not run for wrong-account Firestore event")

    def firebase_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, object, Mapping[str, str]]:
        if url.startswith("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?"):
            return 200, {"idToken": "firebase_id_token_fixture", "expiresIn": "3600", "localId": claim["account_id"]}, {}
        _assert_safe_firestore_structured_query(method=method, url=url, body=body, account_id=claim["account_id"])
        return 200, _firestore_run_query_payload(event), {}

    report = build_realtime_sync_firestore_poll_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-client-key-fixture",
        },
        config_path=str(config_path),
        state_path=tmp_path / "sync-state.json",
        transport=official_transport,
        firebase_rest_transport=firebase_transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "firestore_sync_event_rejected"
    assert "acct_other_public_fixture" not in serialized
    assert "firebase_id_token_fixture" not in serialized
    assert str(tmp_path) not in serialized


def test_listener_readiness_reports_client_sign_in_config_without_printing_value(tmp_path: Path) -> None:
    from yonerai_cli.services.realtime_sync_client_service import build_realtime_sync_listener_readiness_report

    config_path, claim = _save_session(tmp_path)
    official_calls: list[str] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        official_calls.append(url)
        if url == f"{ORIGIN}/v1/sync/firebase-token":
            return 200, _firebase_token_payload(claim["account_id"]), RATE_HEADERS
        assert url == f"{ORIGIN}/v1/sync/firebase-config"
        return 200, _firebase_config_payload(ready=True, sync_enabled=False, firebase={}), RATE_HEADERS

    def firebase_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        assert method == "POST"
        assert url.startswith("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?")
        assert body == {"token": "firebase_custom_token_fixture_value", "returnSecureToken": True}
        assert not headers
        return (
            200,
            {
                "idToken": _jwt_with_uid(claim["account_id"]),
                "refreshToken": "refresh_token_fixture_should_not_leak",
                "expiresIn": "900",
            },
            {},
        )

    report = build_realtime_sync_listener_readiness_report(
        env={
            "YONERAI_STAGING_AUTH_ORIGIN": ORIGIN,
            "YONERAI_FIREBASE_CLIENT_API_KEY": "public-firebase-client-config-fixture",
        },
        config_path=str(config_path),
        transport=transport,
        firebase_rest_transport=firebase_transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["ready"] is False
    assert report["firestore_read_auth_bridge_ready"] is True
    assert report["firestore_client_sign_in_config_present"] is True
    assert report["firestore_client_sign_in_config_source"] == "env"
    assert report["firebase_custom_token_exchange_attempted"] is True
    assert report["firebase_custom_token_exchange_passed"] is True
    assert report["firebase_id_token_received"] is True
    assert report["firebase_id_token_printed"] is False
    assert report["firebase_id_token_persisted"] is False
    assert report["firebase_refresh_token_discarded"] is True
    assert report["firebase_refresh_token_persisted"] is False
    assert report["firebase_public_api_key_received"] is False
    assert report["firestore_sdk_listener_ready"] is False
    assert report["next_blocker"] == "firestore_sync_disabled_until_live_e2e_and_owner_flip"
    assert official_calls.count(f"{ORIGIN}/v1/sync/firebase-token") == 1
    assert "public-firebase-client-config-fixture" not in serialized
    assert "firebase_custom_token_fixture_value" not in serialized
    assert "refresh_token_fixture_should_not_leak" not in serialized
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
        if url == f"{ORIGIN}/v1/sync/firebase-config":
            return 200, _firebase_config_payload(), RATE_HEADERS
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


def test_listener_readiness_pretty_shows_japanese_relogin_summary() -> None:
    from yonerai_cli.commands.sync import format_sync_pretty_v2

    output = format_sync_pretty_v2(
        {
            "operation": "realtime_sync_listener_readiness",
            "ok": True,
            "ready": False,
            "next_blocker": "canonical_account_id_required",
            "required_next_actions": (
                "run yonerai logout to clear the legacy staging account_ref session",
                "run yonerai login to get a fresh opaque YonerAI staging session with canonical account_id",
            ),
        },
        lang="ja",
        color="never",
    )

    assert "要約" in output
    assert "同期リスナーはまだ使えません" in output
    assert "保存済みログインが古い account_ref 形式です" in output
    assert "yonerai logout の後に yonerai login" in output


def test_listener_readiness_pretty_shows_english_firebase_config_blocker() -> None:
    from yonerai_cli.commands.sync import format_sync_pretty_v2

    output = format_sync_pretty_v2(
        {
            "operation": "realtime_sync_listener_readiness",
            "ok": True,
            "ready": False,
            "next_blocker": "firebase_public_config_not_ready",
            "firebase_config_endpoint_live": True,
            "firebase_public_config_ready": False,
        },
        lang="en",
        color="never",
    )

    assert "not ready" in output
    assert "The staging Firebase public client config is not ready yet." in output
    assert "Wait for AWS to publish a ready public config" in output
