from __future__ import annotations

import ipaddress
import os
import threading
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx


LOCAL_LLM_PROVIDER_OLLAMA = "ollama"
LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE = "openai_compatible_local"
LOCAL_LLM_PROVIDER_ALIASES = {
    "ollama": LOCAL_LLM_PROVIDER_OLLAMA,
    "local-ollama": LOCAL_LLM_PROVIDER_OLLAMA,
    "openai_compatible_local": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "openai-compatible-local": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "openai_compatible": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "openai-compatible": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "lmstudio": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "lm_studio": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "lm-studio": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "llama_cpp": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "llama-cpp": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "llama.cpp": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "text_generation_webui": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "text-generation-webui": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    "localai": LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
}
LOCAL_LLM_PROVIDER_LABELS = {
    LOCAL_LLM_PROVIDER_OLLAMA: "local-ollama",
    LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE: "local-openai-compatible",
}
DEFAULT_LOCAL_LLM_PROVIDER = LOCAL_LLM_PROVIDER_OLLAMA
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_LOCAL_LLM_BASE_URL = DEFAULT_OLLAMA_BASE_URL
DEFAULT_LOCAL_LLM_MODEL = "llama3.2"
DEFAULT_OPENAI_COMPATIBLE_MODEL = "local-model"
DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS = 10.0
MAX_LOCAL_LLM_TIMEOUT_SECONDS = 30.0
MAX_LOCAL_LLM_MAX_TOKENS = 4096
DEFAULT_OLLAMA_TEMPERATURE = 0.0
LOOPBACK_HOSTNAMES = frozenset({"localhost"})
_DEFAULT_CLIENT: httpx.Client | None = None
_DEFAULT_CLIENT_LOCK = threading.Lock()


class LocalLLMError(Exception):
    """Base class for public-safe local LLM adapter failures."""


class LocalLLMDisabledError(LocalLLMError):
    """Raised when local mode is explicitly disabled."""


class LocalLLMSecurityError(LocalLLMError):
    """Raised when local LLM configuration crosses the loopback boundary."""


class LocalLLMProviderError(LocalLLMError):
    """Raised when local LLM provider selection is unsupported."""


class LocalLLMConnectionError(LocalLLMError):
    """Raised when the configured local LLM runtime is unavailable."""


class LocalLLMResponseError(LocalLLMError):
    """Raised when the local runtime returns an unsupported response."""


@dataclass(frozen=True)
class LocalLLMConfig:
    enabled: bool
    base_url: str
    model: str
    timeout_seconds: float
    provider: str = DEFAULT_LOCAL_LLM_PROVIDER
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class LocalLLMReply:
    reply: str
    provider: str
    model: str


