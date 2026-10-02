from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.views import image_gen


class _FakeResponse:
    def __init__(self) -> None:
        self.done = False
        self.defer_calls = 0

    def is_done(self) -> bool:
        return self.done

    async def defer(self) -> None:
        if self.done:
            raise AssertionError("interaction was deferred twice")
        self.done = True
        self.defer_calls += 1


class _FakeFollowup:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, content: str, **kwargs) -> None:
        self.messages.append(content)
        file = kwargs.get("file")
        if file is not None:
            file.close()


class _FakeInteraction:
    def __init__(self, *, stale: bool = False) -> None:
        self.response = _FakeResponse()
        self.followup = _FakeFollowup()
        self.edit_calls = 0
        self.stale = stale

    async def edit_original_response(self, **_kwargs) -> None:
        if self.stale:
            raise AssertionError("the saved interaction must not be reused")
        self.edit_calls += 1


class _FakeResourceManager:
    def __init__(self) -> None:
        self.contexts: list[str] = []

    async def switch_context(self, context: str) -> None:
        self.contexts.append(context)


class _FakeCog:
    def __init__(self) -> None:
        self.llm = None
        self.is_generating_image = False
        self.resource_manager = _FakeResourceManager()
        self.bot = SimpleNamespace(config=SimpleNamespace(sd_api_url="http://127.0.0.1:8188"))
        self.queue_calls = 0

    async def process_message_queue(self) -> None:
        self.queue_calls += 1


class _FakeWorkflow:
    def __init__(self, *, server_address: str) -> None:
        assert server_address == "127.0.0.1:8188"

    def generate_image(self, **_kwargs) -> bytes:
        return b"test-image"


def _make_view() -> tuple[image_gen.StyleSelectView, _FakeCog]:
    cog = _FakeCog()
    saved_interaction = _FakeInteraction(stale=True)
    view = image_gen.StyleSelectView(cog, saved_interaction, "a mountain", None, 1024, 1024)
    return view, cog


@pytest.mark.asyncio
async def test_auto_style_reuses_its_existing_defer(monkeypatch) -> None:
    monkeypatch.setattr(image_gen, "ComfyWorkflow", _FakeWorkflow)
    view, cog = _make_view()
    interaction = _FakeInteraction()

    await image_gen.StyleSelectView.style_auto(view, interaction, None)
    await asyncio.sleep(0)

    assert interaction.response.defer_calls == 1
    assert interaction.edit_calls == 2
    assert cog.resource_manager.contexts == ["image", "llm"]
    assert cog.queue_calls == 1


@pytest.mark.asyncio
async def test_normal_style_defers_once_before_generation(monkeypatch) -> None:
    monkeypatch.setattr(image_gen, "ComfyWorkflow", _FakeWorkflow)
    view, cog = _make_view()
    interaction = _FakeInteraction()

    await image_gen.StyleSelectView.style_nature(view, interaction, None)
    await asyncio.sleep(0)

    assert interaction.response.defer_calls == 1
    assert interaction.edit_calls == 1
    assert cog.resource_manager.contexts == ["image", "llm"]
    assert cog.queue_calls == 1
