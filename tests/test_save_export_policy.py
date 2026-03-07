from __future__ import annotations

import asyncio
import uuid

from ora_core.api.schemas.messages import MessageRequest

from tests.test_core_effective_route import _SequenceOmniEngine, _event_data, _run_main_process


def test_attachment_analysis_does_not_get_save_format_clarification(monkeypatch) -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-attach-normal"},
            content="この画像を説明して",
            attachments=[{"type": "image_url", "url": "https://example.com/test.png", "name": "test.png"}],
            idempotency_key=f"attach-normal-{uuid.uuid4().hex[:6]}",
            source="discord",
            route_hint={
                "route_score": 0.5,
                "difficulty_score": 0.5,
                "security_risk_score": 0.1,
                "explicit_save_intent": False,
            },
        )
        events = await _run_main_process(
            monkeypatch,
            req,
            run_id=f"run-attach-normal-{uuid.uuid4().hex[:8]}",
            omni_engine=_SequenceOmniEngine(
                [
                    "どの形式で保存したいですか？",
                    "画像には複数のCPUグラフが表示されています。",
                ]
            ),
        )
        final = _event_data(events, "final")
        text = str(final.get("output_text") or "")
        assert "画像には複数のCPUグラフ" in text
        assert "どの形式で保存したいですか" not in text

    asyncio.run(_run())


def test_explicit_export_request_may_default_without_format_clarification(monkeypatch) -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-export"},
            content="この結果をPDFで保存して",
            idempotency_key=f"export-{uuid.uuid4().hex[:6]}",
            source="discord",
            route_hint={
                "route_score": 0.5,
                "difficulty_score": 0.5,
                "security_risk_score": 0.1,
                "explicit_save_intent": True,
            },
        )
        events = await _run_main_process(
            monkeypatch,
            req,
            run_id=f"run-export-{uuid.uuid4().hex[:8]}",
            omni_engine=_SequenceOmniEngine(
                [
                    "どの形式で保存したいですか？",
                    "PDFとして保存処理を進めます。",
                ]
            ),
        )
        final = _event_data(events, "final")
        text = str(final.get("output_text") or "")
        assert "PDFとして保存処理を進めます" in text
        assert "どの形式で保存したいですか" not in text

    asyncio.run(_run())


def test_missing_referenced_input_still_allows_clarification(monkeypatch) -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-missing-image"},
            content="この画像を要約して",
            idempotency_key=f"missing-image-{uuid.uuid4().hex[:6]}",
            source="discord",
            route_hint={
                "route_score": 0.5,
                "difficulty_score": 0.5,
                "security_risk_score": 0.1,
                "explicit_save_intent": False,
            },
        )
        events = await _run_main_process(
            monkeypatch,
            req,
            run_id=f"run-missing-image-{uuid.uuid4().hex[:8]}",
            omni_engine=_SequenceOmniEngine(
                [
                    "画像がまだ添付されていません。画像を送ってください。",
                ]
            ),
        )
        final = _event_data(events, "final")
        assert "画像を送ってください" in str(final.get("output_text") or "")

    asyncio.run(_run())


def test_contradictory_export_constraints_still_allow_clarification(monkeypatch) -> None:
    async def _run() -> None:
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-contradiction"},
            content="PDFで保存して でも画像のままにして",
            idempotency_key=f"contradiction-{uuid.uuid4().hex[:6]}",
            source="discord",
            route_hint={
                "route_score": 0.5,
                "difficulty_score": 0.5,
                "security_risk_score": 0.1,
                "explicit_save_intent": True,
            },
        )
        events = await _run_main_process(
            monkeypatch,
            req,
            run_id=f"run-contradiction-{uuid.uuid4().hex[:8]}",
            omni_engine=_SequenceOmniEngine(
                [
                    "PDFと画像形式の指定が矛盾しています。どちらを優先しますか？",
                ]
            ),
        )
        final = _event_data(events, "final")
        text = str(final.get("output_text") or "")
        assert "矛盾しています" in text

    asyncio.run(_run())
