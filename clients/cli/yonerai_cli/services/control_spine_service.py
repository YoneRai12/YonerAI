from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from yonerai_cli import __version__
from yonerai_cli.auth_policy import (
    STAGING_AUTH_ALLOW_LOCALHOST_DEV_ENV,
    build_google_auth_status,
    _env_truthy,
    _validate_staging_auth_origin,
)
from yonerai_cli.config import load_cli_config
from yonerai_cli.services.auth_session_service import sanitize_staging_account
from yonerai_cli.services.staging_session_service import load_staging_session_token


CONTROL_SPINE_SCHEMA_VERSION = "yonerai-control-spine-client/v0.1"
CONTRACT_VERSION_POLICY = "yonerai-official-api-contract/v0.14"
DEFAULT_STAGING_CONTROL_SPINE_ORIGIN = "https://api-staging.yonerai.com"
STATUS_PATH = "/v1/status"
HEALTH_PATH = "/v1/health"
RATE_LIMIT_PATH = "/v1/rate-limit"
WHOAMI_PATH = "/v1/whoami"
ACCOUNT_ME_PATH = "/v1/account/me"
PING_PATH = "/v1/ping"
PROJECTS_PATH = "/v1/projects"
PROJECT_CURRENT_PATH = "/v1/projects/current"
PROJECT_USE_PATH = "/v1/projects/current"
SESSIONS_PATH = "/v1/sessions"
SESSION_REVOKE_PATH_TEMPLATE = "/v1/sessions/{session_id}/revoke"
AUDIT_EVENTS_PATH = "/v1/audit/events"
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,120}$")
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,160}$")
PRIVATE_URL_RE = re.compile(
    r"https?://(?:localhost\b|10\.|127\.|169\.254\.|192\.168\.|"
    r"172\.(?:1[6-9]|2[0-9]|3[0-1])\.|\[::1\])",
    re.IGNORECASE,
)
PUBLIC_PAYLOAD_FORBIDDEN_MARKERS = (
    "access_token",
    "refresh_token",
    "id_token",
    "client_secret",
    "authorization",
    "authorization_code",
    "google_token",
    "staging_session_token",
    "session_token",
    "api_key",
    "password",
    "bearer",
    "secret",
    "token",
    "c:\\users",
    "\\\\",
    "/users/",
    "/home/",
    "/root/",
    "arn:",
    "internal_hostname",
    "worker_identity",
    "account_id",
    "169.254.169.254",
)

HeaderJsonTransport = Callable[
    [str, str, Mapping[str, str], Mapping[str, object] | None, float],
    tuple[int, Mapping[str, object], Mapping[str, str]],
]


class ControlSpineServiceError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code

    def to_safe_error(self) -> dict[str, object]:
        return _safe_error(self.code, self.message, status_code=self.status_code)


def build_control_spine_context(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
) -> dict[str, object]:
    source = _control_spine_env(env)
    auth = build_google_auth_status(config or {}, env=source, claim_path=claim_path)
    staging = auth.get("staging") if isinstance(auth.get("staging"), Mapping) else {}
    session_token, session_claim = load_staging_session_token(claim_path)
    session_claim_map = session_claim if isinstance(session_claim, Mapping) else {}
    session_origin_raw = str(session_claim_map.get("origin") or "").strip()
    session_origin = _validated_session_origin(session_origin_raw, source)
    origin_configured = bool(staging.get("configured")) or bool(session_token and session_origin)
    if bool(staging.get("configured")):
        origin = str(staging.get("origin") or "not_configured")
    elif session_token and session_origin:
        origin = session_origin
    else:
        origin = "not_configured"
    auth_state = str(session_claim_map.get("auth_state") or auth.get("staging_auth_state") or "unauthenticated")
    return {
        "origin_configured": origin_configured,
        "origin": origin,
        "auth_state": auth_state,
        "account_linked": bool(session_token and auth_state == "linked"),
        "session_available": session_token is not None,
        "session_token": session_token,
        "session_claim": dict(session_claim_map),
        "session_origin_valid": bool(session_origin),
        "session_origin_mismatch": bool(
            session_token
            and session_origin_raw
            and session_origin_raw not in {"configured", "not_configured"}
            and not session_origin
        ),
        "session_schema_mismatch": bool(
            session_token
            and not session_origin
            and session_origin_raw not in {"configured", "not_configured"}
        ),
        "production_login_enabled": False,
        "production_backend_enabled": False,
        "shared_traffic_enabled": False,
        "local_private_upload_enabled": False,
    }


