from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.cogs.handlers.tool_selector import ToolSelector


class _FakeLLM:
    def __init__(self, response: str):
        self._resp = response

    async def chat(self, *_args, **_kwargs):
        return self._resp, None, {}


@pytest.mark.asyncio
async def test_router_strips_web_fetch_without_explicit_download(monkeypatch) -> None:
    # Strict mode on by default; ensure it is enabled for the test.
    monkeypatch.setenv("ORA_ROUTER_REQUIRE_EXPLICIT_DOWNLOAD", "1")

    bot = SimpleNamespace(config=SimpleNamespace(standard_model="gpt-5-mini", openai_api_key="dummy"))
    sel = ToolSelector(bot)

    # Force router to (incorrectly) include WEB_FETCH even though intents.download=false.
    sel.llm_client = _FakeLLM('{"categories":["WEB_READ","WEB_FETCH"],"intents":{"download":false,"screenshot":false,"browser_control":false}}')

    tools = [
        {"name": "read_web_page", "tags": ["web", "read"]},
        {"name": "web_download", "tags": ["browser", "download"]},
        {"name": "system_info", "tags": ["system"]},
    ]

    out = await sel.select_tools("評価して https://github.com/YoneRai12/ORA", available_tools=tools)
    names = {t["name"] for t in out}
    assert "web_download" not in names


@pytest.mark.asyncio
async def test_router_keeps_web_fetch_with_explicit_download(monkeypatch) -> None:
    monkeypatch.setenv("ORA_ROUTER_REQUIRE_EXPLICIT_DOWNLOAD", "1")

    bot = SimpleNamespace(config=SimpleNamespace(standard_model="gpt-5-mini", openai_api_key="dummy"))
    sel = ToolSelector(bot)
    sel.llm_client = _FakeLLM('{"categories":["WEB_FETCH"],"intents":{"download":true,"screenshot":false,"browser_control":false}}')

    tools = [
        {"name": "web_download", "tags": ["browser", "download"]},
        {"name": "read_web_page", "tags": ["web", "read"]},
    ]
    out = await sel.select_tools("このURLをダウンロードして検証して https://example.com", available_tools=tools)
    names = {t["name"] for t in out}
    assert "web_download" in names

