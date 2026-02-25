from __future__ import annotations

import asyncio
import sys
import types
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# Allow importing ora_core package from core/src during tests.
CORE_SRC = Path(__file__).resolve().parents[1] / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

if "sqlalchemy.ext.asyncio" not in sys.modules:
    sa_mod = types.ModuleType("sqlalchemy")
    sa_ext_mod = types.ModuleType("sqlalchemy.ext")
    sa_async_mod = types.ModuleType("sqlalchemy.ext.asyncio")

    class _AsyncSession:  # pragma: no cover - type stub for import only
        pass

    sa_async_mod.AsyncSession = _AsyncSession
    sa_ext_mod.asyncio = sa_async_mod
    sa_mod.ext = sa_ext_mod
    sys.modules.setdefault("sqlalchemy", sa_mod)
    sys.modules["sqlalchemy.ext"] = sa_ext_mod
    sys.modules["sqlalchemy.ext.asyncio"] = sa_async_mod

# Lightweight dependency stubs for environments without sqlalchemy.
if "ora_core.database.repo" not in sys.modules:
    repo_mod = types.ModuleType("ora_core.database.repo")

    class _RunStatus:
        in_progress = "in_progress"
        completed = "completed"
        failed = "failed"

    class _Repository:
        def __init__(self, *_args, **_kwargs):
            return None

    repo_mod.Repository = _Repository
    repo_mod.RunStatus = _RunStatus
    sys.modules["ora_core.database.repo"] = repo_mod

if "ora_core.brain.context" not in sys.modules:
    ctx_mod = types.ModuleType("ora_core.brain.context")

    class _ContextBuilder:
        @staticmethod
        async def build_context(*_args, **_kwargs):
            return []

    ctx_mod.ContextBuilder = _ContextBuilder
    sys.modules["ora_core.brain.context"] = ctx_mod

if "ora_core.brain.memory" not in sys.modules:
    mem_mod = types.ModuleType("ora_core.brain.memory")
    mem_mod.memory_store = SimpleNamespace()
    sys.modules["ora_core.brain.memory"] = mem_mod

if "ora_core.engine.simple_worker" not in sys.modules:
    worker_mod = types.ModuleType("ora_core.engine.simple_worker")
    worker_mod.event_manager = SimpleNamespace(
        emit=None,
        wait_for_tool_result=None,
    )
    sys.modules["ora_core.engine.simple_worker"] = worker_mod

if "src.utils.cost_manager" not in sys.modules:
    cm_mod = types.ModuleType("src.utils.cost_manager")

    class _Usage:
        def __init__(self, tokens_in: int = 0, tokens_out: int = 0):
            self.tokens_in = tokens_in
            self.tokens_out = tokens_out

    class _CostManager:
        def add_cost(self, *_args, **_kwargs):
            return None

    cm_mod.Usage = _Usage
    cm_mod.CostManager = _CostManager
    sys.modules["src.utils.cost_manager"] = cm_mod

from ora_core.api.schemas.messages import MessageRequest
from ora_core.brain.process import MainProcess
from src.utils.link_attribution import get_run_effective_route


class _FakeRepo:
    async def update_run_status(self, *_args, **_kwargs):
        return None

    async def get_or_create_user(self, *_args, **_kwargs):
        return SimpleNamespace(id="user-test")

    async def create_assistant_message(self, *_args, **_kwargs):
        return SimpleNamespace(id="assistant-msg")


class _FakeOmniEngine:
    async def generate(self, *_args, **_kwargs):
        message = SimpleNamespace(content="ok", tool_calls=[])
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None, model="test-model")
        return response


async def _run_main_process(monkeypatch, req: MessageRequest, *, run_id: str) -> list[dict[str, Any]]:
    import ora_core.brain.process as process_mod

    events: list[dict[str, Any]] = []

    async def _fake_emit(_run_id: str, event_type: str, data: dict):
        events.append({"event": event_type, "data": data})

    async def _fake_build_context(*_args, **_kwargs):
        return []

    fake_omni_module = types.ModuleType("ora_core.engine.omni_engine")
    fake_omni_module.omni_engine = _FakeOmniEngine()

    monkeypatch.setattr(process_mod.event_manager, "emit", _fake_emit)
    monkeypatch.setattr(process_mod.ContextBuilder, "build_context", _fake_build_context)
    monkeypatch.setitem(sys.modules, "ora_core.engine.omni_engine", fake_omni_module)

    proc = MainProcess(run_id=run_id, conversation_id="conv-test", request=req, db_session=object())
    proc.repo = _FakeRepo()

    async def _noop_memory_update(_user_id: str, _user_text: str, _assistant_text: str):
        return None

    proc._update_memory_on_completion = _noop_memory_update
    await proc.run()
    return events


