from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import yaml


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model_id: str

    def as_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "model_id": self.model_id}


class ModelRegistry:
    _VALID_TIERS = {"instant", "balanced", "pro"}
    _BAND_TO_TIER = {"instant": "instant", "task": "balanced", "agent": "pro"}

    def __init__(self, payload: dict[str, Any], *, strict: bool) -> None:
        if not isinstance(payload, dict):
            raise ValueError("model registry payload must be dict")

        self.strict = bool(strict)
        self.aliases = self._build_aliases(payload.get("aliases"))
        self.stable_fallback = self._normalize_spec(payload.get("stable_fallback"), field="stable_fallback")
        self._runtime_disabled: set[tuple[str, str]] = set()

        tiers_raw = payload.get("tiers")
        if not isinstance(tiers_raw, dict):
            raise ValueError("tiers is required")

        tiers: dict[str, tuple[ModelSpec, ...]] = {}
        for tier in self._VALID_TIERS:
            node = tiers_raw.get(tier)
            if not isinstance(node, dict):
                raise ValueError(f"tiers.{tier} is required")
            fallback_order = node.get("fallback_order")
            if not isinstance(fallback_order, list) or not fallback_order:
                raise ValueError(f"tiers.{tier}.fallback_order must be non-empty list")
            seen: set[tuple[str, str]] = set()
            resolved: list[ModelSpec] = []
            for item in fallback_order:
                spec = self._normalize_spec(item, field=f"tiers.{tier}.fallback_order")
                key = (spec.provider, spec.model_id)
                if key in seen:
                    raise ValueError(f"duplicate model in tiers.{tier}.fallback_order: {spec.provider}/{spec.model_id}")
                seen.add(key)
                resolved.append(spec)
            tiers[tier] = tuple(resolved)
        self.tiers = tiers

    def _build_aliases(self, raw_aliases: Any) -> dict[str, str]:
        aliases: dict[str, str] = {}
        if not isinstance(raw_aliases, dict):
            return aliases
        for k, v in raw_aliases.items():
            src = str(k or "").strip()
            dst = str(v or "").strip()
            if not src or not dst:
                continue
            aliases[src] = dst
            aliases[src.lower()] = dst
        return aliases

    def resolve_alias(self, model_id: str) -> str:
        raw = str(model_id or "").strip()
        if not raw:
            raise ValueError("model_id is required")
        return self.aliases.get(raw) or self.aliases.get(raw.lower()) or raw

    def _normalize_spec(self, raw_spec: Any, *, field: str) -> ModelSpec:
        if not isinstance(raw_spec, dict):
            raise ValueError(f"{field} must be object")
        provider = str(raw_spec.get("provider") or "").strip().lower()
        model_id_raw = str(raw_spec.get("model_id") or "").strip()
        if not provider:
            raise ValueError(f"{field}.provider is required")
        if not model_id_raw:
            raise ValueError(f"{field}.model_id is required")
        model_id = self.resolve_alias(model_id_raw)
        return ModelSpec(provider=provider, model_id=model_id)

    @classmethod
    def tier_for_route_band(cls, route_band: str | None) -> str:
        band = str(route_band or "").strip().lower()
        return cls._BAND_TO_TIER.get(band, "balanced")

    def disable_runtime(self, provider: str, model_id: str) -> None:
        key = (str(provider or "").strip().lower(), self.resolve_alias(model_id))
        self._runtime_disabled.add(key)

    def is_runtime_disabled(self, provider: str, model_id: str) -> bool:
        key = (str(provider or "").strip().lower(), self.resolve_alias(model_id))
        return key in self._runtime_disabled

    def resolve_candidates(self, *, route_band: str | None = None, tier: str | None = None) -> list[ModelSpec]:
        if tier is None:
            tier = self.tier_for_route_band(route_band)
        tier_norm = str(tier or "").strip().lower()
        if tier_norm not in self._VALID_TIERS:
            tier_norm = "balanced"

        ordered: list[ModelSpec] = list(self.tiers.get(tier_norm, ()))
        if self.strict:
            ordered.append(self.stable_fallback)

        out: list[ModelSpec] = []
        seen: set[tuple[str, str]] = set()
        for spec in ordered:
            key = (spec.provider, spec.model_id)
            if key in seen:
                continue
            seen.add(key)
            if key in self._runtime_disabled:
                continue
            out.append(spec)

        if not out:
            out = [self.stable_fallback]
        return out

    @staticmethod
    def is_model_not_found_error(exc: Exception) -> bool:
        msg = str(exc or "").lower()
        markers = (
            "model_not_found",
            "model not found",
            "unknown model",
            "no such model",
            "invalid model",
            "not a valid model",
        )
        return any(m in msg for m in markers)

    @classmethod
    def load_from_path(cls, path: str | Path, *, strict: bool) -> "ModelRegistry":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"model registry file not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
        return cls(payload, strict=strict)


_REGISTRY_CACHE: dict[tuple[str, bool, float], ModelRegistry] = {}
_REGISTRY_LOCK = Lock()


def _default_registry_path() -> Path:
    env_path = (os.getenv("MODEL_REGISTRY_PATH") or "").strip()
    if env_path:
        return Path(env_path)
    # core/src/ora_core/models/model_registry.py -> repo root is parents[4]
    return Path(__file__).resolve().parents[4] / "config" / "model_registry.yaml"


def _truthy(raw: str | None, *, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def get_model_registry(*, strict: bool | None = None) -> ModelRegistry:
    strict_mode = _truthy(os.getenv("MODEL_REGISTRY_STRICT"), default=True) if strict is None else bool(strict)
    registry_path = _default_registry_path()
    mtime = registry_path.stat().st_mtime if registry_path.exists() else -1.0
    key = (str(registry_path.resolve()) if registry_path.exists() else str(registry_path), strict_mode, float(mtime))

    with _REGISTRY_LOCK:
        cached = _REGISTRY_CACHE.get(key)
        if cached is not None:
            return cached
        reg = ModelRegistry.load_from_path(registry_path, strict=strict_mode)
        _REGISTRY_CACHE.clear()
        _REGISTRY_CACHE[key] = reg
        return reg
