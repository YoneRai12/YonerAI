from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

from yonerai_cli.config import default_config_path
from yonerai_cli.services.realtime_sync_event_service import (
    REALTIME_SYNC_SCHEMA_VERSION,
    RealtimeSyncEventError,
    build_realtime_sync_event_fixture,
    build_realtime_sync_event_validation_report,
)
from yonerai_cli.services.staging_sync_service import (
    HeaderJsonTransport,
    StagingSyncServiceError,
    _auth_context,
    _auth_headers,
    _rate_limit_headers_present,
    _request_json,
)


REALTIME_SYNC_CLIENT_SCHEMA_VERSION = "yonerai.realtime-sync-client/v0.1"
STATE_SCHEMA_VERSION = "yonerai.realtime-sync-state/v0.1"
CONVERSATION_EVENTS_PATH = "/v1/conversations/events"
FIREBASE_TOKEN_PATH = "/v1/sync/firebase-token"
FIREBASE_AUTH_CONTRACT_VERSION = "yonerai.firebase.custom_token.v1"
FIRESTORE_SYNC_EVENT_PATH_TEMPLATE = "/accounts/{account_id}/sync_events/{event_id}"
READINESS_NON_BLOCKING_ERROR_CODES = {
    "staging_origin_not_configured",
    "staging_auth_required",
    "staging_session_required",
    "firebase_token_request_failed",
}
FORBIDDEN_BODY_MARKERS = (
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
    "id_token",
    "idtoken",
    "auth_code",
    "authcode",
    "authorization_code",
    "authorizationcode",
    "google_token",
    "googletoken",
    "session_token",
    "sessiontoken",
    "provider_key",
    "providerkey",
    "api_key",
    "apikey",
    "client_secret",
    "clientsecret",
    "secret_key",
    "secretkey",
    "arn:",
    "c:\\users",
    "\\\\",
    "/users/",
    "/home/",
    "/root/",
    "http://10.",
    "http://192.168.",
    "http://127.",
    "169.254.169.254",
)


class RealtimeSyncClientError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code

    def to_safe_error(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "status_code": self.status_code,
            "token_printed": False,
            "local_path_printed": False,
            "raw_body_printed": False,
            "private_runtime_detail_printed": False,
        }


def default_realtime_sync_state_path(config_path: str | Path | None = None) -> Path:
    base = Path(config_path).expanduser() if config_path is not None else default_config_path()
    return base.with_name(f"{base.stem}.realtime-sync-state.json")


