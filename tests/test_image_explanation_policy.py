from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import types

CORE_SRC = Path(__file__).resolve().parents[1] / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from ora_core.api.schemas.messages import MessageRequest

CONTEXT_PATH = CORE_SRC / "ora_core" / "brain" / "context.py"


class _FakeRepo:
    def __init__(self, messages):
        self._messages = list(messages)

    async def get_messages(self, *_args, **_kwargs):
        return list(self._messages)


def _msg(*, author: str, content: str, attachments: list[dict] | None = None):
    return SimpleNamespace(author=author, content=content, attachments=attachments or [])


def _req(content: str, attachments: list[dict] | None = None) -> MessageRequest:
    return MessageRequest(
        user_identity={"provider": "web", "id": "user-1", "display_name": "tester"},
        content=content,
        attachments=attachments or [],
        idempotency_key="abcdefgh",
        source="web",
    )


async def _build(req: MessageRequest, history: list[SimpleNamespace], monkeypatch):
    async def _fake_profile(*_args, **_kwargs):
        return {}

    fake_memory_mod = types.ModuleType("ora_core.brain.memory")
    fake_memory_mod.memory_store = SimpleNamespace(
        get_or_create_profile=_fake_profile,
        get_channel_path=lambda *_args, **_kwargs: "",
    )
    monkeypatch.setitem(sys.modules, "ora_core.brain.memory", fake_memory_mod)
    spec = importlib.util.spec_from_file_location("ora_core.brain.context_test_policy", CONTEXT_PATH)
    assert spec and spec.loader
    context_mod = importlib.util.module_from_spec(spec)
    sys.modules["ora_core.brain.context_test_policy"] = context_mod
    spec.loader.exec_module(context_mod)
    repo = _FakeRepo(history)
    return await context_mod.ContextBuilder.build_context(req, "internal-user", "conv-1", repo)


def _find_policy_message(messages) -> str | None:
    for msg in messages:
        if msg.get("role") == "system" and "[IMAGE EXPLANATION POLICY]" in str(msg.get("content", "")):
            return str(msg["content"])
    return None


def _last_user_content(messages):
    return messages[-1]["content"]


def test_generic_image_request_adds_broad_structure_policy(monkeypatch) -> None:
    async def _run():
        req = _req(
            "この画像を説明して",
            attachments=[{"type": "image_url", "url": "https://example.com/first.png", "name": "first.png"}],
        )
        messages = await _build(req, [], monkeypatch)
        policy = _find_policy_message(messages)
        assert policy is not None
        assert "overall screen" in policy
        assert "2-4 major visible sections" in policy
        assert "main focus area" in policy

    asyncio.run(_run())


def test_focused_request_does_not_add_broad_structure_policy(monkeypatch) -> None:
    async def _run():
        req = _req(
            "CPUのところだけ説明して",
            attachments=[{"type": "image_url", "url": "https://example.com/first.png", "name": "first.png"}],
        )
        messages = await _build(req, [], monkeypatch)
        assert _find_policy_message(messages) is None

    asyncio.run(_run())


def test_followup_carryover_remains_compatible(monkeypatch) -> None:
    async def _run():
        history = [
            _msg(
                author="user",
                content="この画像を説明して",
                attachments=[{"type": "image_url", "url": "https://example.com/first.png", "name": "first.png"}],
            ),
            _msg(author="assistant", content="最初の説明"),
        ]
        req = _req("続き")
        messages = await _build(req, history, monkeypatch)
        content = _last_user_content(messages)
        assert isinstance(content, list)
        urls = [part["image_url"]["url"] for part in content if part.get("type") == "image_url"]
        assert urls == ["https://example.com/first.png"]

    asyncio.run(_run())
