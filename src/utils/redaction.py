from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

# Keep this module dependency-free and safe to import anywhere (including CI/tests).


_SENSITIVE_KEY_MARKERS = (
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "session",
    "bearer",
)


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # OpenAI-style API keys (including service accounts).
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("openai_svcacct", re.compile(r"\bsk-svcacct-[A-Za-z0-9_-]{20,}\b")),
    # Google API keys.
    ("google_key", re.compile(r"\bAIzaSy[A-Za-z0-9_-]{20,}\b")),
    # Discord webhooks.
    ("discord_webhook", re.compile(r"https?://(?:canary\\.|ptb\\.)?discord\\.com/api/webhooks/\\d+/[A-Za-z0-9_-]+")),
    # PEM private keys.
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\\s\\S]+?-----END [A-Z ]*PRIVATE KEY-----")),
]


def _strip_query_from_urls(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        raw = match.group(0)
        try:
            split = urllib.parse.urlsplit(raw)
            if not split.query:
                return raw
            return urllib.parse.urlunsplit((split.scheme, split.netloc, split.path, "[REDACTED_QUERY]", split.fragment))
        except Exception:
            return raw

    return re.sub(r"https?://[^\s\"'<>]+", repl, text)


def redact_text(text: str) -> str:
    """Redact secrets from arbitrary text (best-effort)."""
    if not isinstance(text, str) or not text:
        return "" if text is None else str(text)

    out = _strip_query_from_urls(text)
    for label, pat in _PATTERNS:
        out = pat.sub("[REDACTED]", out)

    # Heuristic: Discord bot tokens often look like three dot-separated base64-ish chunks.
    # This is intentionally conservative to reduce false positives.
    out = re.sub(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}\b", "[REDACTED]", out)
    return out


def redact_json(value: Any) -> Any:
    """Recursively redact secrets inside JSON-like structures."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            lk = str(k).lower()
            if any(m in lk for m in _SENSITIVE_KEY_MARKERS):
                out[str(k)] = "[REDACTED]"
            else:
                out[str(k)] = redact_json(v)
        return out
    if isinstance(value, list):
        return [redact_json(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_json_string(raw: str, *, max_chars: int = 5000) -> str:
    """Redact a string that is expected to be JSON (but may be plain text)."""
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
        safe = redact_json(parsed)
        out = json.dumps(safe, ensure_ascii=False)
    except Exception:
        out = redact_text(raw)
    if len(out) > max_chars:
        out = out[: max(0, max_chars - 3)] + "..."
    return out
