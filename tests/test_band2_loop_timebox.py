from __future__ import annotations

import asyncio
import sys
import types
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

        async def _timeout_wait_for(awaitable, timeout):
            del timeout
            if asyncio.isfuture(awaitable):
                awaitable.cancel()
            elif asyncio.iscoroutine(awaitable):
                awaitable.close()
            raise asyncio.TimeoutError()

        monkeypatch.setattr(process_mod.asyncio, "wait_for", _timeout_wait_for)

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


def test_budget_stop_returns_final_user_safe_message(monkeypatch) -> None:
    async def _run() -> None:
        import ora_core.brain.process as process_mod

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
            del self, omni_engine, messages, client_type, tool_schemas, route_band, pass_index, llm_pref
            tool_calls = [
                SimpleNamespace(id="tc-1", function=SimpleNamespace(name="dummy_tool", arguments="{}")),
                SimpleNamespace(id="tc-2", function=SimpleNamespace(name="dummy_tool", arguments="{}")),
            ]
            msg = SimpleNamespace(content="", tool_calls=tool_calls)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None, model="fake-model")

        fake_runner_mod = types.ModuleType("ora_core.mcp.runner")

        class _ToolRunner:
            def __init__(self, *_args, **_kwargs):
                return None

            async def run_tool(self, *_args, **_kwargs):
                return {"result": {"ok": True}}

        fake_runner_mod.ToolRunner = _ToolRunner

        monkeypatch.setattr(process_mod.MainProcess, "_generate_with_registry", _fake_generate_with_registry)
        monkeypatch.setitem(sys.modules, "ora_core.mcp.runner", fake_runner_mod)

        run_id = f"run-budget-stop-{uuid.uuid4().hex[:8]}"
        req = MessageRequest(
            user_identity={"provider": "web", "id": "u-budget-stop"},
            content="budget stop check",
            idempotency_key=f"budget-stop-{uuid.uuid4().hex[:6]}",
            source="web",
            available_tools=[
                {"name": "dummy_tool", "description": "tool", "parameters": {"type": "object", "properties": {}}}
            ],
            route_hint={
                "route_score": 0.5,
                "difficulty_score": 0.5,
                "security_risk_score": 0.1,
                "budget": {"max_turns": 5, "max_tool_calls": 1, "time_budget_seconds": 120},
            },
        )
        events = await _run_main_process(monkeypatch, req, run_id=run_id)
        final = _event_data(events, "final")
        assert final.get("output_text") == "[System] Request stopped by Core safety limits."
        assert not any(ev.get("event") == "error" for ev in events)

    asyncio.run(_run())
