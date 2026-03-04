from __future__ import annotations

import asyncio
import uuid

from tests.test_core_effective_route import MessageRequest, _event_data, _run_main_process


def test_sse_progress_final_error_contract_fields(monkeypatch) -> None:
    async def _run() -> None:
        run_id = f"run-sse-{uuid.uuid4().hex[:8]}"
        req = MessageRequest(
            user_identity={"provider": "web", "id": "u-sse"},
            content="contract check",
            idempotency_key=f"sse-{uuid.uuid4().hex[:6]}",
            source="web",
            route_hint={"route_score": 0.8, "difficulty_score": 0.8, "security_risk_score": 0.1},
        )
        events = await _run_main_process(monkeypatch, req, run_id=run_id)

        progress_events = [e for e in events if e.get("event") == "progress"]
        assert progress_events, "expected progress events"
        for ev in progress_events:
            data = ev.get("data") or {}
            assert set(data.keys()) == {"stage", "pass", "toc"}
            assert data["stage"] in {"plan", "memory", "search", "compose", "deliver"}
            assert isinstance(data["pass"], int)
            assert isinstance(data["toc"], list)

        final = _event_data(events, "final")
        assert set(final.keys()) == {"output_text"}
        assert isinstance(final["output_text"], str)

        error_events = [e for e in events if e.get("event") == "error"]
        assert not error_events

    asyncio.run(_run())
