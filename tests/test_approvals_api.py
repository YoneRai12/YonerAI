from __future__ import annotations

import asyncio
import importlib
import sys
import time

from fastapi.testclient import TestClient

from src.storage import Store


def _fresh_web_app():
    # Ensure env changes apply (FastAPI app + endpoints are module-level singletons).
    for name in ["src.web.app", "src.web.endpoints"]:
        if name in sys.modules:
            del sys.modules[name]
    import src.web.app as web_app
    importlib.reload(web_app)
    return web_app.app


def test_approvals_endpoints_require_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "testtoken")
    monkeypatch.setenv("ORA_ALLOW_MISSING_SECRETS", "1")
    monkeypatch.setenv("ORA_BOT_DB", str(tmp_path / "ora_test.db"))

    app = _fresh_web_app()
    with TestClient(app) as c:
        r = c.get("/api/approvals")
        assert r.status_code == 403

        r = c.get("/api/approvals", headers={"x-ora-token": "testtoken"})
        assert r.status_code == 200
        assert r.json()["ok"] is True


def test_expected_code_is_not_exposed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "testtoken")
    monkeypatch.setenv("ORA_ALLOW_MISSING_SECRETS", "1")
    db_path = str(tmp_path / "ora_test.db")
    monkeypatch.setenv("ORA_BOT_DB", db_path)

    # Seed a pending CRITICAL approval row with an expected_code.
    async def _seed() -> None:
        store = Store(db_path)
        await store.init()
        now = int(time.time())
        await store.upsert_approval_request(
            tool_call_id="call_test_1",
            created_at=now,
            expires_at=now + 60,
            actor_id=123,
            tool_name="web_navigate",
            correlation_id="cid",
            risk_score=95,
            risk_level="CRITICAL",
            requires_code=True,
            expected_code="123456",
            args_hash="x" * 64,
            requested_role="guest",
            args_json='{"url":"https://example.com"}',
            summary="test",
        )

    asyncio.run(_seed())

    app = _fresh_web_app()
    with TestClient(app) as c:
        r = c.get("/api/approvals", headers={"x-ora-token": "testtoken"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert any(row.get("tool_call_id") == "call_test_1" for row in data)
        row = [row for row in data if row.get("tool_call_id") == "call_test_1"][0]
        assert row.get("expected_code") is None
        assert row.get("expected_code_present") is True

        r2 = c.get("/api/approvals/call_test_1", headers={"x-ora-token": "testtoken"})
        assert r2.status_code == 200
        row2 = r2.json()["data"]
        assert row2.get("expected_code") is None
        assert row2.get("expected_code_present") is True
