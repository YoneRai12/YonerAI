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
async def test_string_false_intents_do_not_keep_remote_browser_tools() -> None:
    bot = SimpleNamespace(config=SimpleNamespace(standard_model="gpt-5-mini", openai_api_key="dummy"))
    sel = ToolSelector(bot)
    sel.llm_client = _FakeLLM(
        '{"categories":["WEB_READ"],"intents":{"download":"false","screenshot":"false","browser_control":"false"}}'
    )

    tools = [
        {"name": "web_remote_control", "tags": ["web"]},
        {"name": "web_action", "tags": ["web"]},
        {"name": "web_screenshot", "tags": ["web"]},
        {"name": "read_web_page", "tags": ["web", "read"]},
    ]

    out = await sel.select_tools("https://example.com を確認して", available_tools=tools)
    names = {t["name"] for t in out}
    assert "web_remote_control" not in names
    assert "web_action" not in names
    assert "web_screenshot" not in names
    assert "read_web_page" in names


def test_intent_flag_coercion_handles_string_booleans() -> None:
    assert ToolSelector._coerce_intent_flag("true") is True
    assert ToolSelector._coerce_intent_flag("false") is False
    assert ToolSelector._coerce_intent_flag("1") is True
    assert ToolSelector._coerce_intent_flag("0") is False
    assert ToolSelector._coerce_intent_flag("unexpected") is False

