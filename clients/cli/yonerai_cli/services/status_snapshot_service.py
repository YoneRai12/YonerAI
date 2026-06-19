from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from yonerai_cli import __version__


STATUS_SNAPSHOT_CLIENT_SCHEMA_VERSION = "yonerai-status-snapshot-client/v0.1"
STATUS_SNAPSHOT_SCHEMA_VERSION = "yonerai.status.v1"
STATUS_CONTRACT_POLICY_VERSION = "yonerai-official-api-contract/v0.14"
DEFAULT_STATUS_ORIGIN = "https://api-staging.yonerai.com"
STATUS_PATH = "/v1/status"
HEALTH_PATH = "/v1/health"

HEALTH_VALUES = {
    "operational",
    "degraded",
    "partial_outage",
    "major_outage",
    "maintenance",
    "offline",
    "unknown",
}
AVAILABILITY_VALUES = {"available", "limited", "unavailable"}
STAGE_VALUES = {"preview", "staging", "production", "disabled"}
CANONICAL_COMPONENTS = (
    "api",
    "auth",
    "provider_gateway",
    "official_execution_worker",
    "run_queue",
    "realtime_sync",
    "web",
    "audit",
    "discord",
)
ALLOWED_STATUS_HOSTS = frozenset({"api-staging.yonerai.com", "status.yonerai.com", "yonerai.com"})

HeaderJsonTransport = Callable[
    [str, str, Mapping[str, str], Mapping[str, object] | None, float],
    tuple[int, Mapping[str, object], Mapping[str, str]],
]


class StatusSnapshotError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code

    def to_safe_error(self) -> dict[str, object]:
        return _safe_error(self.code, self.message, status_code=self.status_code)


