import pytest


class _DummyORACog:
    async def _check_permission(self, user_id: int, perm: str) -> bool:
        return True


class _DummyBot:
    def __init__(self):
        self._cogs = {"ORACog": _DummyORACog()}

    def get_cog(self, name: str):
        return self._cogs.get(name)


class _DummyAuthor:
    def __init__(self, user_id: int):
        self.id = user_id


class _DummyChannel:
    def __init__(self, name: str = "general"):
        self.name = name
        self.sent = []

    async def send(self, content: str):
        self.sent.append(content)


class _DummyMessage:
    def __init__(self):
        self.author = _DummyAuthor(123)
        self.channel = _DummyChannel()
        self.guild = None


@pytest.mark.asyncio
async def test_say_skill_uses_bot_not_message_client():
    # Regression: discord.Message has no `.client` attribute; skills must use passed `bot`.
    from src.skills.say.tool import execute

    msg = _DummyMessage()  # intentionally has no `.client`
    bot = _DummyBot()

    res = await execute({"message": "hi"}, msg, bot=bot)
    assert "Message sent" in res
    assert msg.channel.sent == ["hi"]

