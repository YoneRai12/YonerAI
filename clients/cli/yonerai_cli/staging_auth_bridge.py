from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


CLI_BRIDGE_START_PATH = "/auth/cli/start"
CLI_BRIDGE_POLL_PATH_TEMPLATE = "/auth/cli/poll/{request_id}"
GOOGLE_BROWSER_START_PATH = "/auth/google/start"
GOOGLE_CALLBACK_PATH = "/api/auth/callback/google"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,160}$")

JsonTransport = Callable[[str, str, Mapping[str, object] | None, float], tuple[int, Mapping[str, object]]]


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
        "expires_at": body.get("expires_at"),
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
    caller = transport or _default_json_transport
    safe_request_id = _safe_request_id(request_id)
    poll_path = CLI_BRIDGE_POLL_PATH_TEMPLATE.format(request_id=quote(safe_request_id, safe=""))
    status_code, body = caller("GET", _join_origin_path(origin, poll_path), None, timeout_seconds)
    if status_code >= 400:
        raise StagingAuthBridgeError("staging_bridge_poll_failed", "Staging CLI bridge poll failed.", status_code=status_code)
    _assert_no_token_return(body, allow_session_placeholder=True)
    status = str(body.get("status") or "unknown")
    session_received = "staging_session_token" in body
    return {
        "status": status,
        "request_id": safe_request_id,
        "expires_at": body.get("expires_at"),
        "staging_session_received": session_received,
        "staging_session_token_printed": False,
        "google_token_returned": False,
        "refresh_token_returned": False,
        "replay_protected": bool(body.get("replay_protected", False)),
        "linked_identity": "session_placeholder_only" if session_received else "not_linked_yet",
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
    return path


def _safe_request_id(value: object) -> str:
    request_id = str(value or "").strip()
    if not _REQUEST_ID_RE.fullmatch(request_id):
        raise StagingAuthBridgeError("staging_bridge_request_id_invalid", "Staging CLI bridge request id is invalid.")
    return request_id


def _assert_no_token_return(body: Mapping[str, object], *, allow_session_placeholder: bool = False) -> None:
    if body.get("google_token_returned") is True or body.get("refresh_token_returned") is True:
        raise StagingAuthBridgeError("staging_bridge_token_return_forbidden", "Staging CLI bridge attempted to return tokens.")
    forbidden_keys = {"google_token", "id_token", "access_token", "refresh_token", "authorization_code"}
    if not allow_session_placeholder:
        forbidden_keys.add("staging_session_token")
    if _contains_forbidden_key(body, forbidden_keys):
        raise StagingAuthBridgeError("staging_bridge_token_return_forbidden", "Staging CLI bridge attempted to return tokens.")


def _contains_forbidden_key(value: object, forbidden_keys: set[str]) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in forbidden_keys:
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
