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
_POLL_VERIFIER_RE = re.compile(r"^clipoll_[A-Za-z0-9_-]{8,256}$")
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
    "poll_verifier",
    "secret",
}
_POLL_URL_ALLOWED_QUERY_KEYS = frozenset({"poll_verifier"})
_FORBIDDEN_PUBLIC_SCALAR_VALUE_RE = re.compile(
    r"(?i)(?:^|[^A-Za-z0-9])"
    r"['\"]?"
    r"(?:"
    r"staging[_-]session[_-](?:token|claim)"
    r"|google[_-]access[_-]token"
    r"|google[_-]id[_-]token"
    r"|session[_-]token"
    r"|access[_-]token"
    r"|id[_-]token"
    r"|refresh[_-]token"
    r"|authorization[_-]code"
    r"|auth[_-]code"
    r"|client[_-]secret"
    r"|api[_-]key"
    r")['\"]?\s*[:=]"
)
_LOCAL_PATH_VALUE_RE = re.compile(r"([A-Za-z]:[/\\]|\\\\|/Users/|/home/|/root/)", re.IGNORECASE)

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
    report, _poll_url = start_cli_bridge_for_polling(
        origin,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    return report


def start_cli_bridge_for_polling(
    origin: str,
    *,
    transport: JsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> tuple[dict[str, object], str]:
    caller = transport or _default_json_transport
    status_code, body = caller("POST", _join_origin_path(origin, CLI_BRIDGE_START_PATH), None, timeout_seconds)
    if status_code >= 400:
        raise StagingAuthBridgeError("staging_bridge_start_failed", "Staging CLI bridge start failed.", status_code=status_code)
    _assert_no_token_return(body)
    request_id = _safe_request_id(body.get("request_id"))
    browser_start_path = _safe_relative_path(body.get("browser_start_path"), "browser_start_path")
    poll_path_value = body.get("poll_path")
    poll_url_value = body.get("poll_url")
    poll_path = (
        _safe_relative_path(poll_path_value, "poll_path", allowed_query_param_keys=_POLL_URL_ALLOWED_QUERY_KEYS)
        if poll_path_value
        else ""
    )
    if browser_start_path != GOOGLE_BROWSER_START_PATH and not browser_start_path.startswith(f"{GOOGLE_BROWSER_START_PATH}?"):
        raise StagingAuthBridgeError("staging_bridge_browser_start_path_invalid", "Staging CLI bridge start path is invalid.")
    raw_poll_url = _safe_poll_url(origin, poll_url_value, request_id) if poll_url_value else ""
    if raw_poll_url:
        poll_url_path = str(urlparse(raw_poll_url).path or "")
        if poll_path and _public_relative_path(poll_path) != poll_url_path:
            raise StagingAuthBridgeError("staging_bridge_poll_path_invalid", "Staging CLI bridge poll path is invalid.")
        poll_path = poll_path or poll_url_path
    if not poll_path:
        raise StagingAuthBridgeError("staging_bridge_poll_path_invalid", "Staging CLI bridge poll path is invalid.")
    _assert_poll_path_matches_request(poll_path, request_id)
    raw_poll_url = raw_poll_url or _join_origin_path(
        origin,
        poll_path,
        allowed_query_param_keys=_POLL_URL_ALLOWED_QUERY_KEYS,
    )
    public_poll_path = _public_relative_path(poll_path)
    report = {
        "status": str(body.get("status") or "created"),
        "request_id": request_id,
        "expires_at": _safe_optional_public_scalar(body.get("expires_at"), "expires_at"),
        "browser_start_path": browser_start_path,
        "browser_start_url": _join_origin_path(origin, browser_start_path),
        "poll_path": public_poll_path,
        "poll_url": _public_url_without_query(raw_poll_url),
        "poll_url_received": bool(poll_url_value),
        "poll_verifier_received": _poll_url_has_verifier(raw_poll_url),
        "poll_verifier_printed": False,
        "google_token_returned": False,
        "refresh_token_returned": False,
        "staging_session_token_printed": False,
    }
    return report, raw_poll_url


def poll_cli_bridge(
    origin: str,
    request_id: str,
    *,
    poll_url: str | None = None,
    transport: JsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    safe_request_id, body = _poll_cli_bridge_body(
        origin,
        request_id,
        poll_url=poll_url,
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
    poll_url: str | None = None,
) -> dict[str, object]:
    deadline = time.monotonic() + max(0.0, max_wait_seconds)
    interval = max(0.25, min(max(poll_interval_seconds, 0.25), 10.0))
    attempts = 0
    last_report: dict[str, object] | None = None
    last_transient_error: StagingAuthBridgeError | None = None
    linked_session_token: str | None = None
    while True:
        attempts += 1
        try:
            safe_request_id, body = _poll_cli_bridge_body(
                origin,
                request_id,
                poll_url=poll_url,
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
        status = str(last_report.get("status") or "unknown")
        linked = bool(last_report.get("linked")) or status in {"linked", "completed", "complete"}
        if linked:
            linked_session_token = _session_token_from_body(body)
            last_report["waited_until_linked"] = True
            if not bool(last_report.get("cli_session_available")):
                last_report["linked_without_cli_session"] = True
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
    if linked_session_token and fetch_account:
        account_report = fetch_staging_account_me(
            origin,
            linked_session_token,
            transport=account_transport,
            timeout_seconds=timeout_seconds,
        )
        if session_claim_handler is not None and account_report.get("ok") is True:
            session_storage_report = session_claim_handler(linked_session_token, last_report, account_report)
    last_report.update(
        {
            "poll_attempts": attempts,
            "waited_until_linked": bool(last_report.get("waited_until_linked")),
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
    _assert_no_token_return(body)
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
    poll_url: str | None = None,
    transport: JsonTransport | None,
    timeout_seconds: float,
) -> tuple[str, Mapping[str, object]]:
    caller = transport or _default_json_transport
    safe_request_id = _safe_request_id(request_id)
    if poll_url:
        poll_endpoint = _safe_poll_url(origin, poll_url, safe_request_id)
    else:
        poll_path = CLI_BRIDGE_POLL_PATH_TEMPLATE.format(request_id=quote(safe_request_id, safe=""))
        poll_endpoint = _join_origin_path(origin, poll_path)
    status_code, body = caller("GET", poll_endpoint, None, timeout_seconds)
    if status_code >= 400:
        raise StagingAuthBridgeError("staging_bridge_poll_failed", "Staging CLI bridge poll failed.", status_code=status_code)
    _assert_no_token_return(body, allow_session_placeholder=True)
    return safe_request_id, body


def _safe_poll_report(safe_request_id: str, body: Mapping[str, object]) -> dict[str, object]:
    status = str(body.get("status") or "unknown")
    linked = bool(body.get("linked")) or status in {"linked", "completed", "complete"}
    session_token = _session_token_from_body(body)
    session_source = body.get("session") if isinstance(body.get("session"), Mapping) else {}
    if session_source.get("token_returned") is True and not session_token:
        raise StagingAuthBridgeError("staging_bridge_token_return_forbidden", "Staging CLI bridge attempted to return tokens.")
    cli_session_available = bool(session_token)
    account_source = body.get("account") or body.get("identity") or body.get("profile")
    account = sanitize_staging_account(account_source if isinstance(account_source, Mapping) else {})
    return {
        "status": status,
        "linked": linked,
        "request_id": safe_request_id,
        "expires_at": _safe_optional_public_scalar(body.get("expires_at"), "expires_at"),
        "staging_session_received": cli_session_available,
        "cli_session_available": cli_session_available,
        "linked_without_cli_session": bool(linked and not cli_session_available),
        "linked_without_session_claim": bool(linked and not cli_session_available),
        "staging_session_token_printed": False,
        "google_token_returned": False,
        "refresh_token_returned": False,
        "replay_protected": bool(body.get("replay_protected", False)),
        "linked_identity": "linked_without_cli_session" if linked and not cli_session_available else "not_linked_yet",
        "account": account if account_source else None,
        "session": _safe_session_metadata(session_source),
    }


def _session_token_from_body(body: Mapping[str, object]) -> str | None:
    candidates: list[object] = []
    for key in ("staging_session_token", "staging_session_claim"):
        value = body.get(key)
        if value is not None:
            candidates.append(value)
    session = body.get("session")
    if isinstance(session, Mapping):
        for key in ("staging_session_token", "staging_session_claim"):
            value = session.get(key)
            if value is not None:
                candidates.append(value)
    if not candidates:
        return None
    normalized: list[str] = []
    for value in candidates:
        if not isinstance(value, str):
            raise StagingAuthBridgeError("staging_session_claim_invalid", "Staging session claim is invalid.")
        text = value.strip()
        if any(ord(char) < 32 or ord(char) == 127 for char in text):
            raise StagingAuthBridgeError("staging_session_claim_invalid", "Staging session claim is invalid.")
        normalized.append(text)
    if not any(normalized):
        return None
    first = normalized[0]
    if any(value != first for value in normalized):
        raise StagingAuthBridgeError("staging_session_claim_invalid", "Staging session claim is invalid.")
    return first


def _safe_session_metadata(session: Mapping[str, object]) -> dict[str, object]:
    if not session:
        return {
            "token_returned": False,
            "bearer_authorization_supported": False,
            "browser_cookie_session_present": False,
        }
    return {
        "type": _safe_optional_public_scalar(session.get("type"), "session_type"),
        "token_returned": False,
        "token_field": _safe_optional_public_scalar(session.get("token_field"), "session_token_field"),
        "opaque_session_available": isinstance(session.get("staging_session_token"), str)
        or isinstance(session.get("staging_session_claim"), str),
        "bearer_authorization_supported": bool(session.get("bearer_authorization_supported", False)),
        "browser_cookie_session_present": bool(session.get("cookie_name")),
        "expires_at": _safe_optional_public_scalar(session.get("expires_at"), "session_expires_at"),
    }


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


def _join_origin_path(origin: str, path: str, *, allowed_query_param_keys: frozenset[str] = frozenset()) -> str:
    parsed_origin = urlparse(origin)
    safe_path = _safe_relative_path(path, "path", allowed_query_param_keys=allowed_query_param_keys)
    return f"{parsed_origin.scheme}://{_url_host(parsed_origin.hostname or '')}{_port(parsed_origin)}{safe_path}"


def _safe_relative_path(
    value: object,
    field_name: str,
    *,
    allowed_query_param_keys: frozenset[str] = frozenset(),
) -> str:
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
    _assert_no_sensitive_url_parts(parsed, field_name, allowed_query_param_keys=allowed_query_param_keys)
    _assert_poll_verifier_shape(parsed, field_name, allowed_query_param_keys=allowed_query_param_keys)
    return path


def _safe_request_id(value: object) -> str:
    request_id = str(value or "").strip()
    if not _REQUEST_ID_RE.fullmatch(request_id):
        raise StagingAuthBridgeError("staging_bridge_request_id_invalid", "Staging CLI bridge request id is invalid.")
    return request_id


def _assert_no_token_return(body: Mapping[str, object], *, allow_session_placeholder: bool = False) -> None:
    if body.get("google_token_returned") is True or body.get("refresh_token_returned") is True:
        raise StagingAuthBridgeError("staging_bridge_token_return_forbidden", "Staging CLI bridge attempted to return tokens.")
    scan_body: Mapping[str, object] = body
    if allow_session_placeholder:
        scan_body = _body_without_allowed_opaque_session(body)
    forbidden_keys = set(_FORBIDDEN_TOKEN_KEYS) | {"staging_session_token", "staging_session_claim"}
    if _contains_forbidden_key(scan_body, forbidden_keys):
        raise StagingAuthBridgeError("staging_bridge_token_return_forbidden", "Staging CLI bridge attempted to return tokens.")


def _body_without_allowed_opaque_session(body: Mapping[str, object]) -> Mapping[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in body.items():
        if key in {"staging_session_token", "staging_session_claim"} and isinstance(value, str):
            continue
        if key == "session" and isinstance(value, Mapping):
            sanitized[key] = {
                nested_key: nested_value
                for nested_key, nested_value in value.items()
                if not (nested_key in {"staging_session_token", "staging_session_claim"} and isinstance(nested_value, str))
            }
            continue
        sanitized[key] = value
    return sanitized


def _safe_optional_public_scalar(value: object, field_name: str) -> object:
    if value is None or isinstance(value, int | float | bool):
        return value
    if isinstance(value, str):
        if (
            any(ord(char) < 32 or ord(char) == 127 for char in value)
            or _FORBIDDEN_PUBLIC_SCALAR_VALUE_RE.search(value)
            or _LOCAL_PATH_VALUE_RE.search(value)
        ):
            raise StagingAuthBridgeError(
                f"staging_bridge_{field_name}_invalid",
                "Staging CLI bridge returned an invalid public field.",
            )
        return value
    raise StagingAuthBridgeError(
        f"staging_bridge_{field_name}_invalid",
        "Staging CLI bridge returned an invalid public field.",
    )


def _safe_poll_url(origin: str, value: object, request_id: str) -> str:
    raw_url = str(value or "").strip()
    parsed = urlparse(raw_url)
    parsed_origin = urlparse(origin)
    if (
        not raw_url
        or any(ord(char) < 32 or ord(char) == 127 for char in raw_url)
        or parsed.scheme != parsed_origin.scheme
        or parsed.hostname != parsed_origin.hostname
        or _port(parsed) != _port(parsed_origin)
        or parsed.username
        or parsed.password
    ):
        raise StagingAuthBridgeError("staging_bridge_poll_url_invalid", "Staging CLI bridge poll URL is invalid.")
    _assert_no_sensitive_url_parts(parsed, "poll_url", allowed_query_param_keys=_POLL_URL_ALLOWED_QUERY_KEYS)
    _assert_poll_verifier_shape(parsed, "poll_url", allowed_query_param_keys=_POLL_URL_ALLOWED_QUERY_KEYS)
    _assert_poll_path_matches_request(parsed.path, request_id)
    return raw_url


def _assert_poll_path_matches_request(path: str, request_id: str) -> None:
    parsed = urlparse(path)
    if not parsed.path.startswith("/auth/cli/poll/") or parsed.path.rsplit("/", 1)[-1] != request_id:
        raise StagingAuthBridgeError("staging_bridge_poll_path_invalid", "Staging CLI bridge poll path is invalid.")


def _public_relative_path(path: str) -> str:
    parsed = urlparse(path)
    return str(parsed.path or "")


def _public_url_without_query(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    return f"{parsed.scheme}://{_url_host(parsed.hostname or '')}{_port(parsed)}{parsed.path}"


def _poll_url_has_verifier(raw_url: str) -> bool:
    parsed = urlparse(raw_url)
    return any(_normalize_key(key) == "poll_verifier" for key, _value in parse_qsl(parsed.query, keep_blank_values=True))


def _assert_no_sensitive_url_parts(parsed: Any, field_name: str, *, allowed_query_param_keys: frozenset[str] = frozenset()) -> None:
    allowed = {_normalize_key(key) for key in allowed_query_param_keys}
    pairs = list(parse_qsl(parsed.query, keep_blank_values=True))
    pairs.extend(parse_qsl(parsed.fragment, keep_blank_values=True))
    if any(_normalize_key(key) in _FORBIDDEN_QUERY_PARAM_KEYS - allowed for key, _value in pairs):
        raise StagingAuthBridgeError(
            f"staging_bridge_{field_name}_invalid",
            "Staging CLI bridge returned an invalid path.",
        )
    query = str(parsed.query or "").lower()
    fragment = str(parsed.fragment or "").lower()
    forbidden_markers = _FORBIDDEN_QUERY_PARAM_KEYS - allowed
    if any(f"{key}=" in query or f"{key}=" in fragment for key in forbidden_markers):
        raise StagingAuthBridgeError(
            f"staging_bridge_{field_name}_invalid",
            "Staging CLI bridge returned an invalid path.",
        )


def _assert_poll_verifier_shape(
    parsed: Any,
    field_name: str,
    *,
    allowed_query_param_keys: frozenset[str] = frozenset(),
) -> None:
    if "poll_verifier" not in {_normalize_key(key) for key in allowed_query_param_keys}:
        if "poll_verifier=" in str(parsed.query or "").lower() or "poll_verifier=" in str(parsed.fragment or "").lower():
            raise StagingAuthBridgeError(
                f"staging_bridge_{field_name}_invalid",
                "Staging CLI bridge returned an invalid path.",
            )
        return
    verifier_values = [
        value
        for key, value in parse_qsl(str(parsed.query or ""), keep_blank_values=True)
        if _normalize_key(key) == "poll_verifier"
    ]
    query_keys = {_normalize_key(key) for key, _value in parse_qsl(str(parsed.query or ""), keep_blank_values=True)}
    fragment_keys = {_normalize_key(key) for key, _value in parse_qsl(str(parsed.fragment or ""), keep_blank_values=True)}
    if query_keys - {"poll_verifier"} or fragment_keys:
        raise StagingAuthBridgeError(
            f"staging_bridge_{field_name}_invalid",
            "Staging CLI bridge returned an invalid path.",
        )
    if len(verifier_values) > 1:
        raise StagingAuthBridgeError(
            f"staging_bridge_{field_name}_invalid",
            "Staging CLI bridge returned an invalid path.",
        )
    if verifier_values and not _POLL_VERIFIER_RE.fullmatch(verifier_values[0]):
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
