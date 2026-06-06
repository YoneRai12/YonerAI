from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from yonerai_cli.services.auth_session_service import sanitize_staging_account


CLI_BRIDGE_START_PATH = "/auth/cli/start"
CLI_BRIDGE_POLL_PATH_TEMPLATE = "/auth/cli/poll/{request_id}"
GOOGLE_BROWSER_START_PATH = "/auth/google/start"
GOOGLE_CALLBACK_PATH = "/api/auth/callback/google"
ACCOUNT_ME_PATH = "/v1/account/me"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,160}$")
_FORBIDDEN_TOKEN_KEYS = {
    "google_token",
    "id_token",
    "access_token",
    "refresh_token",
    "authorization_code",
    "code_verifier",
    "client_secret",
    "api_key",
}
_FORBIDDEN_QUERY_PARAM_KEYS = _FORBIDDEN_TOKEN_KEYS | {
    "code",
    "auth_code",
    "token",
    "session",
    "session_token",
    "staging_session_token",
    "staging_session_claim",
    "secret",
}

JsonTransport = Callable[[str, str, Mapping[str, object] | None, float], tuple[int, Mapping[str, object]]]
HeaderJsonTransport = Callable[
    [str, str, Mapping[str, str], Mapping[str, object] | None, float],
    tuple[int, Mapping[str, object]],
]
SessionClaimHandler = Callable[[str, Mapping[str, object], Mapping[str, object]], Mapping[str, object]]


class StagingAuthBridgeError(ValueError):
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
            "token_printed": False,
        }


