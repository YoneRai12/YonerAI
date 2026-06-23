from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from yonerai_cli.auth_policy import build_google_auth_status
from yonerai_cli.services.auth_session_service import empty_staging_auth_claim
from yonerai_cli.services.staging_session_service import empty_staging_session_claim, load_staging_session_token


STAGING_SYNC_SCHEMA_VERSION = "yonerai-staging-conversation-sync/v0.1"
STATUS_PATH = "/v1/status"
RATE_LIMIT_PATH = "/v1/rate-limit"
CONVERSATIONS_PATH = "/v1/conversations"
CONVERSATION_PATH_TEMPLATE = "/v1/conversations/{conversation_id}"
SYNC_PREVIEW_PATH = "/v1/sync/preview"
SYNC_DIRECTIONS = {"cloud-to-local": "cloud_to_local", "local-to-cloud": "local_to_cloud"}

HeaderJsonTransport = Callable[
    [str, str, Mapping[str, str], Mapping[str, object] | None, float],
    tuple[int, Mapping[str, object], Mapping[str, str]],
]


class StagingSyncServiceError(ValueError):
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
            "private_endpoint_printed": False,
            "local_path_printed": False,
            "token_printed": False,
        }


def build_staging_sync_status(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = _auth_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("sync_status", context)
    if not context["origin_configured"]:
        report["ok"] = True
        return report
    try:
        status = _get_json(context["origin"], STATUS_PATH, transport=transport, timeout_seconds=timeout_seconds)
        rate_limit = _get_json(context["origin"], RATE_LIMIT_PATH, transport=transport, timeout_seconds=timeout_seconds)
    except StagingSyncServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report.update(
        {
            "official_backend_called": True,
            "status_endpoint": _sanitize_status_payload(status),
            "rate_limit": _sanitize_rate_limit_payload(rate_limit),
        }
    )
    conversation_sync = report["rate_limit"].get("conversation_sync") if isinstance(report.get("rate_limit"), dict) else {}
    if isinstance(conversation_sync, dict):
        report["directions"]["cloud_to_local"]["staging_state"] = _safe_text(
            conversation_sync.get("cloud_to_local"), fallback="unknown"
        )
        report["directions"]["local_to_cloud"]["staging_state"] = _safe_text(
            conversation_sync.get("local_to_cloud"), fallback="approval_required"
        )
    return report


def build_staging_conversations_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = _auth_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("sync_conversations", context)
    report["conversations"] = []
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if context["auth_state"] != "linked":
        report["ok"] = False
        report["error"] = _safe_error("staging_auth_required", "Staging Google login is required before listing cloud conversations.")
        return report
    if not context["staging_session_available"]:
        report["ok"] = False
        report["error"] = _safe_error(
            "staging_session_required",
            "A safe YonerAI staging session is required before reading account cloud conversations.",
        )
        return report
    try:
        status_code, body, headers = _request_json(
            "GET",
            context["origin"],
            CONVERSATIONS_PATH,
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
            "The saved YonerAI staging session was not accepted by the conversation API.",
            status_code=status_code,
        )
        report["backend_auth_required_confirmed"] = True
        return report
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _safe_error("staging_conversations_failed", "Staging conversations request failed.", status_code=status_code)
        return report
    try:
        report["conversations"] = _sanitize_conversations(body)
    except StagingSyncServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report["selected_count"] = sum(1 for item in report["conversations"] if item.get("selected_by_user") is True)
    return report


def build_staging_conversation_show_report(
    *,
    conversation_id: str,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = _auth_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("sync_conversation_show", context)
    report["conversation"] = None
    safe_conversation_id = _safe_conversation_id(conversation_id)
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if context["auth_state"] != "linked":
        report["ok"] = False
        report["error"] = _safe_error("staging_auth_required", "Staging Google login is required before reading a cloud conversation.")
        return report
    if not context["staging_session_available"]:
        report["ok"] = False
        report["error"] = _safe_error(
            "staging_session_required",
            "A safe YonerAI staging session is required before reading account cloud conversations.",
        )
        return report
    try:
        status_code, body, headers = _request_json(
            "GET",
            context["origin"],
            CONVERSATION_PATH_TEMPLATE.format(conversation_id=safe_conversation_id),
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
            "The saved YonerAI staging session was not accepted by the conversation API.",
            status_code=status_code,
        )
        return report
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _safe_error("staging_conversation_show_failed", "Staging conversation request failed.", status_code=status_code)
        return report
    try:
        report["conversation"] = _sanitize_conversation(body)
    except StagingSyncServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    return report


def build_staging_sync_preview_report(
    *,
    direction: str,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    conversation_ref: str = "cloud-conversation-fixture",
    audit_reason: str = "public_cli_sync_preview",
    explicit_approval: bool = False,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    normalized_direction = _normalize_direction(direction)
    context = _auth_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("sync_preview", context)
    report.update(
        {
            "direction": normalized_direction,
            "conversation_ref": _safe_text(conversation_ref, fallback="cloud-conversation-fixture"),
            "preview_only": True,
            "sync_performed": False,
            "approval_recorded": False,
            "private_content_exclusion": _private_content_exclusion(),
        }
    )
    if normalized_direction == "local_to_cloud":
        report["ok"] = True
        report["decision"] = {
            "state": "approval_required" if not explicit_approval else "allowed",
            "reason": "local_to_cloud_requires_explicit_approval"
            if not explicit_approval
            else "explicit_approval_preview_only_no_upload",
            "requires_explicit_approval": True,
            "private_content_excluded": True,
        }
        report["actions_not_performed"] = _sync_non_actions()
        return report
    if not context["origin_configured"]:
        report["ok"] = False
        report["decision"] = _blocked_decision("staging_origin_not_configured")
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if context["auth_state"] != "linked":
        report["ok"] = False
        report["decision"] = _blocked_decision("staging_auth_required")
        report["error"] = _safe_error("staging_auth_required", "Staging Google login is required before cloud-to-local sync preview.")
        return report
    if not context["staging_session_available"]:
        report["ok"] = False
        report["decision"] = _blocked_decision("staging_session_required")
        report["error"] = _safe_error(
            "staging_session_required",
            "A safe YonerAI staging session is required before cloud-to-local sync preview.",
        )
        return report
    body = {
        "direction": normalized_direction,
        "conversation_ref": _safe_text(conversation_ref, fallback="cloud-conversation-fixture"),
        "audit_reason": _safe_text(audit_reason, fallback="public_cli_sync_preview"),
        "contains_private_content": False,
    }
    try:
        status_code, response, headers = _request_json(
            "POST",
            context["origin"],
            SYNC_PREVIEW_PATH,
            _auth_headers(context),
            body,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except StagingSyncServiceError as exc:
        report["ok"] = False
        report["decision"] = _blocked_decision(exc.code)
        report["error"] = exc.to_safe_error()
        return report
    report["official_backend_called"] = True
    report["backend_status_code"] = status_code
    report["rate_limit_headers_present"] = _rate_limit_headers_present(headers)
    if status_code in {401, 403}:
        report["ok"] = False
        report["decision"] = _blocked_decision("staging_session_required")
        report["error"] = _safe_error(
            "staging_session_required",
            "The saved YonerAI staging session was not accepted by the sync preview API.",
            status_code=status_code,
        )
        report["backend_auth_required_confirmed"] = True
        return report
    if status_code >= 400:
        report["ok"] = False
        report["decision"] = _blocked_decision("staging_sync_preview_failed")
        report["error"] = _safe_error("staging_sync_preview_failed", "Staging sync preview request failed.", status_code=status_code)
        return report
    try:
        _assert_public_safe_payload(response)
        decision = response.get("decision") if isinstance(response.get("decision"), Mapping) else {}
        report["decision"] = _sanitize_decision(decision) if decision else _decision_from_preview_response(response)
        report["ok"] = bool(response.get("ok", report["decision"].get("state") == "allowed"))
        response_exclusion = response.get("private_content_exclusion")
        report["private_content_exclusion"] = (
            _sanitize_private_content_exclusion(response_exclusion)
            if isinstance(response_exclusion, Mapping)
            else _private_content_exclusion()
        )
    except StagingSyncServiceError as exc:
        report["ok"] = False
        report["decision"] = _blocked_decision(exc.code)
        report["error"] = exc.to_safe_error()
        return report
    report["sync_performed"] = False
    report["approval_recorded"] = False
    return report


def _auth_context(
    *,
    config: Mapping[str, object] | None,
    env: Mapping[str, str | None] | None,
    claim_path: str | None,
) -> dict[str, Any]:
    auth = build_google_auth_status(config, env=env, claim_path=claim_path)
    staging = auth.get("staging") if isinstance(auth.get("staging"), Mapping) else {}
    claim = auth.get("staging_session") if isinstance(auth.get("staging_session"), Mapping) else empty_staging_auth_claim()
    session_token, session_claim = load_staging_session_token(claim_path)
    if not isinstance(session_claim, Mapping):
        session_claim = empty_staging_session_claim()
    account = claim.get("account") if isinstance(claim.get("account"), Mapping) else {}
    auth_state = str(claim.get("auth_state") or auth.get("staging_auth_state") or "unauthenticated")
    if session_claim.get("auth_state") == "linked":
        auth_state = "linked"
        account = {
            "account_id": session_claim.get("account_id"),
            "display_name": session_claim.get("display_name"),
            "email_redacted": session_claim.get("redacted_email"),
        }
    return {
        "origin_configured": bool(staging.get("configured")),
        "origin": str(staging.get("origin") or "not_configured") if staging.get("configured") else "not_configured",
        "auth_state": auth_state,
        "linked_account": _sanitize_account(account),
        "staging_claim_present": auth_state == "linked",
        "staging_session_available": session_token is not None,
        "staging_session_claim": dict(session_claim),
        "session_token": session_token,
        "production_login_enabled": False,
        "shared_traffic_enabled": False,
    }


def _base_report(operation: str, context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": STAGING_SYNC_SCHEMA_VERSION,
        "ok": True,
        "operation": operation,
        "staging_origin_configured": bool(context["origin_configured"]),
        "staging_origin": context["origin"],
        "auth_state": context["auth_state"],
        "linked_account": context["linked_account"],
        "staging_claim_present": bool(context["staging_claim_present"]),
        "staging_session_available": bool(context["staging_session_available"]),
        "staging_session_storage": _sanitize_session_storage(context.get("staging_session_claim")),
        "production_login_enabled": False,
        "shared_traffic_enabled": False,
        "official_cloud_runtime_enabled": False,
        "production_oracle_enabled": False,
        "official_backend_called": False,
        "directions": {
            "cloud_to_local": {
                "supported_by_contract": True,
                "enabled_now": bool(context["staging_claim_present"]) and bool(context["staging_session_available"]),
                "requires": ["linked staging account", "user-selected cloud conversation", "account-required staging session"],
                "preview_only": True,
                "raw_private_content_uploaded": False,
            },
            "local_to_cloud": {
                "supported_by_contract": True,
                "enabled_by_default": False,
                "requires_explicit_approval": True,
                "private_file_content_excluded": True,
                "local_memory_excluded": True,
                "local_node_payload_excluded": True,
            },
        },
        "next_safe_commands": [
            "yonerai login",
            "yonerai sync conversations",
            "yonerai sync preview",
            "yonerai sync preview local-to-cloud",
        ],
        "actions_not_performed": _sync_non_actions(),
    }


def _get_json(
    origin: str,
    path: str,
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> Mapping[str, object]:
    status_code, body, _headers = _request_json(
        "GET",
        origin,
        path,
        {},
        None,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    if status_code >= 400:
        raise StagingSyncServiceError("staging_sync_source_failed", "Staging sync source request failed.", status_code=status_code)
    return body


def _request_json(
    method: str,
    origin: str,
    path: str,
    headers: Mapping[str, str],
    body: Mapping[str, object] | None,
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
    url = f"{origin}{path}"
    caller = transport or _default_header_json_transport
    status_code, payload, response_headers = caller(method, url, dict(headers), body, timeout_seconds)
    return status_code, payload, response_headers


def _auth_headers(context: Mapping[str, Any]) -> dict[str, str]:
    token = context.get("session_token")
    if not isinstance(token, str) or not token.strip():
        return {}
    return {"Authorization": f"Bearer {token}"}


def _default_header_json_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, object] | None,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
    data = None if body is None else json.dumps(dict(body)).encode("utf-8")
    request = Request(url, data=data, method=method.upper())
    request.add_header("Accept", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=timeout_seconds) as response:  # noqa: S310 - origin is allowlisted before use.
            return int(response.status), _read_json_body(response.read()), dict(response.headers)
    except HTTPError as exc:
        if 300 <= int(exc.code) < 400:
            raise StagingSyncServiceError(
                "staging_sync_redirect_forbidden",
                "Staging sync source attempted to redirect.",
                status_code=int(exc.code),
            ) from exc
        try:
            return int(exc.code), _read_json_body(exc.read()), dict(exc.headers)
        except StagingSyncServiceError:
            return int(exc.code), {}, dict(exc.headers)
    except (OSError, URLError) as exc:
        raise StagingSyncServiceError("staging_sync_unreachable", "Staging sync source is unreachable.") from exc


def _read_json_body(raw: bytes) -> Mapping[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StagingSyncServiceError("staging_sync_invalid_json", "Staging sync source returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise StagingSyncServiceError("staging_sync_invalid_json", "Staging sync source returned invalid JSON.")
    return value


def _sanitize_status_payload(payload: Mapping[str, object]) -> dict[str, object]:
    return {
        "status": _safe_text(payload.get("status"), fallback="unknown"),
        "contract_version": _safe_text(payload.get("contract_version"), fallback=None),
        "official_api_contract_version": _safe_text(payload.get("official_api_contract_version"), fallback=None),
        "production": False,
        "private_runtime_details_included": False,
    }


def _sanitize_rate_limit_payload(payload: Mapping[str, object]) -> dict[str, object]:
    conversation_sync = payload.get("conversation_sync") if isinstance(payload.get("conversation_sync"), Mapping) else {}
    return {
        "allowed": bool(payload.get("allowed", False)),
        "scope": _safe_text(payload.get("scope"), fallback="unknown"),
        "fallback_reason": _safe_text(payload.get("fallback_reason"), fallback="unknown"),
        "quota_exceeded": bool(payload.get("quota_exceeded", False)),
        "conversation_sync": {
            "mode": _safe_text(conversation_sync.get("mode"), fallback="staging"),
            "cloud_to_local": _safe_text(conversation_sync.get("cloud_to_local"), fallback="unknown"),
            "local_to_cloud": _safe_text(conversation_sync.get("local_to_cloud"), fallback="approval_required"),
            "shared_traffic": _safe_text(conversation_sync.get("shared_traffic"), fallback="off"),
        },
        "shared_traffic": _safe_text(payload.get("shared_traffic"), fallback="off"),
    }


def _sanitize_conversations(payload: Mapping[str, object]) -> list[dict[str, object]]:
    _assert_public_safe_payload(payload)
    raw = payload.get("conversations")
    if not isinstance(raw, list):
        raise StagingSyncServiceError("staging_conversations_invalid", "Staging conversations response is invalid.")
    conversations: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise StagingSyncServiceError("staging_conversations_invalid", "Staging conversations response is invalid.")
        extra_keys = set(item) - {
            "cloud_conversation_id",
            "conversation_id",
            "title",
            "selected_by_user",
            "created_at",
            "updated_at",
            "message_count",
            "privacy_class",
            "source",
            "sync_direction",
            "audit_reason",
            "account_id",
        }
        if extra_keys:
            raise StagingSyncServiceError(
                "staging_conversations_private_fields",
                "Staging conversations response contained non-public fields.",
            )
        conversation_id = item.get("cloud_conversation_id") or item.get("conversation_id")
        conversations.append(
            {
                "cloud_conversation_id": _safe_text(conversation_id, fallback="cloud-conversation-redacted"),
                "title": _safe_text(item.get("title"), fallback="cloud conversation"),
                "selected_by_user": bool(item.get("selected_by_user", False)),
                "created_at": _safe_text(item.get("created_at"), fallback=None),
                "updated_at": _safe_text(item.get("updated_at"), fallback=None),
                "message_count": int(item.get("message_count", 0)) if isinstance(item.get("message_count"), int) else 0,
                "privacy_class": _safe_text(item.get("privacy_class"), fallback="unknown"),
                "source": _safe_text(item.get("source"), fallback="staging"),
                "raw_body_included": False,
            }
        )
    return conversations


def _sanitize_conversation(payload: Mapping[str, object]) -> dict[str, object]:
    _assert_public_safe_payload(payload)
    raw = payload.get("conversation") if isinstance(payload.get("conversation"), Mapping) else payload
    if not isinstance(raw, Mapping):
        raise StagingSyncServiceError("staging_conversation_invalid", "Staging conversation response is invalid.")
    extra_keys = set(raw) - {
        "cloud_conversation_id",
        "conversation_id",
        "title",
        "selected_by_user",
        "summary",
        "created_at",
        "updated_at",
        "message_count",
        "privacy_class",
        "source",
        "sync_direction",
        "audit_reason",
        "account_id",
        "raw_body_included",
    }
    if extra_keys:
        raise StagingSyncServiceError(
            "staging_conversation_private_fields",
            "Staging conversation response contained non-public fields.",
        )
    conversation_id = raw.get("cloud_conversation_id") or raw.get("conversation_id")
    return {
        "cloud_conversation_id": _safe_text(conversation_id, fallback="cloud-conversation-redacted"),
        "title": _safe_text(raw.get("title"), fallback="cloud conversation"),
        "summary": _safe_text(raw.get("summary"), fallback="summary unavailable"),
        "selected_by_user": bool(raw.get("selected_by_user", False)),
        "created_at": _safe_text(raw.get("created_at"), fallback=None),
        "updated_at": _safe_text(raw.get("updated_at"), fallback=None),
        "message_count": int(raw.get("message_count", 0)) if isinstance(raw.get("message_count"), int) else 0,
        "privacy_class": _safe_text(raw.get("privacy_class"), fallback="unknown"),
        "source": _safe_text(raw.get("source"), fallback="staging"),
        "raw_body_included": False,
    }


def _sanitize_session_storage(claim: object) -> dict[str, object]:
    if not isinstance(claim, Mapping):
        return {"storage_backend": "none", "session_hash": None, "token_printed": False}
    return {
        "storage_backend": _safe_text(claim.get("storage_backend"), fallback="none"),
        "session_hash": _safe_text(claim.get("session_hash"), fallback=None),
        "token_printed": False,
        "google_token_stored": False,
        "google_access_token_stored": False,
        "google_refresh_token_stored": False,
        "plaintext_session_token_stored": False,
    }


def _sanitize_decision(decision: Mapping[str, object]) -> dict[str, object]:
    state = _safe_text(decision.get("state"), fallback="blocked")
    if state not in {"allowed", "blocked", "approval_required"}:
        state = "blocked"
    return {
        "state": state,
        "reason": _safe_text(decision.get("reason"), fallback="unknown"),
        "requires_explicit_approval": bool(decision.get("requires_explicit_approval", False)),
        "private_content_excluded": True,
    }


def _decision_from_preview_response(response: Mapping[str, object]) -> dict[str, object]:
    reasons = response.get("reasons") if isinstance(response.get("reasons"), list) else []
    reason = next((str(item) for item in reasons if isinstance(item, str) and item.strip()), None)
    allowed = bool(response.get("allowed", False))
    requires_approval = bool(response.get("requires_approval", False))
    if allowed:
        state = "allowed"
    elif requires_approval:
        state = "approval_required"
    else:
        state = "blocked"
    raw_flags = (
        bool(response.get("raw_content_included", False)),
        bool(response.get("raw_payload_logged", False)),
        bool(response.get("raw_prompt_logged", False)),
        bool(response.get("local_private_content_accepted", False)),
        bool(response.get("openai_shared_traffic_enabled", False)),
    )
    return {
        "state": state,
        "reason": _safe_text(reason or response.get("cloud_to_local") or response.get("local_to_cloud"), fallback="unknown"),
        "requires_explicit_approval": requires_approval,
        "private_content_excluded": not any(raw_flags),
    }


def _sanitize_private_content_exclusion(payload: Mapping[str, object]) -> dict[str, object]:
    default = _private_content_exclusion()
    sanitized = dict(default)
    for key in default:
        sanitized[key] = bool(payload.get(key, default[key]))
    return sanitized


def _sanitize_account(account: Mapping[str, object]) -> dict[str, object]:
    account_id = _safe_text(account.get("account_id") or account.get("account_ref"), fallback="not-linked")
    return {
        "account_id": account_id,
        "display_name": _safe_text(account.get("display_name"), fallback="not-linked"),
        "email_redacted": _safe_text(account.get("email_redacted"), fallback="not-linked"),
        "raw_email_stored": False,
        "raw_subject_stored": False,
    }


def _assert_public_safe_payload(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = serialized.lower()
    forbidden_markers = (
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "authorization_code",
        "google_token",
        "staging_session_token",
        "c:\\users",
        "\\\\",
        "/users/",
        "/home/",
        "/root/",
    )
    if any(marker in lowered for marker in forbidden_markers):
        raise StagingSyncServiceError(
            "staging_sync_private_payload_rejected",
            "Staging sync source returned non-public fields.",
        )


def _safe_text(value: object, *, fallback: str | None) -> str | None:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    lowered = text.lower()
    if any(marker in lowered for marker in ("access_token", "refresh_token", "client_secret", "authorization_code")):
        return fallback
    if any(marker in lowered for marker in ("c:\\users", "\\\\", "/users/", "/home/", "/root/")):
        return fallback
    return text[:180]


def _safe_conversation_id(value: object) -> str:
    text = _safe_text(value, fallback="cloud-conversation-fixture") or "cloud-conversation-fixture"
    sanitized = "".join(char for char in text if char.isalnum() or char in "-_.")
    if not sanitized:
        raise StagingSyncServiceError("staging_conversation_id_invalid", "Staging conversation id is invalid.")
    return sanitized[:120]


def _normalize_direction(direction: str) -> str:
    normalized = str(direction or "").strip().lower().replace("_", "-")
    if normalized not in SYNC_DIRECTIONS:
        raise StagingSyncServiceError("sync_direction_invalid", "Sync direction is invalid.")
    return SYNC_DIRECTIONS[normalized]


def _blocked_decision(reason: str) -> dict[str, object]:
    return {
        "state": "blocked",
        "reason": reason,
        "requires_explicit_approval": False,
        "private_content_excluded": True,
    }


def _safe_error(code: str, message: str, *, status_code: int | None = None) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "status_code": status_code,
        "private_endpoint_printed": False,
        "local_path_printed": False,
        "token_printed": False,
    }


def _rate_limit_headers_present(headers: Mapping[str, str]) -> list[str]:
    expected = {
        "x-yonerai-ratelimit-scope": "X-YonerAI-RateLimit-Scope",
        "x-yonerai-ratelimit-limit": "X-YonerAI-RateLimit-Limit",
        "x-yonerai-ratelimit-remaining": "X-YonerAI-RateLimit-Remaining",
        "x-yonerai-ratelimit-reset": "X-YonerAI-RateLimit-Reset",
        "x-yonerai-ratelimit-reason": "X-YonerAI-RateLimit-Reason",
    }
    normalized = {key.lower() for key in headers}
    return [public for key, public in expected.items() if key in normalized]


def _private_content_exclusion() -> dict[str, bool]:
    return {
        "raw_prompt_excluded": True,
        "private_file_content_excluded": True,
        "local_memory_excluded": True,
        "local_node_payload_excluded": True,
        "provider_keys_excluded": True,
        "local_absolute_paths_excluded": True,
        "openai_shared_traffic_excluded": True,
    }


def _sync_non_actions() -> list[str]:
    return [
        "no production Google login",
        "no Google token storage",
        "no refresh token storage",
        "no automatic local-to-cloud upload",
        "no private file content upload",
        "no local memory upload",
        "no local node payload upload",
        "no provider key upload",
        "no OpenAI shared traffic",
        "no production Oracle/cloud runtime",
    ]


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)
