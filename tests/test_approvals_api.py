from __future__ import annotations

import importlib
import sqlite3
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

    app = _fresh_web_app()
    with TestClient(app) as c:
        # Seed a pending CRITICAL approval row with an expected_code (sync insert avoids aiosqlite loop/thread warnings).
        now = int(time.time())
        con = sqlite3.connect(db_path)
        try:
            con.execute(
                (
                    "INSERT OR REPLACE INTO approval_requests("
                    "tool_call_id, created_at, expires_at, actor_id, tool_name, correlation_id, "
                    "risk_score, risk_level, requires_code, expected_code, args_hash, requested_role, args_json, summary, status, decided_at, decided_by"
                    ") VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                (
                    "call_test_1",
                    now,
                    now + 60,
                    "123",
                    "web_navigate",
                    "cid",
                    95,
                    "CRITICAL",
                    1,
                    "123456",
                    "x" * 64,
                    "guest",
                    '{"url":"https://example.com"}',
                    "test",
                    "pending",
                    None,
                    None,
                ),
            )
            con.commit()
        finally:
            con.close()

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
