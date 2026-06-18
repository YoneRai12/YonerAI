from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request

from yonerai_cli.services.control_spine_service import (
    DEFAULT_STAGING_CONTROL_SPINE_ORIGIN,
    build_control_spine_context,
    load_config_for_control_spine,
)
from yonerai_cli.services.native_run_service import NativeRunServiceError


PROVIDER_GATEWAY_SCHEMA_VERSION = "yonerai-provider-gateway-client/v0.1"
PROVIDER_STATUS_PATH = "/v1/provider-gateway/status"
PROVIDER_QUOTA_PATH = "/v1/provider-gateway/status"
PROVIDER_MODELS_PATH = "/v1/provider-gateway/status"

HeaderJsonTransport = Callable[
    [str, str, Mapping[str, str], Mapping[str, object] | None, float],
    tuple[int, Mapping[str, object], Mapping[str, str]],
]


def build_provider_gateway_report(
    command: str,
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    if command == "disable":
        return _base_report("provider_disable", _context(config=config, env=env, claim_path=claim_path), disabled=True)
    path_map = {
        "status": PROVIDER_STATUS_PATH,
        "quota": PROVIDER_QUOTA_PATH,
        "models": PROVIDER_MODELS_PATH,
    }
    if command not in path_map:
        raise ValueError("provider command is invalid")
    context = _context(config=config, env=env, claim_path=claim_path)
    report = _base_report(f"provider_{command}", context)
    try:
        status_code, body, headers = _request_json(
            "GET",
            str(context.get("origin") or DEFAULT_STAGING_CONTROL_SPINE_ORIGIN).rstrip("/") + path_map[command],
            _auth_headers(context),
            None,
            timeout_seconds,
            transport=transport,
        )
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report["official_backend_called"] = True
    report["backend_status_code"] = status_code
    report["rate_limit_headers_present"] = _rate_limit_headers_present(headers)
    if status_code == 404:
        report["ok"] = False
        report["provider_gateway_available"] = False
        report["error"] = _safe_error(
            "provider_gateway_not_available",
            "Staging provider gateway endpoint is not available yet.",
            status_code=status_code,
        )
        return report
    if status_code == 401:
        report["ok"] = False
        report["error"] = _safe_error(
            "staging_auth_required",
            "Staging login is required before provider gateway access.",
            status_code=status_code,
            next_safe_command="yonerai login",
        )
        return report
    if status_code >= 400:
        detail = body.get("detail") if isinstance(body.get("detail"), Mapping) else body
        reason = str(detail.get("reason") if isinstance(detail, Mapping) else "provider_gateway_failed")
        report["ok"] = False
        report["error"] = _safe_error(reason, "Staging provider gateway request failed.", status_code=status_code)
        return report
    try:
        _assert_public_safe(body)
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    report["provider_gateway_available"] = True
    if command == "status":
        report["provider_status"] = _sanitize_mapping(body.get("provider_status") if isinstance(body.get("provider_status"), Mapping) else body)
    elif command == "quota":
        quota = body.get("quota") if isinstance(body.get("quota"), Mapping) else body.get("cost_policy")
        if not isinstance(quota, Mapping):
            quota = body
        report["quota"] = _sanitize_mapping(quota)
    elif command == "models":
        models = body.get("models") if isinstance(body.get("models"), list) else []
        if not models:
            model_policy = body.get("model_policy") if isinstance(body.get("model_policy"), Mapping) else {}
            selected_model = model_policy.get("selected_model_hint")
            if selected_model:
                models = [
                    {
                        "model_id": selected_model,
                        "configured": body.get("model_configured", False),
                        "tools_enabled": model_policy.get("tools_enabled", False),
                        "file_inputs_enabled": model_policy.get("file_inputs_enabled", False),
                        "web_search_enabled": model_policy.get("web_search_enabled", False),
                        "code_interpreter_enabled": model_policy.get("code_interpreter_enabled", False),
                    }
                ]
        report["models"] = [_sanitize_mapping(item) for item in models if isinstance(item, Mapping)]
    return report


def load_config_for_provider_gateway(config_path: str | None) -> dict[str, object]:
    return load_config_for_control_spine(config_path)


def _context(
    *,
    config: Mapping[str, object] | None,
    env: Mapping[str, str | None] | None,
    claim_path: str | None,
) -> dict[str, object]:
    context = dict(build_control_spine_context(config=config, env=env, claim_path=claim_path))
    origin = str(context.get("origin") or "").strip()
    if (
        not context.get("origin_configured")
        or origin in {"", "not_configured", "configured"}
        or not _is_allowed_staging_origin(origin)
    ):
        context["origin"] = DEFAULT_STAGING_CONTROL_SPINE_ORIGIN
        context["origin_configured"] = True
        context["origin_from_default"] = True
        context["origin_invalid_replaced"] = bool(origin and origin not in {"not_configured"})
    return context


def _base_report(operation: str, context: Mapping[str, object], *, disabled: bool = False) -> dict[str, object]:
    return {
        "schema_version": PROVIDER_GATEWAY_SCHEMA_VERSION,
        "ok": True,
        "operation": operation,
        "staging_only": True,
        "backend_url": str(context.get("origin") or DEFAULT_STAGING_CONTROL_SPINE_ORIGIN),
        "provider_gateway_available": False if disabled else None,
        "provider_gateway_disabled_locally": bool(disabled),
        "provider_data_policy_default": "none",
        "openai_shared_traffic_default": False,
        "openai_key_in_public_cli": False,
        "paid_overage_allowed": False,
        "production_cloud_runtime_enabled": False,
        "google_token_stored": False,
        "refresh_token_stored": False,
        "provider_key_stored": False,
        "local_private_auto_upload_enabled": False,
        "official_backend_called": False,
        "actions_not_performed": [
            "no production Google login",
            "no OpenAI key in Public CLI",
            "no shared traffic by default",
            "no implicit consent",
            "no local_only transmission",
            "no local/workspace files or attachments",
            "no paid overage",
        ],
    }


def _auth_headers(context: Mapping[str, object]) -> dict[str, str]:
    token = context.get("session_token")
    if isinstance(token, str) and token.strip():
        return {"Authorization": f"Bearer {token}"}
    return {}


def _request_json(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, object] | None,
    timeout_seconds: float,
    *,
    transport: HeaderJsonTransport | None,
) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
    if transport is not None:
        return transport(method, url, headers, body, timeout_seconds)
    data = None if body is None else json.dumps(dict(body)).encode("utf-8")
    try:
        request = Request(url, data=data, method=method.upper())
    except ValueError as exc:
        raise NativeRunServiceError("provider_gateway_invalid_origin", "Staging provider gateway origin is invalid.") from exc
    try:
        request.add_header("Accept", "application/json")
        for key, value in headers.items():
            request.add_header(key, value)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        with __import__("urllib.request").request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - allowlisted staging host only.
            return int(response.status), _read_json(response.read()), dict(response.headers)
    except HTTPError as exc:
        try:
            return int(exc.code), _read_json(exc.read()), dict(exc.headers)
        except NativeRunServiceError:
            return int(exc.code), {}, dict(exc.headers)
    except (OSError, URLError) as exc:
        raise NativeRunServiceError("provider_gateway_unreachable", "Staging provider gateway is unreachable.") from exc


