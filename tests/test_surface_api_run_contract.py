from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def _load_core_app(monkeypatch, tmp_path, *, token: str | None = None):
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    for path in (repo_root, core_src):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    monkeypatch.setenv("ORA_ALLOW_MISSING_SECRETS", "1")
    monkeypatch.setenv("ORA_BOT_DB", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("ORA_DOTENV_PATH", str(tmp_path / "missing.env"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    if token is None:
        monkeypatch.delenv("ORA_CORE_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ORA_CORE_API_TOKEN", token)

    for name in [
        "ora_core.main",
        "ora_core.api.routes.agent_runs",
    ]:
        sys.modules.pop(name, None)
    main_mod = importlib.import_module("ora_core.main")
    from ora_core.api.routes.agent_runs import reset_surface_agent_run_store
    from ora_core.sessions import reset_public_conversation_session_store

    reset_surface_agent_run_store()
    reset_public_conversation_session_store()
    return main_mod.app


def test_surface_agent_run_contract_mock_success(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.post("/api/v1/agent/run", json={"prompt": "hello", "mode": "mock"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["run_id"].startswith("surface-run-")
    assert body["status"] == "completed"
    assert body["mode"] == "mock"
    assert body["provider"] == "offline-mock"
    assert body["memory_persisted"] is False
    assert body["events_url"] == f"/api/v1/agent/runs/{body['run_id']}/events"
    assert body["results_url"] == f"/api/v1/agent/runs/{body['run_id']}/results"
    assert body["contract_version"] == "surface-api-run-contract-0.1"
    assert "no provider call" in body["reply"]


def test_surface_agent_events_and_results_round_trip(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        created = client.post("/api/v1/agent/run", json={"prompt": "hello"})
        run_id = created.json()["run_id"]
        events = client.get(f"/api/v1/agent/runs/{run_id}/events")
        result = client.post(
            f"/api/v1/agent/runs/{run_id}/results",
            json={
                "result_type": "surface_api_smoke_result",
                "tool": "fixture_tool",
                "tool_call_id": "fixture-call-1",
                "result": {"ok": True},
            },
        )
        updated_events = client.get(f"/api/v1/agent/runs/{run_id}/events")

    assert events.status_code == 200
    event_body = events.json()
    assert event_body["ok"] is True
    assert event_body["memory_persisted"] is False
    assert [event["event"] for event in event_body["events"]] == ["meta", "final"]

    assert result.status_code == 200
    result_body = result.json()
    assert result_body["accepted"] is True
    assert result_body["trusted"] is False
    assert result_body["memory_persisted"] is False

    assert updated_events.status_code == 200
    assert [event["event"] for event in updated_events.json()["events"]] == [
        "meta",
        "final",
        "tool_result_submit",
    ]


def test_surface_agent_unknown_run_id_is_safe_error(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        events = client.get("/api/v1/agent/runs/missing-run/events")
        result = client.post("/api/v1/agent/runs/missing-run/results", json={"result": "ok"})

    assert events.status_code == 404
    assert events.json()["detail"]["error"] == "run_not_found"
    assert result.status_code == 404
    assert result.json()["detail"]["error"] == "run_not_found"


def test_surface_agent_run_rejects_invalid_payload(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        empty_prompt = client.post("/api/v1/agent/run", json={"prompt": "   "})
        missing_prompt = client.post("/api/v1/agent/run", json={})

    assert empty_prompt.status_code == 400
    assert empty_prompt.json()["detail"]["error"] == "empty_prompt"
    assert missing_prompt.status_code == 422
    assert missing_prompt.json()["error"] == "VALIDATION_ERROR"


def test_surface_agent_mock_output_is_deterministic_and_no_local_provider_call(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    from ora_core.providers import local_llm

    def fail_local_provider_call(**kwargs):
        raise AssertionError("mock mode must not call a local provider")

    monkeypatch.setattr(local_llm, "generate_local_llm_reply", fail_local_provider_call)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        first = client.post("/api/v1/agent/run", json={"prompt": "same prompt", "mode": "offline"})
        second = client.post("/api/v1/agent/run", json={"prompt": "same prompt", "mode": "offline"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["reply"] == second.json()["reply"]
    assert first.json()["memory_persisted"] is False
    assert second.json()["memory_persisted"] is False


def test_surface_agent_local_mode_remains_loopback_only(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path, token="secret-token")

    with TestClient(app, client=("203.0.113.10", 50000)) as client:
        response = client.post(
            "/api/v1/agent/run",
            headers={"X-ORA-Core-Token": "secret-token"},
            json={"prompt": "hello", "mode": "local"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "local_llm_loopback_required"


def test_surface_agent_run_respects_core_token_gate(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path, token="secret-token")

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        denied = client.post("/api/v1/agent/run", json={"prompt": "hello"})
        allowed = client.post(
            "/api/v1/agent/run",
            headers={"X-ORA-Core-Token": "secret-token"},
            json={"prompt": "hello"},
        )

    assert denied.status_code == 401
    assert allowed.status_code == 200
