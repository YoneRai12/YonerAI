from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def _prepare_core_path() -> None:
    core_src = Path(__file__).resolve().parents[1] / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_anthropic_adapter_requires_env_and_redacts_key() -> None:
    _prepare_core_path()
    from ora_core.providers import ProviderError, ProviderRequest
    from ora_core.providers.anthropic import AnthropicProviderAdapter

    pseudo_key = "redaction-fixture-key"
    adapter = AnthropicProviderAdapter({"YONERAI_ANTHROPIC_API_KEY": pseudo_key})
    status = adapter.status().to_public_dict()

    assert status["available"] is True
    assert status["env_status"]["YONERAI_ANTHROPIC_API_KEY"] == "present_redacted"
    assert pseudo_key not in json.dumps(status)
    with pytest.raises(ProviderError) as exc_info:
        adapter.generate(ProviderRequest(prompt="hello"), allow_live_call=True)
    public = exc_info.value.to_public_dict()
    assert public["code"] == "live_provider_env_not_enabled"
    assert pseudo_key not in json.dumps(public)


def test_anthropic_live_request_shape_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_core_path()
    from ora_core.providers import ProviderRequest
    from ora_core.providers.anthropic import AnthropicProviderAdapter

    seen: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> _FakeHTTPResponse:
        seen["timeout"] = timeout
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeHTTPResponse(
            {
                "type": "message",
                "model": "claude-test",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "anthropic reply"}],
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    adapter = AnthropicProviderAdapter(
        {
            "YONERAI_ANTHROPIC_API_KEY": "redaction-fixture-key",
            "YONERAI_ANTHROPIC_LIVE": "1",
            "YONERAI_ANTHROPIC_BASE_URL": "https://api.example.invalid",
            "YONERAI_ANTHROPIC_MODEL": "claude-test",
        }
    )
    response = adapter.generate(ProviderRequest(prompt="hello", system="be terse"), allow_live_call=True)

    assert seen["url"] == "https://api.example.invalid/v1/messages"
    assert seen["payload"] == {
        "model": "claude-test",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "hello"}],
        "system": "be terse",
    }
    headers = {str(key).lower(): value for key, value in seen["headers"].items()}
    assert headers["x-api-key"] == "redaction-fixture-key"
    assert headers["anthropic-version"] == "2023-06-01"
    assert response.provider == "anthropic"
    assert response.output_text == "anthropic reply"


def test_gemini_adapter_requires_env_and_redacts_key() -> None:
    _prepare_core_path()
    from ora_core.providers import ProviderError, ProviderRequest
    from ora_core.providers.gemini import GeminiProviderAdapter

    pseudo_key = "redaction-fixture-key"
    adapter = GeminiProviderAdapter({"YONERAI_GEMINI_API_KEY": pseudo_key})
    status = adapter.status().to_public_dict()

    assert status["available"] is True
    assert status["env_status"]["YONERAI_GEMINI_API_KEY"] == "present_redacted"
    assert pseudo_key not in json.dumps(status)
    with pytest.raises(ProviderError) as exc_info:
        adapter.generate(ProviderRequest(prompt="hello"), allow_live_call=True)
    public = exc_info.value.to_public_dict()
    assert public["code"] == "live_provider_env_not_enabled"
    assert pseudo_key not in json.dumps(public)


