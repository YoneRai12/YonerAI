from __future__ import annotations

from typing import Callable


LEGACY_TEXT_NORMALIZER_SOURCE = "src/cogs/ora_pure_helpers.py"
_CACHE_MISSING = object()
_LEGACY_CLEANER_CACHE: Callable[[str], str] | None | object = _CACHE_MISSING


def normalize_legacy_generated_text(text: object) -> str:
    """Apply the legacy ORA generated-text cleaner when it is importable."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    cleaner = _load_legacy_cleaner()
    if cleaner is None:
        return raw
    try:
        return cleaner(raw)
    except Exception:
        return raw


def legacy_text_normalizer_status() -> dict[str, object]:
    cleaner = _load_legacy_cleaner()
    available = cleaner is not None
    sample_cleaned = cleaner("<|final|>demo") if cleaner else "demo"
    ok = available and sample_cleaned == "demo"
    return {
        "name": "legacy_ora_text_normalizer",
        "source": LEGACY_TEXT_NORMALIZER_SOURCE,
        "status": "ok" if ok else "unavailable",
        "available": available,
        "execution_spine_connected": ok,
        "broad_ora_refactor": False,
    }


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
