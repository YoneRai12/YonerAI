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


GEMINI_ENV_KEYS = (
    "YONERAI_GEMINI_API_KEY",
    "YONERAI_GEMINI_BASE_URL",
    "YONERAI_GEMINI_MODEL",
    "YONERAI_GEMINI_LIVE",
    "YONERAI_GEMINI_TIMEOUT_SECONDS",
)
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash"


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str | None
    api_key_present: bool
    base_url: str
    base_url_configured: bool
    live_enabled: bool
    model: str
    timeout_seconds: float


class GeminiProviderAdapter:
    provider_id = "gemini"
    capabilities = ProviderCapabilities(
        chat=True,
        structured_output=True,
        streaming=False,
        vision=True,
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
            reason=None if available else "gemini_provider_not_configured",
            capabilities=self.capabilities,
            env_status=redact_env_presence(self._env, GEMINI_ENV_KEYS),
        )

    def build_generate_content_payload(self, request: ProviderRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
        }
        if request.system:
            payload["systemInstruction"] = {"parts": [{"text": request.system}]}
        if request.structured:
            payload["generationConfig"] = {"responseMimeType": "application/json"}
        return payload

    def generate(self, request: ProviderRequest, *, allow_live_call: bool = False) -> ProviderResponse:
        if not allow_live_call:
            raise ProviderError(
                self.provider_id,
                "live_provider_call_disabled",
                "Gemini provider calls are disabled in preview and default tests.",
                safe_context={"provider_configured": self.status().configured},
            )
        if not self.config.live_enabled:
            raise ProviderError(
                self.provider_id,
                "live_provider_env_not_enabled",
                "Gemini live execution requires YONERAI_GEMINI_LIVE=1.",
                safe_context={"provider_configured": self.status().configured},
            )
        if not self.status().available:
            raise ProviderError(
                self.provider_id,
                "provider_unavailable",
                "Gemini provider requires YONERAI_GEMINI_API_KEY.",
                safe_context={"provider_configured": self.status().configured},
            )
        model = request.model or self.config.model
        payload = self.build_generate_content_payload(request)
        response = self._post_generate_content_payload(model, payload)
        return ProviderResponse(
            provider=self.provider_id,
            model=model,
            output_text=_extract_gemini_text(response),
            deterministic=False,
            finish_reason=_extract_finish_reason(response),
        )

    def _post_generate_content_payload(self, model: str, payload: dict[str, object]) -> dict[str, object]:
        if not self.config.api_key:
            raise ProviderError(self.provider_id, "provider_unavailable", "Gemini provider is not configured.")
        request = urllib.request.Request(
            _generate_content_url(self.config.base_url, model),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-goog-api-key": self.config.api_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise ProviderError(self.provider_id, "provider_http_error", f"Gemini provider returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(self.provider_id, "provider_connection_error", "Gemini provider request failed.") from exc
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError(self.provider_id, "provider_bad_response", "Gemini provider returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise ProviderError(self.provider_id, "provider_bad_response", "Gemini provider response must be a JSON object.")
        return decoded

    @staticmethod
    def _build_config(env: Mapping[str, str | None]) -> GeminiConfig:
        api_key = str(env.get("YONERAI_GEMINI_API_KEY") or "").strip() or None
        base_url_raw = str(env.get("YONERAI_GEMINI_BASE_URL") or "").strip()
        model = str(env.get("YONERAI_GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
        return GeminiConfig(
            api_key=api_key,
            api_key_present=bool(api_key),
            base_url=base_url_raw or DEFAULT_GEMINI_BASE_URL,
            base_url_configured=bool(base_url_raw),
            live_enabled=str(env.get("YONERAI_GEMINI_LIVE") or "").strip().lower() in {"1", "true", "yes", "on"},
            model=model,
            timeout_seconds=_parse_timeout_seconds(env.get("YONERAI_GEMINI_TIMEOUT_SECONDS")),
        )


def _parse_timeout_seconds(raw: str | None) -> float:
    try:
        value = float(str(raw or "").strip())
    except ValueError:
        return 20.0
    if value <= 0:
        return 20.0
    return min(value, 60.0)


def _generate_content_url(base_url: str, model: str) -> str:
    parsed = urllib.parse.urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProviderError("gemini", "provider_config_invalid", "Gemini base URL is invalid.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderError("gemini", "provider_config_invalid", "Gemini base URL must not include credentials, query, or fragment.")
    path = parsed.path.rstrip("/")
    if not path:
        path = "/v1beta"
    if path.endswith(":generateContent"):
        return parsed._replace(path=path, query="", fragment="").geturl()
    model_id = urllib.parse.quote((model or DEFAULT_GEMINI_MODEL).strip(), safe="-_.")
    path = f"{path}/models/{model_id}:generateContent"
    return parsed._replace(path=path, query="", fragment="").geturl()


def _extract_gemini_text(payload: dict[str, object]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ProviderError("gemini", "provider_bad_response", "Gemini response did not include candidates.")
    first = candidates[0]
    if not isinstance(first, dict):
        raise ProviderError("gemini", "provider_bad_response", "Gemini candidate must be an object.")
    content = first.get("content")
    if not isinstance(content, dict):
        raise ProviderError("gemini", "provider_bad_response", "Gemini candidate did not include content.")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise ProviderError("gemini", "provider_bad_response", "Gemini content did not include parts.")
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            text = part["text"].strip()
            if text:
                texts.append(text)
    if not texts:
        raise ProviderError("gemini", "provider_bad_response", "Gemini response did not include text content.")
    return "\n".join(texts)


def _extract_finish_reason(payload: dict[str, object]) -> str:
    candidates = payload.get("candidates")
    if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
        reason = candidates[0].get("finishReason")
        if isinstance(reason, str) and reason.strip():
            return reason.strip().lower()
    return "stop"
