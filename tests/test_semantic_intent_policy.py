from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
import types

from _pytest.monkeypatch import MonkeyPatch

# Allow importing ora_core package from core/src during tests.
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
from src.cogs.handlers.tool_selector import ToolSelector
from src.utils.intent_semantics import classify_semantic_intent, has_explicit_export_constraint


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


def test_generic_image_request_injects_broad_summary_policy() -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-generic"},
            content="この画像を説明して",
            attachments=[_image("https://example.com/task-manager.png")],
            idempotency_key="generic-img-001",
            source="discord",
        )
        messages = await _build_context(req, _FakeRepo())
        joined = "\n".join(str(m.get("content") or "") for m in messages if m.get("role") == "system")
        assert "[IMAGE OUTPUT CONTRACT]" in joined
        assert "## 1. 何の画面か" in joined
        user_content = messages[-1]["content"]
        assert isinstance(user_content, list)
        assert sum(1 for part in user_content if part.get("type") == "image_url") == 1

    asyncio.run(_run())


def test_focused_image_request_stays_narrow() -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-focused"},
            content="CPUのところだけ説明して",
            attachments=[_image("https://example.com/task-manager.png")],
            idempotency_key="focused-img-001",
            source="discord",
        )
        messages = await _build_context(req, _FakeRepo())
        assert not any("[IMAGE OUTPUT CONTRACT]" in str(m.get("content") or "") for m in messages if m.get("role") == "system")

    asyncio.run(_run())


def test_followup_reinjects_latest_prior_image() -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-follow"},
            content="続き",
            client_history=[HistoryMessage(role="assistant", content="前の画像の説明です")],
            idempotency_key="follow-img-001",
            source="discord",
        )
        repo = _FakeRepo(
            [
                _msg("user", "この画像を説明して", attachments=[_image("https://example.com/1.png")]),
                _msg("assistant", "説明しました"),
            ]
        )
        messages = await _build_context(req, repo)
        user_content = messages[-1]["content"]
        assert isinstance(user_content, list)
        assert any(part.get("type") == "image_url" for part in user_content)

    asyncio.run(_run())


def test_unrelated_followup_does_not_reinject_image() -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-unrelated"},
            content="ありがとう",
            idempotency_key="unrelated-001",
            source="discord",
        )
        repo = _FakeRepo([_msg("user", "この画像を説明して", attachments=[_image("https://example.com/1.png")])])
        messages = await _build_context(req, repo)
        assert messages[-1]["content"] == "ありがとう"

    asyncio.run(_run())


def test_followup_carryover_caps_to_three_images() -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-cap"},
            content="しっかり見て",
            client_history=[HistoryMessage(role="assistant", content="前の画像の説明です")],
            idempotency_key="cap-0001",
            source="discord",
        )
        repo = _FakeRepo(
            [
                _msg(
                    "user",
                    "この画像を説明して",
                    attachments=[_image(f"https://example.com/{idx}.png", name=f"{idx}.png") for idx in range(5)],
                )
            ]
        )
        messages = await _build_context(req, repo)
        user_content = messages[-1]["content"]
        assert isinstance(user_content, list)
        assert sum(1 for part in user_content if part.get("type") == "image_url") == 3

    asyncio.run(_run())


def test_non_image_attachment_does_not_trigger_carryover() -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-nonimg"},
            content="続き",
            client_history=[HistoryMessage(role="assistant", content="前のファイルの説明です")],
            idempotency_key="nonimg-001",
            source="discord",
        )
        repo = _FakeRepo(
            [
                _msg(
                    "user",
                    "このファイルを見て",
                    attachments=[{"type": "file_url", "url": "https://example.com/report.pdf", "name": "report.pdf"}],
                )
            ]
        )
        messages = await _build_context(req, repo)
        assert messages[-1]["content"] == "続き"

    asyncio.run(_run())


def test_explicit_export_request_is_detected_semantically() -> None:
    text = "この結果をPDFで保存して"
    result = classify_semantic_intent(
        text,
        has_explicit_export_constraint=has_explicit_export_constraint(text),
    )
    assert result.save_export_intent is True
    assert ToolSelector._is_explicit_save_intent(text) is True


def test_ambiguous_request_defaults_to_normal() -> None:
    result = classify_semantic_intent("これどう？")
    assert result.low_confidence is True
    assert result.generic_image_overview is False
    assert result.focused_image_question is False
    assert result.image_followup is False
    assert result.save_export_intent is False
