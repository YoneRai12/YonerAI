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


ANTHROPIC_ENV_KEYS = (
    "YONERAI_ANTHROPIC_API_KEY",
    "YONERAI_ANTHROPIC_BASE_URL",
    "YONERAI_ANTHROPIC_MODEL",
    "YONERAI_ANTHROPIC_LIVE",
    "YONERAI_ANTHROPIC_TIMEOUT_SECONDS",
    "YONERAI_ANTHROPIC_VERSION",
)
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-1"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"


@dataclass(frozen=True)
class AnthropicConfig:
    api_key: str | None
    api_key_present: bool
    base_url: str
    base_url_configured: bool
    live_enabled: bool
    model: str
    timeout_seconds: float
    anthropic_version: str


class AnthropicProviderAdapter:
    provider_id = "anthropic"
    capabilities = ProviderCapabilities(
        chat=True,
        structured_output=False,
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
        configured = self.config.api_key_present or self.config.base_url_configured
        available = self.config.api_key_present
        return ProviderStatus(
            provider_id=self.provider_id,
            configured=configured,
            available=available,
            reason=None if available else "anthropic_provider_not_configured",
            capabilities=self.capabilities,
            env_status=redact_env_presence(self._env, ANTHROPIC_ENV_KEYS),
        )

    def build_messages_payload(self, request: ProviderRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": request.model or self.config.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system:
            payload["system"] = request.system
        return payload

    def generate(self, request: ProviderRequest, *, allow_live_call: bool = False) -> ProviderResponse:
        if not allow_live_call:
            raise ProviderError(
                self.provider_id,
                "live_provider_call_disabled",
                "Anthropic provider calls are disabled in preview and default tests.",
                safe_context={"provider_configured": self.status().configured},
            )
        if not self.config.live_enabled:
            raise ProviderError(
                self.provider_id,
                "live_provider_env_not_enabled",
                "Anthropic live execution requires YONERAI_ANTHROPIC_LIVE=1.",
                safe_context={"provider_configured": self.status().configured},
            )
        if not self.status().available:
            raise ProviderError(
                self.provider_id,
                "provider_unavailable",
                "Anthropic provider requires YONERAI_ANTHROPIC_API_KEY.",
                safe_context={"provider_configured": self.status().configured},
            )
        payload = self.build_messages_payload(request)
        response = self._post_messages_payload(payload)
        return ProviderResponse(
            provider=self.provider_id,
            model=str(response.get("model") or payload.get("model") or self.config.model),
            output_text=_extract_anthropic_text(response),
            deterministic=False,
            finish_reason=str(response.get("stop_reason") or "stop"),
        )

    def _post_messages_payload(self, payload: dict[str, object]) -> dict[str, object]:
        if not self.config.api_key:
            raise ProviderError(self.provider_id, "provider_unavailable", "Anthropic provider is not configured.")
        request = urllib.request.Request(
            _messages_url(self.config.base_url),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-api-key": self.config.api_key,
                "anthropic-version": self.config.anthropic_version,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise ProviderError(self.provider_id, "provider_http_error", f"Anthropic provider returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(self.provider_id, "provider_connection_error", "Anthropic provider request failed.") from exc
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError(self.provider_id, "provider_bad_response", "Anthropic provider returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise ProviderError(self.provider_id, "provider_bad_response", "Anthropic provider response must be a JSON object.")
        return decoded

    @staticmethod
    def _build_config(env: Mapping[str, str | None]) -> AnthropicConfig:
        api_key = str(env.get("YONERAI_ANTHROPIC_API_KEY") or "").strip() or None
        base_url_raw = str(env.get("YONERAI_ANTHROPIC_BASE_URL") or "").strip()
        model = str(env.get("YONERAI_ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL).strip() or DEFAULT_ANTHROPIC_MODEL
        version = str(env.get("YONERAI_ANTHROPIC_VERSION") or DEFAULT_ANTHROPIC_VERSION).strip() or DEFAULT_ANTHROPIC_VERSION
        return AnthropicConfig(
            api_key=api_key,
            api_key_present=bool(api_key),
            base_url=base_url_raw or DEFAULT_ANTHROPIC_BASE_URL,
            base_url_configured=bool(base_url_raw),
            live_enabled=str(env.get("YONERAI_ANTHROPIC_LIVE") or "").strip().lower() in {"1", "true", "yes", "on"},
            model=model,
            timeout_seconds=_parse_timeout_seconds(env.get("YONERAI_ANTHROPIC_TIMEOUT_SECONDS")),
            anthropic_version=version,
        )


def _parse_timeout_seconds(raw: str | None) -> float:
    try:
        value = float(str(raw or "").strip())
    except ValueError:
        return 20.0
    if value <= 0:
        return 20.0
    return min(value, 60.0)


def _messages_url(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProviderError("anthropic", "provider_config_invalid", "Anthropic base URL is invalid.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderError("anthropic", "provider_config_invalid", "Anthropic base URL must not include credentials, query, or fragment.")
    path = parsed.path.rstrip("/")
    if path.endswith("/v1/messages"):
        return parsed._replace(path=path, query="", fragment="").geturl()
    if path.endswith("/v1"):
        path = f"{path}/messages"
    else:
        path = f"{path}/v1/messages" if path else "/v1/messages"
    return parsed._replace(path=path, query="", fragment="").geturl()


def _extract_anthropic_text(payload: dict[str, object]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        raise ProviderError("anthropic", "provider_bad_response", "Anthropic response did not include content.")
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            text = item["text"].strip()
            if text:
                parts.append(text)
    if not parts:
        raise ProviderError("anthropic", "provider_bad_response", "Anthropic response did not include text content.")
    return "\n".join(parts)
