import sys
import types

from fastapi.testclient import TestClient

from src.web import endpoints
from src.web.app import app


def test_runtime_diagnostics_includes_memory_sync(monkeypatch):
    monkeypatch.setenv("ADMIN_DASHBOARD_TOKEN", "adm")
    monkeypatch.setattr(
        endpoints,
        "_collect_memory_sync_status",
        lambda: {
            "available": True,
            "ok": False,
            "paused": True,
            "auth_fail_streak": 3,
            "backoff_until_ts": 1234567890,
            "backoff_remaining_sec": 120,
            "reason_code": "core_memory_sync_auth_backoff",
        },
    )

    with TestClient(app) as client:
        r = client.get("/api/platform/ops/web-runtime-diagnostics", headers={"x-admin-token": "adm"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True

        memory_sync = data.get("memory_sync")
        assert isinstance(memory_sync, dict)
        assert memory_sync.get("available") is True
        assert memory_sync.get("ok") is False
        assert memory_sync.get("paused") is True
        assert isinstance(memory_sync.get("auth_fail_streak"), int)
        assert isinstance(memory_sync.get("backoff_until_ts"), int)
        assert "adm" not in r.text


def test_runtime_diagnostics_requires_admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_DASHBOARD_TOKEN", "adm")

    with TestClient(app) as client:
        r = client.get("/api/platform/ops/web-runtime-diagnostics")
        assert r.status_code == 403


def test_collect_memory_sync_status_handles_missing_cog(monkeypatch):
    class _FakeBot:
        def get_cog(self, _name: str):
            return None

    fake_bot_module = types.ModuleType("src.bot")
    fake_bot_module.get_bot = lambda: _FakeBot()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.bot", fake_bot_module)

    status = endpoints._collect_memory_sync_status()
    assert status.get("available") is False
    assert status.get("reason_code") == "memory_sync_cog_unavailable"
