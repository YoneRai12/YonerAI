from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.cogs.media import MediaCog


class _FakeResponse:
    def __init__(self) -> None:
        self._done = False
        self.sent = []

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, content: str, *, ephemeral: bool = False) -> None:
        self._done = True
        self.sent.append((content, ephemeral))

    async def defer(self, *, ephemeral: bool = False) -> None:
        self._done = True


class _FakeFollowup:
    def __init__(self) -> None:
        self.sent = []

    async def send(self, content: str, *, ephemeral: bool = False) -> None:
        self.sent.append((content, ephemeral))


@pytest.mark.asyncio
async def test_vc_returns_early_when_voice_disabled(monkeypatch):
    monkeypatch.setenv("ORA_VOICE_ENABLED", "0")

    cog = MediaCog.__new__(MediaCog)
    cog._store = SimpleNamespace(
        ensure_user=AsyncMock(side_effect=AssertionError("ensure_user must not be called"))
    )
    cog._voice_manager = SimpleNamespace(
        ensure_voice_client=AsyncMock(side_effect=AssertionError("voice path must not be called"))
    )

    interaction = SimpleNamespace(
        response=_FakeResponse(),
        followup=_FakeFollowup(),
        user=SimpleNamespace(id=123),
        guild=SimpleNamespace(id=456),
        channel=SimpleNamespace(id=789),
    )

    await MediaCog.vc.callback(cog, interaction)

    assert interaction.response.sent == [("音声機能は現在無効です。", True)]
    cog._store.ensure_user.assert_not_called()
    cog._voice_manager.ensure_voice_client.assert_not_called()
