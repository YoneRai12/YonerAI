from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient


def _reload_core_main(monkeypatch, token: str | None):
    if token is None:
        monkeypatch.delenv("ORA_CORE_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ORA_CORE_API_TOKEN", token)

    core_src = Path(__file__).resolve().parents[1] / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    sys.modules.pop("ora_core.main", None)
    import ora_core.main as main_mod

    return importlib.reload(main_mod)


def test_core_access_gate_is_attached_to_all_sensitive_routes(monkeypatch):
    main_mod = _reload_core_main(monkeypatch, token="secret-token")
    app = main_mod.create_app()

    protected_paths = {
        "/v1/messages",
        "/v1/runs/{run_id}/events",
        "/v1/runs/{run_id}/results",
        "/v1/auth/link-code",
        "/v1/auth/link",
        "/v1/dashboard",
        "/v1/memory/history",
    }

    from ora_core.api.dependencies.auth import require_core_access

    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path not in protected_paths:
            continue
        assert any(dep.call is require_core_access for dep in route.dependant.dependencies), route.path


def test_core_access_gate_blocks_and_allows_with_token(monkeypatch):
    main_mod = _reload_core_main(monkeypatch, token="secret-token")
    client = TestClient(main_mod.app)

    denied = client.get("/v1/dashboard")
    assert denied.status_code == 401

    allowed = client.post("/v1/messages", headers={"X-ORA-Core-Token": "secret-token"}, json={})
    assert allowed.status_code == 422
