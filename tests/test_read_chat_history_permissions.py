from __future__ import annotations

import pytest

from src.skills.read_chat_history.tool import execute


class _Perms:
    def __init__(self, view_channel: bool, read_message_history: bool):
        self.view_channel = view_channel
        self.read_message_history = read_message_history


class _DummyAuthor:
    display_name = "tester"
    bot = False


class _DummyChannel:
    id = 123
    name = "private"

    def __init__(self, view_channel: bool, read_history: bool):
        self._perms = _Perms(view_channel=view_channel, read_message_history=read_history)

    def permissions_for(self, _author):
        return self._perms

    async def history(self, limit: int = 20):
        self.last_limit = limit
        if False:
            yield limit


class _DummyMessage:
    guild = None

    def __init__(self, channel):
        self.channel = channel
        self.author = _DummyAuthor()


@pytest.mark.asyncio
async def test_read_chat_history_denies_without_permission():
    msg = _DummyMessage(_DummyChannel(view_channel=False, read_history=False))

    result = await execute({"limit": 5}, msg)

    assert result == "Error: You do not have permission to read this channel's history."


@pytest.mark.asyncio
async def test_read_chat_history_caps_limit_to_50():
    channel = _DummyChannel(view_channel=True, read_history=True)
    msg = _DummyMessage(channel)

    await execute({"limit": 500}, msg)

    assert channel.last_limit == 50
