from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
import types

from _pytest.monkeypatch import MonkeyPatch


CORE_SRC = Path(__file__).resolve().parents[1] / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

try:
    import ora_core.brain.memory as _real_memory  # type: ignore
except Exception:
    if "ora_core.brain.memory" not in sys.modules:
        mem_mod = types.ModuleType("ora_core.brain.memory")
        mem_mod.memory_store = SimpleNamespace()
        sys.modules["ora_core.brain.memory"] = mem_mod

from ora_core.api.schemas.messages import HistoryMessage, MessageRequest
from ora_core.brain.context import ContextBuilder
from ora_core.brain.memory import memory_store


class _FakeRepo:
    def __init__(self, messages: list[object] | None = None):
        self._messages = list(messages or [])

    async def get_messages(self, _conversation_id: str, limit: int = 20):
        return list(self._messages)[-limit:]


def _msg(author: str, content: str, attachments: list[dict] | None = None) -> object:
    return SimpleNamespace(author=author, content=content, attachments=attachments or [])


def _image(url: str, name: str = "img.png") -> dict:
    return {"type": "image_url", "url": url, "name": name, "mime": "image/png"}


async def _build_context(req: MessageRequest, repo: _FakeRepo) -> list[dict]:
    monkeypatch = MonkeyPatch()

    async def _fake_profile(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(memory_store, "get_or_create_profile", _fake_profile, raising=False)
    try:
        return await ContextBuilder.build_context(req, "internal-user", "conv-test", repo)
    finally:
        monkeypatch.undo()


def _system_messages(messages: list[dict]) -> list[str]:
    return [str(m.get("content") or "") for m in messages if m.get("role") == "system"]


def test_generic_image_request_gets_structured_output_contract() -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-generic-structured"},
            content="What is shown in this screenshot?",
            attachments=[_image("https://example.com/screen.png")],
            idempotency_key="generic-structured-001",
            source="discord",
        )
        messages = await _build_context(req, _FakeRepo())
        joined = "\n".join(_system_messages(messages))
        assert "[IMAGE OUTPUT CONTRACT]" in joined
        assert "## 1. 何の画面か" in joined
        assert "## 2. 主な区画" in joined
        assert "## 3. 注目点" in joined
        assert "## 4. 読み取れる値や文字" in joined
        assert "## 5. 要約" in joined

    asyncio.run(_run())


def test_focused_image_request_does_not_get_broad_contract() -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-focused-structured"},
            content="Focus only on the CPU section in the image.",
            attachments=[_image("https://example.com/screen.png")],
            idempotency_key="focused-structured-001",
            source="discord",
        )
        messages = await _build_context(req, _FakeRepo())
        joined = "\n".join(_system_messages(messages))
        assert "[IMAGE OUTPUT CONTRACT]" not in joined

    asyncio.run(_run())


def test_followup_with_prior_image_keeps_image_and_followup_contract() -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-followup-structured"},
            content="continue with the same screenshot",
            client_history=[HistoryMessage(role="assistant", content="I already explained the image once.")],
            idempotency_key="followup-structured-001",
            source="discord",
        )
        repo = _FakeRepo(
            [
                _msg("user", "What is shown in this screenshot?", attachments=[_image("https://example.com/prev.png")]),
                _msg("assistant", "This is the first explanation."),
            ]
        )
        messages = await _build_context(req, repo)
        joined = "\n".join(_system_messages(messages))
        assert "[IMAGE FOLLOW-UP CONTRACT]" in joined
        user_content = messages[-1]["content"]
        assert isinstance(user_content, list)
        assert any(part.get("type") == "image_url" for part in user_content)

    asyncio.run(_run())