def _env_enabled(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _parse_timeout(raw: str | None) -> float:
    if raw is None or not raw.strip():
        return DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except ValueError:
        return DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS
    if timeout <= 0:
        return DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS
    return min(timeout, MAX_LOCAL_LLM_TIMEOUT_SECONDS)


def _parse_optional_float(raw: str | float | int | None, *, lower: float, upper: float) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        if not raw.strip():
            return None
        raw = raw.strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < lower or value > upper:
        return None
    return value


def _parse_optional_int(raw: str | int | None, *, lower: int, upper: int) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        if not raw.strip():
            return None
        raw = raw.strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < lower or value > upper:
        return None
    return value


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip().lower()
    if normalized in LOOPBACK_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_loopback_base_url(raw_url: str) -> str:
    parsed = urlparse((raw_url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise LocalLLMSecurityError("Local LLM endpoint must use http or https on a loopback host.")
    if parsed.username or parsed.password:
        raise LocalLLMSecurityError("Local LLM endpoint must not embed credentials.")
    if parsed.query or parsed.fragment:
        raise LocalLLMSecurityError("Local LLM endpoint must not include query strings or fragments.")

    host = parsed.hostname
    if not host:
        raise LocalLLMSecurityError("Local LLM endpoint must include a loopback host.")

    if not is_loopback_host(host):
        raise LocalLLMSecurityError("Local LLM endpoint must use localhost or a loopback IP address.")

    normalized = parsed._replace(query="", fragment="").geturl().rstrip("/")
    return normalized


def _append_url_path(base_url: str, path_suffix: str) -> str:
    parsed = urlparse(base_url)
    base_path = parsed.path.rstrip("/")
    suffix = path_suffix.strip("/")
    path = f"{base_path}/{suffix}" if base_path else f"/{suffix}"
    return parsed._replace(path=path).geturl()


def normalize_local_llm_provider(raw_provider: str | None) -> str:
    if raw_provider is None or not raw_provider.strip():
        return DEFAULT_LOCAL_LLM_PROVIDER
    normalized = raw_provider.strip().lower()
    provider = LOCAL_LLM_PROVIDER_ALIASES.get(normalized)
    if provider is None:
        raise LocalLLMProviderError("Unsupported local LLM provider.")
    return provider


def _default_base_url_for_provider(provider: str) -> str:
    if provider == LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE:
        return DEFAULT_OPENAI_COMPATIBLE_BASE_URL
    return DEFAULT_OLLAMA_BASE_URL


def _default_model_for_provider(provider: str) -> str:
    if provider == LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE:
        return DEFAULT_OPENAI_COMPATIBLE_MODEL
    return DEFAULT_LOCAL_LLM_MODEL


def build_local_llm_config(
    environ: Mapping[str, str] | None = None,
    *,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LocalLLMConfig:
    source = os.environ if environ is None else environ
    enabled = _env_enabled(source.get("ORA_LOCAL_LLM_ENABLED"))
    selected_provider = normalize_local_llm_provider(provider or source.get("ORA_LOCAL_LLM_PROVIDER"))
    default_base_url = _default_base_url_for_provider(selected_provider)
    raw_base_url = base_url or source.get("ORA_LOCAL_LLM_BASE_URL") or default_base_url
    normalized_base_url = validate_loopback_base_url(raw_base_url)
    default_model = _default_model_for_provider(selected_provider)
    selected_model = (model or source.get("ORA_LOCAL_LLM_MODEL") or default_model).strip() or default_model
    timeout_seconds = _parse_timeout(source.get("ORA_LOCAL_LLM_TIMEOUT_SECONDS"))
    selected_temperature = (
        _parse_optional_float(temperature, lower=0.0, upper=2.0)
        if temperature is not None
        else _parse_optional_float(source.get("ORA_LOCAL_LLM_TEMPERATURE"), lower=0.0, upper=2.0)
    )
    selected_max_tokens = (
        _parse_optional_int(max_tokens, lower=1, upper=MAX_LOCAL_LLM_MAX_TOKENS)
        if max_tokens is not None
        else _parse_optional_int(source.get("ORA_LOCAL_LLM_MAX_TOKENS"), lower=1, upper=MAX_LOCAL_LLM_MAX_TOKENS)
    )
    return LocalLLMConfig(
        enabled=enabled,
        base_url=normalized_base_url,
        model=selected_model,
        timeout_seconds=timeout_seconds,
        provider=selected_provider,
        temperature=selected_temperature,
        max_tokens=selected_max_tokens,
    )


def _get_default_client() -> httpx.Client:
    global _DEFAULT_CLIENT
    with _DEFAULT_CLIENT_LOCK:
        if _DEFAULT_CLIENT is None or _DEFAULT_CLIENT.is_closed:
            _DEFAULT_CLIENT = httpx.Client()
        return _DEFAULT_CLIENT


def close_default_client() -> None:
    global _DEFAULT_CLIENT
    with _DEFAULT_CLIENT_LOCK:
        if _DEFAULT_CLIENT is not None:
            _DEFAULT_CLIENT.close()
            _DEFAULT_CLIENT = None


def _extract_ollama_reply(payload: object) -> str:
    if not isinstance(payload, dict):
        raise LocalLLMResponseError("Local LLM response must be a JSON object.")

    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        reply = message["content"].strip()
        if reply:
            return reply

    generated = payload.get("response")
    if isinstance(generated, str):
        reply = generated.strip()
        if reply:
            return reply

    raise LocalLLMResponseError("Local LLM response did not include assistant content.")


def _extract_openai_compatible_reply(payload: object) -> str:
    if not isinstance(payload, dict):
        raise LocalLLMResponseError("Local LLM response must be a JSON object.")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LocalLLMResponseError("OpenAI-compatible local response did not include choices.")

    first = choices[0]
    if not isinstance(first, dict):
        raise LocalLLMResponseError("OpenAI-compatible local response choice must be an object.")

    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        reply = message["content"].strip()
        if reply:
            return reply

    text = first.get("text")
    if isinstance(text, str):
        reply = text.strip()
        if reply:
            return reply

    raise LocalLLMResponseError("OpenAI-compatible local response did not include assistant content.")


def _ollama_chat_payload(message: str, selected_model: str, cfg: LocalLLMConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": selected_model,
        "messages": [{"role": "user", "content": message}],
        "stream": False,
    }
    options: dict[str, Any] = {}
    if cfg.temperature is not None:
        options["temperature"] = cfg.temperature
    else:
        options["temperature"] = DEFAULT_OLLAMA_TEMPERATURE
    if cfg.max_tokens is not None:
        options["num_predict"] = cfg.max_tokens
    if options:
        payload["options"] = options
    return payload


def _openai_compatible_chat_payload(message: str, selected_model: str, cfg: LocalLLMConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": selected_model,
        "messages": [{"role": "user", "content": message}],
        "stream": False,
    }
    if cfg.temperature is not None:
        payload["temperature"] = cfg.temperature
    if cfg.max_tokens is not None:
        payload["max_tokens"] = cfg.max_tokens
    return payload


def _chat_endpoint_for_provider(cfg: LocalLLMConfig) -> str:
    parsed = urlparse(cfg.base_url)
    normalized_path = parsed.path.rstrip("/")
    if cfg.provider == LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE:
        if normalized_path.endswith("/v1/chat/completions"):
            return cfg.base_url
        if normalized_path.endswith("/v1"):
            return _append_url_path(cfg.base_url, "chat/completions")
        return _append_url_path(cfg.base_url, "v1/chat/completions")
    if cfg.provider == LOCAL_LLM_PROVIDER_OLLAMA:
        if normalized_path.endswith("/api/chat"):
            return cfg.base_url
        if normalized_path.endswith("/api"):
            return _append_url_path(cfg.base_url, "chat")
        return _append_url_path(cfg.base_url, "api/chat")
    raise LocalLLMProviderError("Unsupported local LLM provider.")


def generate_local_llm_reply(
    *,
    message: str,
    conversation_id: str,
    model: str | None = None,
    config: LocalLLMConfig | None = None,
    client: httpx.Client | None = None,
) -> LocalLLMReply:
    cfg = config or build_local_llm_config()
    if not cfg.enabled:
        raise LocalLLMDisabledError("Local LLM mode is disabled.")

    selected_model = (model or cfg.model).strip() or cfg.model
    endpoint = _chat_endpoint_for_provider(cfg)
    if cfg.provider == LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE:
        payload = _openai_compatible_chat_payload(message, selected_model, cfg)
        extract_reply = _extract_openai_compatible_reply
    else:
        payload = _ollama_chat_payload(message, selected_model, cfg)
        extract_reply = _extract_ollama_reply

    active_client = client or _get_default_client()
    try:
        response = active_client.post(endpoint, json=payload, timeout=cfg.timeout_seconds)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise LocalLLMConnectionError("Local LLM runtime timed out.") from exc
    except httpx.HTTPError as exc:
        raise LocalLLMConnectionError("Local LLM runtime is unavailable on the configured loopback endpoint.") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise LocalLLMResponseError("Local LLM response was not valid JSON.") from exc

    return LocalLLMReply(reply=extract_reply(data), provider=LOCAL_LLM_PROVIDER_LABELS[cfg.provider], model=selected_model)
