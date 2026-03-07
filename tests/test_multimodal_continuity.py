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


def _last_user_content(messages):
    return messages[-1]["content"]


async def _build(req: MessageRequest, history: list[SimpleNamespace], monkeypatch):
    async def _fake_profile(*_args, **_kwargs):
        return {}

    fake_memory_mod = types.ModuleType("ora_core.brain.memory")
    fake_memory_mod.memory_store = SimpleNamespace(
        get_or_create_profile=_fake_profile,
        get_channel_path=lambda *_args, **_kwargs: "",
    )
    monkeypatch.setitem(sys.modules, "ora_core.brain.memory", fake_memory_mod)
    spec = importlib.util.spec_from_file_location("ora_core.brain.context_test_impl", CONTEXT_PATH)
    assert spec and spec.loader
    context_mod = importlib.util.module_from_spec(spec)
    sys.modules["ora_core.brain.context_test_impl"] = context_mod
    spec.loader.exec_module(context_mod)
    repo = _FakeRepo(history)
    return await context_mod.ContextBuilder.build_context(req, "internal-user", "conv-1", repo)


def test_current_turn_image_attachment_is_used(monkeypatch) -> None:
    async def _run():
        req = _req(
            "この画像を説明して",
            attachments=[{"type": "image_url", "url": "https://example.com/first.png", "name": "first.png"}],
        )
        messages = await _build(req, [], monkeypatch)
        content = _last_user_content(messages)
        assert isinstance(content, list)
        assert any(part.get("type") == "image_url" for part in content)

    asyncio.run(_run())


def test_followup_reinjects_latest_prior_image_attachment(monkeypatch) -> None:
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
        assert any(part.get("type") == "text" and part.get("text") == "続き" for part in content)

    asyncio.run(_run())


def test_unrelated_followup_does_not_reinject_image(monkeypatch) -> None:
    async def _run():
        history = [
            _msg(
                author="user",
                content="この画像を説明して",
                attachments=[{"type": "image_url", "url": "https://example.com/first.png", "name": "first.png"}],
            ),
            _msg(author="assistant", content="最初の説明"),
        ]
        req = _req("今日は何曜日？")
        messages = await _build(req, history, monkeypatch)
        content = _last_user_content(messages)
        assert content == "今日は何曜日？"

    asyncio.run(_run())


def test_followup_reinject_caps_attachment_count(monkeypatch) -> None:
    async def _run():
        history = [
            _msg(
                author="user",
                content="この画像を見て",
                attachments=[
                    {"type": "image_url", "url": f"https://example.com/{idx}.png", "name": f"{idx}.png"}
                    for idx in range(5)
                ],
            ),
            _msg(author="assistant", content="見ました"),
        ]
        req = _req("しっかり見て")
        messages = await _build(req, history, monkeypatch)
        content = _last_user_content(messages)
        assert isinstance(content, list)
        image_parts = [part for part in content if part.get("type") == "image_url"]
        assert len(image_parts) == 3

    asyncio.run(_run())


def test_non_image_attachment_is_not_reinjected(monkeypatch) -> None:
    async def _run():
        history = [
            _msg(
                author="user",
                content="このファイルを見て",
                attachments=[{"type": "file_url", "url": "https://example.com/report.pdf", "name": "report.pdf"}],
            ),
            _msg(author="assistant", content="見ました"),
        ]
        req = _req("続き")
        messages = await _build(req, history, monkeypatch)
        content = _last_user_content(messages)
        assert content == "続き"

    asyncio.run(_run())
