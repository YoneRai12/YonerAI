from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class UnsafeSignalError(ValueError):
    """Raised when a fixture contains non-public or action-taking material."""


FORBIDDEN_FIELD_NAMES = {
    "raw_prompt",
    "raw_completion",
    "raw_conversation",
    "chain_of_thought",
    "file_content",
    "user_id",
    "account_id",
    "ip",
    "ip_address",
    "discord_user_id",
    "email",
    "phone",
    "address",
    "device_fingerprint",
    "token",
    "secret",
    "password",
    "credential",
    "api_key",
    "private_key",
}

FORBIDDEN_ACTION_FIELDS = {
    "create_branch",
    "open_pr",
    "merge",
    "deploy",
    "apply_patch",
    "commit",
    "release",
    "push",
}

FORBIDDEN_LIVE_SOURCE_FIELDS = {
    "scrape_url",
    "sns_query",
    "competitor_scrape",
    "live_telemetry_source",
    "provider_log_source",
    "discord_runtime_source",
}

SECRET_VALUE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}"),
]

LOCAL_PATH_PATTERN = re.compile(r"([A-Za-z]:[\\/]|\\\\|/Users/|/home/)", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)
DATE_BUCKET_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALLOWED_SOURCES = {"synthetic_fixture", "manual_fixture", "public_safe_fixture"}
ALLOWED_PRIVACY_CLASSES = {"synthetic", "public_fixture"}


@dataclass(frozen=True)
class SignalEvent:
    id: str
    source: str
    kind: str
    summary: str
    severity: int
    frequency: int
    evidence: tuple[str, ...]
    created_at: str
    privacy_class: str
    approval_required: bool


def _check_key(key: str) -> None:
    normalized = key.strip().lower()
    forbidden = FORBIDDEN_FIELD_NAMES | FORBIDDEN_ACTION_FIELDS | FORBIDDEN_LIVE_SOURCE_FIELDS
    if normalized in forbidden:
        raise UnsafeSignalError(f"forbidden field: {key}")


def _check_string(value: str) -> None:
    if LOCAL_PATH_PATTERN.search(value):
        raise UnsafeSignalError("local or user-machine path is not allowed")
    if URL_PATTERN.search(value):
        raise UnsafeSignalError("live URL input is not allowed in proposal-only fixtures")
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(value):
            raise UnsafeSignalError("secret-shaped value is not allowed")


def _walk_public_safe(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            _check_key(str(key))
            _walk_public_safe(nested)
        return
    if isinstance(value, list):
        for nested in value:
            _walk_public_safe(nested)
        return
    if isinstance(value, str):
        _check_string(value)


def _bounded_int(payload: dict[str, Any], field: str) -> int:
    try:
        value = int(payload[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnsafeSignalError(f"{field} must be an integer") from exc
    if value < 1 or value > 5:
        raise UnsafeSignalError(f"{field} must be between 1 and 5")
    return value


def normalize_signal(payload: dict[str, Any]) -> SignalEvent:
    _walk_public_safe(payload)
    required = {
        "id",
        "source",
        "kind",
        "summary",
        "severity",
        "frequency",
        "evidence",
        "created_at",
        "privacy_class",
        "approval_required",
    }
    missing = required.difference(payload)
    if missing:
        raise UnsafeSignalError(f"missing required fields: {', '.join(sorted(missing))}")

    evidence = payload["evidence"]
    if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) for item in evidence):
        raise UnsafeSignalError("evidence must be a non-empty list of public-safe strings")

    approval_required = payload["approval_required"]
    if approval_required is not True:
        raise UnsafeSignalError("proposal-only signals must require owner approval")
    source = str(payload["source"])
    if source not in ALLOWED_SOURCES:
        raise UnsafeSignalError("source must be a synthetic or public-safe local fixture")
    privacy_class = str(payload["privacy_class"])
    if privacy_class not in ALLOWED_PRIVACY_CLASSES:
        raise UnsafeSignalError("privacy_class must be synthetic or public_fixture")
    created_at = str(payload["created_at"])
    if not DATE_BUCKET_PATTERN.match(created_at):
        raise UnsafeSignalError("created_at must be a date bucket, not an exact timestamp")

    return SignalEvent(
        id=str(payload["id"]),
        source=source,
        kind=str(payload["kind"]),
        summary=str(payload["summary"]),
        severity=_bounded_int(payload, "severity"),
        frequency=_bounded_int(payload, "frequency"),
        evidence=tuple(evidence),
        created_at=created_at,
        privacy_class=privacy_class,
        approval_required=True,
    )


def load_signal_fixture(path: str | Path) -> list[SignalEvent]:
    fixture_path = Path(path)
    if not fixture_path.is_file():
        raise UnsafeSignalError("fixture path must be a local file")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    signals = payload.get("signals") if isinstance(payload, dict) else payload
    if not isinstance(signals, list):
        raise UnsafeSignalError("fixture must contain a list of signals")
    return [normalize_signal(item) for item in signals]
