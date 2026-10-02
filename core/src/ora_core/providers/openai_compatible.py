from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
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
    "YONERAI_OPENAI_COMPATIBLE_LIVE",
    "YONERAI_OPENAI_COMPATIBLE_TIMEOUT_SECONDS",
)


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str | None
    api_key: str | None
    base_url_configured: bool
    api_key_present: bool
    live_enabled: bool
    model: str
    timeout_seconds: float


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
        if not allow_live_call:
            raise ProviderError(
                self.provider_id,
                "live_provider_call_disabled",
                "OpenAI-compatible provider calls are disabled in preview and default tests.",
                safe_context={"provider_configured": self.status().configured},
            )
        if not self.config.live_enabled:
            raise ProviderError(
                self.provider_id,
                "live_provider_env_not_enabled",
                "OpenAI-compatible live execution requires YONERAI_OPENAI_COMPATIBLE_LIVE=1.",
                safe_context={"provider_configured": self.status().configured},
            )
        if not self.status().available:
            raise ProviderError(
                self.provider_id,
                "provider_unavailable",
                "OpenAI-compatible provider requires configured base URL and API key.",
                safe_context={"provider_configured": self.status().configured},
            )
        payload = self.build_chat_payload(request)
        response = self._post_chat_payload(payload)
        return ProviderResponse(
            provider=self.provider_id,
            model=str(payload.get("model") or self.config.model),
            output_text=_extract_chat_text(response),
            deterministic=False,
            finish_reason="stop",
        )

    def _post_chat_payload(self, payload: dict[str, object]) -> dict[str, object]:
        if not self.config.base_url or not self.config.api_key:
            raise ProviderError(self.provider_id, "provider_unavailable", "OpenAI-compatible provider is not configured.")
        request = urllib.request.Request(
            _chat_completions_url(self.config.base_url),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise ProviderError(self.provider_id, "provider_http_error", f"OpenAI-compatible provider returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(self.provider_id, "provider_connection_error", "OpenAI-compatible provider request failed.") from exc
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError(self.provider_id, "provider_bad_response", "OpenAI-compatible provider returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise ProviderError(self.provider_id, "provider_bad_response", "OpenAI-compatible provider response must be a JSON object.")
        return decoded

    @staticmethod
    def _build_config(env: Mapping[str, str | None]) -> OpenAICompatibleConfig:
        base_url = str(env.get("YONERAI_OPENAI_COMPATIBLE_BASE_URL") or "").strip() or None
        api_key = str(env.get("YONERAI_OPENAI_COMPATIBLE_API_KEY") or "").strip() or None
        model = str(env.get("YONERAI_OPENAI_COMPATIBLE_MODEL") or "gpt-5.4").strip() or "gpt-5.4"
        live_enabled = str(env.get("YONERAI_OPENAI_COMPATIBLE_LIVE") or "").strip().lower() in {"1", "true", "yes", "on"}
        return OpenAICompatibleConfig(
            base_url=base_url,
            api_key=api_key,
            base_url_configured=bool(base_url),
            api_key_present=bool(api_key),
            live_enabled=live_enabled,
            model=model,
            timeout_seconds=_parse_timeout_seconds(env.get("YONERAI_OPENAI_COMPATIBLE_TIMEOUT_SECONDS")),
        )


def _parse_timeout_seconds(raw: str | None) -> float:
    try:
        value = float(str(raw or "").strip())
    except ValueError:
        return 20.0
    if value <= 0:
        return 20.0
    return min(value, 60.0)


def _chat_completions_url(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProviderError("openai-compatible", "provider_config_invalid", "OpenAI-compatible base URL is invalid.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderError(
            "openai-compatible",
            "provider_config_invalid",
            "OpenAI-compatible base URL must not include credentials, query, or fragment.",
        )
    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        return parsed._replace(path=path, query="", fragment="").geturl()
    if path.endswith("/v1"):
        path = f"{path}/chat/completions"
    else:
        path = f"{path}/v1/chat/completions" if path else "/v1/chat/completions"
    return parsed._replace(path=path, query="", fragment="").geturl()


def _extract_chat_text(payload: dict[str, object]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError("openai-compatible", "provider_bad_response", "OpenAI-compatible response did not include choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderError("openai-compatible", "provider_bad_response", "OpenAI-compatible choice must be an object.")
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        content = message["content"].strip()
        if content:
            return content
    text = first.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    raise ProviderError("openai-compatible", "provider_bad_response", "OpenAI-compatible response did not include assistant content.")
