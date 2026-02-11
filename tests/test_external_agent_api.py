from __future__ import annotations

import importlib
import sys

from fastapi.testclient import TestClient


def _fresh_web_app():
    # Ensure env changes apply (FastAPI app + endpoints are module-level singletons).
    for name in ["src.web.app", "src.web.endpoints"]:
        if name in sys.modules:
            del sys.modules[name]
    import src.web.app as web_app
    importlib.reload(web_app)
    return web_app.app


def test_external_agent_run_requires_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "testtoken")
    monkeypatch.setenv("ORA_ALLOW_MISSING_SECRETS", "1")
    monkeypatch.setenv("ORA_BOT_DB", str(tmp_path / "ora_test.db"))

    app = _fresh_web_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/agent/run", json={"prompt": "hello"})
        assert r.status_code == 403

        r2 = c.post(
            "/api/v1/agent/run",
            headers={"Authorization": "Bearer testtoken"},
            json={"prompt": "hello from external api", "user_id": "external-user-1"},
        )
        assert r2.status_code == 200
        body = r2.json()
        assert body.get("status") == "started"
        assert isinstance(body.get("run_id"), str) and body["run_id"]
        assert body.get("events_url", "").startswith("/api/v1/agent/runs/")
        assert body.get("results_url", "").startswith("/api/v1/agent/runs/")

