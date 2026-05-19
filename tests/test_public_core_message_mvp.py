from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def _load_core_app(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    for path in (repo_root, core_src):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    monkeypatch.setenv("ORA_ALLOW_MISSING_SECRETS", "1")
    monkeypatch.setenv("ORA_BOT_DB", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("ORA_DOTENV_PATH", str(tmp_path / "missing.env"))
    monkeypatch.delenv("ORA_CORE_API_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)

    sys.modules.pop("ora_core.main", None)
    main_mod = importlib.import_module("ora_core.main")
    return main_mod.app


def test_public_message_endpoint_returns_deterministic_offline_reply(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        health = client.get("/health")
        first = client.post(
            "/v1/public/messages",
            json={"message": "hello", "conversation_id": "optional-public-smoke"},
        )
        second = client.post(
            "/v1/public/messages",
            json={"message": "hello", "conversation_id": "optional-public-smoke"},
        )

    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert first.status_code == 200
    assert first.json() == second.json()
    body = first.json()
    assert body["ok"] is True
    assert body["mode"] == "mock"
    assert body["conversation_id"] == "optional-public-smoke"
    assert body["message_id"].startswith("public-msg-")
    assert body["provider"] == "offline-mock"
    assert body["requires_approval"] is False
    assert "no provider call" in body["reply"]
    assert "memory store" in body["reply"]
    assert "Discord gateway" in body["reply"]


def test_public_message_endpoint_supports_explicit_offline_mode(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/public/messages", json={"message": "hello", "mode": "offline"})

    assert response.status_code == 200
    assert response.json()["mode"] == "offline"
    assert response.json()["provider"] == "offline-mock"


def test_public_message_endpoint_rejects_unsupported_mode(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/public/messages", json={"message": "hello", "mode": "live"})

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "unsupported_mode"


def test_public_message_endpoint_rejects_empty_message(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/public/messages", json={"message": "   "})

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "empty_message"


def test_public_message_endpoint_rejects_message_length_over_cap(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/public/messages", json={"message": "x" * 2001})

    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_public_message_endpoint_rejects_secret_like_payload(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/public/messages", json={"message": "please store this api_key placeholder"})

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "unsafe_public_message"
