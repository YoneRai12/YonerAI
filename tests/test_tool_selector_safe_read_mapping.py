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
async def test_router_web_read_includes_read_web_page_tool() -> None:
    """
    Regression test:
    - "read_web_page" does not follow the "web_*" prefix convention.
    - It must still be classified as WEB_READ so URL prompts don't end up with 0 tools
      when only public allowlist tools are visible.
    """
    bot = SimpleNamespace(config=SimpleNamespace(standard_model="gpt-5-mini", openai_api_key="dummy"))
    sel = ToolSelector(bot)
    sel.llm_client = _FakeLLM('{"categories":["WEB_READ"],"intents":{"download":false,"screenshot":false,"browser_control":false}}')

    tools = [
        {"name": "read_web_page", "tags": ["web", "read"]},
        {"name": "weather", "tags": ["system"]},
    ]

    out = await sel.select_tools("このURLを読んで https://example.com", available_tools=tools)
    names = {t["name"] for t in out}
    assert "read_web_page" in names


@pytest.mark.asyncio
async def test_router_system_util_includes_read_messages_tool() -> None:
    """
    Regression test:
    - "read_messages" contains "read" and was previously misclassified as CODEBASE.
    - It must be treated as SYSTEM_UTIL so "Fix this" / "check history" flows have tools.
    """
    bot = SimpleNamespace(config=SimpleNamespace(standard_model="gpt-5-mini", openai_api_key="dummy"))
    sel = ToolSelector(bot)
    sel.llm_client = _FakeLLM('{"categories":["SYSTEM_UTIL"],"intents":{"download":false,"screenshot":false,"browser_control":false}}')

    tools = [
        {"name": "read_messages", "tags": ["read", "history"]},
        {"name": "weather", "tags": ["system"]},
    ]
    out = await sel.select_tools("Fix this", available_tools=tools)
    names = {t["name"] for t in out}
    assert "read_messages" in names


@pytest.mark.asyncio
async def test_router_route_score_has_vision_floor() -> None:
    bot = SimpleNamespace(config=SimpleNamespace(standard_model="gpt-5-mini", openai_api_key="dummy"))
    sel = ToolSelector(bot)
    sel.llm_client = _FakeLLM('{"categories":["MEDIA_ANALYZE"],"intents":{"download":false,"screenshot":false,"browser_control":false}}')

    tools = [
        {"name": "read_web_page", "tags": ["web", "read"]},
    ]
    await sel.select_tools("これは何の画像？", available_tools=tools, has_vision_attachment=True)
    route = sel.last_route_meta
    assert float(route.get("route_score", 0.0)) >= 0.35
    assert str(route.get("mode") or "") in {"TASK", "AGENT_LOOP"}
    assert str(route.get("route_band") or "") in {"task", "agent"}
    assert "router_vision_floor_applied" in list(route.get("reason_codes") or [])


@pytest.mark.asyncio
async def test_router_high_risk_forces_task_mode() -> None:
    bot = SimpleNamespace(config=SimpleNamespace(standard_model="gpt-5-mini", openai_api_key="dummy"))
    sel = ToolSelector(bot)
    sel.llm_client = _FakeLLM('{"categories":["OTHER"],"intents":{"download":false,"screenshot":false,"browser_control":false}}')

    # Include a high-risk publish-like tool and enough tools to trigger high complexity.
    tools = [
        {"name": "deploy_release", "tags": []},
        {"name": "helper_a", "tags": []},
        {"name": "helper_b", "tags": []},
        {"name": "helper_c", "tags": []},
        {"name": "helper_d", "tags": []},
    ]
    await sel.select_tools("first do x and then after that do y and finally deploy", available_tools=tools)
    route = sel.last_route_meta
    assert str(route.get("mode") or "") == "TASK"
    assert str(route.get("route_band") or "") in {"task", "agent"}
    assert float(route.get("security_risk_score", 0.0)) >= 0.6
    assert "router_mode_forced_safe" in list(route.get("reason_codes") or [])


@pytest.mark.asyncio
async def test_router_instant_with_tools_forces_task_mode() -> None:
    bot = SimpleNamespace(config=SimpleNamespace(standard_model="gpt-5-mini", openai_api_key="dummy"))
    sel = ToolSelector(bot)
    sel.llm_client = _FakeLLM('{"categories":["WEB_READ"],"intents":{"download":false,"screenshot":false,"browser_control":false}}')

    # Force a low base score; tool presence should still prevent INSTANT mode.
    sel._compose_route_score = lambda **_kwargs: 0.2  # type: ignore[method-assign]

    tools = [
        {"name": "read_web_page", "tags": ["web", "read"]},
    ]
    out = await sel.select_tools("https://example.com を読んで", available_tools=tools)
    assert out

    route = sel.last_route_meta
    assert str(route.get("mode") or "") == "TASK"
    assert str(route.get("route_band") or "") in {"instant", "task", "agent"}
    assert "router_mode_forced_tools" in list(route.get("reason_codes") or [])
    route_meta = route.get("route_meta") if isinstance(route.get("route_meta"), dict) else {}
    assert route_meta.get("memory_used") is True

