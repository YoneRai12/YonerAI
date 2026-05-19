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
    assert "hello" not in body["reply"]


def test_public_message_endpoint_supports_explicit_offline_mode(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/public/messages", json={"message": "hello", "mode": "offline"})

    assert response.status_code == 200
    assert response.json()["mode"] == "offline"
    assert response.json()["provider"] == "offline-mock"


def test_public_message_endpoint_supports_loopback_local_mode(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    from ora_core.providers import local_llm

    def fake_generate_local_llm_reply(*, message, conversation_id, model=None, config=None, client=None):
        assert message == "hello"
        assert conversation_id == "local-smoke"
        assert model is None
        assert config is not None
        assert config.provider == "ollama"
        assert config.model == "local-test"
        return local_llm.LocalLLMReply(reply="local test reply", provider="local-ollama", model="local-test")

    monkeypatch.setattr(local_llm, "generate_local_llm_reply", fake_generate_local_llm_reply)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.post(
            "/v1/public/messages",
            json={
                "message": "hello",
                "conversation_id": "local-smoke",
                "mode": "local",
                "model": "local-test",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["mode"] == "local"
    assert body["provider"] == "local-ollama"
    assert body["model"] == "local-test"
    assert body["reply"] == "local test reply"
    assert body["requires_approval"] is False
    assert body["contract_version"] == "local-llm-conversation-mvp-0.1"


def test_public_message_endpoint_supports_openai_compatible_local_provider(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    from ora_core.providers import local_llm

    def fake_generate_local_llm_reply(*, message, conversation_id, model=None, config=None, client=None):
        assert message == "hello"
        assert conversation_id == "local-openai-smoke"
        assert model is None
        assert config is not None
        assert config.provider == "openai_compatible_local"
        assert config.base_url == "http://127.0.0.1:1234/v1"
        assert config.model == "lm-studio-model"
        assert config.temperature == 0.3
        assert config.max_tokens == 128
        return local_llm.LocalLLMReply(
            reply="openai compatible local reply",
            provider="local-openai-compatible",
            model="lm-studio-model",
        )

    monkeypatch.setattr(local_llm, "generate_local_llm_reply", fake_generate_local_llm_reply)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.post(
            "/v1/public/messages",
            json={
                "message": "hello",
                "conversation_id": "local-openai-smoke",
                "mode": "local",
                "local_provider": "openai_compatible_local",
                "local_base_url": "http://127.0.0.1:1234/v1",
                "model": "lm-studio-model",
                "temperature": 0.3,
                "max_tokens": 128,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["mode"] == "local"
    assert body["provider"] == "local-openai-compatible"
    assert body["model"] == "lm-studio-model"
    assert body["reply"] == "openai compatible local reply"


def test_public_message_endpoint_rejects_unsupported_local_provider(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.post(
            "/v1/public/messages",
            json={"message": "hello", "mode": "local", "local_provider": "remote-openai"},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "unsupported_local_llm_provider"
    assert "lmstudio" in body["message"]
    assert "localai" in body["message"]
    assert "detail" not in body


def test_public_message_endpoint_rejects_non_loopback_client_for_local_mode(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app, client=("203.0.113.10", 50000)) as client:
        response = client.post("/v1/public/messages", json={"message": "hello", "mode": "local"})

    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "local_llm_loopback_required"
    assert "detail" not in body


def test_public_message_endpoint_rejects_non_loopback_local_llm_url(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.post(
            "/v1/public/messages",
            json={"message": "hello", "mode": "local", "local_base_url": "https://example.com"},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "unsafe_local_llm_endpoint"
    assert "detail" not in body
    assert "example.com" not in body["message"]


def test_public_message_endpoint_returns_safe_error_when_local_llm_unavailable(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    from ora_core.providers import local_llm

    def fail_generate_local_llm_reply(*, message, conversation_id, model=None, config=None, client=None):
        raise local_llm.LocalLLMConnectionError("internal connection failure http://127.0.0.1/private")

    monkeypatch.setattr(local_llm, "generate_local_llm_reply", fail_generate_local_llm_reply)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.post("/v1/public/messages", json={"message": "hello", "mode": "local"})

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "local_llm_unavailable"
    assert "detail" not in body
    assert "127.0.0.1" not in body["message"]
    assert "private" not in body["message"]


def test_public_message_endpoint_rejects_unsupported_mode(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/public/messages", json={"message": "hello", "mode": "live"})

    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_mode"
    assert "detail" not in response.json()


def test_public_message_endpoint_rejects_empty_message(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/public/messages", json={"message": "   "})

    assert response.status_code == 400
    assert response.json()["error"] == "empty_message"
    assert "detail" not in response.json()


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
    assert response.json()["error"] == "unsafe_public_message"
    assert "detail" not in response.json()


def test_public_message_endpoint_rejects_secret_like_conversation_id(monkeypatch, tmp_path):
    app = _load_core_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/v1/public/messages",
            json={"message": "hello", "conversation_id": "user_api_key_placeholder"},
        )

    assert response.status_code == 400
    assert response.json()["error"] == "unsafe_public_conversation_id"
    assert "detail" not in response.json()