def build_realtime_sync_listener_once_report(
    *,
    event: Mapping[str, object],
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    config_path: str | None = None,
    state_path: str | Path | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    context = _auth_context(config=config, env=env, claim_path=config_path)
    report = _base_report(context)
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if context["auth_state"] != "linked":
        report["ok"] = False
        report["error"] = _safe_error("staging_auth_required", "Staging login is required before realtime sync receive.")
        return report
    if not context["staging_session_available"]:
        report["ok"] = False
        report["error"] = _safe_error(
            "staging_session_required",
            "A safe YonerAI staging session is required before realtime sync receive.",
        )
        return report

    try:
        linked_account_id = _linked_account_id(context)
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    state_file = Path(state_path).expanduser() if state_path is not None else default_realtime_sync_state_path(config_path)
    state = _load_state(state_file)
    seen = _seen_for_event(state, linked_account_id, event)
    validation = build_realtime_sync_event_validation_report(
        event,
        linked_account_id=linked_account_id,
        seen_event_ids=seen["event_ids"],
        seen_idempotency_keys=seen["idempotency_keys"],
    )
    report["validation"] = _public_validation(validation)
    report.update(
        {
            "event_validated": bool(validation.get("ok")),
            "event_id": validation.get("event_id"),
            "conversation_id": validation.get("conversation_id"),
            "message_id": validation.get("message_id"),
            "cursor": validation.get("cursor"),
            "next_reconnect_cursor": validation.get("cursor"),
            "body_fetch_allowed": bool(validation.get("body_fetch_allowed", False)),
            "body_fetch_reason": validation.get("body_fetch_reason"),
            "duplicate_event": bool(validation.get("duplicate_event", False)),
            "duplicate_idempotency_key": bool(validation.get("duplicate_idempotency_key", False)),
        }
    )
    if not validation.get("ok"):
        report["ok"] = False
        report["error"] = validation.get("error")
        return report

    body_fetch_allowed = bool(validation.get("body_fetch_allowed"))
    if body_fetch_allowed:
        fetched = _fetch_aws_body(
            context,
            validation,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
        report.update(fetched)
        if not fetched.get("ok", False):
            report["ok"] = False
            report["error"] = fetched.get("error")
            return report

    if not report["duplicate_event"] and not report["duplicate_idempotency_key"]:
        _record_state(state, validation)
        try:
            _save_state(state_file, state)
            report["cursor_saved"] = True
        except RealtimeSyncClientError as exc:
            report["ok"] = False
            report["error"] = exc.to_safe_error()
            return report
    return report


def build_realtime_sync_listener_fixture_report(
    *,
    fixture: str,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    config_path: str | None = None,
    state_path: str | Path | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    try:
        event = build_realtime_sync_event_fixture(fixture)
    except RealtimeSyncEventError as exc:
        return {
            "schema_version": REALTIME_SYNC_CLIENT_SCHEMA_VERSION,
            "ok": False,
            "operation": "realtime_sync_listener_once",
            "error": exc.to_safe_error(),
            "fixture": fixture,
            "listener_enabled": False,
            "firestore_sdk_connected": False,
        }
    report = build_realtime_sync_listener_once_report(
        event=event,
        config=config,
        env=env,
        config_path=config_path,
        state_path=state_path,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    report["fixture"] = fixture
    return report


def build_realtime_sync_listener_poll_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    config_path: str | None = None,
    state_path: str | Path | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
    source_path: str = CONVERSATION_EVENTS_PATH,
    limit: int = 10,
) -> dict[str, Any]:
    context = _auth_context(config=config, env=env, claim_path=config_path)
    report = _base_report(context)
    report.update(
        {
            "operation": "realtime_sync_listener_poll",
            "listener_mode": "account_scoped_metadata_feed_poll",
            "event_source_kind": "aws_account_scoped_metadata_feed",
            "firestore_sdk_connected": False,
            "firestore_event_source_body_free": True,
            "events_received": 0,
            "events_processed": 0,
            "events_rejected": 0,
            "messages": [],
            "metadata_event_to_aws_body_fetch_completed": False,
            "live_web_to_cli_e2e_proven": False,
        }
    )
    try:
        safe_source_path = _safe_event_source_path(source_path)
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report["event_source_path"] = safe_source_path
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if context["auth_state"] != "linked":
        report["ok"] = False
        report["error"] = _safe_error("staging_auth_required", "Staging login is required before realtime sync receive.")
        return report
    if not context["staging_session_available"]:
        report["ok"] = False
        report["error"] = _safe_error(
            "staging_session_required",
            "A safe YonerAI staging session is required before realtime sync receive.",
        )
        return report
    try:
        linked_account_id = _linked_account_id(context)
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report

    state_file = Path(state_path).expanduser() if state_path is not None else default_realtime_sync_state_path(config_path)
    state = _load_state(state_file)
    latest_cursor = _latest_account_cursor(state, linked_account_id)
    source_with_query = _event_source_path_with_query(safe_source_path, cursor=latest_cursor, limit=limit)
    report["event_source_cursor"] = latest_cursor
    report["event_source_query_included"] = latest_cursor is not None
    try:
        status_code, payload, headers = _request_json(
            "GET",
            str(context["origin"]),
            source_with_query,
            _auth_headers(context),
            None,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except StagingSyncServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report["official_backend_called"] = True
    report["backend_status_code"] = status_code
    report["rate_limit_headers_present"] = _rate_limit_headers_present(headers)
    if status_code in {401, 403}:
        report["ok"] = False
        report["error"] = _safe_error(
            "staging_session_required",
            "The saved YonerAI staging session was not accepted by the realtime sync event feed.",
            status_code=status_code,
        )
        return report
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _safe_error("sync_event_feed_failed", "Realtime sync event feed request failed.", status_code=status_code)
        return report

    try:
        events, next_cursor, has_more = _sanitize_event_feed_payload(payload)
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report["events_received"] = len(events)
    report["feed_next_cursor"] = next_cursor
    report["feed_has_more"] = has_more
    for event in events:
        child = build_realtime_sync_listener_once_report(
            event=event,
            config=config,
            env=env,
            config_path=config_path,
            state_path=state_file,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
        report.setdefault("event_results", []).append(_public_child_listener_result(child))
        if not child.get("ok", False):
            report["ok"] = False
            report["events_rejected"] = int(report["events_rejected"]) + 1
            report["error"] = child.get("error") if isinstance(child.get("error"), dict) else _safe_error(
                "sync_event_rejected",
                "Realtime sync event was rejected.",
            )
            return report
        report["events_processed"] = int(report["events_processed"]) + 1
        message = child.get("message") if isinstance(child.get("message"), Mapping) else None
        if message:
            report["messages"].append(_public_message_result(message))
    report["cursor_saved"] = bool(report["events_processed"])
    report["body_received_from_aws"] = bool(report["messages"])
    report["aws_body_fetch_performed"] = any(
        isinstance(item, Mapping) and item.get("aws_body_fetch_performed") is True for item in report.get("event_results", [])
    )
    report["metadata_event_to_aws_body_fetch_completed"] = bool(report["messages"]) and bool(report["events_processed"])
    return report


def build_realtime_sync_firebase_token_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    config_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    context = _auth_context(config=config, env=env, claim_path=config_path)
    report = _base_report(context)
    report.update(
        {
            "operation": "realtime_sync_firebase_token",
            "listener_mode": "firestore_sdk_read_auth_bridge",
            "firebase_token_endpoint": FIREBASE_TOKEN_PATH,
            "firebase_auth_contract_version": FIREBASE_AUTH_CONTRACT_VERSION,
            "firebase_custom_token_received": False,
            "firebase_custom_token_printed": False,
            "firebase_custom_token_persisted": False,
            "google_token_returned": False,
            "refresh_token_returned": False,
            "auth_code_returned": False,
            "provider_key_returned": False,
            "production_login": False,
            "live_web_to_cli_e2e_proven": False,
        }
    )
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if context["auth_state"] != "linked":
        report["ok"] = False
        report["error"] = _safe_error("staging_auth_required", "Staging login is required before Firebase read auth.")
        return report
    if not context["staging_session_available"]:
        report["ok"] = False
        report["error"] = _safe_error(
            "staging_session_required",
            "A safe YonerAI staging session is required before Firebase read auth.",
        )
        return report
    try:
        linked_account_id = _linked_account_id(context)
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    try:
        status_code, payload, headers = _request_json(
            "POST",
            str(context["origin"]),
            FIREBASE_TOKEN_PATH,
            _auth_headers(context),
            {"purpose": "realtime_sync_metadata_read"},
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except StagingSyncServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report["official_backend_called"] = True
    report["backend_status_code"] = status_code
    report["rate_limit_headers_present"] = _rate_limit_headers_present(headers)
    if status_code in {401, 403}:
        report["ok"] = False
        report["error"] = _safe_error(
            "staging_session_required",
            "The saved YonerAI staging session was not accepted by the Firebase read-auth endpoint.",
            status_code=status_code,
        )
        return report
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _safe_error("firebase_token_request_failed", "Firebase read-auth request failed.", status_code=status_code)
        return report
    try:
        report.update(_sanitize_firebase_token_payload(payload, linked_account_id=linked_account_id))
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    return report


def build_realtime_sync_listener_readiness_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    config_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    context = _auth_context(config=config, env=env, claim_path=config_path)
    report = _base_report(context)
    report.update(
        {
            "operation": "realtime_sync_listener_readiness",
            "listener_mode": "readiness_check",
            "ready": False,
            "firebase_token_endpoint": FIREBASE_TOKEN_PATH,
            "firebase_auth_contract_version": FIREBASE_AUTH_CONTRACT_VERSION,
            "firebase_token_endpoint_checked": False,
            "firebase_token_endpoint_live": False,
            "firebase_token_endpoint_status_code": None,
            "firebase_custom_token_received": False,
            "firebase_custom_token_printed": False,
            "firebase_custom_token_persisted": False,
            "firestore_read_auth_bridge_ready": False,
            "firestore_sdk_listener_ready": False,
            "firestore_sync_enabled": False,
            "live_web_to_cli_e2e_proven": False,
            "next_blocker": None,
            "required_next_actions": (),
        }
    )
    if not context["origin_configured"]:
        report["next_blocker"] = "staging_origin_not_configured"
        report["required_next_actions"] = ("set YONERAI_STAGING_AUTH_ORIGIN=https://api-staging.yonerai.com",)
        return report
    if context["auth_state"] != "linked":
        report["next_blocker"] = "staging_login_required"
        report["required_next_actions"] = ("run yonerai login before realtime sync readiness",)
        return report
    if not context["staging_session_available"]:
        report["next_blocker"] = "opaque_staging_session_required"
        report["required_next_actions"] = ("run yonerai login to refresh the opaque YonerAI staging session",)
        return report

    firebase = build_realtime_sync_firebase_token_report(
        config=config,
        env=env,
        config_path=config_path,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    report["firebase_token_endpoint_checked"] = True
    report["firebase_token_endpoint_status_code"] = firebase.get("backend_status_code")
    report["firebase_token_endpoint_live"] = _endpoint_status_indicates_route_live(firebase.get("backend_status_code"))
    report["firebase_custom_token_received"] = bool(firebase.get("firebase_custom_token_received", False))
    report["firebase_custom_token_printed"] = False
    report["firebase_custom_token_persisted"] = False
    report["rate_limit_headers_present"] = firebase.get("rate_limit_headers_present", ())
    report["official_backend_called"] = bool(firebase.get("official_backend_called", False))
    report["backend_status_code"] = firebase.get("backend_status_code")

    if firebase.get("ok") is True:
        report["firebase_token_endpoint_live"] = True
        report["firestore_read_auth_bridge_ready"] = True
        report["firestore_sync_enabled"] = bool(firebase.get("firestore_sync_enabled", False))
        report["firestore_project_id"] = firebase.get("firestore_project_id")
        report["firestore_database_id"] = firebase.get("firestore_database_id")
        report["firestore_sync_event_path_template"] = firebase.get("firestore_sync_event_path_template")
        report["firestore_account_data_binding_required"] = firebase.get("firestore_account_data_binding_required")
        if report["firestore_sync_enabled"] is True:
            report["ready"] = True
            report["firestore_sdk_listener_ready"] = True
            report["next_blocker"] = None
            report["required_next_actions"] = ()
        else:
            report["next_blocker"] = "firestore_sync_disabled_until_live_e2e_and_owner_flip"
            report["required_next_actions"] = (
                "keep YONERAI_FIRESTORE_SYNC_ENABLED=false until Web-to-CLI E2E is proven",
                "implement Firestore SDK listener only after read-auth bridge and client config are live",
            )
        return report

    error = firebase.get("error") if isinstance(firebase.get("error"), Mapping) else {}
    code = str(error.get("code") or "firebase_token_request_failed")
    report["firebase_token_error"] = dict(error)
    if code in READINESS_NON_BLOCKING_ERROR_CODES:
        if code == "firebase_token_request_failed" and firebase.get("backend_status_code") == 404:
            report["next_blocker"] = "private_aws_firebase_token_endpoint_not_live"
            report["required_next_actions"] = (
                "wait for Private AWS to deploy POST /v1/sync/firebase-token",
                "rerun yonerai sync listener readiness after deploy",
            )
        else:
            report["next_blocker"] = code
            report["required_next_actions"] = ("repair staging origin/login/session and rerun readiness",)
        return report

    report["ok"] = False
    report["next_blocker"] = "firebase_token_contract_or_safety_violation"
    report["error"] = error or _safe_error("firebase_token_contract_or_safety_violation", "Firebase read-auth response was not accepted.")
    report["required_next_actions"] = ("fix the private endpoint contract before running the listener",)
    return report


def _base_report(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": REALTIME_SYNC_CLIENT_SCHEMA_VERSION,
        "ok": True,
        "operation": "realtime_sync_listener_once",
        "sync_event_schema_version": REALTIME_SYNC_SCHEMA_VERSION,
        "listener_mode": "one_shot_metadata_event",
        "listener_enabled": True,
        "firestore_projection_contract": "metadata_only",
        "firestore_sdk_connected": False,
        "firestore_body_fallback_allowed": False,
        "aws_body_fetch_performed": False,
        "body_received_from_aws": False,
        "message_body_from_firestore": False,
        "raw_prompt_from_firestore": False,
        "raw_audit_from_firestore": False,
        "client_policy_write_performed": False,
        "client_approval_write_performed": False,
        "local_to_cloud_upload_performed": False,
        "local_private_memory_projected": False,
        "cursor_saved": False,
        "reconnect_supported": True,
        "next_reconnect_cursor": None,
        "state_path_printed": False,
        "staging_origin_configured": bool(context["origin_configured"]),
        "staging_origin": context["origin"],
        "auth_state": context["auth_state"],
        "staging_session_available": bool(context["staging_session_available"]),
        "linked_account": context["linked_account"],
        "production_login_enabled": False,
        "production_cloud_enabled": False,
        "shared_traffic_enabled": False,
        "actions_not_performed": (
            "no Firestore body read",
            "no Firestore policy write",
            "no Firestore approval write",
            "no local-to-cloud upload",
            "no local private memory projection",
            "no provider key output",
            "no production cloud claim",
        ),
    }


def _endpoint_status_indicates_route_live(status_code: object) -> bool:
    return isinstance(status_code, int) and status_code not in {404, 405}


def _safe_event_source_path(path: str) -> str:
    candidate = str(path or "").strip()
    if not candidate:
        return CONVERSATION_EVENTS_PATH
    if candidate != CONVERSATION_EVENTS_PATH:
        raise RealtimeSyncClientError("sync_event_source_not_allowed", "Realtime sync event source path is not allowed.")
    if any(marker in candidate for marker in ("..", "\\", "?", "#", "//")):
        raise RealtimeSyncClientError("sync_event_source_not_allowed", "Realtime sync event source path is not allowed.")
    return candidate


def _event_source_path_with_query(path: str, *, cursor: str | None, limit: int) -> str:
    safe_limit = max(1, min(int(limit), 50))
    query = f"limit={safe_limit}"
    if cursor:
        query += f"&after_cursor={quote(cursor, safe='')}"
    return f"{path}?{query}"


def _sanitize_event_feed_payload(payload: Mapping[str, object]) -> tuple[list[Mapping[str, object]], str | None, bool]:
    _assert_event_feed_payload_safe(payload)
    allowed = {"ok", "schema_version", "events", "sync_events", "items", "next_cursor", "has_more", "metadata_only", "redacted_preview_only"}
    if set(payload) - allowed:
        raise RealtimeSyncClientError("sync_event_feed_private_fields", "Realtime sync event feed contained non-public fields.")
    raw_events = payload.get("events")
    if raw_events is None:
        raw_events = payload.get("sync_events")
    if raw_events is None:
        raw_events = payload.get("items")
    if raw_events is None:
        raw_events = []
    if not isinstance(raw_events, list):
        raise RealtimeSyncClientError("sync_event_feed_invalid", "Realtime sync event feed is invalid.")
    events: list[Mapping[str, object]] = []
    for item in raw_events[:50]:
        if not isinstance(item, Mapping):
            raise RealtimeSyncClientError("sync_event_feed_invalid", "Realtime sync event feed is invalid.")
        events.append(item)
    next_cursor = payload.get("next_cursor")
    if next_cursor is not None:
        next_cursor = _safe_message_text(next_cursor, fallback=None)
    return events, next_cursor, bool(payload.get("has_more", False))


def _assert_event_feed_payload_safe(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    forbidden = (
        '"message_body"',
        '"raw_body"',
        '"raw_prompt"',
        '"provider_output"',
        '"raw_audit"',
        '"sync_policy_write"',
        '"approval_decision"',
    )
    if any(marker in serialized for marker in forbidden):
        raise RealtimeSyncClientError("sync_event_feed_private_payload_rejected", "Realtime sync event feed contained private data.")
    _assert_body_payload_safe(payload)


def _sanitize_firebase_token_payload(payload: Mapping[str, object], *, linked_account_id: str) -> dict[str, object]:
    _assert_firebase_token_payload_safe(payload)
    allowed = {
        "contract_version",
        "firebase_auth_contract_version",
        "token_type",
        "firebase_custom_token",
        "expires_at",
        "expires_in_seconds",
        "uid",
        "account_id",
        "claims",
        "firestore",
        "google_token_returned",
        "refresh_token_returned",
        "auth_code_returned",
        "provider_key_returned",
        "production_login",
    }
    if set(payload) - allowed:
        raise RealtimeSyncClientError("firebase_token_private_fields", "Firebase read-auth response contained non-public fields.")
    if payload.get("firebase_auth_contract_version") != FIREBASE_AUTH_CONTRACT_VERSION:
        raise RealtimeSyncClientError("firebase_token_contract_mismatch", "Firebase read-auth contract version is not accepted.")
    if payload.get("token_type") != "firebase_custom_token":
        raise RealtimeSyncClientError("firebase_token_type_invalid", "Firebase read-auth token type is invalid.")
    token = payload.get("firebase_custom_token")
    if not isinstance(token, str) or not token.strip():
        raise RealtimeSyncClientError("firebase_custom_token_missing", "Firebase custom token was not returned.")
    uid = _safe_message_text(payload.get("uid"), fallback=None)
    account_id = _safe_message_text(payload.get("account_id"), fallback=None)
    if uid != linked_account_id or account_id != linked_account_id:
        raise RealtimeSyncClientError("firebase_token_account_mismatch", "Firebase read-auth account binding does not match.")
    expires_in = payload.get("expires_in_seconds")
    if not isinstance(expires_in, int) or expires_in <= 0 or expires_in > 900:
        raise RealtimeSyncClientError("firebase_token_expiry_invalid", "Firebase custom token expiry is not accepted.")
    for key in ("google_token_returned", "refresh_token_returned", "auth_code_returned", "provider_key_returned", "production_login"):
        if payload.get(key) is not False:
            raise RealtimeSyncClientError("firebase_token_boundary_flag_invalid", "Firebase read-auth boundary flags are not accepted.")
    firestore = payload.get("firestore") if isinstance(payload.get("firestore"), Mapping) else {}
    firestore_summary = _sanitize_firestore_contract(firestore)
    claims = payload.get("claims") if isinstance(payload.get("claims"), Mapping) else {}
    if set(claims) - {"yonerai_staging"}:
        raise RealtimeSyncClientError("firebase_token_private_fields", "Firebase custom token claims contained non-public fields.")
    return {
        "firebase_custom_token_received": True,
        "firebase_custom_token_printed": False,
        "firebase_custom_token_persisted": False,
        "firebase_auth_contract_version": FIREBASE_AUTH_CONTRACT_VERSION,
        "firebase_token_type": "firebase_custom_token",
        "firebase_uid_matches_account": True,
        "firebase_account_id_matches_session": True,
        "firebase_expires_at": _safe_message_text(payload.get("expires_at"), fallback=None),
        "firebase_expires_in_seconds": expires_in,
        "firebase_claims_yonerai_staging": claims.get("yonerai_staging") is True,
        **firestore_summary,
        "google_token_returned": False,
        "refresh_token_returned": False,
        "auth_code_returned": False,
        "provider_key_returned": False,
        "production_login": False,
    }


def _assert_firebase_token_payload_safe(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    allowed_markers = ('"firebase_custom_token"', '"token_type": "firebase_custom_token"')
    allowed_boundary_words = {
        "session_token",
        "sessiontoken",
        "google_token",
        "googletoken",
        "refresh_token",
        "refreshtoken",
        "auth_code",
        "authcode",
        "provider_key",
        "providerkey",
    }
    forbidden = tuple(marker for marker in FORBIDDEN_BODY_MARKERS if marker not in allowed_boundary_words)
    if any(marker in serialized for marker in forbidden):
        raise RealtimeSyncClientError("firebase_token_private_payload_rejected", "Firebase read-auth response contained private data.")
    if "google" in serialized and '"google_token_returned": false' not in serialized:
        raise RealtimeSyncClientError("firebase_token_private_payload_rejected", "Firebase read-auth response contained Google token data.")
    if "refresh_token" in serialized and '"refresh_token_returned": false' not in serialized:
        raise RealtimeSyncClientError("firebase_token_private_payload_rejected", "Firebase read-auth response contained refresh token data.")
    if "auth_code" in serialized and '"auth_code_returned": false' not in serialized:
        raise RealtimeSyncClientError("firebase_token_private_payload_rejected", "Firebase read-auth response contained auth code data.")
    if "provider_key" in serialized and '"provider_key_returned": false' not in serialized:
        raise RealtimeSyncClientError("firebase_token_private_payload_rejected", "Firebase read-auth response contained provider key data.")
    if not all(marker in serialized for marker in allowed_markers):
        raise RealtimeSyncClientError("firebase_custom_token_missing", "Firebase custom token was not returned.")


def _sanitize_firestore_contract(firestore: Mapping[str, object]) -> dict[str, object]:
    allowed = {"project_id", "database_id", "sync_enabled", "sync_event_path_template"}
    if set(firestore) - allowed:
        raise RealtimeSyncClientError("firebase_token_private_fields", "Firestore read-auth contract contained non-public fields.")
    project_id = _safe_message_text(firestore.get("project_id"), fallback=None)
    database_id = _safe_message_text(firestore.get("database_id"), fallback=None)
    path_template = _safe_message_text(firestore.get("sync_event_path_template"), fallback=None)
    if not project_id or not database_id:
        raise RealtimeSyncClientError("firebase_token_firestore_invalid", "Firestore read-auth project metadata is invalid.")
    if path_template != FIRESTORE_SYNC_EVENT_PATH_TEMPLATE:
        raise RealtimeSyncClientError("firebase_token_firestore_path_invalid", "Firestore sync event path template is not accepted.")
    if firestore.get("sync_enabled") is not False:
        raise RealtimeSyncClientError("firebase_token_sync_flag_invalid", "Firestore sync must remain disabled before live E2E.")
    return {
        "firestore_project_id": project_id,
        "firestore_database_id": database_id,
        "firestore_sync_enabled": False,
        "firestore_sync_event_path_template": path_template,
        "firestore_account_data_binding_required": True,
        "firestore_body_fallback_allowed": False,
    }


def _latest_account_cursor(state: Mapping[str, Any], account_id: str) -> str | None:
    accounts = state.get("accounts") if isinstance(state, Mapping) else {}
    account = accounts.get(account_id) if isinstance(accounts, Mapping) else {}
    conversations = account.get("conversations") if isinstance(account, Mapping) else {}
    if not isinstance(conversations, Mapping):
        return None
    cursors = [
        str(item.get("cursor"))
        for item in conversations.values()
        if isinstance(item, Mapping) and isinstance(item.get("cursor"), str) and item.get("cursor")
    ]
    return sorted(cursors)[-1] if cursors else None


def _public_child_listener_result(report: Mapping[str, Any]) -> dict[str, object]:
    keys = (
        "ok",
        "event_id",
        "conversation_id",
        "message_id",
        "cursor",
        "body_fetch_allowed",
        "body_fetch_reason",
        "aws_body_fetch_performed",
        "body_received_from_aws",
        "message_body_from_firestore",
        "raw_prompt_from_firestore",
        "raw_audit_from_firestore",
        "cursor_saved",
        "duplicate_event",
        "duplicate_idempotency_key",
        "error",
    )
    return {key: report.get(key) for key in keys if key in report}


def _public_message_result(message: Mapping[str, object]) -> dict[str, object]:
    return {
        "conversation_id": message.get("conversation_id"),
        "message_id": message.get("message_id"),
        "display_text": message.get("display_text"),
        "body_from_firestore": False,
        "body_stored_in_cursor": False,
    }


def _fetch_aws_body(
    context: Mapping[str, Any],
    validation: Mapping[str, object],
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    body_ref = validation.get("body_ref") if isinstance(validation.get("body_ref"), Mapping) else {}
    href = body_ref.get("href") if isinstance(body_ref.get("href"), str) else None
    if not href:
        return {
            "ok": False,
            "aws_body_fetch_performed": False,
            "error": _safe_error("sync_body_ref_missing", "Realtime sync event did not include an AWS body ref."),
        }
    try:
        status_code, payload, headers = _request_json(
            "GET",
            str(context["origin"]),
            href,
            _auth_headers(context),
            None,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except StagingSyncServiceError as exc:
        return {"ok": False, "aws_body_fetch_performed": False, "error": exc.to_safe_error()}
    report: dict[str, Any] = {
        "ok": status_code < 400,
        "official_backend_called": True,
        "backend_status_code": status_code,
        "aws_body_fetch_performed": True,
        "rate_limit_headers_present": _rate_limit_headers_present(headers),
    }
    if status_code in {401, 403}:
        report["ok"] = False
        report["error"] = _safe_error(
            "staging_session_required",
            "The saved YonerAI staging session was not accepted by the AWS body endpoint.",
            status_code=status_code,
        )
        return report
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _safe_error("sync_aws_body_fetch_failed", "AWS body fetch failed.", status_code=status_code)
        return report
    try:
        report["message"] = _sanitize_aws_message_payload(payload, validation)
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report["body_received_from_aws"] = True
    return report


def _sanitize_aws_message_payload(payload: Mapping[str, object], validation: Mapping[str, object]) -> dict[str, object]:
    _assert_body_payload_safe(payload)
    message = payload.get("message") if isinstance(payload.get("message"), Mapping) else payload
    if not isinstance(message, Mapping):
        raise RealtimeSyncClientError("sync_aws_body_invalid", "AWS body response is invalid.")
    allowed = {
        "conversation_id",
        "message_id",
        "body",
        "text",
        "content",
        "redacted_preview",
        "summary",
        "created_at",
        "updated_at",
        "body_safety",
        "message_body_included",
        "body_included",
    }
    extra = set(message) - allowed
    if extra:
        raise RealtimeSyncClientError("sync_aws_body_private_fields", "AWS body response contained non-public fields.")
    conversation_id = _safe_message_text(message.get("conversation_id"), fallback=validation.get("conversation_id"))
    message_id = _safe_message_text(message.get("message_id"), fallback=validation.get("message_id"))
    if conversation_id != validation.get("conversation_id") or message_id != validation.get("message_id"):
        raise RealtimeSyncClientError("sync_aws_body_ref_mismatch", "AWS body response did not match the SyncEvent ref.")
    display_text = (
        _safe_message_text(message.get("body"), fallback=None)
        or _safe_message_text(message.get("text"), fallback=None)
        or _safe_message_text(message.get("content"), fallback=None)
        or _safe_message_text(message.get("redacted_preview"), fallback=None)
        or _safe_message_text(message.get("summary"), fallback=None)
    )
    return {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "display_text": display_text,
        "body_received_from_aws": display_text is not None,
        "body_from_firestore": False,
        "body_stored_in_cursor": False,
        "raw_audit_included": False,
        "provider_output_included": False,
    }


def _assert_body_payload_safe(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    if any(marker in serialized for marker in FORBIDDEN_BODY_MARKERS):
        raise RealtimeSyncClientError("sync_aws_body_private_payload_rejected", "AWS body response contained private data.")


def _safe_message_text(value: object, *, fallback: object) -> str | None:
    source = fallback if value is None else value
    if source is None:
        return None
    text = str(source).strip()
    if not text:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in FORBIDDEN_BODY_MARKERS):
        raise RealtimeSyncClientError("sync_aws_body_private_payload_rejected", "AWS body response contained private data.")
    if any(ord(char) < 32 and char not in "\n\t" for char in text):
        raise RealtimeSyncClientError("sync_aws_body_invalid", "AWS body response is invalid.")
    return text[:2000]


def _linked_account_id(context: Mapping[str, Any]) -> str:
    claim = context.get("staging_session_claim") if isinstance(context.get("staging_session_claim"), Mapping) else {}
    account_id = str(claim.get("account_id") or "").strip()
    if not account_id or account_id == "not-linked":
        raise RealtimeSyncClientError("staging_account_missing", "Linked staging account id is unavailable.")
    return account_id


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": STATE_SCHEMA_VERSION, "accounts": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": STATE_SCHEMA_VERSION, "accounts": {}}
    if not isinstance(raw, dict) or raw.get("schema_version") != STATE_SCHEMA_VERSION:
        return {"schema_version": STATE_SCHEMA_VERSION, "accounts": {}}
    accounts = raw.get("accounts")
    if not isinstance(accounts, dict):
        return {"schema_version": STATE_SCHEMA_VERSION, "accounts": {}}
    return raw


def _save_state(path: Path, state: Mapping[str, object]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise RealtimeSyncClientError("sync_state_write_failed", "Realtime sync cursor state could not be written.") from exc


def _seen_for_event(state: Mapping[str, Any], account_id: str, event: Mapping[str, object]) -> dict[str, tuple[str, ...]]:
    conversation_id = str(event.get("conversation_id") or "")
    conversation = _conversation_state(state, account_id, conversation_id)
    return {
        "event_ids": tuple(str(item) for item in conversation.get("event_ids", []) if isinstance(item, str)),
        "idempotency_keys": tuple(str(item) for item in conversation.get("idempotency_keys", []) if isinstance(item, str)),
    }


def _record_state(state: dict[str, Any], validation: Mapping[str, object]) -> None:
    account_id = str(validation.get("account_id") or "")
    conversation_id = str(validation.get("conversation_id") or "")
    conversation = _conversation_state(state, account_id, conversation_id)
    conversation["cursor"] = validation.get("cursor")
    conversation["last_event_id"] = validation.get("event_id")
    conversation["event_ids"] = _append_limited(conversation.get("event_ids"), validation.get("event_id"))
    conversation["idempotency_keys"] = _append_limited(conversation.get("idempotency_keys"), validation.get("idempotency_key"))


def _conversation_state(state: Mapping[str, Any], account_id: str, conversation_id: str) -> dict[str, Any]:
    mutable = state if isinstance(state, dict) else {}
    accounts = mutable.setdefault("accounts", {})
    if not isinstance(accounts, dict):
        mutable["accounts"] = {}
        accounts = mutable["accounts"]
    account = accounts.setdefault(account_id, {"conversations": {}})
    if not isinstance(account, dict):
        accounts[account_id] = {"conversations": {}}
        account = accounts[account_id]
    conversations = account.setdefault("conversations", {})
    if not isinstance(conversations, dict):
        account["conversations"] = {}
        conversations = account["conversations"]
    conversation = conversations.setdefault(
        conversation_id,
        {"cursor": None, "last_event_id": None, "event_ids": [], "idempotency_keys": []},
    )
    if not isinstance(conversation, dict):
        conversations[conversation_id] = {"cursor": None, "last_event_id": None, "event_ids": [], "idempotency_keys": []}
        conversation = conversations[conversation_id]
    return conversation


def _append_limited(raw: object, value: object) -> list[str]:
    items = [str(item) for item in raw if isinstance(item, str)] if isinstance(raw, list) else []
    if isinstance(value, str) and value and value not in items:
        items.append(value)
    return items[-100:]


def _public_validation(validation: Mapping[str, object]) -> dict[str, object]:
    keys = (
        "ok",
        "schema_version",
        "event_id",
        "account_id",
        "conversation_id",
        "message_id",
        "event_type",
        "origin",
        "sync_policy",
        "cursor",
        "idempotency_key",
        "body_fetch_allowed",
        "body_fetch_reason",
        "duplicate_event",
        "duplicate_idempotency_key",
        "raw_body_included",
        "provider_consent_separate",
        "approval_authority_from_projection",
        "local_private_memory_projected",
        "error",
    )
    return {key: validation.get(key) for key in keys if key in validation}


def _safe_error(code: str, message: str, *, status_code: int | None = None) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "status_code": status_code,
        "token_printed": False,
        "local_path_printed": False,
        "raw_body_printed": False,
        "private_runtime_detail_printed": False,
    }