def build_status_snapshot_report(
    *,
    source: str = "live",
    status_source: str | None = None,
    allow_network_status_fetch: bool = False,
    component_id: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    report = _base_report("status_snapshot")
    try:
        safe_timeout_seconds = _safe_timeout_seconds(timeout_seconds)
        status_payload, status_headers = _load_status_payload(
            source=source,
            status_source=status_source,
            allow_network_status_fetch=allow_network_status_fetch,
            transport=transport,
            timeout_seconds=safe_timeout_seconds,
        )
        health_payload: Mapping[str, object] = {}
        health_headers: Mapping[str, str] = {}
        if _should_fetch_health(source=source, status_source=status_source):
            try:
                health_payload, health_headers = _fetch_json(
                    DEFAULT_STATUS_ORIGIN,
                    HEALTH_PATH,
                    transport=transport,
                    timeout_seconds=safe_timeout_seconds,
                )
            except StatusSnapshotError:
                health_payload = {}
                health_headers = {}
        snapshot = normalize_status_snapshot(status_payload, health_payload=health_payload)
        _assert_public_safe_payload(snapshot)
    except StatusSnapshotError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report

    report["ok"] = True
    report["official_backend_called"] = source == "live" and status_source is None
    report["snapshot"] = snapshot
    report["component_count"] = len(snapshot["components"]) if isinstance(snapshot.get("components"), list) else 0
    report["compatibility"] = _compatibility_report(health_payload)
    report["cache"] = _cache_report(status_headers, health_headers)
    report["private_runtime_details_included"] = False
    report["production_cloud_claim"] = False
    report["actions_not_performed"] = _non_actions()
    if component_id:
        report["component"] = _find_component(snapshot, component_id)
        if report["component"] is None:
            report["ok"] = False
            report["error"] = _safe_error(
                "status_component_not_found",
                "Requested status component was not found.",
            )
    return report


def normalize_status_snapshot(
    payload: Mapping[str, object],
    *,
    health_payload: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if payload.get("schema_version") == STATUS_SNAPSHOT_SCHEMA_VERSION:
        snapshot = _snapshot_from_v1(payload)
    else:
        snapshot = _snapshot_from_legacy(payload, health_payload=health_payload or {})
    _validate_snapshot(snapshot)
    return snapshot


def _snapshot_from_v1(payload: Mapping[str, object]) -> dict[str, object]:
    if payload.get("private_runtime_details_included") is True:
        raise StatusSnapshotError(
            "status_snapshot_private_payload_rejected",
            "Status snapshot declared private runtime details.",
        )
    components = payload.get("components")
    if not isinstance(components, list) or not components:
        raise StatusSnapshotError("status_snapshot_schema_invalid", "Status snapshot components are required.")
    return {
        "schema_version": STATUS_SNAPSHOT_SCHEMA_VERSION,
        "snapshot_id": _safe_token(payload.get("snapshot_id"), fallback=_snapshot_id(payload)),
        "generated_at": _safe_timestamp(payload.get("generated_at")),
        "stale_after_seconds": _safe_int(payload.get("stale_after_seconds"), fallback=60, minimum=1, maximum=3600),
        "overall": _normalize_overall(payload.get("overall")),
        "components": [_normalize_component(item) for item in components if isinstance(item, Mapping)],
        "cache_policy": _safe_cache_policy(payload.get("cache_policy")),
        "private_runtime_details_included": False,
    }


def _snapshot_from_legacy(
    payload: Mapping[str, object],
    *,
    health_payload: Mapping[str, object],
) -> dict[str, object]:
    status_snapshot = payload.get("status_snapshot") if isinstance(payload.get("status_snapshot"), Mapping) else {}
    generated_at = _safe_timestamp(payload.get("generated_at") or health_payload.get("generated_at"))
    stale_after = _safe_int(status_snapshot.get("worker_heartbeat_max_age_seconds"), fallback=60, minimum=1, maximum=3600)
    raw_components = payload.get("components") if isinstance(payload.get("components"), list) else []
    components = (
        [_normalize_component(item) for item in raw_components if isinstance(item, Mapping)]
        if raw_components
        else _components_from_status_snapshot(status_snapshot, generated_at=generated_at)
    )
    overall = _normalize_overall(payload.get("overall"))
    if not isinstance(payload.get("overall"), Mapping):
        overall = _derive_overall(components, stage=_stage_from_environment(payload.get("environment")))
    if str(payload.get("overall_status") or payload.get("status") or "").strip() == "not_production":
        overall["stage"] = "staging"
        if overall["health"] == "operational" and any(item["health"] == "offline" for item in components):
            overall["health"] = "degraded"
            overall["availability"] = "limited"
        overall["message"] = _safe_text(
            overall.get("message"),
            fallback="Staging runtime status only; production availability is not claimed.",
        )
    return {
        "schema_version": STATUS_SNAPSHOT_SCHEMA_VERSION,
        "snapshot_id": _snapshot_id(payload),
        "generated_at": generated_at,
        "stale_after_seconds": stale_after,
        "overall": overall,
        "components": components,
        "cache_policy": {
            "etag_supported": True,
            "cache_control_max_age_must_be_below_stale_after_seconds": True,
        },
        "private_runtime_details_included": False,
    }


def _components_from_status_snapshot(snapshot: Mapping[str, object], *, generated_at: str) -> list[dict[str, object]]:
    worker_stale = bool(snapshot.get("worker_heartbeat_stale"))
    worker_health = _health_value(snapshot.get("worker_effective_health") or snapshot.get("official_execution_worker"))
    queue_health = _health_value(snapshot.get("queue"), fallback="unknown")
    provider_stage = "staging" if _safe_text(snapshot.get("provider_gateway"), fallback="") in {"staging", "operational"} else "preview"
    realtime_stage = "preview" if str(snapshot.get("realtime_sync") or "") == "not_production" else "staging"
    return [
        _component(
            "api",
            _health_value(snapshot.get("yonerai_api"), fallback="unknown"),
            "available" if snapshot.get("yonerai_api") == "operational" else "limited",
            "staging",
            "Staging API status is public-safe; production availability is not claimed.",
            updated_at=generated_at,
        ),
        _component(
            "auth",
            "operational",
            "available",
            "staging",
            "Staging auth/session boundary is available; production login is disabled.",
            updated_at=generated_at,
        ),
        _component(
            "provider_gateway",
            "operational" if provider_stage == "staging" else "unknown",
            "available" if provider_stage == "staging" else "limited",
            provider_stage,
            "Provider gateway state is public-safe and consent-gated.",
            updated_at=generated_at,
        ),
        _component(
            "official_execution_worker",
            worker_health,
            "unavailable" if worker_health == "offline" else "limited",
            "staging",
            "Worker availability is derived from cloud heartbeat freshness; self-report is advisory.",
            updated_at=_safe_timestamp(snapshot.get("last_worker_heartbeat_at") or generated_at),
            stale=worker_stale,
        ),
        _component(
            "run_queue",
            "degraded" if worker_health == "offline" and queue_health == "operational" else queue_health,
            "limited",
            "staging",
            "Run queue is metadata-only and waits for an available execution path.",
            updated_at=generated_at,
        ),
        _component(
            "realtime_sync",
            "degraded" if realtime_stage == "preview" else "operational",
            "limited" if realtime_stage == "preview" else "available",
            realtime_stage,
            "Realtime sync is contract-limited; no production sync claim is made.",
            updated_at=generated_at,
        ),
        _component(
            "web",
            "degraded" if _safe_text(snapshot.get("web"), fallback="") == "staging" else "unknown",
            "limited",
            "staging",
            "Web/status surface is staging-aware; production availability is not claimed.",
            updated_at=generated_at,
        ),
        _component(
            "audit",
            _health_value(snapshot.get("audit"), fallback="unknown"),
            "available" if snapshot.get("audit") == "operational" else "limited",
            "staging",
            "Audit status is metadata-only and does not expose raw events.",
            updated_at=generated_at,
        ),
        _component(
            "discord",
            "offline",
            "unavailable",
            "disabled",
            "Live Discord is not part of this staging runtime status.",
            updated_at=generated_at,
        ),
    ]


def _load_status_payload(
    *,
    source: str,
    status_source: str | None,
    allow_network_status_fetch: bool,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> tuple[Mapping[str, object], Mapping[str, str]]:
    if status_source:
        parsed = urlparse(status_source)
        if parsed.scheme:
            if not allow_network_status_fetch:
                raise StatusSnapshotError(
                    "status_snapshot_network_fetch_not_allowed",
                    "Status URL fetch requires --allow-network-status-fetch.",
                )
            origin, path = _validate_status_url(status_source)
            return _fetch_json(origin, path, transport=transport, timeout_seconds=timeout_seconds)
        return _read_status_source_file(status_source), {}
    if source == "fixture":
        fixture = (
            Path(__file__).resolve().parents[4]
            / "docs"
            / "contracts"
            / "fixtures"
            / "status-snapshot-v1"
            / "staging-offline-worker.fixture.json"
        )
        return _read_status_source_file(str(fixture)), {}
    if source != "live":
        raise StatusSnapshotError("status_snapshot_source_invalid", "Status snapshot source is invalid.")
    return _fetch_json(DEFAULT_STATUS_ORIGIN, STATUS_PATH, transport=transport, timeout_seconds=timeout_seconds)


def _should_fetch_health(*, source: str, status_source: str | None) -> bool:
    if status_source:
        return False
    return source == "live"


def _fetch_json(
    origin: str,
    path: str,
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> tuple[Mapping[str, object], Mapping[str, str]]:
    caller = transport or _default_header_json_transport
    status_code, payload, headers = caller("GET", f"{origin}{path}", {}, None, timeout_seconds)
    if not 200 <= status_code < 300:
        raise StatusSnapshotError(
            "status_snapshot_fetch_failed",
            "Status source returned a controlled non-success response.",
            status_code=status_code,
        )
    return payload, headers


def _default_header_json_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, object] | None,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
    data = None if body is None else json.dumps(dict(body)).encode("utf-8")
    try:
        request = Request(url, data=data, method=method.upper())
    except ValueError as exc:
        raise StatusSnapshotError("status_snapshot_url_invalid", "Status URL is invalid.") from exc
    request.add_header("Accept", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=timeout_seconds) as response:  # noqa: S310 - host is fixed or allowlisted.
            return int(response.status), _read_json_body(response.read()), dict(response.headers)
    except HTTPError as exc:
        if 300 <= int(exc.code) < 400:
            raise StatusSnapshotError(
                "status_snapshot_redirect_forbidden",
                "Status source attempted to redirect.",
                status_code=int(exc.code),
            ) from exc
        try:
            return int(exc.code), _read_json_body(exc.read()), dict(exc.headers)
        except StatusSnapshotError:
            return int(exc.code), {}, dict(exc.headers)
    except (OSError, URLError) as exc:
        raise StatusSnapshotError("status_snapshot_unreachable", "Status source is unreachable.") from exc


def _read_json_body(raw: bytes) -> Mapping[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StatusSnapshotError("status_snapshot_invalid_json", "Status source returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise StatusSnapshotError("status_snapshot_invalid_json", "Status source returned invalid JSON.")
    return value


def _read_status_source_file(path: str) -> Mapping[str, object]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise StatusSnapshotError(
            "status_snapshot_source_read_failed",
            "Failed to read status snapshot source file.",
        ) from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StatusSnapshotError(
            "status_snapshot_source_invalid_json",
            "Status snapshot source file is not valid JSON.",
        ) from exc
    if not isinstance(value, dict):
        raise StatusSnapshotError(
            "status_snapshot_source_invalid_json",
            "Status snapshot source file is not valid JSON.",
        )
    return value


def _validate_status_url(value: str) -> tuple[str, str]:
    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise StatusSnapshotError("status_snapshot_url_invalid", "Status URL is invalid.") from exc
    host = (parsed.hostname or "").lower()
    if parsed.username or parsed.password:
        raise StatusSnapshotError("status_snapshot_url_invalid", "Status URL must not include credentials.")
    if parsed.scheme != "https":
        raise StatusSnapshotError("status_snapshot_url_invalid", "Status URL must use HTTPS.")
    if host not in ALLOWED_STATUS_HOSTS or (parsed.port is not None and parsed.port != 443):
        raise StatusSnapshotError("status_snapshot_url_invalid", "Status URL host is not allowlisted.")
    if _is_private_host(host):
        raise StatusSnapshotError("status_snapshot_url_invalid", "Status URL host is not public.")
    path = parsed.path or "/"
    if path not in {STATUS_PATH, "/status.json", "/status/v1.json"}:
        raise StatusSnapshotError("status_snapshot_url_invalid", "Status URL path is not allowlisted.")
    if parsed.query or parsed.fragment:
        raise StatusSnapshotError("status_snapshot_url_invalid", "Status URL must not include query or fragment.")
    return f"{parsed.scheme}://{host}", path


def _validate_snapshot(snapshot: Mapping[str, object]) -> None:
    if snapshot.get("schema_version") != STATUS_SNAPSHOT_SCHEMA_VERSION:
        raise StatusSnapshotError("status_snapshot_schema_invalid", "Status snapshot schema version is invalid.")
    overall = snapshot.get("overall")
    components = snapshot.get("components")
    if not isinstance(overall, Mapping) or not isinstance(components, list):
        raise StatusSnapshotError("status_snapshot_schema_invalid", "Status snapshot shape is invalid.")
    if not components:
        raise StatusSnapshotError("status_snapshot_schema_invalid", "Status snapshot components are required.")
    _normalize_overall(overall)
    for item in components:
        if not isinstance(item, Mapping):
            raise StatusSnapshotError("status_snapshot_schema_invalid", "Status snapshot component is invalid.")
        _normalize_component(item)
    serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    if "not_production" in {str(overall.get("health")), str(overall.get("availability"))}:
        raise StatusSnapshotError("status_snapshot_schema_invalid", "not_production is not a health value.")
    _assert_public_safe_payload(snapshot)
    if "last_worker_id_hash" in serialized:
        raise StatusSnapshotError("status_snapshot_private_payload_rejected", "Status snapshot included private worker details.")


def _normalize_overall(value: object) -> dict[str, object]:
    data = value if isinstance(value, Mapping) else {}
    health = _health_value(data.get("health"), fallback="unknown")
    availability = _availability_value(data.get("availability"), fallback="limited")
    stage = _stage_value(data.get("stage"), fallback="preview")
    return {
        "health": health,
        "availability": availability,
        "stage": stage,
        "message": _safe_message(data.get("message"), fallback="Status snapshot is public-safe and contract-limited."),
    }


def _normalize_component(value: Mapping[str, object]) -> dict[str, object]:
    component_id = _safe_component_id(value.get("id"))
    return {
        "id": component_id,
        "health": _health_value(value.get("health"), fallback="unknown"),
        "availability": _availability_value(value.get("availability"), fallback="limited"),
        "stage": _stage_value(value.get("stage"), fallback="preview"),
        "message": _safe_message(value.get("message"), fallback="No public status message."),
        "updated_at": _safe_timestamp(value.get("updated_at")),
        "stale": bool(value.get("stale")),
        "incident_ref": _safe_incident_ref(value.get("incident_ref")),
        "known_component": component_id in CANONICAL_COMPONENTS,
    }


def _derive_overall(components: list[dict[str, object]], *, stage: str) -> dict[str, object]:
    health_rank = {
        "major_outage": 5,
        "partial_outage": 4,
        "offline": 4,
        "degraded": 3,
        "maintenance": 2,
        "unknown": 1,
        "operational": 0,
    }
    worst = "unknown"
    for item in components:
        health = str(item.get("health") or "unknown")
        if health_rank.get(health, 1) > health_rank.get(worst, 1):
            worst = health
    if worst == "offline":
        worst = "degraded"
    availability = "available" if worst == "operational" else "limited"
    return {
        "health": worst,
        "availability": availability,
        "stage": stage,
        "message": "Status is derived from public-safe component snapshots.",
    }


def _component(
    component_id: str,
    health: str,
    availability: str,
    stage: str,
    message: str,
    *,
    updated_at: str,
    stale: bool = False,
) -> dict[str, object]:
    return {
        "id": component_id,
        "health": _health_value(health),
        "availability": _availability_value(availability),
        "stage": _stage_value(stage),
        "message": _safe_message(message, fallback="No public status message."),
        "updated_at": updated_at,
        "stale": stale,
        "incident_ref": None,
        "known_component": component_id in CANONICAL_COMPONENTS,
    }


def _find_component(snapshot: Mapping[str, object], component_id: str) -> dict[str, object] | None:
    safe_id = _safe_component_id(component_id)
    components = snapshot.get("components") if isinstance(snapshot.get("components"), list) else []
    for item in components:
        if isinstance(item, Mapping) and item.get("id") == safe_id:
            return dict(item)
    return None


def _compatibility_report(health_payload: Mapping[str, object]) -> dict[str, object]:
    min_cli_version = _safe_version(health_payload.get("min_cli_version"))
    api_version = _safe_api_version(health_payload.get("api_version"))
    warning = False
    reason = "field_missing_no_warning"
    if min_cli_version:
        warning = _version_tuple(__version__) < _version_tuple(min_cli_version)
        reason = "min_cli_version_satisfied" if not warning else "min_cli_version_too_new"
    return {
        "contract_policy": STATUS_CONTRACT_POLICY_VERSION,
        "api_version": api_version,
        "min_cli_version": min_cli_version,
        "current_cli_version": __version__,
        "skew_warning": warning,
        "reason": reason,
        "compat_window": "current minor and previous minor",
        "missing_fields_warn": False,
    }


def _cache_report(status_headers: Mapping[str, str], health_headers: Mapping[str, str]) -> dict[str, object]:
    headers = {key.lower(): value for key, value in dict(status_headers).items()}
    health = {key.lower(): value for key, value in dict(health_headers).items()}
    return {
        "etag": _safe_text(headers.get("etag"), fallback=None),
        "cache_control": _safe_text(headers.get("cache-control"), fallback=None),
        "health_etag": _safe_text(health.get("etag"), fallback=None),
        "source_cache_supported": bool(headers.get("etag") or headers.get("cache-control")),
        "stale_handling_is_payload_explicit": True,
    }


def _base_report(operation: str) -> dict[str, object]:
    return {
        "schema_version": STATUS_SNAPSHOT_CLIENT_SCHEMA_VERSION,
        "ok": False,
        "operation": operation,
        "staging_only": True,
        "official_backend_called": False,
        "private_runtime_details_included": False,
        "production_cloud_claim": False,
    }


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


def _non_actions() -> list[str]:
    return [
        "no production Oracle/cloud runtime",
        "no Google token storage",
        "no provider key storage",
        "no raw run or conversation content",
        "no worker endpoint call",
    ]


def _safe_cache_policy(value: object) -> dict[str, object]:
    data = value if isinstance(value, Mapping) else {}
    return {
        "etag_supported": bool(data.get("etag_supported", True)),
        "cache_control_max_age_must_be_below_stale_after_seconds": bool(
            data.get("cache_control_max_age_must_be_below_stale_after_seconds", True)
        ),
    }


def _safe_component_id(value: object) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,80}", text):
        raise StatusSnapshotError("status_snapshot_component_invalid", "Status component id is invalid.")
    return text


def _safe_token(value: object, *, fallback: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_.:-]{4,120}", text):
        return text
    return fallback


def _safe_incident_ref(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", text):
        return None
    return text


def _safe_text(value: object, *, fallback: object, max_length: int = 240) -> object:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if any((ord(char) < 32 and char not in "\r\n\t") or ord(char) == 127 for char in text):
        return fallback
    text = re.sub(r"[\r\n\t]+", " ", text)
    lowered = text.lower()
    forbidden = (
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "authorization_code",
        "google_token",
        "staging_session_token",
        "api_key",
        "password",
        "arn:aws:",
        "c:\\users",
        "\\\\",
        "/users/",
        "/home/",
        "/root/",
        "169.254.169.254",
    )
    if any(marker in lowered for marker in forbidden):
        return fallback
    return text[:max_length]


def _safe_message(value: object, *, fallback: str) -> str:
    text = str(value or "").strip()
    _reject_private_text(text)
    return str(_safe_text(text, fallback=fallback, max_length=240))


def _reject_private_text(text: str) -> None:
    lowered = text.lower()
    if any(
        marker in lowered
        for marker in (
            "access_token",
            "refresh_token",
            "id_token",
            "client_secret",
            "authorization_code",
            "google_token",
            "staging_session_token",
            "api_key",
            "password",
            "arn:aws:",
            "c:\\users",
            "\\\\",
            "/users/",
            "/home/",
            "/root/",
            "169.254.169.254",
        )
    ):
        raise StatusSnapshotError(
            "status_snapshot_private_payload_rejected",
            "Status snapshot included non-public fields.",
        )
    for url_match in re.finditer(r"https?://[^\s\"'<>]+", text):
        try:
            parsed = urlparse(url_match.group(0))
        except ValueError as exc:
            raise StatusSnapshotError(
                "status_snapshot_private_payload_rejected",
                "Status snapshot included non-public fields.",
            ) from exc
        host = (parsed.hostname or "").lower()
        if not host or _is_private_host(host):
            raise StatusSnapshotError(
                "status_snapshot_private_payload_rejected",
                "Status snapshot included non-public fields.",
            )
    for match in re.finditer(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", lowered):
        try:
            address = ipaddress.ip_address(match.group(0))
        except ValueError:
            continue
        if address.is_private or address.is_loopback or address.is_link_local:
            raise StatusSnapshotError(
                "status_snapshot_private_payload_rejected",
                "Status snapshot included non-public fields.",
            )
    for match in re.finditer(r"(?<![A-Za-z0-9])(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f:.%]*(?![A-Za-z0-9])", text):
        try:
            address = ipaddress.ip_address(match.group(0).strip("[]"))
        except ValueError:
            continue
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
        ):
            raise StatusSnapshotError(
                "status_snapshot_private_payload_rejected",
                "Status snapshot included non-public fields.",
            )
    for match in re.finditer(r"\b(?:localhost|[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b", lowered):
        host = match.group(0).strip(".")
        if _is_private_host(host):
            raise StatusSnapshotError(
                "status_snapshot_private_payload_rejected",
                "Status snapshot included non-public fields.",
            )


def _safe_timestamp(value: object) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", text):
        return text
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value: object, *, fallback: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, number))


def _safe_timeout_seconds(value: object) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise StatusSnapshotError(
            "status_snapshot_timeout_invalid",
            "Status timeout must be a positive finite number.",
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 60:
        raise StatusSnapshotError(
            "status_snapshot_timeout_invalid",
            "Status timeout must be a positive finite number no greater than 60 seconds.",
        )
    return timeout


def _safe_version(value: object) -> str | None:
    text = str(value or "").strip()
    if re.fullmatch(r"v?\d+\.\d+\.\d+(?:-[A-Za-z0-9_.-]+)?", text):
        return text
    return None


def _safe_api_version(value: object) -> str | None:
    text = str(value or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_.:-]{3,120}", text):
        return text
    return None


def _version_tuple(value: object) -> tuple[int, int, int]:
    text = str(value or "0.0.0").strip().lstrip("v")
    main = text.split("-", 1)[0]
    parts = main.split(".")
    try:
        return tuple(int(part) for part in (parts + ["0", "0", "0"])[:3])  # type: ignore[return-value]
    except ValueError:
        return (0, 0, 0)


def _health_value(value: object, *, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    if text in HEALTH_VALUES:
        return text
    if text == "not_production":
        return "degraded"
    if text in {"staging", "contract_only", "preview"}:
        return "degraded"
    if text == "disabled":
        return "offline"
    return fallback


def _availability_value(value: object, *, fallback: str = "limited") -> str:
    text = str(value or "").strip()
    return text if text in AVAILABILITY_VALUES else fallback


def _stage_value(value: object, *, fallback: str = "preview") -> str:
    text = str(value or "").strip()
    return text if text in STAGE_VALUES else fallback


def _stage_from_environment(value: object) -> str:
    text = str(value or "").strip()
    if text == "staging":
        return "staging"
    if text == "production":
        return "production"
    return "preview"


def _snapshot_id(payload: Mapping[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
    return f"snapshot_{digest}"


def _assert_public_safe_payload(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    forbidden_markers = (
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "authorization_code",
        "google_token",
        "staging_session_token",
        "api_key",
        "password",
        "arn:aws:",
        "c:\\users",
        "\\\\",
        "/users/",
        "/home/",
        "/root/",
        "169.254.169.254",
        "last_worker_id_hash",
        "worker_pc",
        "internal_hostname",
    )
    if any(marker in serialized for marker in forbidden_markers):
        raise StatusSnapshotError(
            "status_snapshot_private_payload_rejected",
            "Status snapshot included non-public fields.",
        )
    if re.search(r"\b[\w.%+-]+@[\w.-]+\.[a-z]{2,}\b", serialized):
        raise StatusSnapshotError(
            "status_snapshot_private_payload_rejected",
            "Status snapshot included account-like details.",
        )
    for text in _iter_payload_text(payload):
        _reject_private_text(text)
    for match in re.finditer(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", serialized):
        try:
            if ipaddress.ip_address(match.group(0)).is_private or ipaddress.ip_address(match.group(0)).is_loopback:
                raise StatusSnapshotError(
                    "status_snapshot_private_payload_rejected",
                    "Status snapshot included private network details.",
                )
        except ValueError:
            continue


def _iter_payload_text(payload: object) -> list[str]:
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, Mapping):
        values: list[str] = []
        for key, value in payload.items():
            values.extend(_iter_payload_text(key))
            values.extend(_iter_payload_text(value))
        return values
    if isinstance(payload, list | tuple):
        values = []
        for value in payload:
            values.extend(_iter_payload_text(value))
        return values
    return []


def _is_private_host(host: str) -> bool:
    if host.lower().strip(".") == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host.endswith((".internal", ".local", ".lan", ".corp", ".home"))
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
    )


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)
