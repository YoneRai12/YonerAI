from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from types import SimpleNamespace

from tests.test_core_effective_route import MessageRequest


@dataclass(frozen=True)
class _Spec:
    provider: str
    model_id: str


class _FakeRegistry:
    def __init__(self) -> None:
        self.stable_fallback = _Spec(provider="openai", model_id="stable-model")
        self._disabled: set[tuple[str, str]] = set()

    @staticmethod
    def tier_for_route_band(_route_band: str) -> str:
        return "balanced"

    def resolve_candidates(self, *, route_band: str | None = None, tier: str | None = None):
        del route_band, tier
        out = []
        for spec in [_Spec("openai", "bad-model"), _Spec("openai", "good-model")]:
            if (spec.provider, spec.model_id) not in self._disabled:
                out.append(spec)
        return out

    def disable_runtime(self, provider: str, model_id: str) -> None:
        self._disabled.add((provider, model_id))


def test_router_model_selection_and_fallback_logs(monkeypatch, caplog) -> None:
    async def _run() -> None:
        import ora_core.brain.process as process_mod

        fake_registry = _FakeRegistry()
        monkeypatch.setattr(process_mod, "get_model_registry", lambda strict=True: fake_registry)

        attempts = {"count": 0}

        class _FakeOmni:
            async def generate(self, messages, client_type, stream, preference, tool_schemas):
                del messages, client_type, stream, tool_schemas
                attempts["count"] += 1
                if preference == "bad-model":
                    raise RuntimeError("model_not_found: bad-model")
                msg = SimpleNamespace(content="ok", tool_calls=[])
                return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None, model=preference)

        req = MessageRequest(
            user_identity={"provider": "web", "id": "u-log"},
            content="logging check",
            idempotency_key="log-check-01",
            source="web",
        )
        proc = process_mod.MainProcess(run_id="run-log-01", conversation_id="conv-log-01", request=req, db_session=object())

        caplog.set_level(logging.INFO, logger=process_mod.logger.name)
        await proc._generate_with_registry(
            omni_engine=_FakeOmni(),
            messages=[{"role": "user", "content": "hi"}],
            client_type="web",
            tool_schemas=None,
            route_band="task",
            pass_index=1,
            llm_pref=None,
        )

        selected = [r for r in caplog.records if r.msg == "router.model.selected"]
        fallback = [r for r in caplog.records if r.msg == "router.model.fallback"]
        assert selected, "router.model.selected log missing"
        assert fallback, "router.model.fallback log missing"
        assert attempts["count"] >= 2

        has_reason = False
        for rec in fallback:
            route_event = getattr(rec, "route_event", {})
            if isinstance(route_event, dict) and route_event.get("reason") in {"model_not_found", "provider_unavailable", "none"}:
                has_reason = True
                assert "provider" in route_event
                assert "model_id" in route_event
        assert has_reason

    asyncio.run(_run())