def _event_data(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for ev in events:
        if ev.get("event") == event_type and isinstance(ev.get("data"), dict):
            return ev["data"]
    raise AssertionError(f"missing event: {event_type}")


def test_effective_route_emitted_and_persisted_with_route_hint(monkeypatch) -> None:
    async def _run() -> None:
        run_id = f"run-{uuid.uuid4().hex[:10]}"
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "12345", "display_name": "tester"},
            content="hello",
            idempotency_key="hintcase1",
            source="discord",
            route_hint={
                "mode": "AGENT_LOOP",
                "difficulty_score": 0.95,
                "security_risk_score": 0.9,
                "security_risk_level": "HIGH",
                "budget": {
                    "max_turns": 999,
                    "max_tool_calls": 999,
                    "time_budget_seconds": 9999,
                },
                "reason_codes": ["hint_seen"],
            },
        )
        events = await _run_main_process(monkeypatch, req, run_id=run_id)
        meta = _event_data(events, "meta")
        final = _event_data(events, "final")

        meta_route = meta.get("effective_route")
        final_route = final.get("effective_route")
        assert isinstance(meta_route, dict)
        assert isinstance(final_route, dict)

        assert meta_route.get("source_hint_present") is True
        assert meta_route.get("mode") == "TASK"
        assert isinstance(meta_route.get("route_score"), float)
        assert "router_mode_forced_safe" in list(meta_route.get("reason_codes") or [])
        assert int(meta_route.get("budget", {}).get("max_turns", 0)) <= 20
        assert final_route.get("mode") == meta_route.get("mode")
        assert final_route.get("route_score") == meta_route.get("route_score")

        stored = await get_run_effective_route(run_id)
        assert isinstance(stored, dict)
        assert stored.get("mode") == meta_route.get("mode")

    asyncio.run(_run())


def test_effective_route_emitted_without_route_hint_for_discord_and_web(monkeypatch) -> None:
    async def _run() -> None:
        modes: dict[str, str] = {}
        for source in ("discord", "web"):
            run_id = f"run-{source}-{uuid.uuid4().hex[:8]}"
            req = MessageRequest(
                user_identity={"provider": source if source in {"discord", "web"} else "web", "id": "u-1"},
                content="same input",
                idempotency_key=f"{source}case01",
                source=source,  # type: ignore[arg-type]
            )
            events = await _run_main_process(monkeypatch, req, run_id=run_id)
            meta = _event_data(events, "meta")
            final = _event_data(events, "final")
            route = final.get("effective_route")
            assert isinstance(route, dict)
            assert isinstance(meta.get("effective_route"), dict)
            assert route.get("source_hint_present") is False
            assert str(route.get("mode") or "") in {"INSTANT", "TASK", "AGENT_LOOP"}
            modes[source] = str(route.get("mode") or "")

        # Core computes mode for both clients from the same fallback policy.
        assert modes["discord"] == modes["web"] == "TASK"

    asyncio.run(_run())


def test_effective_route_mode_thresholds_follow_route_score(monkeypatch) -> None:
    async def _run() -> None:
        cases = [
            (0.20, "INSTANT"),
            (0.50, "TASK"),
            (0.90, "AGENT_LOOP"),
        ]
        for score, expected_mode in cases:
            run_id = f"run-thr-{uuid.uuid4().hex[:8]}"
            req = MessageRequest(
                user_identity={"provider": "discord", "id": "u-42"},
                content="threshold check",
                idempotency_key=f"thr-{score}-{uuid.uuid4().hex[:6]}",
                source="discord",
                route_hint={"route_score": score, "difficulty_score": score, "security_risk_score": 0.1},
            )
            events = await _run_main_process(monkeypatch, req, run_id=run_id)
            final = _event_data(events, "final")
            route = final.get("effective_route") or {}
            assert route.get("mode") == expected_mode
            assert abs(float(route.get("route_score", -1.0)) - score) < 0.01

    asyncio.run(_run())


def test_effective_route_vision_floor_recomputes_mode_after_hint(monkeypatch) -> None:
    async def _run() -> None:
        run_id = f"run-vision-{uuid.uuid4().hex[:8]}"
        req = MessageRequest(
            user_identity={"provider": "web", "id": "u-vision"},
            content="画像を見て",
            idempotency_key=f"vision-{uuid.uuid4().hex[:6]}",
            source="web",
            route_hint={
                "mode": "INSTANT",
                "route_score": 0.1,
                "difficulty_score": 0.1,
                "security_risk_score": 0.1,
                "function_category": "vision",
            },
        )
        events = await _run_main_process(monkeypatch, req, run_id=run_id)
        final = _event_data(events, "final")
        route = final.get("effective_route") or {}
        assert route.get("mode") == "TASK"
        assert "router_vision_floor_applied" in list(route.get("reason_codes") or [])

    asyncio.run(_run())


def test_effective_route_with_tools_never_stays_instant(monkeypatch) -> None:
    async def _run() -> None:
        run_id = f"run-tools-{uuid.uuid4().hex[:8]}"
        req = MessageRequest(
            user_identity={"provider": "discord", "id": "u-tools"},
            content="この内容で処理して",
            idempotency_key=f"tools-{uuid.uuid4().hex[:6]}",
            source="discord",
            available_tools=[
                {"name": "dummy_tool", "description": "tool", "parameters": {"type": "object", "properties": {}}}
            ],
            route_hint={
                "mode": "INSTANT",
                "route_score": 0.2,
                "difficulty_score": 0.2,
                "security_risk_score": 0.1,
            },
        )
        events = await _run_main_process(monkeypatch, req, run_id=run_id)
        final = _event_data(events, "final")
        route = final.get("effective_route") or {}
        assert route.get("mode") == "TASK"
        assert "router_mode_forced_tools" in list(route.get("reason_codes") or [])

    asyncio.run(_run())
