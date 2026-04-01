# ruff: noqa: E402
from __future__ import annotations

import asyncio
import os
import secrets

from fastapi.testclient import TestClient

os.environ["ORA_BOT_DB"] = "test_managed_cloud_mvp.db"
os.environ["ORA_DISABLE_WEB_BG_TASKS"] = "1"

from src.web import endpoints
from src.web.app import app, get_store


def _attach_session_cookie(client: TestClient, *, user_id: str = "web:test-user") -> str:
    raw_token = secrets.token_urlsafe(32)
    store = get_store()
    asyncio.run(store.ensure_user_id(user_id=user_id, display_name="Test User"))
    asyncio.run(
        store.upsert_user_identity(
            provider="google",
            provider_sub=f"google-sub:{user_id}",
            user_id=user_id,
            email="test@example.com",
            display_name="Test User",
            avatar_url="https://example.com/avatar.png",
        )
    )
    asyncio.run(
        store.create_web_session(
            session_hash=endpoints._session_hash(raw_token),
            user_id=user_id,
            provider="google",
            ttl_sec=3600,
        )
    )
    client.cookies.set(endpoints.WEB_SESSION_COOKIE, raw_token)
    return user_id


def test_managed_cloud_pages_render():
    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "YonerAI Platform Preview" in root.text

        jp = client.get("/jp")
        assert jp.status_code == 200
        assert "YonerAI Platform Preview" in jp.text

        chat = client.get("/jp/chat")
        assert chat.status_code == 200
        assert "YonerAI Chat" in chat.text

        terms = client.get("/terms")
        assert terms.status_code == 200
        assert "Terms of Service" in terms.text

        privacy = client.get("/privacy")
        assert privacy.status_code == 200
        assert "Privacy Policy" in privacy.text


def test_auth_me_requires_session_then_returns_identity():
    with TestClient(app) as client:
        unauth = client.get("/api/auth/me")
        assert unauth.status_code == 401

        user_id = _attach_session_cookie(client)
        authed = client.get("/api/auth/me")
        assert authed.status_code == 200
        data = authed.json()
        assert data["authenticated"] is True
        assert data["user_id"] == user_id
        assert data["provider"] == "google"


def test_public_chat_message_uses_session_actor(monkeypatch):
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()
    endpoints._PUBLIC_CHAT_IDEMPOTENCY.clear()

    def fake_start_agent_run(*, content: str, available_tools, provider_id: str, attachments):
        assert content == "hello"
        assert provider_id == "web:test-user"
        assert available_tools == []
        return "run-public-1"

    monkeypatch.setattr(endpoints, "_start_agent_run", fake_start_agent_run)

    with TestClient(app) as client:
        _attach_session_cookie(client)
        response = client.post(
            "/api/public/chat/messages",
            json={"content": "hello", "idempotency_key": "abc-123"},
            headers={"Idempotency-Key": "abc-123"},
        )
        assert response.status_code == 200
        assert response.json()["run_id"] == "run-public-1"
        assert endpoints._RUN_OWNERS["run-public-1"] == "web:test-user"


def test_public_chat_events_require_owner():
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()

    queue: asyncio.Queue = asyncio.Queue()
    queue.put_nowait({"event": "final", "data": {"output_text": "ok"}})
    queue.put_nowait(None)
    endpoints._RUN_QUEUES["run-owned"] = queue
    endpoints._RUN_OWNERS["run-owned"] = "web:owner"

    with TestClient(app) as client:
        _attach_session_cookie(client, user_id="web:other")
        response = client.get("/api/public/chat/runs/run-owned/events")
        assert response.status_code == 403


def test_public_chat_events_stream_for_owner():
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()

    queue: asyncio.Queue = asyncio.Queue()
    queue.put_nowait({"event": "progress", "data": {"stage": "compose"}})
    queue.put_nowait({"event": "final", "data": {"output_text": "done"}})
    queue.put_nowait(None)
    endpoints._RUN_QUEUES["run-owned"] = queue
    endpoints._RUN_OWNERS["run-owned"] = "web:owner"

    with TestClient(app) as client:
        _attach_session_cookie(client, user_id="web:owner")
        response = client.get("/api/public/chat/runs/run-owned/events")
        assert response.status_code == 200
        assert '"event": "progress"' in response.text
        assert '"event": "final"' in response.text
        assert '"output_text": "done"' in response.text


def teardown_module():
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()
    endpoints._PUBLIC_CHAT_IDEMPOTENCY.clear()
    try:
        if os.path.exists("test_managed_cloud_mvp.db"):
            os.remove("test_managed_cloud_mvp.db")
    except Exception:
        pass
