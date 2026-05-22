from __future__ import annotations

import os
from typing import Iterable, Mapping

from .contracts import ProviderAdapter, ProviderCapabilities, ProviderStatus, UnavailableProviderAdapter
from .local import LocalLLMProviderAdapter
from .mock import MockProviderAdapter
from .openai_compatible import OpenAICompatibleProviderAdapter


class ProviderRegistry:
    def __init__(self, adapters: Iterable[ProviderAdapter]) -> None:
        self._adapters = {adapter.provider_id: adapter for adapter in adapters}

    def list_adapters(self) -> tuple[ProviderAdapter, ...]:
        return tuple(self._adapters[key] for key in sorted(self._adapters))

    def list_statuses(self) -> list[dict[str, object]]:
        return [adapter.status().to_public_dict() for adapter in self.list_adapters()]

    def resolve(self, provider_id: str) -> ProviderAdapter:
        normalized = normalize_provider_id(provider_id)
        if normalized == "auto":
            normalized = "mock"
        adapter = self._adapters.get(normalized)
        if adapter is None:
            return UnavailableProviderAdapter(
                normalized,
                capabilities=ProviderCapabilities(chat=False),
                reason="provider_not_registered",
            )
        return adapter

    def status_for(self, provider_id: str) -> ProviderStatus:
        return self.resolve(provider_id).status()


def normalize_provider_id(provider_id: str | None) -> str:
    text = str(provider_id or "auto").strip().lower().replace("_", "-")
    aliases = {
        "openai": "openai-compatible",
        "openai-compatible-local": "local",
        "local-openai-compatible": "local",
        "local-node": "local",
    }
    return aliases.get(text, text or "auto")


def build_default_provider_registry(env: Mapping[str, str | None] | None = None) -> ProviderRegistry:
    source = dict(os.environ if env is None else env)
    return ProviderRegistry(
        (
            MockProviderAdapter(),
            OpenAICompatibleProviderAdapter(source),
            LocalLLMProviderAdapter(source),
            UnavailableProviderAdapter(
                "anthropic",
                capabilities=ProviderCapabilities(chat=True, structured_output=True, external_provider=True, cloud=True),
                reason="anthropic_provider_contract_only",
            ),
            UnavailableProviderAdapter(
                "gemini",
                capabilities=ProviderCapabilities(chat=True, structured_output=True, vision=True, external_provider=True, cloud=True),
                reason="gemini_provider_contract_only",
            ),
        )
    )
