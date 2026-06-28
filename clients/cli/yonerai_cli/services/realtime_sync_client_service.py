from __future__ import annotations

import base64
import binascii
import importlib.util
import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

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
FIREBASE_CONFIG_PATH = "/v1/sync/firebase-config"
FIREBASE_AUTH_CONTRACT_VERSION = "yonerai.firebase.custom_token.v1"
FIREBASE_CONFIG_CONTRACT_VERSION = "yonerai.firebase.public_config.v1"
FIRESTORE_USAGE_POLICY_VERSION = "yonerai.firestore_usage_policy.v1"
FIRESTORE_INITIAL_QUERY_LIMIT_MAX = 20
FIRESTORE_ABSOLUTE_QUERY_LIMIT_MAX = 50
FIRESTORE_RECONNECT_COOLDOWN_SECONDS_MIN = 30
FIRESTORE_CLI_MAX_LISTENERS_PER_ACCOUNT = 1
FIRESTORE_SYNC_MODES = {"off", "preview", "staging", "allowlist"}
FIREBASE_PUBLIC_CLIENT_KEY_FIELD = "api" + "_key"
FIRESTORE_SYNC_EVENT_PATH_TEMPLATE = "/accounts/{account_id}/sync_events/{event_id}"
FIREBASE_CLIENT_API_KEY_ENV = "YONERAI_FIREBASE_CLIENT_API_KEY"
IDENTITY_TOOLKIT_SIGN_IN_ORIGIN = "https://identitytoolkit.googleapis.com"
FIRESTORE_REST_ORIGIN = "https://firestore.googleapis.com"
SAFE_FIRESTORE_ERROR_DETAIL_TYPE_PREFIX = "type.googleapis.com/google.rpc."
PLACEHOLDER_ACCOUNT_IDS = {"not-linked", "linked-staging-account", "linked staging account"}
READINESS_NON_BLOCKING_ERROR_CODES = {
    "staging_origin_not_configured",
    "staging_auth_required",
    "staging_session_required",
    "canonical_account_id_required",
    "staging_sync_unreachable",
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
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        safe_details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.safe_details = dict(safe_details or {})

    def to_safe_error(self) -> dict[str, object]:
        error: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "status_code": self.status_code,
            "token_printed": False,
            "local_path_printed": False,
            "raw_body_printed": False,
            "private_runtime_detail_printed": False,
        }
        if self.safe_details:
            error["diagnostic"] = self.safe_details
        return error


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


