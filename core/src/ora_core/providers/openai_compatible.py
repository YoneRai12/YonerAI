from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .contracts import (
    ProviderCapabilities,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    redact_env_presence,
)


OPENAI_COMPATIBLE_ENV_KEYS = (
    "YONERAI_OPENAI_COMPATIBLE_BASE_URL",
    "YONERAI_OPENAI_COMPATIBLE_API_KEY",
    "YONERAI_OPENAI_COMPATIBLE_MODEL",
)


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url_configured: bool
    api_key_present: bool
    model: str


class OpenAICompatibleProviderAdapter:
    provider_id = "openai-compatible"
    capabilities = ProviderCapabilities(
        chat=True,
        structured_output=True,
        streaming=False,
        vision=False,
        tool_use=True,
        local_only=False,
        cloud=True,
        external_provider=True,
    )

    def __init__(self, env: Mapping[str, str | None] | None = None) -> None:
        self._env = dict(env or {})
        self.config = self._build_config(self._env)

    def status(self) -> ProviderStatus:
        configured = self.config.base_url_configured or self.config.api_key_present
        available = self.config.base_url_configured and self.config.api_key_present
        reason = None if available else "openai_compatible_provider_not_configured"
        return ProviderStatus(
            provider_id=self.provider_id,
            configured=configured,
            available=available,
            reason=reason,
            capabilities=self.capabilities,
            env_status=redact_env_presence(self._env, OPENAI_COMPATIBLE_ENV_KEYS),
        )

    def build_chat_payload(self, request: ProviderRequest) -> dict[str, object]:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        payload: dict[str, object] = {
            "model": request.model or self.config.model,
            "messages": messages,
            "stream": False,
        }
        if request.structured:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def generate(self, request: ProviderRequest, *, allow_live_call: bool = False) -> ProviderResponse:
        del request
        if not allow_live_call:
            raise ProviderError(
                self.provider_id,
                "live_provider_call_disabled",
                "OpenAI-compatible provider calls are disabled in preview and default tests.",
                safe_context={"provider_configured": self.status().configured},
            )
        raise ProviderError(
            self.provider_id,
            "live_provider_call_not_implemented",
            "Live OpenAI-compatible generation requires a separate approved provider lane.",
        )

    @staticmethod
    def _build_config(env: Mapping[str, str | None]) -> OpenAICompatibleConfig:
        base_url_configured = bool(str(env.get("YONERAI_OPENAI_COMPATIBLE_BASE_URL") or "").strip())
        api_key_present = bool(str(env.get("YONERAI_OPENAI_COMPATIBLE_API_KEY") or "").strip())
        model = str(env.get("YONERAI_OPENAI_COMPATIBLE_MODEL") or "gpt-5.4").strip() or "gpt-5.4"
        return OpenAICompatibleConfig(
            base_url_configured=base_url_configured,
            api_key_present=api_key_present,
            model=model,
        )