def _validated_session_origin(value: object, env: Mapping[str, str | None]) -> str:
    raw_origin = str(value or "").strip()
    if not raw_origin:
        return ""
    localhost_dev_allowed = _env_truthy(env.get(STAGING_AUTH_ALLOW_LOCALHOST_DEV_ENV))
    report = _validate_staging_auth_origin(raw_origin, localhost_dev_allowed=localhost_dev_allowed)
    if not report.get("valid"):
        return ""
    return str(report.get("origin") or "").strip()


def build_control_spine_status_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = build_control_spine_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("api_status", context)
    if not context["origin_configured"]:
        report["ok"] = True
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    status = _safe_get(context, STATUS_PATH, transport=transport, timeout_seconds=timeout_seconds)
    health = _safe_get(context, HEALTH_PATH, transport=transport, timeout_seconds=timeout_seconds)
    rate_limit = _safe_get(context, RATE_LIMIT_PATH, transport=transport, timeout_seconds=timeout_seconds)
    report["official_backend_called"] = bool(
        status.get("official_backend_called")
        or health.get("official_backend_called")
        or rate_limit.get("official_backend_called")
    )
    report["backend_status"] = status
    report["health"] = health
    report["rate_limit"] = rate_limit
    report["scopes"] = _scopes_from_rate_limit(rate_limit.get("body") if isinstance(rate_limit.get("body"), Mapping) else {})
    report["contract_skew"] = _contract_skew_from_health(
        health.get("body") if isinstance(health.get("body"), Mapping) else {}
    )
    report["control_spine"] = _control_spine_from_status(
        status.get("body") if isinstance(status.get("body"), Mapping) else {},
        rate_limit.get("body") if isinstance(rate_limit.get("body"), Mapping) else {},
        health.get("body") if isinstance(health.get("body"), Mapping) else {},
    )
    return report


def build_control_spine_rate_limit_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = build_control_spine_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("api_rate_limit", context)
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    rate_limit = _safe_get(context, RATE_LIMIT_PATH, transport=transport, timeout_seconds=timeout_seconds)
    report["official_backend_called"] = bool(rate_limit.get("official_backend_called"))
    report["rate_limit"] = rate_limit
    report["scopes"] = _scopes_from_rate_limit(rate_limit.get("body") if isinstance(rate_limit.get("body"), Mapping) else {})
    report["ok"] = bool(rate_limit.get("ok"))
    if rate_limit.get("error"):
        report["error"] = rate_limit["error"]
    return report


def build_control_spine_ping_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = build_control_spine_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("api_ping", context)
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    result = _safe_get(context, PING_PATH, transport=transport, timeout_seconds=timeout_seconds, auth=True)
    report["official_backend_called"] = bool(result.get("official_backend_called"))
    report["backend_status_code"] = result.get("status_code")
    report["rate_limit_headers_present"] = result.get("rate_limit_headers_present", [])
    if result.get("ok"):
        body = result.get("body") if isinstance(result.get("body"), Mapping) else {}
        report["ping"] = {
            "ok": True,
            "message": _safe_text(body.get("message") or body.get("status"), fallback="pong"),
        }
        return report
    report["ok"] = False
    report["error"] = result.get("error") or _safe_error("api_ping_failed", "Staging API ping failed.")
    return report


def build_whoami_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = build_control_spine_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("whoami", context)
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if not context["session_available"]:
        report["ok"] = False
        report["error"] = _auth_required_error("Staging login is required before whoami.")
        return report
    result = _safe_get(context, WHOAMI_PATH, transport=transport, timeout_seconds=timeout_seconds, auth=True)
    if result.get("status_code") == 404:
        result = _safe_get(context, ACCOUNT_ME_PATH, transport=transport, timeout_seconds=timeout_seconds, auth=True)
    report["official_backend_called"] = bool(result.get("official_backend_called"))
    report["backend_status_code"] = result.get("status_code")
    report["rate_limit_headers_present"] = result.get("rate_limit_headers_present", [])
    if not result.get("ok"):
        report["ok"] = False
        report["error"] = result.get("error") or _safe_error("account_me_failed", "Staging account check failed.")
        return report
    body = result.get("body") if isinstance(result.get("body"), Mapping) else {}
    account_source = body.get("account") or body.get("identity") or body.get("profile") or body
    report["account"] = sanitize_staging_account(account_source if isinstance(account_source, Mapping) else {})
    report["account_linked"] = True
    return report


