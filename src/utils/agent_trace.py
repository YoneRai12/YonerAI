import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict

SENSITIVE_KEYS = ("token", "secret", "password", "api_key", "authorization", "cookie", "webhook")


def _is_enabled() -> bool:
    raw = (os.getenv("ORA_TRACE_ENABLED") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _log_path() -> str:
    return os.getenv("ORA_TRACE_LOG", os.path.join("logs", "agent_trace.jsonl"))


def _sanitize(value: Any, max_str: int = 500) -> Any:
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            lk = str(k).lower()
            if any(marker in lk for marker in SENSITIVE_KEYS):
                out[k] = "[REDACTED]"
            else:
                out[k] = _sanitize(v, max_str=max_str)
        return out
    if isinstance(value, list):
        return [_sanitize(v, max_str=max_str) for v in value]
    if isinstance(value, str):
        return _sanitize_text(value, max_str=max_str)
    return value


def _sanitize_text(value: str, max_str: int = 500) -> str:
    """Best-effort redaction for free-form text and URLs in trace payloads."""
    sanitized = value
    for marker in SENSITIVE_KEYS:
        safe_marker = re.escape(marker)
        sanitized = re.sub(
            rf"([?&]{safe_marker}=)([^&#\s]+)",
            r"\1[REDACTED]",
            sanitized,
            flags=re.IGNORECASE,
        )
        sanitized = re.sub(
            rf"\b({safe_marker}\s*[:=]\s*)([^,;\s]+)",
            r"\1[REDACTED]",
            sanitized,
            flags=re.IGNORECASE,
        )
    return sanitized[:max_str] + ("..." if len(sanitized) > max_str else "")


def trace_event(event: str, correlation_id: str = "", **payload: Any) -> None:
    """Write a sanitized single-line JSON trace event for agent debugging."""
    if not _is_enabled():
        return
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "cid": correlation_id,
        "payload": _sanitize(payload),
    }
    path = _log_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8", errors="ignore") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