def start_cli_bridge(
    origin: str,
    *,
    transport: JsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    caller = transport or _default_json_transport
    status_code, body = caller("POST", _join_origin_path(origin, CLI_BRIDGE_START_PATH), None, timeout_seconds)
    if status_code >= 400:
        raise StagingAuthBridgeError("staging_bridge_start_failed", "Staging CLI bridge start failed.", status_code=status_code)
    _assert_no_token_return(body)
    request_id = _safe_request_id(body.get("request_id"))
    browser_start_path = _safe_relative_path(body.get("browser_start_path"), "browser_start_path")
    poll_path = _safe_relative_path(body.get("poll_path"), "poll_path")
    if browser_start_path != GOOGLE_BROWSER_START_PATH and not browser_start_path.startswith(f"{GOOGLE_BROWSER_START_PATH}?"):
        raise StagingAuthBridgeError("staging_bridge_browser_start_path_invalid", "Staging CLI bridge start path is invalid.")
    if not poll_path.startswith("/auth/cli/poll/"):
        raise StagingAuthBridgeError("staging_bridge_poll_path_invalid", "Staging CLI bridge poll path is invalid.")
    return {
        "status": str(body.get("status") or "created"),
        "request_id": request_id,
        "expires_at": _safe_optional_public_scalar(body.get("expires_at"), "expires_at"),
        "browser_start_path": browser_start_path,
        "browser_start_url": _join_origin_path(origin, browser_start_path),
        "poll_path": poll_path,
        "poll_url": _join_origin_path(origin, poll_path),
        "google_token_returned": False,
        "refresh_token_returned": False,
        "staging_session_token_printed": False,
    }


def poll_cli_bridge(
    origin: str,
    request_id: str,
    *,
    transport: JsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    safe_request_id, body = _poll_cli_bridge_body(
        origin,
        request_id,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    return _safe_poll_report(safe_request_id, body)


def wait_for_cli_bridge_link(
    origin: str,
    request_id: str,
    *,
    transport: JsonTransport | None = None,
    account_transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
    max_wait_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
    fetch_account: bool = True,
    session_claim_handler: SessionClaimHandler | None = None,
) -> dict[str, object]:
    deadline = time.monotonic() + max(0.0, max_wait_seconds)
    interval = max(0.25, min(max(poll_interval_seconds, 0.25), 10.0))
    attempts = 0
    last_report: dict[str, object] | None = None
    last_transient_error: StagingAuthBridgeError | None = None
    session_token: str | None = None
    while True:
        attempts += 1
        try:
            safe_request_id, body = _poll_cli_bridge_body(
                origin,
                request_id,
                transport=transport,
                timeout_seconds=timeout_seconds,
            )
        except StagingAuthBridgeError as exc:
            if not _is_transient_poll_error(exc):
                raise
            last_transient_error = exc
            if time.monotonic() >= deadline:
                break
            time.sleep(interval)
            continue
        last_report = _safe_poll_report(safe_request_id, body)
        session_token = _session_token_from_body(body)
        status = str(last_report.get("status") or "unknown")
        session_received = bool(last_report.get("staging_session_received"))
        if session_received:
            break
        if status in {"linked", "completed", "complete"}:
            last_report["linked_without_session_claim"] = True
            break
        if status in {"expired", "revoked", "error", "failed"} or time.monotonic() >= deadline:
            break
        time.sleep(interval)
    if last_report is None:
        if last_transient_error is not None:
            raise StagingAuthBridgeError(
                "staging_bridge_poll_transient_timeout",
                "Staging CLI bridge poll did not recover before the wait timeout.",
                status_code=last_transient_error.status_code,
            )
        raise StagingAuthBridgeError("staging_bridge_poll_failed", "Staging CLI bridge poll failed.")
    account_report: dict[str, object] | None = None
    session_storage_report: Mapping[str, object] | None = None
    if fetch_account and session_token:
        account_report = fetch_staging_account_me(
            origin,
            session_token,
            transport=account_transport,
            timeout_seconds=timeout_seconds,
        )
        if account_report.get("ok") is True and session_claim_handler is not None:
            session_storage_report = session_claim_handler(session_token, last_report, account_report)
    last_report.update(
        {
            "poll_attempts": attempts,
            "waited_until_linked": bool(last_report.get("staging_session_received")),
            "account_me": account_report,
            "session_storage": dict(session_storage_report or {}),
            "google_token_returned": False,
            "refresh_token_returned": False,
            "staging_session_token_printed": False,
        }
    )
    return last_report


def _is_transient_poll_error(error: StagingAuthBridgeError) -> bool:
    if error.code == "staging_bridge_unreachable":
        return True
    return error.status_code in {408, 429, 500, 502, 503, 504}


def fetch_staging_account_me(
    origin: str,
    staging_session_token: str,
    *,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    if not staging_session_token or any(ord(char) < 32 or ord(char) == 127 for char in staging_session_token):
        raise StagingAuthBridgeError("staging_session_claim_invalid", "Staging session claim is invalid.")
    caller = transport or _default_header_json_transport
    status_code, body = caller(
        "GET",
        _join_origin_path(origin, ACCOUNT_ME_PATH),
        {"Authorization": f"Bearer {staging_session_token}"},
        None,
        timeout_seconds,
    )
    _assert_no_token_return(body, allow_session_placeholder=True)
    account_source = body.get("account") or body.get("identity") or body.get("profile") or body
    account = sanitize_staging_account(account_source if isinstance(account_source, Mapping) else {})
    return {
        "status_code": status_code,
        "ok": 200 <= status_code < 300,
        "account": account,
        "session_claim_sent": True,
        "session_claim_printed": False,
        "google_token_returned": False,
        "refresh_token_returned": False,
    }


def _poll_cli_bridge_body(
    origin: str,
    request_id: str,
    *,
    transport: JsonTransport | None,
    timeout_seconds: float,
) -> tuple[str, Mapping[str, object]]:
    caller = transport or _default_json_transport
    safe_request_id = _safe_request_id(request_id)
    poll_path = CLI_BRIDGE_POLL_PATH_TEMPLATE.format(request_id=quote(safe_request_id, safe=""))
    status_code, body = caller("GET", _join_origin_path(origin, poll_path), None, timeout_seconds)
    if status_code >= 400:
        raise StagingAuthBridgeError("staging_bridge_poll_failed", "Staging CLI bridge poll failed.", status_code=status_code)
    _assert_no_token_return(body, allow_session_placeholder=True)
    return safe_request_id, body


def _safe_poll_report(safe_request_id: str, body: Mapping[str, object]) -> dict[str, object]:
    status = str(body.get("status") or "unknown")
    session_received = _session_token_from_body(body) is not None
    account_source = body.get("account") or body.get("identity") or body.get("profile")
    account = sanitize_staging_account(account_source if isinstance(account_source, Mapping) else {})
    return {
        "status": status,
        "request_id": safe_request_id,
        "expires_at": _safe_optional_public_scalar(body.get("expires_at"), "expires_at"),
        "staging_session_received": session_received,
        "staging_session_token_printed": False,
        "google_token_returned": False,
        "refresh_token_returned": False,
        "replay_protected": bool(body.get("replay_protected", False)),
        "linked_identity": "staging_session_claim_received" if session_received else "not_linked_yet",
        "account": account if session_received or account_source else None,
    }


def _session_token_from_body(body: Mapping[str, object]) -> str | None:
    value = body.get("staging_session_token")
    if value is None:
        value = body.get("staging_session_claim")
    if value is None:
        return None
    if not isinstance(value, str):
        raise StagingAuthBridgeError("staging_session_claim_invalid", "Staging session claim is invalid.")
    text = value.strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise StagingAuthBridgeError("staging_session_claim_invalid", "Staging session claim is invalid.")
    return text or None


def _default_json_transport(
    method: str,
    url: str,
    body: Mapping[str, object] | None,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, object]]:
    payload = None if body is None else json.dumps(dict(body)).encode("utf-8")
    request = Request(url, data=payload, method=method.upper())
    request.add_header("Accept", "application/json")
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=timeout_seconds) as response:  # noqa: S310 - origin is allowlisted before use.
            return int(response.status), _read_json_body(response.read())
    except HTTPError as exc:
        if 300 <= int(exc.code) < 400:
            raise StagingAuthBridgeError(
                "staging_bridge_redirect_forbidden",
                "Staging CLI bridge attempted to redirect.",
                status_code=int(exc.code),
            ) from exc
        try:
            return int(exc.code), _read_json_body(exc.read())
        except StagingAuthBridgeError:
            return int(exc.code), {}
    except (OSError, URLError) as exc:
        raise StagingAuthBridgeError("staging_bridge_unreachable", "Staging CLI bridge is unreachable.") from exc


def _default_header_json_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, object] | None,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, object]]:
    payload = None if body is None else json.dumps(dict(body)).encode("utf-8")
    request = Request(url, data=payload, method=method.upper())
    request.add_header("Accept", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=timeout_seconds) as response:  # noqa: S310 - allowlisted origin.
            return int(response.status), _read_json_body(response.read())
    except HTTPError as exc:
        if 300 <= int(exc.code) < 400:
            raise StagingAuthBridgeError(
                "staging_bridge_redirect_forbidden",
                "Staging CLI bridge attempted to redirect.",
                status_code=int(exc.code),
            ) from exc
        try:
            return int(exc.code), _read_json_body(exc.read())
        except StagingAuthBridgeError:
            return int(exc.code), {}
    except (OSError, URLError) as exc:
        raise StagingAuthBridgeError("staging_bridge_unreachable", "Staging CLI bridge is unreachable.") from exc


