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
    from ora_core.sessions import reset_public_conversation_session_store

    reset_public_conversation_session_store()
    return main_mod.app


def test_public_message_creates_non_persistent_session_metadata(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/public/messages", json={"message": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"].startswith("session-")
    assert body["conversation_id"] == "public-smoke"
    assert body["turn_index"] == 1
    assert body["history_count"] == 1
    assert body["memory_persisted"] is False
    assert "not persistent memory" in body["reply"]


def test_public_message_reuses_session_and_increments_turn_metadata(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)
    payload = {
        "message": "hello",
        "session_id": "session-alpha",
        "conversation_id": "conversation-alpha",
    }

    with TestClient(app) as client:
        first = client.post("/v1/public/messages", json=payload)
        second = client.post("/v1/public/messages", json={**payload, "message": "follow up"})

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["session_id"] == "session-alpha"
    assert first_body["conversation_id"] == "conversation-alpha"
    assert first_body["turn_index"] == 1
    assert first_body["history_count"] == 1
    assert second_body["session_id"] == "session-alpha"
    assert second_body["turn_index"] == 2
    assert second_body["history_count"] == 2
    assert second_body["memory_persisted"] is False


def test_public_message_rejects_invalid_session_id(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/public/messages", json={"message": "hello", "session_id": "bad session"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "invalid_public_session"
    assert "detail" not in body


def test_public_message_rejects_secret_like_session_id(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/v1/public/messages",
            json={"message": "hello", "session_id": "user_api_key_placeholder"},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "unsafe_public_session_id"
    assert "detail" not in body


def test_public_message_rejects_session_reused_for_different_conversation(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        first = client.post(
            "/v1/public/messages",
            json={"message": "hello", "session_id": "session-alpha", "conversation_id": "conversation-alpha"},
        )
        second = client.post(
            "/v1/public/messages",
            json={"message": "hello", "session_id": "session-alpha", "conversation_id": "conversation-beta"},
        )

    assert first.status_code == 200
    assert second.status_code == 400
    body = second.json()
    assert body["error"] == "invalid_public_session"
    assert "different conversation_id" in body["message"]


def test_local_mode_includes_session_metadata_after_success(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    from ora_core.providers import local_llm

    def fake_generate_local_llm_reply(*, message, conversation_id, model=None, config=None, client=None):
        assert message == "hello"
        assert conversation_id == "local-session-conversation"
        return local_llm.LocalLLMReply(reply="local session reply", provider="local-ollama", model="local-test")

    monkeypatch.setattr(local_llm, "generate_local_llm_reply", fake_generate_local_llm_reply)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.post(
            "/v1/public/messages",
            json={
                "message": "hello",
                "mode": "local",
                "session_id": "local-session",
                "conversation_id": "local-session-conversation",
                "model": "local-test",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "local"
    assert body["session_id"] == "local-session"
    assert body["conversation_id"] == "local-session-conversation"
    assert body["turn_index"] == 1
    assert body["history_count"] == 1
    assert body["memory_persisted"] is False
    assert body["reply"] == "local session reply"
