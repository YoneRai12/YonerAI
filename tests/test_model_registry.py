from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow importing ora_core package from core/src during tests.
CORE_SRC = Path(__file__).resolve().parents[1] / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from ora_core.models.model_registry import ModelRegistry


def _payload() -> dict:
    return {
        "stable_fallback": {"provider": "openai", "model_id": "gpt-5-mini"},
        "aliases": {"fast-openai": "gpt-5.3-instant"},
        "tiers": {
            "instant": {
                "fallback_order": [
                    {"provider": "openai", "model_id": "fast-openai"},
                    {"provider": "google", "model_id": "gemini-3.1-flash-lite-preview"},
                ]
            },
            "balanced": {
                "fallback_order": [
                    {"provider": "openai", "model_id": "gpt-5-mini"},
                ]
            },
            "pro": {
                "fallback_order": [
                    {"provider": "openai", "model_id": "gpt-5"},
                    {"provider": "anthropic", "model_id": "claude-opus-4-1"},
                ]
            },
        },
    }


def test_model_registry_alias_resolution_and_order() -> None:
    reg = ModelRegistry(_payload(), strict=True)
    candidates = reg.resolve_candidates(route_band="instant")
    assert candidates[0].provider == "openai"
    assert candidates[0].model_id == "gpt-5.3-instant"
    assert candidates[-1].model_id == "gpt-5-mini"


def test_model_registry_rejects_duplicate_candidates_per_tier() -> None:
    bad = _payload()
    bad["tiers"]["instant"]["fallback_order"] = [
        {"provider": "openai", "model_id": "gpt-5-mini"},
        {"provider": "openai", "model_id": "gpt-5-mini"},
    ]
    with pytest.raises(ValueError):
        ModelRegistry(bad, strict=True)


def test_model_registry_strict_fallback_when_all_candidates_disabled() -> None:
    reg = ModelRegistry(_payload(), strict=True)
    for spec in list(reg.resolve_candidates(route_band="pro")):
        reg.disable_runtime(spec.provider, spec.model_id)
    out = reg.resolve_candidates(route_band="pro")
    assert len(out) == 1
    assert out[0].provider == "openai"
    assert out[0].model_id == "gpt-5-mini"
