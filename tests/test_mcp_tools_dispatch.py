from __future__ import annotations

import sys
import types

import pytest


if "discord" not in sys.modules:
    discord_stub = types.ModuleType("discord")

    class Message:  # pragma: no cover - minimal stub for typing import
        pass

    discord_stub.Message = Message
    sys.modules["discord"] = discord_stub

from src.cogs.tools import mcp_tools


class _DummyBot:
    def __init__(self, cog):
        self._cog = cog

    def get_cog(self, name: str):
        if name == "MCPCog":
            return self._cog
        return None


class _DummyMessage:
    def __init__(self, bot):
        self.client = bot


class _DummyMcpCog:
    def __init__(self, response):
        self._response = response

    async def call_local_tool(self, _tool_name, _args):
        return self._response


@pytest.mark.asyncio
async def test_dispatch_preserves_false_ok_from_mcp_response():
    mcp_cog = _DummyMcpCog({"ok": False, "error": "boom"})
    message = _DummyMessage(_DummyBot(mcp_cog))

    out = await mcp_tools.dispatch({}, message, tool_name="demo")

    assert out["ok"] is False
    assert out["raw"]["ok"] is False


@pytest.mark.asyncio
async def test_dispatch_uses_truthy_ok_from_mcp_response():
    mcp_cog = _DummyMcpCog({"ok": True, "content": [{"type": "text", "text": "done"}]})
    message = _DummyMessage(_DummyBot(mcp_cog))

    out = await mcp_tools.dispatch({}, message, tool_name="demo")

    assert out["ok"] is True