def test_gemini_live_request_shape_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_core_path()
    from ora_core.providers import ProviderRequest
    from ora_core.providers.gemini import GeminiProviderAdapter

    seen: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> _FakeHTTPResponse:
        seen["timeout"] = timeout
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeHTTPResponse(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "gemini reply"}]},
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    adapter = GeminiProviderAdapter(
        {
            "YONERAI_GEMINI_API_KEY": "redaction-fixture-key",
            "YONERAI_GEMINI_LIVE": "1",
            "YONERAI_GEMINI_BASE_URL": "https://generativelanguage.example.invalid/v1beta",
            "YONERAI_GEMINI_MODEL": "gemini-test",
        }
    )
    response = adapter.generate(ProviderRequest(prompt="hello", structured=True, system="be terse"), allow_live_call=True)

    assert seen["url"] == "https://generativelanguage.example.invalid/v1beta/models/gemini-test:generateContent"
    assert seen["payload"] == {
        "contents": [{"role": "user", "parts": [{"text": "hello"}]}],
        "systemInstruction": {"parts": [{"text": "be terse"}]},
        "generationConfig": {"responseMimeType": "application/json"},
    }
    headers = {str(key).lower(): value for key, value in seen["headers"].items()}
    assert headers["x-goog-api-key"] == "redaction-fixture-key"
    assert response.provider == "gemini"
    assert response.output_text == "gemini reply"
    assert response.finish_reason == "stop"


def test_execution_spine_external_provider_requires_live_without_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_core_path()
    from ora_core.execution import execute_task
    from ora_core.providers import build_default_provider_registry

    registry = build_default_provider_registry({"YONERAI_ANTHROPIC_API_KEY": "redaction-fixture-key"})
    result = execute_task("summarize public docs", mode="self-host", provider="anthropic", registry=registry).to_public_dict()

    assert result["ok"] is False
    assert result["error"]["code"] == "live_required"
    assert result["live_call_performed"] is False
    assert "redaction-fixture-key" not in json.dumps(result)


def test_execution_spine_external_provider_live_uses_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_core_path()
    from ora_core.execution import execute_task
    from ora_core.providers import build_default_provider_registry

    def fake_urlopen(request: object, timeout: float) -> _FakeHTTPResponse:
        return _FakeHTTPResponse(
            {
                "type": "message",
                "model": "claude-opus-4-1",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "execution reply"}],
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    registry = build_default_provider_registry(
        {
            "YONERAI_ANTHROPIC_API_KEY": "redaction-fixture-key",
            "YONERAI_ANTHROPIC_LIVE": "1",
        }
    )
    result = execute_task("summarize public docs", mode="self-host", provider="anthropic", live=True, registry=registry).to_public_dict()

    assert result["ok"] is True
    assert result["response"]["provider"] == "anthropic"
    assert result["response"]["model"] == "claude-opus-4-1"
    assert result["response"]["output_text"] == "execution reply"
    assert result["live_call_performed"] is True
    assert "redaction-fixture-key" not in json.dumps(result)


@pytest.mark.skipif(
    not (
        __import__("os").getenv("YONERAI_ANTHROPIC_LIVE_TEST") == "1"
        and __import__("os").getenv("YONERAI_ANTHROPIC_LIVE") == "1"
        and __import__("os").getenv("YONERAI_ANTHROPIC_API_KEY")
    ),
    reason="Anthropic live provider test is explicitly opt-in",
)
def test_anthropic_live_opt_in_smoke() -> None:
    _prepare_core_path()
    from ora_core.providers import ProviderRequest, build_default_provider_registry

    response = build_default_provider_registry().resolve("anthropic").generate(
        ProviderRequest(prompt="Reply with the word ok."),
        allow_live_call=True,
    )

    assert response.provider == "anthropic"
    assert response.output_text


@pytest.mark.skipif(
    not (
        __import__("os").getenv("YONERAI_GEMINI_LIVE_TEST") == "1"
        and __import__("os").getenv("YONERAI_GEMINI_LIVE") == "1"
        and __import__("os").getenv("YONERAI_GEMINI_API_KEY")
    ),
    reason="Gemini live provider test is explicitly opt-in",
)
def test_gemini_live_opt_in_smoke() -> None:
    _prepare_core_path()
    from ora_core.providers import ProviderRequest, build_default_provider_registry

    response = build_default_provider_registry().resolve("gemini").generate(
        ProviderRequest(prompt="Reply with the word ok."),
        allow_live_call=True,
    )

    assert response.provider == "gemini"
    assert response.output_text
