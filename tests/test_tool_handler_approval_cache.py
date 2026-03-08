from types import SimpleNamespace

import pytest

from src.cogs.tools.tool_handler import ToolHandler


class _DummyStore:
    def __init__(self, approval_row):
        self.approval_row = approval_row

    async def upsert_approval_request(self, **kwargs):
        return None

    async def get_approval_request(self, *, tool_call_id: str):
        return self.approval_row


class _DummySkillLoader:
    def __init__(self):
        self.skills = {}


class _DummyMessage:
    def __init__(self, user_id: int = 111):
        self.author = SimpleNamespace(id=user_id)
        self.guild = None
        self.channel = SimpleNamespace(id=222)


@pytest.mark.asyncio
async def test_cached_approved_status_requires_exact_context_match(monkeypatch):
    called = {"request_approval": 0}

    async def _request_approval(**kwargs):
        called["request_approval"] += 1
        return {"status": "denied"}

    # Risk/policy setup -> requires approval
    monkeypatch.setattr("src.utils.access_control.is_tool_allowed", lambda *a, **k: True)
    monkeypatch.setattr("src.utils.access_control.is_owner", lambda *a, **k: False)
    monkeypatch.setattr("src.cogs.tools.registry.get_tool_meta", lambda *a, **k: {})
    monkeypatch.setattr("src.utils.risk_scoring.score_tool_risk", lambda *a, **k: SimpleNamespace(score=60, level="HIGH", reasons=[]))
    monkeypatch.setattr(
        "src.utils.policy_engine.decide_tool_policy",
        lambda **kwargs: SimpleNamespace(allowed=True, requires_approval=True, requires_code=False, reason=""),
    )
    monkeypatch.setattr("src.utils.approvals.timeout_for_level", lambda *a, **k: 30)
    monkeypatch.setattr("src.utils.approvals.request_approval", _request_approval)
    monkeypatch.setattr("src.utils.approvals.normalize_args_json", lambda *a, **k: "{}")
    monkeypatch.setattr("src.utils.approvals.approval_summary", lambda *a, **k: "summary")
    monkeypatch.setattr("src.utils.approvals.args_hash", lambda a: f"hash:{a}")

    # Existing approved row with mismatched actor/tool/args should NOT be reused
    store = _DummyStore(
        {
            "status": "approved",
            "actor_id": "999",
            "tool_name": "different_tool",
            "args_hash": "hash:{'x': 1}",
            "expires_at": 4102444800,
        }
    )
    bot = SimpleNamespace(store=store, config=SimpleNamespace(profile="private"))
    handler = ToolHandler(bot, None)
    handler._skill_loader = _DummySkillLoader()
    msg = _DummyMessage(user_id=111)

    result = await handler.execute("dangerous_tool", {"y": 2}, msg, tool_call_id="call_unknown")

    assert result == "⛔ DENIED: approval required."
    assert called["request_approval"] == 1