def _is_allowed_staging_origin(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if not host or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if parsed.path not in {"", "/"}:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return parsed.scheme in {"http", "https"}
    if host not in {"api-staging.yonerai.com", "staging.yonerai.com"}:
        return False
    return parsed.scheme == "https" and parsed.port is None


def _read_json(raw: bytes) -> Mapping[str, object]:
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeRunServiceError("provider_gateway_invalid_json", "Staging provider gateway returned invalid JSON.") from exc
    if not isinstance(decoded, dict):
        raise NativeRunServiceError("provider_gateway_invalid_json", "Staging provider gateway returned invalid JSON.")
    return decoded


def _sanitize_mapping(payload: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in payload.items():
        safe_key = _safe_text(key)
        if isinstance(value, Mapping):
            sanitized[safe_key] = _sanitize_mapping(value)
        elif isinstance(value, list):
            sanitized[safe_key] = [
                _sanitize_mapping(item) if isinstance(item, Mapping) else _safe_text(item) for item in value[:20]
            ]
        elif isinstance(value, bool | int | float):
            sanitized[safe_key] = value
        else:
            sanitized[safe_key] = _safe_text(value)
    return sanitized


def _assert_public_safe(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    if any(marker in serialized for marker in _FORBIDDEN_MARKERS):
        raise NativeRunServiceError(
            "provider_gateway_private_payload_rejected",
            "Staging provider gateway returned non-public fields.",
        )


def _safe_text(value: object, *, fallback: str = "redacted") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if _looks_private(text.lower()):
        return fallback
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return fallback
    return text[:240]


def _safe_error(code: str, message: str, *, status_code: int | None = None, next_safe_command: str | None = None) -> dict[str, object]:
    error: dict[str, object] = {
        "code": _safe_text(code),
        "message": message,
        "status_code": status_code,
        "private_endpoint_printed": False,
        "local_path_printed": False,
        "token_printed": False,
        "provider_key_printed": False,
    }
    if next_safe_command:
        error["next_safe_command"] = next_safe_command
    return error


def _rate_limit_headers_present(headers: Mapping[str, str]) -> list[str]:
    normalized = {key.lower() for key in headers}
    return [
        public
        for key, public in {
            "x-yonerai-ratelimit-scope": "X-YonerAI-RateLimit-Scope",
            "x-yonerai-ratelimit-limit": "X-YonerAI-RateLimit-Limit",
            "x-yonerai-ratelimit-remaining": "X-YonerAI-RateLimit-Remaining",
            "x-yonerai-ratelimit-reset": "X-YonerAI-RateLimit-Reset",
            "x-yonerai-ratelimit-reason": "X-YonerAI-RateLimit-Reason",
        }.items()
        if key in normalized
    ]


def _looks_private(lowered: str) -> bool:
    return any(marker in lowered for marker in _FORBIDDEN_MARKERS)


_FORBIDDEN_MARKERS = (
    "access_token",
    "refresh_token",
    "id_token",
    "client_secret",
    "authorization_code",
    "google_token",
    "api_key",
    "password",
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
