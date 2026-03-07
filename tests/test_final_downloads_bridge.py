from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

from tests.test_core_effective_route import MessageRequest, _event_data, _run_main_process


class _ToolThenAnswerEngine:
    def __init__(self, final_text: str = "done") -> None:
        self._final_text = final_text
        self._call_count = 0

    async def generate(self, *_args, **_kwargs):
        self._call_count += 1
        if self._call_count == 1:
            tool_calls = [
                SimpleNamespace(
                    id="tc-download-1",
                    function=SimpleNamespace(name="dummy_tool", arguments="{}"),
                )
            ]
            msg = SimpleNamespace(content="", tool_calls=tool_calls)
        else:
            msg = SimpleNamespace(content=self._final_text, tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None, model="test-model")


class _DownloadsRunner:
    def __init__(self, _repo):
        return None

    async def run_tool(
        self,
        tool_call_id: str,
        run_id: str,
        user_id: str,
        tool_name: str,
        args: dict,
        client_type: str,
        request_meta: dict | None = None,
        effective_route: dict | None = None,
    ) -> dict:
        del tool_call_id, run_id, user_id, tool_name, args, client_type, request_meta, effective_route
        return {
            "status": "completed",
            "result": {
                "ok": True,
                "downloads": [
                    {
                        "url": "https://files.yonerai.com/v1/files/file_123/download",
                        "label": "report.pdf",
                        "file_id": "file_123",
                    }
                ],
            },
        }


class _VideoMetaRunner:
    def __init__(self, _repo):
        return None

    async def run_tool(
        self,
        tool_call_id: str,
        run_id: str,
        user_id: str,
        tool_name: str,
        args: dict,
        client_type: str,
        request_meta: dict | None = None,
        effective_route: dict | None = None,
    ) -> dict:
        del tool_call_id, run_id, user_id, tool_name, args, client_type, request_meta, effective_route
        return {
            "status": "completed",
            "result": {
                "ok": True,
                "video_meta": {
                    "download_page_url": "https://files.yonerai.com/s/share_abc",
                    "filename": "clip.mp4",
                },
            },
        }


def test_final_event_with_explicit_downloads_includes_metadata(monkeypatch) -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-downloads"},
            content="please generate a file",
            idempotency_key=f"downloads-{uuid.uuid4().hex[:6]}",
            source="discord",
            available_tools=[{"name": "dummy_tool", "description": "tool", "parameters": {"type": "object"}}],
            route_hint={"route_score": 0.5, "difficulty_score": 0.5, "security_risk_score": 0.1},
        )
        events = await _run_main_process(
            monkeypatch,
            req,
            run_id=f"run-downloads-{uuid.uuid4().hex[:8]}",
            omni_engine=_ToolThenAnswerEngine(final_text="rendered answer"),
            tool_runner_cls=_DownloadsRunner,
        )
        final = _event_data(events, "final")
        assert final["output_text"] == "rendered answer"
        assert final["downloads"] == [
            {
                "url": "https://files.yonerai.com/v1/files/file_123/download",
                "label": "report.pdf",
                "file_id": "file_123",
            }
        ]

    asyncio.run(_run())


def test_final_event_bridges_video_meta_download_page_url(monkeypatch) -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-video-meta"},
            content="please render a video",
            idempotency_key=f"video-meta-{uuid.uuid4().hex[:6]}",
            source="discord",
            available_tools=[{"name": "dummy_tool", "description": "tool", "parameters": {"type": "object"}}],
            route_hint={"route_score": 0.5, "difficulty_score": 0.5, "security_risk_score": 0.1},
        )
        events = await _run_main_process(
            monkeypatch,
            req,
            run_id=f"run-video-meta-{uuid.uuid4().hex[:8]}",
            omni_engine=_ToolThenAnswerEngine(final_text="video answer"),
            tool_runner_cls=_VideoMetaRunner,
        )
        final = _event_data(events, "final")
        assert final["output_text"] == "video answer"
        assert final["downloads"] == [
            {
                "url": "https://files.yonerai.com/s/share_abc",
                "label": "clip.mp4",
            }
        ]

    asyncio.run(_run())
