from __future__ import annotations

from typing import Any, Mapping
from .contracts import (
    ProviderCapabilities,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    redact_env_presence,
)


LOCAL_PROVIDER_ENV_KEYS = (
    "ORA_LOCAL_LLM_ENABLED",
    "ORA_LOCAL_LLM_PROVIDER",
    "ORA_LOCAL_LLM_BASE_URL",
    "ORA_LOCAL_LLM_MODEL",
    "ORA_LOCAL_LLM_TIMEOUT_SECONDS",
)


class LocalLLMProviderAdapter:
    provider_id = "local"
    capabilities = ProviderCapabilities(
        chat=True,
        structured_output=False,
        streaming=False,
        vision=False,
        tool_use=False,
        local_only=True,
        cloud=False,
        external_provider=False,
    )

    def __init__(self, env: Mapping[str, str | None] | None = None, *, client: Any | None = None) -> None:
        self._env = dict(env or {})
        self._client = client
        self._config: object | None = None
        self._config_error: Exception | None = None
        self._config_error_reason: str | None = None
        try:
            from . import local_llm

            self._config = local_llm.build_local_llm_config(self._env)
        except ModuleNotFoundError as exc:
            self._config_error_reason = "local_provider_dependency_unavailable"
            self._config_error = exc
        except Exception as exc:
            self._config_error_reason = "local_provider_loopback_policy_rejected"
            self._config_error = exc

    def status(self) -> ProviderStatus:
        configured = self._configured()
        if self._config_error is not None:
            return ProviderStatus(
                provider_id=self.provider_id,
                configured=configured,
                available=False,
                reason=self._config_error_reason or "local_provider_unavailable",
                capabilities=self.capabilities,
                env_status=redact_env_presence(self._env, LOCAL_PROVIDER_ENV_KEYS),
            )
        assert self._config is not None
        return ProviderStatus(
            provider_id=self.provider_id,
            configured=configured,
            available=self._config.enabled,
            reason=None if self._config.enabled else "local_provider_not_enabled",
            capabilities=self.capabilities,
            env_status=redact_env_presence(self._env, LOCAL_PROVIDER_ENV_KEYS),
        )

    def generate(self, request: ProviderRequest, *, allow_live_call: bool = False) -> ProviderResponse:
        if not allow_live_call:
            raise ProviderError(
                self.provider_id,
                "local_live_call_disabled",
                "Local LLM execution requires explicit live opt-in.",
            )
        status = self.status()
        if not status.available:
            raise ProviderError(
                self.provider_id,
                "provider_unavailable",
                status.reason or "local_provider_unavailable",
                safe_context={"configured": status.configured},
            )
        try:
            from . import local_llm
        except ModuleNotFoundError as exc:
            raise ProviderError(
                self.provider_id,
                "provider_unavailable",
                "Local LLM provider dependency is unavailable.",
                safe_context={"configured": status.configured},
            ) from exc
        assert self._config is not None
        model = None if request.model == "local-node-required" else request.model
        try:
            reply = local_llm.generate_local_llm_reply(
                message=request.prompt,
                conversation_id=request.metadata.get("run_id", "yonerai-cli"),
                model=model,
                config=self._config,
                client=self._client,
            )
        except local_llm.LocalLLMError as exc:
            raise ProviderError(self.provider_id, "local_provider_error", str(exc)) from exc
        return ProviderResponse(
            provider=self.provider_id,
            model=reply.model,
            output_text=reply.reply,
            deterministic=False,
            finish_reason="stop",
        )

    def _configured(self) -> bool:
        return any(str(self._env.get(key) or "").strip() for key in LOCAL_PROVIDER_ENV_KEYS)