def _read_json_body(raw: bytes) -> Mapping[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StagingAuthBridgeError("staging_bridge_invalid_json", "Staging CLI bridge returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise StagingAuthBridgeError("staging_bridge_invalid_json", "Staging CLI bridge returned invalid JSON.")
    return value


def _join_origin_path(origin: str, path: str) -> str:
    parsed_origin = urlparse(origin)
    safe_path = _safe_relative_path(path, "path")
    return f"{parsed_origin.scheme}://{_url_host(parsed_origin.hostname or '')}{_port(parsed_origin)}{safe_path}"


def _safe_relative_path(value: object, field_name: str) -> str:
    path = str(value or "").strip()
    parsed = urlparse(path)
    if (
        "\\" in path
        or any(ord(char) < 32 or ord(char) == 127 for char in path)
        or not path.startswith("/")
        or path.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise StagingAuthBridgeError(
            f"staging_bridge_{field_name}_invalid",
            "Staging CLI bridge returned an invalid path.",
        )
    _assert_no_sensitive_url_parts(parsed, field_name)
    return path


def _safe_request_id(value: object) -> str:
    request_id = str(value or "").strip()
    if not _REQUEST_ID_RE.fullmatch(request_id):
        raise StagingAuthBridgeError("staging_bridge_request_id_invalid", "Staging CLI bridge request id is invalid.")
    return request_id


def _assert_no_token_return(body: Mapping[str, object], *, allow_session_placeholder: bool = False) -> None:
    if body.get("google_token_returned") is True or body.get("refresh_token_returned") is True:
        raise StagingAuthBridgeError("staging_bridge_token_return_forbidden", "Staging CLI bridge attempted to return tokens.")
    forbidden_keys = set(_FORBIDDEN_TOKEN_KEYS) | {"staging_session_token", "staging_session_claim"}
    body_to_scan: Mapping[str, object] = body
    if allow_session_placeholder:
        stripped: dict[str, object] = {}
        for key, nested in body.items():
            if _normalize_key(key) in {"staging_session_token", "staging_session_claim"}:
                if isinstance(nested, Mapping | list | tuple):
                    stripped[str(key)] = nested
                continue
            stripped[str(key)] = nested
        body_to_scan = stripped
    if _contains_forbidden_key(body_to_scan, forbidden_keys):
        raise StagingAuthBridgeError("staging_bridge_token_return_forbidden", "Staging CLI bridge attempted to return tokens.")


def _safe_optional_public_scalar(value: object, field_name: str) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise StagingAuthBridgeError(
        f"staging_bridge_{field_name}_invalid",
        "Staging CLI bridge returned an invalid public field.",
    )


def _assert_no_sensitive_url_parts(parsed: Any, field_name: str) -> None:
    pairs = list(parse_qsl(parsed.query, keep_blank_values=True))
    pairs.extend(parse_qsl(parsed.fragment, keep_blank_values=True))
    if any(_normalize_key(key) in _FORBIDDEN_QUERY_PARAM_KEYS for key, _value in pairs):
        raise StagingAuthBridgeError(
            f"staging_bridge_{field_name}_invalid",
            "Staging CLI bridge returned an invalid path.",
        )
    query = str(parsed.query or "").lower()
    fragment = str(parsed.fragment or "").lower()
    if any(f"{key}=" in query or f"{key}=" in fragment for key in _FORBIDDEN_QUERY_PARAM_KEYS):
        raise StagingAuthBridgeError(
            f"staging_bridge_{field_name}_invalid",
            "Staging CLI bridge returned an invalid path.",
        )


def _normalize_key(value: object) -> str:
    return str(value).strip().lower()


def _contains_forbidden_key(value: object, forbidden_keys: set[str]) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if _normalize_key(key) in forbidden_keys:
                return True
            if _contains_forbidden_key(nested, forbidden_keys):
                return True
    elif isinstance(value, list | tuple):
        return any(_contains_forbidden_key(item, forbidden_keys) for item in value)
    return False


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


def _url_host(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def _port(parsed: Any) -> str:
    try:
        port = parsed.port
    except ValueError as exc:
        raise StagingAuthBridgeError("staging_bridge_origin_invalid", "Staging CLI bridge origin is invalid.") from exc
    if port is None:
        return ""
    return f":{port}"
