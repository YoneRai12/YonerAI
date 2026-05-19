from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest


repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.providers.local_llm import (  # noqa: E402
    LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
    LOCAL_LLM_PROVIDER_OLLAMA,
    LocalLLMConfig,
    LocalLLMConnectionError,
    LocalLLMProviderError,
    LocalLLMResponseError,
    LocalLLMSecurityError,
    build_local_llm_config,
    generate_local_llm_reply,
    normalize_local_llm_provider,
    validate_loopback_base_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://[::1]:11434",
    ],
)
def test_validate_loopback_base_url_accepts_loopback(url: str) -> None:
    assert validate_loopback_base_url(url).startswith("http")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://192.168.1.10:11434",
        "http://0.0.0.0:11434",
        "file:///tmp/local-model",
        "http://user:pass@127.0.0.1:11434",
    ],
)
def test_validate_loopback_base_url_rejects_non_loopback_or_credential_urls(url: str) -> None:
    with pytest.raises(LocalLLMSecurityError):
        validate_loopback_base_url(url)


@pytest.mark.parametrize(
    ("raw_provider", "expected"),
    [
        ("ollama", LOCAL_LLM_PROVIDER_OLLAMA),
        ("local-ollama", LOCAL_LLM_PROVIDER_OLLAMA),
        ("openai_compatible_local", LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE),
        ("openai-compatible-local", LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE),
        ("lmstudio", LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE),
        ("llama.cpp", LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE),
        ("text-generation-webui", LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE),
        ("localai", LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE),
    ],
)
def test_normalize_local_llm_provider_supports_canonical_and_documented_aliases(
    raw_provider: str, expected: str
) -> None:
    assert normalize_local_llm_provider(raw_provider) == expected


def test_normalize_local_llm_provider_rejects_unknown_provider() -> None:
    with pytest.raises(LocalLLMProviderError):
        normalize_local_llm_provider("remote-openai")


def test_build_local_llm_config_defaults_openai_compatible_local_to_loopback_v1() -> None:
    config = build_local_llm_config(
        {},
        provider="openai_compatible_local",
        model="lm-studio-model",
    )

    assert config.provider == LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE
    assert config.base_url == "http://127.0.0.1:1234/v1"
    assert config.model == "lm-studio-model"


def test_generate_local_llm_reply_uses_ollama_chat_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["model"] == "local-test"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        assert payload["stream"] is False
        assert payload["options"]["temperature"] == 0
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "local reply"}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    config = LocalLLMConfig(
        enabled=True,
        base_url="http://127.0.0.1:11434",
        model="local-test",
        timeout_seconds=1.0,
    )

    reply = generate_local_llm_reply(
        message="hello",
        conversation_id="local-smoke",
        config=config,
        client=client,
    )

    assert reply.reply == "local reply"
    assert reply.provider == "local-ollama"
    assert reply.model == "local-test"


def test_generate_local_llm_reply_uses_openai_compatible_chat_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["model"] == "lm-studio-model"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        assert payload["stream"] is False
        assert payload["temperature"] == 0.2
        assert payload["max_tokens"] == 128
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "openai compatible reply"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    config = LocalLLMConfig(
        enabled=True,
        base_url="http://127.0.0.1:1234/v1",
        model="lm-studio-model",
        timeout_seconds=1.0,
        provider=LOCAL_LLM_PROVIDER_OPENAI_COMPATIBLE,
        temperature=0.2,
        max_tokens=128,
    )

    reply = generate_local_llm_reply(
        message="hello",
        conversation_id="local-smoke",
        config=config,
        client=client,
    )

    assert reply.reply == "openai compatible reply"
    assert reply.provider == "local-openai-compatible"
    assert reply.model == "lm-studio-model"


def test_openai_compatible_local_base_url_still_rejects_remote_hosts() -> None:
    with pytest.raises(LocalLLMSecurityError):
        build_local_llm_config(
            {},
            provider="openai_compatible_local",
            base_url="https://api.openai.com/v1",
            model="gpt-not-local",
        )


def test_generate_local_llm_reply_rejects_empty_or_unknown_response_shape() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"done": True})))
    config = LocalLLMConfig(
        enabled=True,
        base_url="http://127.0.0.1:11434",
        model="local-test",
        timeout_seconds=1.0,
    )

    with pytest.raises(LocalLLMResponseError):
        generate_local_llm_reply(message="hello", conversation_id="local-smoke", config=config, client=client)


def test_generate_local_llm_reply_wraps_timeout_without_leaking_request_details() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout while calling http://127.0.0.1:11434/private")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    config = LocalLLMConfig(
        enabled=True,
        base_url="http://127.0.0.1:11434",
        model="local-test",
        timeout_seconds=1.0,
    )

    with pytest.raises(LocalLLMConnectionError) as excinfo:
        generate_local_llm_reply(message="hello", conversation_id="local-smoke", config=config, client=client)

    message = str(excinfo.value)
    assert "127.0.0.1" not in message
    assert "private" not in message
