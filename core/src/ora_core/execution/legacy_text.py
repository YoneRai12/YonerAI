from __future__ import annotations

import re
from collections.abc import Callable


LEGACY_TEXT_NORMALIZER_SOURCE = "src/cogs/ora_pure_helpers.py"
_CACHE_MISSING = object()
_LEGACY_CLEANER_CACHE: Callable[[str], str] | None | object = _CACHE_MISSING
_LEGACY_ROUTE_STRIPPER_CACHE: Callable[[str], str] | None | object = _CACHE_MISSING
_KNOWN_LEGACY_TAGS = (
    "analysis",
    "assistant",
    "commentary",
    "end",
    "final",
    "system",
    "tool",
    "user",
)
_LEGACY_BOUNDARY_TAG_PATTERN = re.compile(
    rf"^\s*<\|({'|'.join(_KNOWN_LEGACY_TAGS)})\|>|<\|end\|>\s*$",
    re.IGNORECASE,
)


def normalize_legacy_generated_text(text: object) -> str:
    """Apply extracted legacy ORA text cleaners when they are importable."""
    raw = "" if text is None else str(text)
    if not raw:
        return ""

    has_boundary = _LEGACY_BOUNDARY_TAG_PATTERN.search(raw) is not None
    cleaned = _strip_legacy_route_json(raw)
    if not has_boundary and _LEGACY_BOUNDARY_TAG_PATTERN.search(cleaned) is None:
        return raw
    if _LEGACY_BOUNDARY_TAG_PATTERN.search(cleaned) is None:
        return cleaned

    cleaner = _load_legacy_cleaner()
    if cleaner is None:
        return cleaned
    try:
        return cleaner(cleaned)
    except Exception:
        return cleaned


def legacy_text_normalizer_status() -> dict[str, object]:
    cleaner = _load_legacy_cleaner()
    route_stripper = _load_legacy_route_stripper()
    available = cleaner is not None
    sample_cleaned = cleaner("<|final|>demo") if cleaner else "demo"
    route_sample = route_stripper('before {"route_eval": {"route": "internal"}} after') if route_stripper else "before  after"
    ok = available and sample_cleaned == "demo"
    route_ok = route_stripper is not None and route_sample == "before  after"
    return {
        "name": "legacy_ora_text_normalizer",
        "source": LEGACY_TEXT_NORMALIZER_SOURCE,
        "status": "ok" if ok and route_ok else "unavailable",
        "available": available,
        "execution_spine_connected": ok,
        "route_json_stripper_connected": route_ok,
        "broad_ora_refactor": False,
    }


def _strip_legacy_route_json(raw: str) -> str:
    if "route_eval" not in raw:
        return raw
    route_stripper = _load_legacy_route_stripper()
    if route_stripper is None:
        return raw
    try:
        return route_stripper(raw)
    except Exception:
        return raw


def _load_legacy_cleaner() -> Callable[[str], str] | None:
    global _LEGACY_CLEANER_CACHE
    cached = _LEGACY_CLEANER_CACHE
    if cached is not _CACHE_MISSING:
        return cached if callable(cached) else None
    try:
        from src.cogs.ora_pure_helpers import clean_content
    except Exception:
        _LEGACY_CLEANER_CACHE = None
        return None
    else:
        _LEGACY_CLEANER_CACHE = clean_content
        return clean_content


def _load_legacy_route_stripper() -> Callable[[str], str] | None:
    global _LEGACY_ROUTE_STRIPPER_CACHE
    cached = _LEGACY_ROUTE_STRIPPER_CACHE
    if cached is not _CACHE_MISSING:
        return cached if callable(cached) else None
    try:
        from src.cogs.ora_pure_helpers import strip_route_json
    except Exception:
        _LEGACY_ROUTE_STRIPPER_CACHE = None
        return None
    else:
        _LEGACY_ROUTE_STRIPPER_CACHE = strip_route_json
        return strip_route_json
