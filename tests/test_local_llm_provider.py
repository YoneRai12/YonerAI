from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest


repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.providers.local_llm import (  # noqa: E402
    LocalLLMConfig,
    LocalLLMConnectionError,
    LocalLLMResponseError,
    LocalLLMSecurityError,
    generate_local_llm_reply,
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


def test_generate_local_llm_reply_uses_ollama_chat_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = request.read().decode("utf-8")
        assert "hello" in payload
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
