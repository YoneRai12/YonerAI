from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from ora_core.providers.registry import ProviderRegistry, build_default_provider_registry, normalize_provider_id

from .task_classifier import TaskClassification


ModelTier = Literal["fast", "balanced", "strong", "local_required", "disabled"]


@dataclass(frozen=True)
class ProviderSelection:
    provider_id: str
    provider_available: bool
    provider_configured: bool
    provider_reason: str | None
    model_tier: ModelTier
    model_id: str
    approval_required: bool
    local_node_required: bool
    external_provider_allowed: bool
    disabled_reasons: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["disabled_reasons"] = list(self.disabled_reasons)
        payload["reasons"] = list(self.reasons)
        return payload


def select_provider_for_task(
    classification: TaskClassification,
    *,
    mode: str,
    provider_preference: str = "auto",
    registry: ProviderRegistry | None = None,
) -> ProviderSelection:
    registry = registry or build_default_provider_registry()
    provider_id = normalize_provider_id(provider_preference)
    local_required = classification.risk in {"private_data", "local_tool", "pc_operation", "dangerous"}
    approval_required = classification.risk in {"private_data", "local_tool", "pc_operation", "dangerous", "unsupported"}
    external_allowed = not local_required and classification.risk != "unsupported"
    tier = _tier_for_classification(classification)

    if local_required:
        provider_id = "local" if provider_id == "auto" else provider_id
    elif provider_id == "auto":
        provider_id = "mock"

    status = registry.status_for(provider_id)
    disabled_reasons: list[str] = []
    reasons = [f"classification:{classification.category}", f"risk:{classification.risk}"]
    if not status.available:
        disabled_reasons.append(status.reason or "provider_unavailable")
    if mode == "official_managed_cloud":
        disabled_reasons.append("official_managed_cloud_runtime_not_in_public_repo")
    if local_required:
        disabled_reasons.append("local_node_required")
    if classification.risk == "unsupported":
        disabled_reasons.append("unsupported_task")

    return ProviderSelection(
        provider_id=provider_id,
        provider_available=status.available,
        provider_configured=status.configured,
        provider_reason=status.reason,
        model_tier=tier,
        model_id=_model_for(provider_id, tier),
        approval_required=approval_required,
        local_node_required=local_required,
        external_provider_allowed=external_allowed,
        disabled_reasons=tuple(dict.fromkeys(disabled_reasons)),
        reasons=tuple(reasons),
    )


def _tier_for_classification(classification: TaskClassification) -> ModelTier:
    if classification.risk == "unsupported":
        return "disabled"
    if classification.risk in {"private_data", "local_tool", "pc_operation", "dangerous"}:
        return "local_required"
    if classification.category in {"coding", "long_running"}:
        return "strong"
    if classification.category in {"summarize_public", "research_like"}:
        return "balanced"
    return "fast"


def _model_for(provider_id: str, tier: ModelTier) -> str:
    if provider_id == "mock":
        return f"mock-{tier}"
    if provider_id == "local":
        return "local-node-required"
    if tier == "disabled":
        return "disabled"
    registry_tier = {"fast": "instant", "balanced": "balanced", "strong": "pro"}.get(tier, "balanced")
    try:
        from ora_core.models import get_model_registry

        candidates = get_model_registry(strict=False).resolve_candidates(tier=registry_tier)
    except Exception:
        return "model-registry-unavailable"
    for candidate in candidates:
        if provider_id == "openai-compatible" and candidate.provider == "openai":
            return candidate.model_id
        if provider_id == "anthropic" and candidate.provider == "anthropic":
            return candidate.model_id
        if provider_id == "gemini" and candidate.provider in {"gemini", "google"}:
            return candidate.model_id
    if provider_id == "anthropic":
        return "claude-opus-4-1"
    if provider_id == "gemini":
        return "gemini-3.1-flash"
    return candidates[0].model_id if candidates else "model-unavailable"