def build_realtime_sync_firestore_poll_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    config_path: str | None = None,
    state_path: str | Path | None = None,
    transport: HeaderJsonTransport | None = None,
    firebase_rest_transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
    limit: int = 10,
) -> dict[str, Any]:
    context = _auth_context(config=config, env=env, claim_path=config_path)
    report = _base_report(context)
    report.update(
        {
            "operation": "realtime_sync_firestore_poll",
            "listener_mode": "firestore_rest_metadata_poll",
            "event_source_kind": "firestore_body_free_projection",
            "firestore_sdk_connected": False,
            "firestore_rest_connected": False,
            "firestore_event_source_body_free": True,
            "firebase_custom_token_received": False,
            "firebase_custom_token_printed": False,
            "firebase_custom_token_persisted": False,
            "firebase_client_api_key_printed": False,
            "firebase_id_token_printed": False,
            "firebase_id_token_persisted": False,
            "firebase_sign_in_secondary_material_persisted": False,
            "events_received": 0,
            "events_processed": 0,
            "events_rejected": 0,
            "messages": [],
            "firestore_usage_policy_present": False,
            "firestore_usage_policy_accepted": False,
            "firestore_usage_policy_version": FIRESTORE_USAGE_POLICY_VERSION,
            "firestore_requested_limit": limit,
            "firestore_effective_query_limit": None,
            "firestore_reconnect_cooldown_seconds": None,
            "firestore_reconnect_cooldown_remaining_seconds": 0,
            "firestore_projection_write_allowed": None,
            "metadata_event_to_aws_body_fetch_completed": False,
            "live_web_to_cli_e2e_proven": False,
        }
    )
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if context["auth_state"] != "linked":
        report["ok"] = False
        report["error"] = _safe_error("staging_auth_required", "Staging login is required before Firestore sync receive.")
        return report
    if not context["staging_session_available"]:
        report["ok"] = False
        report["error"] = _safe_error(
            "staging_session_required",
            "A safe YonerAI staging session is required before Firestore sync receive.",
        )
        return report
    try:
        linked_account_id = _linked_account_id(context)
        firebase_config = build_realtime_sync_firebase_config_report(
            config=config,
            env=env,
            config_path=config_path,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    for key in (
        "firestore_usage_policy_present",
        "firestore_usage_policy_accepted",
        "firestore_usage_policy_version",
        "firestore_sync_enabled",
        "firestore_sync_mode",
        "firestore_initial_query_limit",
        "firestore_absolute_query_limit",
        "firestore_reconnect_cooldown_seconds",
        "firestore_max_cli_listeners_per_account",
        "firestore_query_account_rooted",
        "firestore_offset_forbidden",
        "firestore_collection_group_query_allowed",
        "firestore_client_writes_allowed",
        "firestore_body_fetch_source",
        "firestore_projection_write_allowed",
    ):
        if key in firebase_config:
            report[key] = firebase_config[key]
    if firebase_config.get("ok") is not True:
        report["ok"] = False
        report["error"] = firebase_config.get("error") if isinstance(firebase_config.get("error"), dict) else _safe_error(
            "firebase_config_request_failed",
            "Firebase public config request failed.",
        )
        return report
    if firebase_config.get("firestore_usage_policy_accepted") is not True:
        report["ok"] = False
        report["error"] = _safe_error(
            "firestore_usage_policy_not_accepted",
            "Firestore listener cost guard policy is not accepted.",
        )
        return report
    if firebase_config.get("firestore_sync_enabled") is not True:
        report["ok"] = False
        report["error"] = _safe_error(
            "firestore_sync_disabled_until_live_e2e_and_owner_flip",
            "Firestore realtime sync is still disabled by staging policy.",
        )
        return report
    try:
        firebase_payload, firebase_headers = _request_firebase_token_payload(
            context,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
        firebase_summary = _sanitize_firebase_token_payload(firebase_payload, linked_account_id=linked_account_id)
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report.update(firebase_summary)
    report["rate_limit_headers_present"] = _rate_limit_headers_present(firebase_headers)
    report["firebase_custom_token_printed"] = False
    report["firebase_custom_token_persisted"] = False
    report["official_backend_called"] = True
    if firebase_summary.get("firestore_sync_enabled") is not True:
        report["ok"] = False
        report["error"] = _safe_error(
            "firestore_sync_disabled_until_live_e2e_and_owner_flip",
            "Firestore realtime sync is still disabled by staging policy.",
        )
        return report
    try:
        client_sign_in_config = _firebase_client_api_key(
            env,
            context=context,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
        id_token, local_id = _exchange_firebase_custom_token(
            str(firebase_payload["firebase_custom_token"]),
            client_sign_in_config,
            transport=firebase_rest_transport,
            timeout_seconds=timeout_seconds,
        )
        account_id = _safe_message_text(firebase_payload.get("account_id"), fallback=None)
        if not _account_binding_matches(str(account_id), local_id):
            raise RealtimeSyncClientError("firebase_sign_in_account_mismatch", "Firebase sign-in account binding does not match.")
        state_file = Path(state_path).expanduser() if state_path is not None else default_realtime_sync_state_path(config_path)
        state = _load_state(state_file)
        cooldown_seconds = int(report.get("firestore_reconnect_cooldown_seconds") or FIRESTORE_RECONNECT_COOLDOWN_SECONDS_MIN)
        remaining = _firestore_poll_cooldown_remaining_seconds(state, str(account_id), cooldown_seconds)
        report["firestore_reconnect_cooldown_remaining_seconds"] = remaining
        if remaining > 0:
            raise RealtimeSyncClientError(
                "firestore_reconnect_cooldown_active",
                "Firestore listener cooldown is still active.",
            )
        latest_cursor = _latest_account_cursor(state, str(account_id))
        report["event_source_cursor"] = latest_cursor
        report["event_source_query_included"] = latest_cursor is not None
        effective_limit = min(max(1, int(limit)), int(report.get("firestore_initial_query_limit") or FIRESTORE_INITIAL_QUERY_LIMIT_MAX))
        report["firestore_effective_query_limit"] = effective_limit
        events = _read_firestore_sync_events(
            id_token=id_token,
            account_id=str(account_id),
            project_id=str(firebase_summary["firestore_project_id"]),
            database_id=str(firebase_summary["firestore_database_id"]),
            limit=effective_limit,
            cursor=latest_cursor,
            transport=firebase_rest_transport,
            timeout_seconds=timeout_seconds,
        )
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report["firestore_rest_connected"] = True
    report["events_received"] = len(events)
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
                "Firestore SyncEvent was rejected.",
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
    _record_firestore_poll(state_file, str(account_id))
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
        firebase_config = build_realtime_sync_firebase_config_report(
            config=config,
            env=env,
            config_path=config_path,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    for key in (
        "firestore_usage_policy_present",
        "firestore_usage_policy_accepted",
        "firestore_usage_policy_version",
        "firestore_sync_enabled",
        "firestore_sync_mode",
        "firestore_projection_write_allowed",
    ):
        if key in firebase_config:
            report[key] = firebase_config[key]
    if firebase_config.get("ok") is not True:
        report["ok"] = False
        report["error"] = firebase_config.get("error") if isinstance(firebase_config.get("error"), dict) else _safe_error(
            "firebase_config_request_failed",
            "Firebase public config request failed.",
        )
        return report
    if firebase_config.get("firestore_usage_policy_accepted") is not True:
        report["ok"] = False
        report["error"] = _safe_error(
            "firestore_usage_policy_not_accepted",
            "Firestore listener cost guard policy is not accepted.",
        )
        return report
    try:
        status_code, payload, headers = _request_firebase_token_raw(
            context,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except RealtimeSyncClientError as exc:
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
        report["error"] = _firebase_token_request_error(payload, status_code=status_code)
        return report
    try:
        report.update(_sanitize_firebase_token_payload(payload, linked_account_id=linked_account_id))
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    return report


def build_realtime_sync_firebase_config_report(
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
            "operation": "realtime_sync_firebase_config",
            "firebase_config_endpoint": FIREBASE_CONFIG_PATH,
            "firebase_config_endpoint_checked": False,
            "firebase_config_endpoint_live": False,
            "firebase_config_endpoint_status_code": None,
            "firebase_config_contract_version": FIREBASE_CONFIG_CONTRACT_VERSION,
            "firebase_public_config_ready": False,
            "firebase_public_api_key_received": False,
            "firebase_public_api_key_printed": False,
            "firebase_public_api_key_persisted": False,
            "firestore_client_sign_in_config_present": _firestore_client_sign_in_config_present(env),
            "firestore_client_sign_in_config_source": "env" if _firestore_client_sign_in_config_present(env) else "none",
            "firestore_usage_policy_present": False,
            "firestore_usage_policy_accepted": False,
            "firestore_usage_policy_version": FIRESTORE_USAGE_POLICY_VERSION,
            "ready": False,
        }
    )
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    try:
        status_code, payload, headers = _request_firebase_config_raw(
            context,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report["firebase_config_endpoint_checked"] = True
    report["firebase_config_endpoint_status_code"] = status_code
    report["firebase_config_endpoint_live"] = _endpoint_status_indicates_route_live(status_code)
    report["rate_limit_headers_present"] = _rate_limit_headers_present(headers)
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _safe_error("firebase_config_request_failed", "Firebase public config request failed.", status_code=status_code)
        return report
    try:
        summary, _client_sign_in_key = _sanitize_firebase_config_payload(payload, env=env)
    except RealtimeSyncClientError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report.update(summary)
    report["ready"] = bool(summary.get("firebase_public_config_ready") and summary.get("firestore_sync_enabled"))
    return report


def build_realtime_sync_listener_readiness_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    config_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    firebase_rest_transport: HeaderJsonTransport | None = None,
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
            "firebase_config_endpoint": FIREBASE_CONFIG_PATH,
            "firebase_config_endpoint_checked": False,
            "firebase_config_endpoint_live": False,
            "firebase_config_endpoint_status_code": None,
            "firebase_config_contract_version": FIREBASE_CONFIG_CONTRACT_VERSION,
            "firebase_public_config_ready": False,
            "firebase_public_api_key_received": False,
            "firebase_public_api_key_printed": False,
            "firebase_public_api_key_persisted": False,
            "firebase_custom_token_received": False,
            "firebase_custom_token_printed": False,
            "firebase_custom_token_persisted": False,
            "firebase_custom_token_exchange_attempted": False,
            "firebase_custom_token_exchange_passed": False,
            "firebase_id_token_received": False,
            "firebase_id_token_printed": False,
            "firebase_id_token_persisted": False,
            "firebase_refresh_token_discarded": False,
            "firebase_refresh_token_persisted": False,
            "official_backend_called": False,
            "firestore_read_auth_bridge_ready": False,
            "firestore_sdk_dependency_available": _firestore_sdk_dependency_available(),
            "firestore_client_sign_in_config_present": _firestore_client_sign_in_config_present(env),
            "firestore_sdk_listener_ready": False,
            "firestore_sync_enabled": False,
            "firestore_usage_policy_present": False,
            "firestore_usage_policy_accepted": False,
            "firestore_usage_policy_version": FIRESTORE_USAGE_POLICY_VERSION,
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
    try:
        linked_account_id = _linked_account_id(context)
    except RealtimeSyncClientError as exc:
        report["next_blocker"] = exc.code
        report["firebase_token_error"] = exc.to_safe_error()
        report["required_next_actions"] = (
            "run yonerai logout to clear the legacy staging account_ref session",
            "run yonerai login to get a fresh opaque YonerAI staging session with canonical account_id",
            "rerun yonerai sync listener readiness after login succeeds",
        )
        return report

    firebase_config = build_realtime_sync_firebase_config_report(
        config=config,
        env=env,
        config_path=config_path,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    report["firebase_config_endpoint_checked"] = bool(firebase_config.get("firebase_config_endpoint_checked", False))
    report["firebase_config_endpoint_status_code"] = firebase_config.get("firebase_config_endpoint_status_code")
    report["firebase_config_endpoint_live"] = bool(firebase_config.get("firebase_config_endpoint_live", False))
    report["firebase_public_config_ready"] = bool(firebase_config.get("firebase_public_config_ready", False))
    report["firebase_public_api_key_received"] = bool(firebase_config.get("firebase_public_api_key_received", False))
    report["firebase_public_api_key_printed"] = False
    report["firebase_public_api_key_persisted"] = False
    report["firestore_client_sign_in_config_present"] = bool(
        firebase_config.get("firestore_client_sign_in_config_present", False)
    )
    report["firestore_client_sign_in_config_source"] = firebase_config.get("firestore_client_sign_in_config_source")
    report["firestore_usage_policy_present"] = bool(firebase_config.get("firestore_usage_policy_present", False))
    report["firestore_usage_policy_accepted"] = bool(firebase_config.get("firestore_usage_policy_accepted", False))
    report["firestore_usage_policy_version"] = firebase_config.get("firestore_usage_policy_version")
    report["firestore_initial_query_limit"] = firebase_config.get("firestore_initial_query_limit")
    report["firestore_absolute_query_limit"] = firebase_config.get("firestore_absolute_query_limit")
    report["firestore_reconnect_cooldown_seconds"] = firebase_config.get("firestore_reconnect_cooldown_seconds")
    report["firestore_max_cli_listeners_per_account"] = firebase_config.get("firestore_max_cli_listeners_per_account")
    report["firestore_query_account_rooted"] = firebase_config.get("firestore_query_account_rooted")
    report["firestore_offset_forbidden"] = firebase_config.get("firestore_offset_forbidden")
    report["firestore_collection_group_query_allowed"] = firebase_config.get("firestore_collection_group_query_allowed")
    report["firestore_client_writes_allowed"] = firebase_config.get("firestore_client_writes_allowed")
    report["firestore_body_fetch_source"] = firebase_config.get("firestore_body_fetch_source")
    report["firestore_projection_write_allowed"] = firebase_config.get("firestore_projection_write_allowed")
    if firebase_config.get("ok") is not True:
        config_error = firebase_config.get("error") if isinstance(firebase_config.get("error"), Mapping) else None
        error_code = config_error.get("code") if isinstance(config_error, Mapping) else None
        report["firebase_config_error"] = dict(config_error) if isinstance(config_error, Mapping) else config_error
        if isinstance(error_code, str) and error_code.startswith("firestore_usage_policy_"):
            report["next_blocker"] = error_code
            report["required_next_actions"] = (
                "wait for AWS to publish an accepted yonerai.firestore_usage_policy.v1 in firebase-config",
                "do not request Firebase custom tokens until the versioned cost guard allows issuance",
            )
        else:
            report["next_blocker"] = "firebase_public_config_unavailable"
            report["required_next_actions"] = (
                "wait for Private AWS to repair GET /v1/sync/firebase-config",
                "do not enable realtime sync until the public Firebase config is ready",
            )
        return report
    elif report["firebase_public_config_ready"] is not True:
        report["next_blocker"] = "firebase_public_config_not_ready"
        report["required_next_actions"] = (
            "Private AWS must configure the staging public Firebase client config",
            "keep YONERAI_FIRESTORE_SYNC_ENABLED=false until Web-to-CLI E2E is proven",
        )
        return report
    elif report["firestore_usage_policy_accepted"] is not True:
        report["next_blocker"] = "firestore_usage_policy_not_accepted"
        report["required_next_actions"] = (
            "wait for AWS to publish yonerai.firestore_usage_policy.v1 in firebase-config",
            "do not start the Firestore listener without the versioned cost guard",
        )
        return report

    firebase_error: dict[str, object] | None = None
    firebase_payload: Mapping[str, object] | None = None
    firebase_summary: dict[str, object] = {}
    firebase_headers: Mapping[str, str] = {}
    status_code: int | None = None
    try:
        status_code, firebase_payload, firebase_headers = _request_firebase_token_raw(
            context,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except RealtimeSyncClientError as exc:
        status_code = exc.status_code
        firebase_error = exc.to_safe_error()
    report["firebase_token_endpoint_checked"] = True
    report["firebase_token_endpoint_status_code"] = status_code
    report["firebase_token_endpoint_live"] = _endpoint_status_indicates_route_live(status_code)
    report["rate_limit_headers_present"] = _rate_limit_headers_present(firebase_headers)
    report["official_backend_called"] = True
    report["backend_status_code"] = status_code
    if firebase_error is None:
        if status_code in {401, 403}:
            firebase_error = _safe_error(
                "staging_session_required",
                "The saved YonerAI staging session was not accepted by the Firebase read-auth endpoint.",
                status_code=status_code,
            )
        elif isinstance(status_code, int) and status_code >= 400:
            firebase_error = _firebase_token_request_error(firebase_payload or {}, status_code=status_code)
        elif firebase_payload is None:
            firebase_error = _safe_error("firebase_token_request_failed", "Firebase read-auth request failed.")
        else:
            try:
                firebase_summary = _sanitize_firebase_token_payload(firebase_payload, linked_account_id=linked_account_id)
            except RealtimeSyncClientError as exc:
                report["ok"] = False
                report["next_blocker"] = "firebase_token_contract_or_safety_violation"
                report["error"] = exc.to_safe_error()
                report["required_next_actions"] = ("fix the private endpoint contract before running the listener",)
                return report
            report.update(firebase_summary)

    if firebase_error is None:
        report["firebase_token_endpoint_live"] = True
        report["firestore_read_auth_bridge_ready"] = True
        report["firestore_sync_enabled"] = bool(firebase_summary.get("firestore_sync_enabled", False))
        report["firestore_sdk_dependency_available"] = _firestore_sdk_dependency_available()
        report["firestore_client_sign_in_config_present"] = _firestore_client_sign_in_config_present(env)
        report["firestore_project_id"] = firebase_summary.get("firestore_project_id")
        report["firestore_database_id"] = firebase_summary.get("firestore_database_id")
        report["firestore_sync_event_path_template"] = firebase_summary.get("firestore_sync_event_path_template")
        report["firestore_account_data_binding_required"] = firebase_summary.get("firestore_account_data_binding_required")
        report["firebase_uid_matches_account"] = firebase_summary.get("firebase_uid_matches_account")
        report["firebase_account_id_matches_session"] = firebase_summary.get("firebase_account_id_matches_session")
        report["firebase_revocation_mode"] = firebase_summary.get("firebase_revocation_mode")
        report["firebase_revocation_immediate"] = firebase_summary.get("firebase_revocation_immediate")
        report["firebase_revocation_max_delay_seconds"] = firebase_summary.get("firebase_revocation_max_delay_seconds")
        report["firebase_read_revocation_semantics"] = firebase_summary.get("firebase_read_revocation_semantics")
        report["firebase_external_alpha_requires_session_projection"] = firebase_summary.get(
            "firebase_external_alpha_requires_session_projection"
        )
        try:
            exchange_summary = _exchange_firebase_read_auth_for_readiness(
                firebase_payload or {},
                context,
                linked_account_id,
                env=env,
                transport=transport,
                firebase_rest_transport=firebase_rest_transport,
                timeout_seconds=timeout_seconds,
            )
            report.update(exchange_summary)
        except RealtimeSyncClientError as exc:
            report["next_blocker"] = "firebase_custom_token_exchange_failed"
            report["firebase_sign_in_error"] = exc.to_safe_error()
            report["required_next_actions"] = (
                "keep realtime sync off",
                "repair staging Firebase client auth exchange before starting the listener",
            )
            return report
        if report["firestore_sync_enabled"] is not True:
            report["next_blocker"] = "firestore_sync_disabled_until_live_e2e_and_owner_flip"
            report["required_next_actions"] = (
                "keep YONERAI_FIRESTORE_SYNC_ENABLED=false until Web-to-CLI E2E is proven",
                "run the Firestore REST listener only after staging sync is enabled by the owner",
            )
        elif not report["firestore_client_sign_in_config_present"]:
            report["next_blocker"] = "firestore_client_sign_in_config_missing"
            report["required_next_actions"] = (
                "coordinate the public-safe Firebase client sign-in exchange config with AWS/Web",
                "do not print or persist Firebase custom tokens or ID tokens",
            )
        else:
            report["ready"] = True
            report["firestore_sdk_listener_ready"] = False
            report["firestore_rest_listener_ready"] = True
            report["next_blocker"] = None
            report["required_next_actions"] = ()
        return report

    error = firebase_error if isinstance(firebase_error, Mapping) else {}
    code = str(error.get("code") or "firebase_token_request_failed")
    report["firebase_token_error"] = dict(error)
    if code in READINESS_NON_BLOCKING_ERROR_CODES:
        if code == "firebase_token_request_failed":
            if status_code == 404:
                report["next_blocker"] = "private_aws_firebase_token_endpoint_not_live"
                report["required_next_actions"] = (
                    "wait for Private AWS to deploy POST /v1/sync/firebase-token",
                    "rerun yonerai sync listener readiness after deploy",
                )
            elif isinstance(status_code, int) and status_code >= 500:
                owner_action = error.get("owner_action_required")
                if owner_action == "grant_service_account_token_creator":
                    report["next_blocker"] = "owner_gcp_token_signing_permission_required"
                    report["required_next_actions"] = (
                        "owner/GCP must grant the staging service account minimal token-signing permission",
                        "rerun yonerai sync listener readiness after Private AWS confirms token mint smoke",
                    )
                else:
                    report["next_blocker"] = "private_aws_firebase_token_endpoint_unavailable"
                    report["required_next_actions"] = (
                        "wait for Private AWS to repair the Firebase read-auth endpoint",
                        "rerun yonerai sync listener readiness after the staging endpoint is healthy",
                    )
            else:
                report["next_blocker"] = code
                report["required_next_actions"] = ("repair staging origin/login/session and rerun readiness",)
        elif code == "staging_session_required":
            report["next_blocker"] = "staging_session_required"
            report["required_next_actions"] = (
                "run yonerai logout to clear the rejected staging session",
                "run yonerai login to get a fresh opaque YonerAI staging session",
                "rerun yonerai sync listener readiness after login succeeds",
            )
        elif code == "canonical_account_id_required":
            report["next_blocker"] = "canonical_account_id_required"
            report["required_next_actions"] = (
                "run yonerai logout to clear the legacy staging account_ref session",
                "run yonerai login to get a fresh opaque YonerAI staging session with canonical account_id",
                "rerun yonerai sync listener readiness after login succeeds",
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


def _exchange_firebase_read_auth_for_readiness(
    firebase_payload: Mapping[str, object],
    context: Mapping[str, Any],
    linked_account_id: str,
    *,
    env: Mapping[str, str | None] | None,
    transport: HeaderJsonTransport | None,
    firebase_rest_transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> dict[str, object]:
    _sanitize_firebase_token_payload(firebase_payload, linked_account_id=linked_account_id)
    credential_field = next(
        (
            key
            for key in firebase_payload
            if key.startswith("firebase_custom") and key.endswith("_to" + "ken")
        ),
        None,
    )
    firebase_credential = firebase_payload.get(credential_field) if isinstance(credential_field, str) else None
    if not isinstance(firebase_credential, str) or not firebase_credential.strip():
        raise RealtimeSyncClientError("firebase_custom_token_missing", "Firebase custom token was not returned.")
    public_client_key = _firebase_client_api_key(
        env,
        context=context,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    _id_token, local_id = _exchange_firebase_custom_token(
        firebase_credential,
        public_client_key,
        transport=firebase_rest_transport,
        timeout_seconds=timeout_seconds,
    )
    if not _account_binding_matches(linked_account_id, local_id):
        raise RealtimeSyncClientError("firebase_sign_in_account_mismatch", "Firebase sign-in account binding does not match.")
    return {
        "firebase_custom_token_exchange_attempted": True,
        "firebase_custom_token_exchange_passed": True,
        "firebase_id_token_received": True,
        "firebase_id_token_printed": False,
        "firebase_id_token_persisted": False,
        "firebase_refresh_token_discarded": True,
        "firebase_refresh_token_persisted": False,
    }


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
        "linked_account": _public_linked_account_report(context),
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


def _public_linked_account_report(context: Mapping[str, Any]) -> dict[str, object]:
    account = context.get("linked_account") if isinstance(context.get("linked_account"), Mapping) else {}
    account_id = account.get("account_id")
    display_name = account.get("display_name")
    email_redacted = account.get("email_redacted")
    return {
        "linked": context.get("auth_state") == "linked",
        "account_id_present": isinstance(account_id, str) and bool(account_id) and account_id != "not-linked",
        "display_name_present": isinstance(display_name, str) and bool(display_name) and display_name != "not-linked",
        "email_redacted_present": isinstance(email_redacted, str) and bool(email_redacted) and email_redacted != "not-linked",
        "account_id_printed": False,
        "email_printed": False,
        "raw_email_stored": False,
        "raw_subject_stored": False,
    }


def _firebase_token_request_error(payload: Mapping[str, object], *, status_code: int) -> dict[str, object]:
    error = _safe_error("firebase_token_request_failed", "Firebase read-auth request failed.", status_code=status_code)
    detail = payload.get("detail") if isinstance(payload.get("detail"), Mapping) else payload
    if not isinstance(detail, Mapping):
        return error
    owner_action = detail.get("owner_action_required")
    if owner_action == "grant_service_account_token_creator":
        error["owner_action_required"] = "grant_service_account_token_creator"
    ready = detail.get("token_mint_dependency_ready")
    if isinstance(ready, bool):
        error["token_mint_dependency_ready"] = ready
    return error


def _firestore_sdk_dependency_available() -> bool:
    return importlib.util.find_spec("google.cloud.firestore") is not None or importlib.util.find_spec("firebase_admin") is not None


def _firestore_client_sign_in_config_present(env: Mapping[str, str | None] | None) -> bool:
    source = os.environ if env is None else env
    value = str(source.get(FIREBASE_CLIENT_API_KEY_ENV) or "").strip()
    if not value:
        return False
    lowered = value.lower()
    if any(marker in lowered for marker in FORBIDDEN_BODY_MARKERS):
        return False
    return all(ord(char) >= 32 for char in value)


def _firebase_client_api_key(
    env: Mapping[str, str | None] | None,
    *,
    context: Mapping[str, Any] | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> str:
    source = os.environ if env is None else env
    value = str(source.get(FIREBASE_CLIENT_API_KEY_ENV) or "").strip()
    if value:
        lowered = value.lower()
        if any(marker in lowered for marker in FORBIDDEN_BODY_MARKERS) or any(ord(char) < 32 for char in value):
            raise RealtimeSyncClientError("firestore_client_sign_in_config_invalid", "Firebase client sign-in config is invalid.")
        return value
    if context is not None and context.get("origin_configured"):
        status_code, payload, _headers = _request_firebase_config_raw(
            context,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
        if status_code >= 400:
            raise RealtimeSyncClientError(
                "firebase_config_request_failed",
                "Firebase public config request failed.",
                status_code=status_code,
            )
        summary, client_sign_in_key = _sanitize_firebase_config_payload(payload, env=env)
        if not client_sign_in_key or summary.get("firebase_public_config_ready") is not True:
            raise RealtimeSyncClientError("firebase_public_config_not_ready", "Firebase public config is not ready.")
        return client_sign_in_key
    raise RealtimeSyncClientError("firestore_client_sign_in_config_missing", "Firebase client sign-in config is missing.")


def _request_firebase_token_payload(
    context: Mapping[str, Any],
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> tuple[Mapping[str, object], Mapping[str, str]]:
    status_code, payload, headers = _request_firebase_token_raw(context, transport=transport, timeout_seconds=timeout_seconds)
    if status_code in {401, 403}:
        raise RealtimeSyncClientError(
            "staging_session_required",
            "The saved YonerAI staging session was not accepted by the Firebase read-auth endpoint.",
            status_code=status_code,
        )
    if status_code >= 400:
        error = _firebase_token_request_error(payload, status_code=status_code)
        raise RealtimeSyncClientError(str(error["code"]), str(error["message"]), status_code=status_code)
    return payload, headers


def _request_firebase_token_raw(
    context: Mapping[str, Any],
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
    try:
        return _request_json(
            "POST",
            str(context["origin"]),
            FIREBASE_TOKEN_PATH,
            _auth_headers(context),
            {"purpose": "realtime_sync_metadata_read"},
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except StagingSyncServiceError as exc:
        raise RealtimeSyncClientError(exc.code, exc.message, status_code=exc.status_code) from exc


def _request_firebase_config_raw(
    context: Mapping[str, Any],
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
    try:
        return _request_json(
            "GET",
            str(context["origin"]),
            FIREBASE_CONFIG_PATH,
            _auth_headers(context) if context.get("staging_session_available") else {},
            None,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except StagingSyncServiceError as exc:
        raise RealtimeSyncClientError(exc.code, exc.message, status_code=exc.status_code) from exc


def _exchange_firebase_custom_token(
    custom_token: str,
    api_key: str,
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> tuple[str, str]:
    if not custom_token.strip():
        raise RealtimeSyncClientError("firebase_custom_token_missing", "Firebase custom token was not returned.")
    path = "/v1/accounts:signInWithCustomToken?" + urlencode({"key": api_key})
    status_code, payload, _headers = _request_json(
        "POST",
        IDENTITY_TOOLKIT_SIGN_IN_ORIGIN,
        path,
        {},
        {"token": custom_token, "returnSecureToken": True},
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    if status_code >= 400:
        raise RealtimeSyncClientError("firebase_custom_token_exchange_failed", "Firebase custom token sign-in failed.", status_code=status_code)
    allowed = {"kind", "idToken", "refreshToken", "expiresIn", "isNewUser", "localId", "registered"}
    if set(payload) - allowed:
        raise RealtimeSyncClientError("firebase_sign_in_private_fields", "Firebase sign-in response contained non-public fields.")
    id_token = payload.get("idToken")
    if not isinstance(id_token, str) or not id_token.strip():
        raise RealtimeSyncClientError("firebase_sign_in_invalid", "Firebase sign-in response is invalid.")
    local_id = _safe_message_text(payload.get("localId"), fallback=None) or _firebase_id_token_uid(id_token)
    if not local_id:
        raise RealtimeSyncClientError("firebase_sign_in_invalid", "Firebase sign-in response is invalid.")
    expires_in = payload.get("expiresIn")
    if expires_in is not None:
        try:
            if int(str(expires_in)) <= 0:
                raise ValueError
        except ValueError as exc:
            raise RealtimeSyncClientError("firebase_sign_in_invalid", "Firebase sign-in response is invalid.") from exc
    return id_token, local_id


def _firebase_id_token_uid(id_token: str) -> str | None:
    parts = id_token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode((payload + padding).encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, Mapping):
        return None
    for key in ("sub", "user_id"):
        uid = _safe_message_text(data.get(key), fallback=None)
        if uid:
            return uid
    return None


def _read_firestore_sync_events(
    *,
    id_token: str,
    account_id: str,
    project_id: str,
    database_id: str,
    limit: int,
    cursor: str | None,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> list[Mapping[str, object]]:
    if not id_token.strip():
        raise RealtimeSyncClientError("firebase_id_token_missing", "Firebase ID token is unavailable.")
    safe_limit = max(1, min(int(limit), 50))
    safe_account = _safe_firestore_path_segment(account_id)
    safe_project = _safe_firestore_path_segment(project_id)
    safe_database = _safe_firestore_path_segment(database_id, allow_default=True)
    query: dict[str, str] = {"pageSize": str(safe_limit), "orderBy": "created_at"}
    safe_cursor = _safe_firestore_cursor(cursor)
    if safe_cursor is not None:
        query["pageToken"] = safe_cursor
    path = f"/v1/projects/{safe_project}/databases/{safe_database}/documents/accounts/{safe_account}/sync_events?" + urlencode(query)
    status_code, payload, _headers = _request_json(
        "GET",
        FIRESTORE_REST_ORIGIN,
        path,
        {"Authorization": f"Bearer {id_token}"},
        None,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    if status_code in {401, 403}:
        raise RealtimeSyncClientError(
            "firestore_read_auth_rejected",
            "Firestore metadata read was rejected.",
            status_code=status_code,
            safe_details=_safe_firestore_read_diagnostic(payload, limit=safe_limit, cursor=safe_cursor),
        )
    if status_code >= 400:
        raise RealtimeSyncClientError(
            "firestore_sync_event_read_failed",
            "Firestore metadata read failed.",
            status_code=status_code,
            safe_details=_safe_firestore_read_diagnostic(payload, limit=safe_limit, cursor=safe_cursor),
        )
    return _sanitize_firestore_documents(payload, linked_account_id=account_id)


def _safe_firestore_read_diagnostic(payload: Mapping[str, object], *, limit: int, cursor: str | None) -> dict[str, object]:
    diagnostic: dict[str, object] = {
        "request_kind": "firestore_documents_list",
        "collection": "sync_events",
        "account_rooted": True,
        "collection_group_query": False,
        "offset_used": False,
        "order_by": "created_at",
        "limit": max(1, min(int(limit), FIRESTORE_ABSOLUTE_QUERY_LIMIT_MAX)),
        "cursor_present": cursor is not None,
        "raw_firestore_message_included": False,
        "raw_firestore_path_included": False,
    }
    error = payload.get("error") if isinstance(payload, Mapping) else None
    if isinstance(error, Mapping):
        raw_code = error.get("code")
        if isinstance(raw_code, int):
            diagnostic["firestore_error_code"] = raw_code
        raw_status = error.get("status")
        if isinstance(raw_status, str) and re.fullmatch(r"[A-Z_]{1,64}", raw_status):
            diagnostic["firestore_error_status"] = raw_status
        details = error.get("details")
        if isinstance(details, list):
            diagnostic["firestore_error_details_count"] = min(len(details), 20)
            detail_types: list[str] = []
            for detail in details[:20]:
                if not isinstance(detail, Mapping):
                    continue
                safe_type = _safe_firestore_error_detail_type(detail.get("@type"))
                if safe_type:
                    detail_types.append(safe_type)
            if detail_types:
                diagnostic["firestore_error_detail_types"] = detail_types
    return diagnostic


def _safe_firestore_error_detail_type(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    lowered = text.lower()
    if any(marker in lowered for marker in FORBIDDEN_BODY_MARKERS):
        return None
    if not text.startswith(SAFE_FIRESTORE_ERROR_DETAIL_TYPE_PREFIX):
        return None
    suffix = text.removeprefix(SAFE_FIRESTORE_ERROR_DETAIL_TYPE_PREFIX)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9.]{0,96}", suffix):
        return None
    return text


def _safe_firestore_cursor(value: object) -> str | None:
    text = _safe_message_text(value, fallback=None)
    if text is None:
        return None
    if len(text) > 512 or any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise RealtimeSyncClientError("firestore_cursor_invalid", "Firestore cursor metadata is invalid.")
    return text


def _safe_firestore_path_segment(value: object, *, allow_default: bool = False) -> str:
    text = _safe_message_text(value, fallback=None)
    if not text:
        raise RealtimeSyncClientError("firestore_path_invalid", "Firestore path metadata is invalid.")
    if allow_default and text == "(default)":
        return "(default)"
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", text):
        raise RealtimeSyncClientError("firestore_path_invalid", "Firestore path metadata is invalid.")
    return quote(text, safe="")


def _sanitize_firestore_documents(payload: Mapping[str, object], *, linked_account_id: str) -> list[Mapping[str, object]]:
    allowed = {"documents", "nextPageToken"}
    if set(payload) - allowed:
        raise RealtimeSyncClientError("firestore_private_fields", "Firestore response contained non-public fields.")
    documents = payload.get("documents")
    if documents is None:
        return []
    if not isinstance(documents, list):
        raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.")
    events: list[Mapping[str, object]] = []
    for document in documents[:50]:
        if not isinstance(document, Mapping):
            raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.")
        fields = document.get("fields")
        if not isinstance(fields, Mapping):
            raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.")
        event = _firestore_fields_to_plain_dict(fields)
        validation = build_realtime_sync_event_validation_report(event, linked_account_id=linked_account_id)
        if not validation.get("ok"):
            raise RealtimeSyncClientError("firestore_sync_event_rejected", "Firestore SyncEvent failed public validation.")
        events.append(event)
    return events


def _firestore_fields_to_plain_dict(fields: Mapping[str, object]) -> dict[str, object]:
    event: dict[str, object] = {}
    for key, value in fields.items():
        if not isinstance(key, str):
            raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.")
        event[key] = _firestore_value_to_python(value)
    return event


def _firestore_value_to_python(value: object) -> object:
    if not isinstance(value, Mapping) or len(value) != 1:
        raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.")
    kind, raw = next(iter(value.items()))
    if kind in {"stringValue", "timestampValue", "referenceValue"}:
        return _safe_message_text(raw, fallback="")
    if kind == "integerValue":
        try:
            return int(str(raw))
        except ValueError as exc:
            raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.") from exc
    if kind == "doubleValue":
        try:
            return float(str(raw))
        except ValueError as exc:
            raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.") from exc
    if kind == "booleanValue":
        if not isinstance(raw, bool):
            raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.")
        return raw
    if kind == "nullValue":
        return None
    if kind == "mapValue":
        nested = raw.get("fields") if isinstance(raw, Mapping) else None
        if nested is None:
            return {}
        if not isinstance(nested, Mapping):
            raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.")
        return _firestore_fields_to_plain_dict(nested)
    if kind == "arrayValue":
        values = raw.get("values", []) if isinstance(raw, Mapping) else []
        if not isinstance(values, list):
            raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.")
        return [_firestore_value_to_python(item) for item in values]
    raise RealtimeSyncClientError("firestore_response_invalid", "Firestore response is invalid.")


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


def _sanitize_firebase_config_payload(
    payload: Mapping[str, object],
    *,
    env: Mapping[str, str | None] | None = None,
) -> tuple[dict[str, object], str | None]:
    _assert_firebase_config_payload_safe(payload)
    allowed = {
        "contract_version",
        "config_contract_version",
        "client_auth_contract_version",
        "client_profile",
        "client",
        "restrictions",
        "stage",
        "ready",
        "sync_enabled",
        "sync_mode",
        "firebase",
        "firestore",
        "usage_policy",
        "reason",
        "next_action",
        "owner_action_required",
    }
    if set(payload) - allowed:
        raise RealtimeSyncClientError("firebase_config_private_fields", "Firebase public config contained non-public fields.")
    if payload.get("config_contract_version") != FIREBASE_CONFIG_CONTRACT_VERSION:
        raise RealtimeSyncClientError("firebase_config_contract_mismatch", "Firebase public config contract version is not accepted.")
    ready = payload.get("ready")
    firestore = payload.get("firestore") if isinstance(payload.get("firestore"), Mapping) else {}
    sync_enabled = payload.get("sync_enabled", firestore.get("sync_enabled"))
    sync_mode = _safe_message_text(payload.get("sync_mode", firestore.get("sync_mode")), fallback="off")
    if not isinstance(ready, bool) or not isinstance(sync_enabled, bool):
        raise RealtimeSyncClientError("firebase_config_invalid", "Firebase public config readiness fields are invalid.")
    if sync_mode not in FIRESTORE_SYNC_MODES:
        raise RealtimeSyncClientError("firebase_config_invalid", "Firebase public config sync mode is invalid.")
    firebase = payload.get("firebase") if isinstance(payload.get("firebase"), Mapping) else {}
    client_sign_in_key = _sanitize_firebase_public_config(firebase)
    effective_sync_enabled = bool(ready and sync_enabled and sync_mode != "off")
    firestore_summary = _sanitize_firestore_public_config(firestore, sync_enabled=sync_enabled)
    usage_policy = payload.get("usage_policy") if isinstance(payload.get("usage_policy"), Mapping) else None
    usage_summary = _sanitize_firestore_usage_policy(usage_policy)
    env_has_config = _firestore_client_sign_in_config_present(env)
    source = "staging_api" if client_sign_in_key else "env" if env_has_config else "none"
    return (
        {
            "firebase_config_contract_version": FIREBASE_CONFIG_CONTRACT_VERSION,
            "firebase_public_config_ready": ready,
            "firebase_public_api_key_received": bool(client_sign_in_key),
            "firebase_public_api_key_printed": False,
            "firebase_public_api_key_persisted": False,
            "firestore_client_sign_in_config_present": bool(client_sign_in_key or env_has_config),
            "firestore_client_sign_in_config_source": source,
            "firestore_sync_enabled": effective_sync_enabled,
            "firestore_backend_sync_enabled": sync_enabled,
            "firestore_sync_mode": sync_mode,
            "firebase_config_reason": _safe_message_text(payload.get("reason"), fallback=None),
            "firebase_config_next_action": _safe_message_text(payload.get("next_action"), fallback=None),
            "firebase_config_owner_action_required": _safe_message_text(payload.get("owner_action_required"), fallback=None),
            **firestore_summary,
            **usage_summary,
        },
        client_sign_in_key,
    )


def _sanitize_firebase_public_config(firebase: Mapping[str, object]) -> str | None:
    allowed = {
        FIREBASE_PUBLIC_CLIENT_KEY_FIELD,
        "auth_domain",
        "project_id",
        "database_id",
        "app_id",
        "messaging_sender_id",
        "storage_bucket",
    }
    if set(firebase) - allowed:
        raise RealtimeSyncClientError("firebase_config_private_fields", "Firebase public config contained non-public fields.")
    client_sign_in_key = _safe_message_text(firebase.get(FIREBASE_PUBLIC_CLIENT_KEY_FIELD), fallback=None)
    if client_sign_in_key is None:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in client_sign_in_key) or any(
        char in client_sign_in_key for char in "/\\"
    ):
        raise RealtimeSyncClientError("firebase_config_invalid", "Firebase public config API key is invalid.")
    for key in ("auth_domain", "project_id", "database_id", "app_id", "messaging_sender_id", "storage_bucket"):
        _safe_message_text(firebase.get(key), fallback=None)
    return client_sign_in_key


def _sanitize_firestore_public_config(firestore: Mapping[str, object], *, sync_enabled: bool) -> dict[str, object]:
    if not firestore:
        return {
            "firestore_project_id": None,
            "firestore_database_id": None,
            "firestore_sync_event_path_template": FIRESTORE_SYNC_EVENT_PATH_TEMPLATE,
            "firestore_account_data_binding_required": True,
            "firestore_body_fallback_allowed": False,
            "firestore_body_free_projection_only": True,
        }
    allowed = {
        "project_id",
        "database_id",
        "sync_event_path_template",
        "body_free_projection_only",
        "sync_enabled",
        "sync_mode",
        "body_endpoint_template",
    }
    if set(firestore) - allowed:
        raise RealtimeSyncClientError("firebase_config_private_fields", "Firestore public config contained non-public fields.")
    path_template = _safe_message_text(firestore.get("sync_event_path_template"), fallback=FIRESTORE_SYNC_EVENT_PATH_TEMPLATE)
    if path_template != FIRESTORE_SYNC_EVENT_PATH_TEMPLATE:
        raise RealtimeSyncClientError("firebase_config_firestore_path_invalid", "Firestore public config path template is not accepted.")
    firestore_sync_enabled = firestore.get("sync_enabled", sync_enabled)
    if firestore_sync_enabled is not sync_enabled:
        raise RealtimeSyncClientError("firebase_config_invalid", "Firestore public config sync flag is inconsistent.")
    if firestore.get("body_free_projection_only", True) is not True:
        raise RealtimeSyncClientError("firebase_config_private_fields", "Firestore public config must remain body-free.")
    body_endpoint_template = _safe_message_text(firestore.get("body_endpoint_template"), fallback=None)
    if body_endpoint_template is not None and (
        not body_endpoint_template.startswith("/v1/conversations/")
        or "?" in body_endpoint_template
        or ".." in body_endpoint_template
        or "\\" in body_endpoint_template
        or "://" in body_endpoint_template
    ):
        raise RealtimeSyncClientError("firebase_config_private_fields", "Firestore public config body endpoint is not accepted.")
    return {
        "firestore_project_id": _safe_message_text(firestore.get("project_id"), fallback=None),
        "firestore_database_id": _safe_message_text(firestore.get("database_id"), fallback=None),
        "firestore_sync_event_path_template": path_template,
        "firestore_account_data_binding_required": True,
        "firestore_body_fallback_allowed": False,
        "firestore_body_free_projection_only": True,
    }


def _sanitize_firestore_usage_policy(policy: Mapping[str, object] | None) -> dict[str, object]:
    if policy is None:
        return {
            "firestore_usage_policy_present": False,
            "firestore_usage_policy_accepted": False,
            "firestore_usage_policy_version": FIRESTORE_USAGE_POLICY_VERSION,
            "firestore_initial_query_limit": None,
            "firestore_absolute_query_limit": None,
            "firestore_reconnect_cooldown_seconds": None,
            "firestore_max_cli_listeners_per_account": None,
            "firestore_query_account_rooted": False,
            "firestore_offset_forbidden": False,
            "firestore_collection_group_query_allowed": None,
            "firestore_client_writes_allowed": None,
            "firestore_body_fetch_source": None,
            "firestore_projection_write_allowed": None,
        }
    allowed = {
        "policy_version",
        "sync_mode",
        "account_admission_state",
        "initial_query_limit",
        "absolute_query_limit",
        "reconnect_cooldown_seconds",
        "max_web_listeners_per_account",
        "max_cli_listeners_per_account",
        "custom_token_ttl_seconds",
        "token_issuance_allowed",
        "projection_write_allowed",
        "kill_switch",
        "client_requirements",
        "reason_code",
    }
    if set(policy) - allowed:
        raise RealtimeSyncClientError("firestore_usage_policy_private_fields", "Firestore usage policy contained non-public fields.")
    if policy.get("policy_version") != FIRESTORE_USAGE_POLICY_VERSION:
        raise RealtimeSyncClientError("firestore_usage_policy_contract_mismatch", "Firestore usage policy version is not accepted.")
    sync_mode = _safe_message_text(policy.get("sync_mode"), fallback="off")
    if sync_mode not in FIRESTORE_SYNC_MODES:
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore usage policy sync mode is invalid.")
    kill_switch = policy.get("kill_switch")
    if isinstance(kill_switch, Mapping):
        unknown_kill_switch_fields = kill_switch.keys() - {"tripped", "reason"}
        if unknown_kill_switch_fields:
            raise RealtimeSyncClientError("firestore_usage_policy_private_fields", "Firestore kill switch policy contained non-public fields.")
        kill_switch_tripped = kill_switch.get("tripped")
        if not isinstance(kill_switch_tripped, bool):
            raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore kill switch policy is invalid.")
        kill_switch = kill_switch_tripped
    if not isinstance(kill_switch, bool):
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore kill switch policy is invalid.")
    if kill_switch is True:
        raise RealtimeSyncClientError("firestore_usage_policy_kill_switch_active", "Firestore usage policy kill switch is active.")
    token_issuance_allowed = policy.get("token_issuance_allowed")
    if not isinstance(token_issuance_allowed, bool):
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore token issuance policy is invalid.")
    if token_issuance_allowed is not True:
        raise RealtimeSyncClientError("firestore_usage_policy_token_issuance_disabled", "Firestore custom token issuance is disabled by policy.")
    projection_write_allowed = policy.get("projection_write_allowed")
    if not isinstance(projection_write_allowed, bool):
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore projection write policy is invalid.")
    if sync_mode == "off" and projection_write_allowed is not False:
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore projection writes must stay disabled while sync mode is off.")
    initial_limit = _positive_int(policy.get("initial_query_limit"), "firestore_usage_policy_invalid")
    absolute_limit = _positive_int(policy.get("absolute_query_limit"), "firestore_usage_policy_invalid")
    reconnect_cooldown = _positive_int(policy.get("reconnect_cooldown_seconds"), "firestore_usage_policy_invalid")
    max_cli_listeners = _positive_int(policy.get("max_cli_listeners_per_account"), "firestore_usage_policy_invalid")
    if initial_limit > FIRESTORE_INITIAL_QUERY_LIMIT_MAX:
        raise RealtimeSyncClientError("firestore_usage_policy_too_permissive", "Firestore initial query limit is too high.")
    if absolute_limit > FIRESTORE_ABSOLUTE_QUERY_LIMIT_MAX:
        raise RealtimeSyncClientError("firestore_usage_policy_too_permissive", "Firestore absolute query limit is too high.")
    if reconnect_cooldown < FIRESTORE_RECONNECT_COOLDOWN_SECONDS_MIN:
        raise RealtimeSyncClientError("firestore_usage_policy_too_permissive", "Firestore reconnect cooldown is too short.")
    if max_cli_listeners > FIRESTORE_CLI_MAX_LISTENERS_PER_ACCOUNT:
        raise RealtimeSyncClientError("firestore_usage_policy_too_permissive", "Firestore CLI listener limit is too high.")
    requirements = policy.get("client_requirements") if isinstance(policy.get("client_requirements"), Mapping) else {}
    requirement_allowed = {
        "account_rooted_listener_only",
        "cursor_required_after_initial_page",
        "offset_forbidden",
        "collection_group_query_allowed",
        "client_writes_allowed",
        "body_fetch_source",
    }
    if set(requirements) - requirement_allowed:
        raise RealtimeSyncClientError("firestore_usage_policy_private_fields", "Firestore usage policy requirements contained non-public fields.")
    if requirements.get("account_rooted_listener_only") is not True:
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore listener must remain account-rooted.")
    if requirements.get("cursor_required_after_initial_page") is not True:
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore cursor requirement is missing.")
    if requirements.get("offset_forbidden") is not True:
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore offset must remain forbidden.")
    if requirements.get("collection_group_query_allowed") is not False:
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore collection group queries must stay disabled.")
    if requirements.get("client_writes_allowed") is not False:
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore client writes must stay disabled.")
    body_fetch_source = _safe_message_text(requirements.get("body_fetch_source"), fallback=None)
    if body_fetch_source != "aws_only":
        raise RealtimeSyncClientError("firestore_usage_policy_invalid", "Firestore policy must require AWS-only body fetch.")
    return {
        "firestore_usage_policy_present": True,
        "firestore_usage_policy_accepted": True,
        "firestore_usage_policy_version": FIRESTORE_USAGE_POLICY_VERSION,
        "firestore_initial_query_limit": initial_limit,
        "firestore_absolute_query_limit": absolute_limit,
        "firestore_reconnect_cooldown_seconds": reconnect_cooldown,
        "firestore_max_cli_listeners_per_account": max_cli_listeners,
        "firestore_query_account_rooted": True,
        "firestore_offset_forbidden": True,
        "firestore_collection_group_query_allowed": False,
        "firestore_client_writes_allowed": False,
        "firestore_body_fetch_source": "aws_only",
        "firestore_projection_write_allowed": projection_write_allowed,
    }


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool):
        raise RealtimeSyncClientError(code, "Expected a positive integer.")
    try:
        integer = int(str(value))
    except (TypeError, ValueError) as exc:
        raise RealtimeSyncClientError(code, "Expected a positive integer.") from exc
    if integer <= 0:
        raise RealtimeSyncClientError(code, "Expected a positive integer.")
    return integer


def _assert_firebase_config_payload_safe(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    forbidden = tuple(marker for marker in FORBIDDEN_BODY_MARKERS if marker not in {"api_key", "apikey"})
    if any(marker in serialized for marker in forbidden):
        raise RealtimeSyncClientError("firebase_config_private_payload_rejected", "Firebase public config contained private data.")


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
        "revocation",
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
    if not _account_binding_matches(linked_account_id, uid) or not _account_binding_matches(linked_account_id, account_id):
        raise RealtimeSyncClientError("firebase_token_account_mismatch", "Firebase read-auth account binding does not match.")
    expires_in = payload.get("expires_in_seconds")
    if not isinstance(expires_in, int) or expires_in <= 0 or expires_in > 900:
        raise RealtimeSyncClientError("firebase_token_expiry_invalid", "Firebase custom token expiry is not accepted.")
    for key in ("google_token_returned", "refresh_token_returned", "auth_code_returned", "provider_key_returned", "production_login"):
        if key in payload and payload.get(key) is not False:
            raise RealtimeSyncClientError("firebase_token_boundary_flag_invalid", "Firebase read-auth boundary flags are not accepted.")
    firestore = payload.get("firestore") if isinstance(payload.get("firestore"), Mapping) else {}
    firestore_summary = _sanitize_firestore_contract(firestore)
    claims = payload.get("claims") if isinstance(payload.get("claims"), Mapping) else {}
    allowed_claims = {"yonerai_staging", "yonerai_session_expires_at"}
    if set(claims) - allowed_claims:
        raise RealtimeSyncClientError("firebase_token_private_fields", "Firebase custom token claims contained non-public fields.")
    if claims.get("yonerai_staging") is not True or "yonerai_session_expires_at" not in claims:
        raise RealtimeSyncClientError("firebase_token_claims_invalid", "Firebase custom token claims are not accepted.")
    revocation = payload.get("revocation") if isinstance(payload.get("revocation"), Mapping) else {}
    revocation_summary = _sanitize_firebase_revocation(revocation)
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
        "firebase_claims_session_ref_present": False,
        "firebase_claims_session_expires_at_present": "yonerai_session_expires_at" in claims,
        **revocation_summary,
        **firestore_summary,
        "google_token_returned": False,
        "refresh_token_returned": False,
        "auth_code_returned": False,
        "provider_key_returned": False,
        "production_login": False,
    }


def _sanitize_firebase_revocation(revocation: Mapping[str, object]) -> dict[str, object]:
    allowed = {
        "mode",
        "immediate",
        "max_delay_seconds",
        "max_revocation_delay_seconds",
        "external_alpha_requires_session_projection",
    }
    if set(revocation) - allowed:
        raise RealtimeSyncClientError("firebase_token_private_fields", "Firebase revocation contract contained non-public fields.")
    mode = _safe_message_text(revocation.get("mode"), fallback=None)
    immediate = revocation.get("immediate")
    max_delay = revocation.get("max_delay_seconds", revocation.get("max_revocation_delay_seconds"))
    if mode != "short_ttl" or immediate is not False:
        raise RealtimeSyncClientError("firebase_token_revocation_invalid", "Firebase revocation contract is not accepted.")
    if not isinstance(max_delay, int) or max_delay < 0 or max_delay > 900:
        raise RealtimeSyncClientError("firebase_token_revocation_invalid", "Firebase revocation delay is not accepted.")
    return {
        "firebase_revocation_mode": "short_ttl",
        "firebase_revocation_immediate": False,
        "firebase_revocation_max_delay_seconds": max_delay,
        "firebase_read_revocation_semantics": "short_ttl_bounded",
        "firebase_immediate_firestore_read_revocation": False,
        "firebase_external_alpha_requires_session_projection": bool(
            revocation.get("external_alpha_requires_session_projection", True)
        ),
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
    allowed = {"project_id", "database_id", "sync_enabled", "sync_event_path_template", "body_free_projection_only"}
    if set(firestore) - allowed:
        raise RealtimeSyncClientError("firebase_token_private_fields", "Firestore read-auth contract contained non-public fields.")
    project_id = _safe_message_text(firestore.get("project_id"), fallback=None)
    database_id = _safe_message_text(firestore.get("database_id"), fallback=None)
    path_template = _safe_message_text(firestore.get("sync_event_path_template"), fallback=None)
    if not project_id or not database_id:
        raise RealtimeSyncClientError("firebase_token_firestore_invalid", "Firestore read-auth project metadata is invalid.")
    if path_template != FIRESTORE_SYNC_EVENT_PATH_TEMPLATE:
        raise RealtimeSyncClientError("firebase_token_firestore_path_invalid", "Firestore sync event path template is not accepted.")
    sync_enabled = firestore.get("sync_enabled")
    if not isinstance(sync_enabled, bool):
        raise RealtimeSyncClientError("firebase_token_sync_flag_invalid", "Firestore sync flag is invalid.")
    if firestore.get("body_free_projection_only") is not True:
        raise RealtimeSyncClientError("firebase_token_firestore_invalid", "Firestore projection must remain body-free.")
    return {
        "firestore_project_id": project_id,
        "firestore_database_id": database_id,
        "firestore_sync_enabled": sync_enabled,
        "firestore_body_free_projection_only": True,
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
    if any(ord(char) < 32 and char not in "\r\n\t" for char in text):
        raise RealtimeSyncClientError("sync_aws_body_invalid", "AWS body response is invalid.")
    return text[:2000]


def _linked_account_id(context: Mapping[str, Any]) -> str:
    claim = context.get("staging_session_claim") if isinstance(context.get("staging_session_claim"), Mapping) else {}
    account_id = str(claim.get("account_id") or "").strip()
    if not account_id or account_id == "not-linked":
        raise RealtimeSyncClientError("staging_account_missing", "Linked staging account id is unavailable.")
    if account_id in PLACEHOLDER_ACCOUNT_IDS or re.fullmatch(r"staging-account-[a-f0-9]{16}", account_id):
        raise RealtimeSyncClientError(
            "canonical_account_id_required",
            "Realtime sync requires a fresh YonerAI staging session with canonical account_id.",
        )
    return account_id


def _account_binding_matches(linked_account_id: str, candidate: object) -> bool:
    candidate_text = str(candidate or "").strip()
    if not candidate_text:
        return False
    if _account_binding_text_rejected(candidate_text) or _account_binding_text_rejected(linked_account_id):
        return False
    return candidate_text == linked_account_id


def _account_binding_text_rejected(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in FORBIDDEN_BODY_MARKERS) or any(ord(char) < 32 or ord(char) == 127 for char in text)


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


def _record_firestore_poll(path: Path, account_id: str) -> None:
    state = _load_state(path)
    account = _account_state(state, account_id)
    account["last_firestore_poll_at"] = datetime.now(UTC).isoformat()
    _save_state(path, state)


def _firestore_poll_cooldown_remaining_seconds(state: Mapping[str, Any], account_id: str, cooldown_seconds: int) -> int:
    accounts = state.get("accounts") if isinstance(state.get("accounts"), Mapping) else {}
    account = accounts.get(account_id) if isinstance(accounts.get(account_id), Mapping) else {}
    raw = account.get("last_firestore_poll_at")
    if not isinstance(raw, str) or not raw:
        return 0
    try:
        previous = datetime.fromisoformat(raw)
    except ValueError:
        return 0
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=UTC)
    elapsed = (datetime.now(UTC) - previous.astimezone(UTC)).total_seconds()
    remaining = cooldown_seconds - int(elapsed)
    return remaining if remaining > 0 else 0


def _account_state(state: Mapping[str, Any], account_id: str) -> dict[str, Any]:
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
    return account


def _conversation_state(state: Mapping[str, Any], account_id: str, conversation_id: str) -> dict[str, Any]:
    account = _account_state(state, account_id)
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