def build_project_report(
    command: str,
    *,
    project_id: str | None = None,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = build_control_spine_context(config=config, env=env, claim_path=claim_path)
    report = _base_report(f"project_{command}", context)
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if not context["session_available"]:
        report["ok"] = False
        report["error"] = _auth_required_error("Staging login is required before reading projects.")
        return report
    method = "GET"
    path = PROJECTS_PATH
    body = None
    if command == "current":
        path = PROJECT_CURRENT_PATH
    elif command == "use":
        safe_project_id = _safe_project_id(project_id)
        method = "POST"
        path = PROJECT_USE_PATH
        body = {"project_id": safe_project_id}
        report["requested_project_id"] = safe_project_id
    elif command != "list":
        raise ControlSpineServiceError("project_command_invalid", "Project command is invalid.")
    result = _safe_request(context, method, path, body, transport=transport, timeout_seconds=timeout_seconds, auth=True)
    report["official_backend_called"] = bool(result.get("official_backend_called"))
    report["backend_status_code"] = result.get("status_code")
    report["rate_limit_headers_present"] = result.get("rate_limit_headers_present", [])
    if not result.get("ok"):
        report["ok"] = False
        report["error"] = result.get("error") or _safe_error("project_api_failed", "Staging project API request failed.")
        return report
    response = result.get("body") if isinstance(result.get("body"), Mapping) else {}
    if command == "list":
        report["projects"] = _sanitize_projects(response)
        report["current_project"] = _first_current_project(report["projects"])
    else:
        report["project"] = _sanitize_project(
            response.get("project") if isinstance(response.get("project"), Mapping) else response
        )
    return report


def build_session_report(
    command: str,
    *,
    session_id: str | None = None,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = build_control_spine_context(config=config, env=env, claim_path=claim_path)
    report = _base_report(f"session_{command}", context)
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if not context["session_available"]:
        report["ok"] = False
        report["error"] = _auth_required_error("Staging login is required before reading sessions.")
        return report
    method = "GET"
    path = SESSIONS_PATH
    body = None
    if command == "revoke":
        safe_session_id = _safe_session_id(session_id)
        method = "POST"
        path = SESSION_REVOKE_PATH_TEMPLATE.format(session_id=quote(safe_session_id, safe=""))
        body = {"session_id": safe_session_id}
        report["requested_session_id"] = safe_session_id
    elif command != "list":
        raise ControlSpineServiceError("session_command_invalid", "Session command is invalid.")
    result = _safe_request(context, method, path, body, transport=transport, timeout_seconds=timeout_seconds, auth=True)
    report["official_backend_called"] = bool(result.get("official_backend_called"))
    report["backend_status_code"] = result.get("status_code")
    report["rate_limit_headers_present"] = result.get("rate_limit_headers_present", [])
    if not result.get("ok"):
        report["ok"] = False
        report["error"] = result.get("error") or _safe_error("session_api_failed", "Staging session API request failed.")
        return report
    response = result.get("body") if isinstance(result.get("body"), Mapping) else {}
    if command == "list":
        report["sessions"] = _sanitize_sessions(response)
    else:
        report["revoked"] = bool(response.get("revoked", True))
        report["session"] = _sanitize_session(
            response.get("session") if isinstance(response.get("session"), Mapping) else response
        )
    return report


def build_audit_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = build_control_spine_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("audit_list", context)
    if not context["origin_configured"]:
        report["ok"] = False
        report["error"] = _safe_error("staging_origin_not_configured", "Staging API origin is not configured.")
        return report
    if not context["session_available"]:
        report["ok"] = False
        report["error"] = _auth_required_error("Staging login is required before reading audit events.")
        return report
    result = _safe_get(context, AUDIT_EVENTS_PATH, transport=transport, timeout_seconds=timeout_seconds, auth=True)
    report["official_backend_called"] = bool(result.get("official_backend_called"))
    report["backend_status_code"] = result.get("status_code")
    report["rate_limit_headers_present"] = result.get("rate_limit_headers_present", [])
    if result.get("status_code") == 404:
        report["ok"] = False
        report["error"] = _safe_error("audit_not_available", "Sanitized audit API is not available on this staging backend.", status_code=404)
        return report
    if not result.get("ok"):
        report["ok"] = False
        report["error"] = result.get("error") or _safe_error("audit_api_failed", "Staging audit API request failed.")
        return report
    response = result.get("body") if isinstance(result.get("body"), Mapping) else {}
    report["events"] = _sanitize_audit_events(response)
    return report


def _base_report(operation: str, context: Mapping[str, object]) -> dict[str, object]:
    session_claim = context.get("session_claim") if isinstance(context.get("session_claim"), Mapping) else {}
    linked_claim_account = session_claim.get("account") if isinstance(session_claim.get("account"), Mapping) else {}
    linked_claim_display_name = linked_claim_account.get("display_name") or session_claim.get("display_name")
    linked_claim_email = (
        linked_claim_account.get("email_redacted")
        or linked_claim_account.get("redacted_email")
        or session_claim.get("email_redacted")
        or session_claim.get("redacted_email")
    )
    return {
        "schema_version": CONTROL_SPINE_SCHEMA_VERSION,
        "ok": True,
        "operation": operation,
        "staging_only": True,
        "backend_url": context.get("origin"),
        "staging_origin_configured": bool(context.get("origin_configured")),
        "auth_state": context.get("auth_state"),
        "account_linked": bool(context.get("account_linked")),
        "staging_session_available": bool(context.get("session_available")),
        "session_expires_at": _safe_text(session_claim.get("expires_at"), fallback=None),
        "linked_claim_account": {
            "display_name": _safe_text(linked_claim_display_name, fallback="not-linked"),
            "email_redacted": _safe_text(linked_claim_email, fallback="not-linked"),
        },
        "session_storage": {
            "storage_backend": _safe_text(session_claim.get("storage_backend"), fallback="none"),
            "session_hash": _safe_text(session_claim.get("session_hash"), fallback=None),
            "token_printed": False,
            "google_token_stored": False,
            "refresh_token_stored": False,
            "plaintext_session_token_stored": False,
        },
        "official_backend_called": False,
        "production_login_enabled": False,
        "production_backend_enabled": False,
        "production_oracle_enabled": False,
        "contract_version_policy": CONTRACT_VERSION_POLICY,
        "shared_traffic_enabled": False,
        "local_private_upload_enabled": False,
        "raw_prompt_upload_enabled": False,
        "next_safe_commands": [
            "yonerai login",
            "yonerai whoami",
            "yonerai projects",
            "yonerai sessions",
            "yonerai ping",
        ],
        "actions_not_performed": [
            "no production Google login",
            "no Google token storage",
            "no refresh token storage",
            "no OpenAI shared traffic",
            "no local private upload",
            "no production Oracle/cloud runtime",
            "no arbitrary shell or file execution",
        ],
    }


def _control_spine_env(env: Mapping[str, str | None] | None) -> dict[str, str | None]:
    return dict(env or {})


def _safe_get(
    context: Mapping[str, object],
    path: str,
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
    auth: bool = False,
) -> dict[str, object]:
    return _safe_request(context, "GET", path, None, transport=transport, timeout_seconds=timeout_seconds, auth=auth)


def _safe_request(
    context: Mapping[str, object],
    method: str,
    path: str,
    body: Mapping[str, object] | None,
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
    auth: bool,
) -> dict[str, object]:
    try:
        status_code, payload, headers = _request_json(
            method,
            str(context["origin"]),
            path,
            _auth_headers(context) if auth else {},
            body,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
        if status_code in {401, 403}:
            return {
                "ok": False,
                "official_backend_called": True,
                "status_code": status_code,
                "body": {},
                "error": _auth_error_for_response(context, payload, status_code=status_code),
                "rate_limit_headers_present": _rate_limit_headers_present(headers),
            }
        payload = _public_payload_for_path(path, payload)
        _assert_public_safe_payload(payload)
    except ControlSpineServiceError as exc:
        return {
            "ok": False,
            "official_backend_called": True,
            "status_code": exc.status_code,
            "error": exc.to_safe_error(),
            "body": {},
            "rate_limit_headers_present": [],
        }
    ok = 200 <= status_code < 300
    error = None if ok else _error_from_status(status_code, payload)
    return {
        "ok": ok,
        "official_backend_called": True,
        "status_code": status_code,
        "body": payload if ok else {},
        "error": error,
        "rate_limit_headers_present": _rate_limit_headers_present(headers),
    }


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
    caller = transport or _default_header_json_transport
    return caller(method, f"{origin}{path}", dict(headers), body, timeout_seconds)


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
        with _NO_REDIRECT_OPENER.open(request, timeout=timeout_seconds) as response:  # noqa: S310 - origin is allowlisted by auth policy.
            return int(response.status), _read_json_body(response.read()), dict(response.headers)
    except HTTPError as exc:
        if 300 <= int(exc.code) < 400:
            raise ControlSpineServiceError(
                "control_spine_redirect_forbidden",
                "Staging API attempted to redirect.",
                status_code=int(exc.code),
            ) from exc
        try:
            return int(exc.code), _read_json_body(exc.read()), dict(exc.headers)
        except ControlSpineServiceError:
            return int(exc.code), {}, dict(exc.headers)
    except (OSError, URLError) as exc:
        raise ControlSpineServiceError("control_spine_unreachable", "Staging API is unreachable.") from exc


def _read_json_body(raw: bytes) -> Mapping[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControlSpineServiceError("control_spine_invalid_json", "Staging API returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise ControlSpineServiceError("control_spine_invalid_json", "Staging API returned invalid JSON.")
    return value


def _auth_headers(context: Mapping[str, object]) -> dict[str, str]:
    token = context.get("session_token")
    if not isinstance(token, str) or not token.strip():
        return {}
    return {"Authorization": f"Bearer {token}"}


def _error_from_status(status_code: int, payload: Mapping[str, object]) -> dict[str, object]:
    reason = "request_failed"
    detail = payload.get("detail")
    if isinstance(detail, Mapping):
        reason = _safe_text(detail.get("reason"), fallback=reason) or reason
    elif isinstance(detail, str):
        reason = _safe_text(detail, fallback=reason) or reason
    if status_code in {401, 403}:
        return _auth_error_for_response({}, payload, status_code=status_code)
    if status_code == 404:
        return _safe_error("control_spine_not_available", "This staging control spine endpoint is not available.", status_code=status_code)
    return _safe_error(str(reason), "Staging control spine request failed.", status_code=status_code)


def _control_spine_from_status(
    status_payload: Mapping[str, object],
    rate_payload: Mapping[str, object],
    health_payload: Mapping[str, object],
) -> dict[str, object]:
    status_control = status_payload.get("control_spine") if isinstance(status_payload.get("control_spine"), Mapping) else {}
    rate_control = rate_payload.get("control_spine") if isinstance(rate_payload.get("control_spine"), Mapping) else {}
    health_control = health_payload.get("control_spine") if isinstance(health_payload.get("control_spine"), Mapping) else {}
    return {
        "contract_version": _safe_text(
            health_payload.get("api_version") or rate_control.get("contract_version"),
            fallback="yonerai.control-spine.v0.1",
        ),
        "contract_version_policy": CONTRACT_VERSION_POLICY,
        "api_version": _safe_text(health_payload.get("api_version"), fallback="unknown"),
        "min_cli_version": _safe_text(health_payload.get("min_cli_version"), fallback="unknown"),
        "status": _safe_text(status_control.get("status"), fallback=status_payload.get("status") or "unknown"),
        "mode": _safe_text(health_control.get("mode") or status_control.get("mode"), fallback="staging"),
        "sessions": _safe_text(status_control.get("sessions"), fallback="unknown"),
        "revoke": _safe_text(status_control.get("revoke"), fallback="unknown"),
        "projects": _safe_text(status_control.get("projects"), fallback="unknown"),
        "audit": _safe_text(status_control.get("audit"), fallback="unknown"),
        "admin_scope": _safe_text(status_control.get("admin_scope"), fallback="disabled_by_default"),
        "shared_traffic": _safe_text(status_control.get("shared_traffic"), fallback="off"),
    }


def _scopes_from_rate_limit(payload: Mapping[str, object]) -> list[dict[str, object]]:
    control = payload.get("control_spine") if isinstance(payload.get("control_spine"), Mapping) else {}
    raw = control.get("scopes") if isinstance(control.get("scopes"), list) else []
    scopes: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        name = _safe_scope(item.get("name"))
        frozen = _dangerous_scope_freeze(name)
        scopes.append(
            {
                "name": name,
                "enabled_by_default": False if frozen else bool(item.get("enabled_by_default")),
                "summary": _safe_text(item.get("summary"), fallback=""),
                "requires_threat_model": bool(frozen),
                "disabled_reason": "dangerous_scope_freeze" if frozen else None,
            }
        )
    return scopes


def _contract_skew_from_health(payload: Mapping[str, object]) -> dict[str, object]:
    api_version = _safe_text(payload.get("api_version"), fallback="unknown")
    min_cli_version = _safe_text(payload.get("min_cli_version"), fallback=None)
    current = _safe_text(__version__, fallback="unknown")
    missing_fields = [
        field for field in ("api_version", "min_cli_version") if not isinstance(payload.get(field), str) or not str(payload.get(field)).strip()
    ]
    below_minimum = False
    if isinstance(min_cli_version, str):
        below_minimum = _version_tuple(str(current)) < _version_tuple(min_cli_version)
    return {
        "api_version": api_version,
        "min_cli_version": min_cli_version or "unknown",
        "current_cli_version": current,
        "policy": CONTRACT_VERSION_POLICY,
        "missing_fields": missing_fields,
        "missing_field_policy": "debug_only_no_user_warning",
        "skew_detected": below_minimum,
        "warning": (
            "YonerAI CLI is older than the staging API minimum. Run `yonerai update` and re-login if needed."
            if below_minimum
            else None
        ),
    }


def _dangerous_scope_freeze(scope: str) -> bool:
    return scope == "agent:run" or scope.startswith("admin:")


def _version_tuple(value: str) -> tuple[int, int, int, int]:
    text = value.strip().lstrip("v")
    main = text.split("-", 1)[0]
    parts = []
    for piece in main.split(".")[:4]:
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    while len(parts) < 4:
        parts.append(0)
    return (parts[0], parts[1], parts[2], parts[3])


def _sanitize_projects(payload: Mapping[str, object]) -> list[dict[str, object]]:
    raw = payload.get("projects") if isinstance(payload.get("projects"), list) else []
    return [_sanitize_project(item) for item in raw if isinstance(item, Mapping)]


def _sanitize_project(project: Mapping[str, object]) -> dict[str, object]:
    scopes = project.get("scopes") if isinstance(project.get("scopes"), list) else []
    return {
        "project_id": _safe_text(project.get("project_id") or project.get("id"), fallback="personal-staging"),
        "name": _safe_text(project.get("name") or project.get("display_name"), fallback="personal staging"),
        "current": bool(project.get("current", False)),
        "billing_enabled": bool(project.get("billing_enabled", False)),
        "scopes": [_safe_scope(scope) for scope in scopes],
        "raw_private_content_included": False,
    }


def _first_current_project(projects: object) -> dict[str, object]:
    if not isinstance(projects, list):
        return {}
    for project in projects:
        if isinstance(project, Mapping) and project.get("current"):
            return dict(project)
    return dict(projects[0]) if projects and isinstance(projects[0], Mapping) else {}


def _sanitize_sessions(payload: Mapping[str, object]) -> list[dict[str, object]]:
    raw = payload.get("sessions") if isinstance(payload.get("sessions"), list) else []
    return [_sanitize_session(item) for item in raw if isinstance(item, Mapping)]


def _sanitize_session(session: Mapping[str, object]) -> dict[str, object]:
    scopes = session.get("scopes") if isinstance(session.get("scopes"), list) else []
    return {
        "session_id": _safe_text(session.get("session_id") or session.get("id"), fallback="session-redacted"),
        "status": _safe_text(session.get("status"), fallback="unknown"),
        "current": bool(session.get("current", False)),
        "created_at": _safe_text(session.get("created_at"), fallback=None),
        "expires_at": _safe_text(session.get("expires_at"), fallback=None),
        "scopes": [_safe_scope(scope) for scope in scopes],
        "token_included": False,
    }


def _sanitize_audit_events(payload: Mapping[str, object]) -> list[dict[str, object]]:
    raw = payload.get("events") if isinstance(payload.get("events"), list) else []
    events: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        events.append(
            {
                "event_id": _safe_text(item.get("event_id") or item.get("id"), fallback="event-redacted"),
                "event_type": _safe_text(item.get("event_type") or item.get("type"), fallback="unknown"),
                "created_at": _safe_text(item.get("created_at"), fallback=None),
                "summary": _safe_text(item.get("summary"), fallback="sanitized audit event"),
                "raw_prompt_included": False,
                "private_content_included": False,
            }
        )
    return events


def _safe_project_id(value: object) -> str:
    text = str(value or "").strip()
    if not PROJECT_ID_RE.fullmatch(text):
        raise ControlSpineServiceError("project_id_invalid", "Project id is invalid.")
    return text


def _safe_session_id(value: object) -> str:
    text = str(value or "").strip()
    if not SESSION_ID_RE.fullmatch(text):
        raise ControlSpineServiceError("session_id_invalid", "Session id is invalid.")
    return text


def _safe_scope(value: object) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"[a-z][a-z0-9:*_-]{1,80}", text):
        return "scope:redacted"
    return text


def _safe_text(value: object, *, fallback: object) -> object:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    lowered = text.lower()
    if _contains_forbidden_public_marker(lowered):
        return fallback
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return fallback
    return text[:240]


def _public_account_payload(payload: Mapping[str, object]) -> Mapping[str, object]:
    account_source = payload.get("account") or payload.get("identity") or payload.get("profile") or payload
    if not isinstance(account_source, Mapping):
        account_source = {}
    return {"account": sanitize_staging_account(account_source)}


def _public_payload_for_path(path: str, payload: Mapping[str, object]) -> Mapping[str, object]:
    if path in {WHOAMI_PATH, ACCOUNT_ME_PATH}:
        return _public_account_payload(payload)
    if path != RATE_LIMIT_PATH:
        return payload
    allowed_top_level = {
        "allowed",
        "scope",
        "fallback_reason",
        "retry_after_seconds",
        "quota_exceeded",
        "api_gateway_usage_plan_is_cost_control_boundary",
        "contract_version",
        "conversation_sync",
        "shared_traffic",
        "control_spine",
    }
    private_known_drop = {"cost_guard"}
    unknown = {
        key: value
        for key, value in payload.items()
        if key not in allowed_top_level and key not in private_known_drop
    }
    if unknown:
        _assert_public_safe_payload(unknown)

    control = payload.get("control_spine") if isinstance(payload.get("control_spine"), Mapping) else {}
    raw_scopes = control.get("scopes") if isinstance(control.get("scopes"), list) else []
    raw_admin_disabled = control.get("admin_scopes_disabled")
    admin_disabled = raw_admin_disabled if isinstance(raw_admin_disabled, list) else []
    raw_session_scopes = control.get("session_scopes")
    session_scopes = raw_session_scopes if isinstance(raw_session_scopes, list) else []
    public_control = {
        "contract_version": _safe_text(control.get("contract_version"), fallback="unknown"),
        "admin_scopes_disabled": [
            _safe_scope(item) for item in admin_disabled if isinstance(item, str)
        ],
        "session_scopes": [
            _safe_scope(item) for item in session_scopes if isinstance(item, str)
        ],
        "scopes": [
            {
                "name": _safe_scope(item.get("name")) if isinstance(item.get("name"), str) else "scope:redacted",
                "enabled_by_default": bool(item.get("enabled_by_default")),
                "summary": _safe_text(item.get("summary"), fallback=""),
            }
            for item in raw_scopes
            if isinstance(item, Mapping)
        ],
    }
    conversation_sync = (
        payload.get("conversation_sync") if isinstance(payload.get("conversation_sync"), Mapping) else {}
    )
    public_conversation_sync = {
        "mode": _safe_text(conversation_sync.get("mode"), fallback="unknown"),
        "cloud_to_local": _safe_text(conversation_sync.get("cloud_to_local"), fallback="unknown"),
        "local_to_cloud": _safe_text(conversation_sync.get("local_to_cloud"), fallback="unknown"),
        "shared_traffic": _safe_text(conversation_sync.get("shared_traffic"), fallback="off"),
    }
    return {
        "allowed": bool(payload.get("allowed")),
        "scope": _safe_text(payload.get("scope"), fallback="unknown"),
        "fallback_reason": _safe_text(payload.get("fallback_reason"), fallback="unknown"),
        "retry_after_seconds": (
            payload.get("retry_after_seconds")
            if isinstance(payload.get("retry_after_seconds"), int)
            else None
        ),
        "quota_exceeded": bool(payload.get("quota_exceeded")),
        "api_gateway_usage_plan_is_cost_control_boundary": bool(
            payload.get("api_gateway_usage_plan_is_cost_control_boundary")
        ),
        "contract_version": _safe_text(payload.get("contract_version"), fallback="unknown"),
        "conversation_sync": public_conversation_sync,
        "shared_traffic": _safe_text(payload.get("shared_traffic"), fallback="off"),
        "control_spine": public_control,
    }


def _assert_public_safe_payload(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    if _contains_forbidden_public_marker(serialized):
        raise ControlSpineServiceError(
            "control_spine_private_payload_rejected",
            "Staging control spine returned non-public fields.",
        )


def _contains_forbidden_public_marker(text: str) -> bool:
    return any(marker in text for marker in PUBLIC_PAYLOAD_FORBIDDEN_MARKERS) or bool(PRIVATE_URL_RE.search(text))


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


def _safe_error(code: str, message: str, *, status_code: int | None = None) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "status_code": status_code,
        "private_endpoint_printed": False,
        "local_path_printed": False,
        "token_printed": False,
        "google_token_printed": False,
    }


def _auth_required_error(message: str, *, status_code: int | None = None) -> dict[str, object]:
    error = _safe_error("staging_auth_required", message, status_code=status_code)
    error["next_safe_command"] = "yonerai login"
    return error


def _auth_error_for_response(
    context: Mapping[str, object],
    payload: Mapping[str, object],
    *,
    status_code: int,
) -> dict[str, object]:
    reason = _safe_reason_from_payload(payload)
    auth_state = str(context.get("auth_state") or "unauthenticated")
    session_available = bool(context.get("session_available"))
    if auth_state == "expired" or reason in {"expired", "session_expired", "staging_session_expired"}:
        error = _safe_error("staging_session_expired", "Saved staging session expired. Run `yonerai login` again.", status_code=status_code)
    elif auth_state == "revoked" or reason in {"revoked", "session_revoked", "staging_session_revoked"}:
        error = _safe_error("staging_session_revoked", "Saved staging session was revoked. Run `yonerai login` again.", status_code=status_code)
    elif session_available:
        error = _safe_error(
            "staging_session_rejected",
            "Saved staging session was rejected by the staging backend. Run `yonerai logout` and then `yonerai login`.",
            status_code=status_code,
        )
        error["backend_reason"] = reason
        error["session_origin_mismatch"] = bool(context.get("session_origin_mismatch"))
        error["session_schema_mismatch"] = bool(context.get("session_schema_mismatch"))
    else:
        error = _auth_required_error("Staging login is required before this command.", status_code=status_code)
    error["next_safe_command"] = "yonerai login"
    error["repair_command"] = "yonerai logout && yonerai login"
    return error


def _safe_reason_from_payload(payload: Mapping[str, object]) -> str:
    detail = payload.get("detail") if isinstance(payload.get("detail"), Mapping) else payload
    reason = detail.get("reason") if isinstance(detail, Mapping) else None
    return str(_safe_text(reason, fallback="auth_rejected"))


def load_config_for_control_spine(config_path: str | None) -> dict[str, object]:
    return load_cli_config(config_path)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)
