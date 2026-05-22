from __future__ import annotations

import sys
import types
from queue import Empty, Queue
from types import SimpleNamespace

if "discord" not in sys.modules:
    discord_stub = types.ModuleType("discord")
    discord_stub.Color = SimpleNamespace(red=lambda: 0xFF0000, orange=lambda: 0xFFA500, green=lambda: 0x00FF00)
    discord_stub.Embed = object
    discord_stub.Attachment = object
    discord_stub.File = object
    discord_stub.Message = object
    discord_stub.Object = object
    discord_stub.User = object
    discord_stub.Interaction = object
    discord_stub.utils = SimpleNamespace(utcnow=lambda: None)
    app_commands_stub = types.ModuleType("discord.app_commands")
    app_commands_stub.command = lambda *args, **kwargs: (lambda func: func)
    app_commands_stub.describe = lambda *args, **kwargs: (lambda func: func)
    ext_stub = types.ModuleType("discord.ext")
    commands_stub = types.ModuleType("discord.ext.commands")
    commands_stub.Cog = object
    commands_stub.Bot = object
    commands_stub.Context = object
    commands_stub.command = lambda *args, **kwargs: (lambda func: func)
    tasks_stub = types.ModuleType("discord.ext.tasks")

    def loop(*_args, **_kwargs):
        def decorator(func):
            return func

        return decorator

    tasks_stub.loop = loop
    sys.modules["discord"] = discord_stub
    sys.modules["discord.app_commands"] = app_commands_stub
    sys.modules["discord.ext"] = ext_stub
    sys.modules["discord.ext.commands"] = commands_stub
    sys.modules["discord.ext.tasks"] = tasks_stub

from src.cogs.system import LOG_FORWARD_MAX_CHARS, SystemCog


def test_forwarded_log_text_redacts_secret_values_and_truncates() -> None:
    raw = (
        "token sk-" + ("A" * 24) + " "
        "webhook https://discord.com/api/webhooks/123/" + ("B" * 32) + " "
        "query https://example.com/callback?code=secret"
    )
    output = SystemCog._sanitize_forwarded_log_text(raw + (" x" * 1000))

    assert "sk-" not in output
    assert "webhooks/123" not in output
    assert "code=secret" not in output
    assert "[REDACTED]" in output
    assert len(output) <= LOG_FORWARD_MAX_CHARS


def test_private_log_channel_allows_forwarding_when_default_role_cannot_read() -> None:
    default_role = object()
    channel = SimpleNamespace(
        guild=SimpleNamespace(default_role=default_role),
        permissions_for=lambda role: SimpleNamespace(read_messages=False, view_channel=False),
    )

    assert SystemCog._is_private_log_channel(channel) is True


def test_public_log_channel_blocks_forwarding_when_default_role_can_read() -> None:
    default_role = object()
    channel = SimpleNamespace(
        guild=SimpleNamespace(default_role=default_role),
        permissions_for=lambda role: SimpleNamespace(read_messages=True, view_channel=True),
    )

    assert SystemCog._is_private_log_channel(channel) is False


def test_log_queue_drain_removes_pending_records() -> None:
    queue: Queue[str] = Queue()
    queue.put("secret one")
    queue.put("secret two")

    assert SystemCog._drain_log_queue(queue) == 2
    assert queue.empty()
    try:
        queue.get_nowait()
    except Empty:
        pass
    else:  # pragma: no cover - defensive failure path
        raise AssertionError("queue should be empty after drain")
