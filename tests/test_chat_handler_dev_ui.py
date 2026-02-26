import asyncio

from src.cogs.handlers.chat_handler import ChatHandler


class _DummyAuthor:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, text: str) -> None:
        self.sent.append(text)


class _DummyChannel:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, text: str) -> None:
        self.sent.append(text)


class _DummyMessage:
    def __init__(self, *, guild: bool) -> None:
        self.guild = object() if guild else None
        self.author = _DummyAuthor()
        self.channel = _DummyChannel()
        self.replies: list[str] = []

    async def reply(self, text: str, mention_author: bool = False) -> None:  # noqa: ARG002
        self.replies.append(text)


def _handler() -> ChatHandler:
    return ChatHandler.__new__(ChatHandler)


def test_public_run_detail_hides_run_id_for_guild_by_default() -> None:
    h = _handler()
    assert h._public_run_detail(run_id="run-abcdef", is_dm=False, dev_ui_enabled=False) == "connected"
    assert h._public_run_detail(run_id="run-abcdef", is_dm=False, dev_ui_enabled=True) == "connected"
    assert h._public_run_detail(run_id="run-abcdef", is_dm=True, dev_ui_enabled=False) == "connected"
    assert h._public_run_detail(run_id="run-abcdef", is_dm=True, dev_ui_enabled=True).startswith("run_id=")


def test_dev_ui_on_guild_sends_dm_debug_with_run_id() -> None:
    async def _run() -> None:
        h = _handler()
        msg = _DummyMessage(guild=True)
        route_meta = {"mode": "TASK", "route_band": "task", "route_score": 0.44, "function_category": "chat"}
        await h._deliver_dev_ui_meta(message=msg, run_id="run-12345678", route_meta=route_meta)
        assert len(msg.author.sent) == 1
        assert "run_id: run-12345678" in msg.author.sent[0]
        assert len(msg.channel.sent) == 0

    asyncio.run(_run())


def test_dev_ui_on_dm_includes_run_id_in_dm_channel() -> None:
    async def _run() -> None:
        h = _handler()
        msg = _DummyMessage(guild=False)
        route_meta = {"mode": "INSTANT", "route_band": "instant", "route_score": 0.2, "function_category": "chat"}
        await h._deliver_dev_ui_meta(message=msg, run_id="run-dm-01", route_meta=route_meta)
        assert len(msg.channel.sent) == 1
        assert "run_id: run-dm-01" in msg.channel.sent[0]

    asyncio.run(_run())
