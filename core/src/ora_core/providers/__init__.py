"""Provider adapters for public-safe Core API paths."""

from .contracts import (
    ProviderAdapter,
    ProviderCapabilities,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
)
from .mock import MockProviderAdapter
from .openai_compatible import OpenAICompatibleProviderAdapter
from .registry import ProviderRegistry, build_default_provider_registry

__all__ = [
    "MockProviderAdapter",
    "OpenAICompatibleProviderAdapter",
    "ProviderAdapter",
    "ProviderCapabilities",
    "ProviderError",
    "ProviderRegistry",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderStatus",
    "build_default_provider_registry",
]
