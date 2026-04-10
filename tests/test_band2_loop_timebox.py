from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

from tests.test_core_effective_route import MessageRequest, _event_data, _run_main_process


def test_band2_runs_fixed_two_passes(monkeypatch) -> None:
    async def _run() -> None:
        import ora_core.brain.process as process_mod

        calls: list[int] = []

        async def _fake_generate_with_registry(
            self,
            *,
            omni_engine,
            messages,
            client_type,
            tool_schemas,
            route_band,
            pass_index,
            llm_pref,
        ):
            del self, omni_engine, messages, client_type, tool_schemas, route_band, llm_pref
            calls.append(int(pass_index))
            msg = SimpleNamespace(content=f"pass-{pass_index}", tool_calls=[])
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None, model="fake-model")

        monkeypatch.setattr(process_mod.MainProcess, "_generate_with_registry", _fake_generate_with_registry)

        run_id = f"run-band2-{uuid.uuid4().hex[:8]}"
        req = MessageRequest(
            user_identity={"provider": "web", "id": "u-band2"},
            content="two pass check",
            idempotency_key=f"band2-{uuid.uuid4().hex[:6]}",
            source="web",
            route_hint={"route_score": 0.9, "difficulty_score": 0.9, "security_risk_score": 0.1},
        )
        events = await _run_main_process(monkeypatch, req, run_id=run_id)
        final = _event_data(events, "final")
        assert final.get("output_text") == "pass-2"
        assert calls == [1, 2]

    asyncio.run(_run())


def test_band2_timeout_ends_with_error_terminal(monkeypatch) -> None:
    async def _run() -> None:
        import ora_core.brain.process as process_mod

        async def _slow_generate_with_registry(
            self,
            *,
            omni_engine,
            messages,
            client_type,
            tool_schemas,
            route_band,
            pass_index,
            llm_pref,
        ):
            del self, omni_engine, messages, client_type, tool_schemas, route_band, pass_index, llm_pref
            await asyncio.sleep(11.0)
            msg = SimpleNamespace(content="too-late", tool_calls=[])
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None, model="slow-model")

        monkeypatch.setenv("ORA_BAND2_PASS_TIMEOUT_SEC", "10")
        monkeypatch.setattr(process_mod.MainProcess, "_generate_with_registry", _slow_generate_with_registry)

        run_id = f"run-timeout-{uuid.uuid4().hex[:8]}"
        req = MessageRequest(
            user_identity={"provider": "web", "id": "u-timeout"},
            content="timeout check",
            idempotency_key=f"tout-{uuid.uuid4().hex[:6]}",
            source="web",
            route_hint={"route_score": 0.8, "difficulty_score": 0.8, "security_risk_score": 0.1},
        )
        events = await _run_main_process(monkeypatch, req, run_id=run_id)
        err = _event_data(events, "error")
        assert set(err.keys()) == {"error_code", "user_safe_message"}
        assert err["error_code"] == "core_timeout"

    asyncio.run(_run())
