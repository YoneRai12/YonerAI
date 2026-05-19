from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urljoin, urlparse

import httpx


DEFAULT_LOCAL_LLM_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_LOCAL_LLM_MODEL = "llama3.2"
DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS = 10.0
MAX_LOCAL_LLM_TIMEOUT_SECONDS = 30.0
LOOPBACK_HOSTNAMES = frozenset({"localhost"})
LOCAL_LLM_PROVIDER = "local-ollama"


class LocalLLMError(Exception):
    """Base class for public-safe local LLM adapter failures."""


class LocalLLMDisabledError(LocalLLMError):
    """Raised when local mode is explicitly disabled."""


class LocalLLMSecurityError(LocalLLMError):
    """Raised when local LLM configuration crosses the loopback boundary."""


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


@dataclass(frozen=True)
class LocalLLMReply:
    reply: str
    provider: str
    model: str


def _env_enabled(raw: str | None) -> bool:
    if raw is None:
        return True
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


def build_local_llm_config(environ: Mapping[str, str] | None = None) -> LocalLLMConfig:
    source = os.environ if environ is None else environ
    enabled = _env_enabled(source.get("ORA_LOCAL_LLM_ENABLED"))
    base_url = validate_loopback_base_url(source.get("ORA_LOCAL_LLM_BASE_URL", DEFAULT_LOCAL_LLM_BASE_URL))
    model = (source.get("ORA_LOCAL_LLM_MODEL") or DEFAULT_LOCAL_LLM_MODEL).strip() or DEFAULT_LOCAL_LLM_MODEL
    timeout_seconds = _parse_timeout(source.get("ORA_LOCAL_LLM_TIMEOUT_SECONDS"))
    return LocalLLMConfig(enabled=enabled, base_url=base_url, model=model, timeout_seconds=timeout_seconds)


def _extract_reply(payload: object) -> str:
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
    endpoint = urljoin(f"{cfg.base_url}/", "api/chat")
    payload = {
        "model": selected_model,
        "messages": [{"role": "user", "content": message}],
        "stream": False,
        "options": {
            "temperature": 0,
        },
    }

    owns_client = client is None
    active_client = client or httpx.Client()
    try:
        response = active_client.post(endpoint, json=payload, timeout=cfg.timeout_seconds)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise LocalLLMConnectionError("Local LLM runtime timed out.") from exc
    except httpx.HTTPError as exc:
        raise LocalLLMConnectionError("Local LLM runtime is unavailable on the configured loopback endpoint.") from exc
    finally:
        if owns_client:
            active_client.close()

    try:
        data = response.json()
    except ValueError as exc:
        raise LocalLLMResponseError("Local LLM response was not valid JSON.") from exc

    return LocalLLMReply(reply=_extract_reply(data), provider=LOCAL_LLM_PROVIDER, model=selected_model)
