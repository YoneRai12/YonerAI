"""Provider adapters for public-safe Core API paths."""

from .anthropic import AnthropicProviderAdapter
from .contracts import (
    ProviderAdapter,
    ProviderCapabilities,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
)
from .gemini import GeminiProviderAdapter
from .local import LocalLLMProviderAdapter
from .mock import MockProviderAdapter
from .openai_compatible import OpenAICompatibleProviderAdapter
from .registry import ProviderRegistry, build_default_provider_registry
from .setup import build_provider_setup_report

__all__ = [
    "AnthropicProviderAdapter",
    "GeminiProviderAdapter",
    "MockProviderAdapter",
    "LocalLLMProviderAdapter",
    "OpenAICompatibleProviderAdapter",
    "ProviderAdapter",
    "ProviderCapabilities",
    "ProviderError",
    "ProviderRegistry",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderStatus",
    "build_default_provider_registry",
    "build_provider_setup_report",
]
