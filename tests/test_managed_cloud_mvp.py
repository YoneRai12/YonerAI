# ruff: noqa: E402
from __future__ import annotations

import asyncio
import base64
import os
import secrets

from fastapi.testclient import TestClient

os.environ["ORA_BOT_DB"] = "test_managed_cloud_mvp.db"
os.environ["ORA_DISABLE_WEB_BG_TASKS"] = "1"

from src.web import endpoints
from src.web.app import app, get_store

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0MsAAAAASUVORK5CYII="
)


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


def _enable_guest_chat(monkeypatch) -> None:
    monkeypatch.setenv("ORA_WEB_GUEST_CHAT", "1")
    monkeypatch.setattr(endpoints, "_can_use_unauthenticated_loopback", lambda _request: True)


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

        login = client.get("/auth/login?returnTo=/jp/chat")
        assert login.status_code == 200
        assert "Continue with Google" in login.text
        assert "Sign in with Microsoft" not in login.text
        assert "Sign in with Discord" not in login.text
        assert "Sign in with X" not in login.text


def test_chat_redirect_prefers_cf_country_then_accept_language():
    with TestClient(app) as client:
        jp = client.get("/chat", headers={"cf-ipcountry": "JP"}, follow_redirects=False)
        assert jp.status_code == 307
        assert jp.headers["location"] == "/jp/chat"

        en = client.get("/chat", headers={"cf-ipcountry": "DE"}, follow_redirects=False)
        assert en.status_code == 307
        assert en.headers["location"] == "/en/chat"


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


def test_auth_me_issues_guest_session_on_loopback(monkeypatch):
    _enable_guest_chat(monkeypatch)

    with TestClient(app) as client:
        first = client.get("/api/auth/me", headers={"accept-language": "ja"})
        assert first.status_code == 200
        guest_a = first.json()
        assert guest_a["provider"] == "guest"
        assert guest_a["guest"] is True
        assert guest_a["display_name"] == "ゲスト"
        assert guest_a["user_id"].startswith("web:guest:")

        second = client.get("/api/auth/me", headers={"accept-language": "ja"})
        assert second.status_code == 200
        guest_b = second.json()
        assert guest_b["user_id"] == guest_a["user_id"]
        assert guest_b["provider"] == "guest"


def test_public_chat_message_uses_session_actor(monkeypatch):
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()
    endpoints._PUBLIC_CHAT_IDEMPOTENCY.clear()

    seen: dict[str, object] = {}

    def fake_start_agent_run(*, content: str, available_tools, provider_id: str, attachments, conversation_id=None, runtime_kind: str = "default"):
        assert content == "hello"
        seen["provider_id"] = provider_id
        assert available_tools == []
        assert isinstance(conversation_id, str)
        assert runtime_kind == "managed_cloud_web"
        return "run-public-1"

    monkeypatch.setattr(endpoints, "_start_agent_run", fake_start_agent_run)

    with TestClient(app) as client:
        user_id = _attach_session_cookie(client, user_id=f"web:test-user:{secrets.token_hex(4)}")
        response = client.post(
            "/api/public/chat/messages",
            json={"content": "hello", "idempotency_key": "abc-123"},
            headers={"Idempotency-Key": "abc-123"},
        )
        assert response.status_code == 200
        assert response.json()["run_id"] == "run-public-1"
        assert seen["provider_id"] == user_id
        assert endpoints._RUN_OWNERS["run-public-1"] == user_id


def test_public_chat_message_allows_guest_session(monkeypatch):
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()
    endpoints._PUBLIC_CHAT_IDEMPOTENCY.clear()
    _enable_guest_chat(monkeypatch)

    seen: dict[str, str] = {}

    def fake_start_agent_run(*, content: str, available_tools, provider_id: str, attachments, conversation_id=None, runtime_kind: str = "default"):
        seen["provider_id"] = provider_id
        seen["conversation_id"] = conversation_id
        return "run-guest-1"

    monkeypatch.setattr(endpoints, "_start_agent_run", fake_start_agent_run)

    with TestClient(app) as client:
        response = client.post(
            "/api/public/chat/messages",
            json={"content": "hello guest", "idempotency_key": "guest-123"},
            headers={"Idempotency-Key": "guest-123"},
        )
        assert response.status_code == 200
        assert response.json()["run_id"] == "run-guest-1"
        assert seen["provider_id"].startswith("web:guest:")
        assert endpoints._RUN_OWNERS["run-guest-1"] == seen["provider_id"]

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["user_id"] == seen["provider_id"]


def test_public_chat_upload_accepts_guest_images(monkeypatch):
    endpoints._PUBLIC_CHAT_ATTACHMENTS.clear()
    _enable_guest_chat(monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/public/attachments/upload",
            files=[("files", ("tiny.png", _TINY_PNG, "image/png"))],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["max_count"] == 4
        assert len(data["attachments"]) == 1
        item = data["attachments"][0]
        assert item["mime_type"] == "image/png"
        assert item["size"] == len(_TINY_PNG)
        attachment_id = item["attachment_id"]
        assert attachment_id in endpoints._PUBLIC_CHAT_ATTACHMENTS


def test_public_chat_upload_rejects_more_than_four_images(monkeypatch):
    endpoints._PUBLIC_CHAT_ATTACHMENTS.clear()
    _enable_guest_chat(monkeypatch)

    with TestClient(app) as client:
        files = [("files", (f"tiny-{idx}.png", _TINY_PNG, "image/png")) for idx in range(5)]
        response = client.post("/api/public/attachments/upload", files=files)
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "ATTACHMENT_TOO_MANY"
        assert detail["max_count"] == 4


def test_public_chat_message_rejects_content_over_5000(monkeypatch):
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()
    endpoints._PUBLIC_CHAT_IDEMPOTENCY.clear()
    _enable_guest_chat(monkeypatch)

    response = TestClient(app).post(
        "/api/public/chat/messages",
        json={"content": "a" * 5001},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "CHAT_CONTENT_TOO_LONG"
    assert detail["max_chars"] == 5000


def test_public_chat_message_resolves_uploaded_image_refs(monkeypatch):
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()
    endpoints._PUBLIC_CHAT_IDEMPOTENCY.clear()
    endpoints._PUBLIC_CHAT_ATTACHMENTS.clear()
    _enable_guest_chat(monkeypatch)

    seen: dict[str, object] = {}

    def fake_start_agent_run(*, content: str, available_tools, provider_id: str, attachments, conversation_id=None, runtime_kind: str = "default"):
        seen["content"] = content
        seen["attachments"] = attachments
        seen["provider_id"] = provider_id
        return "run-vision-1"

    monkeypatch.setattr(endpoints, "_start_agent_run", fake_start_agent_run)

    with TestClient(app) as client:
        upload = client.post(
            "/api/public/attachments/upload",
            files=[("files", ("tiny.png", _TINY_PNG, "image/png"))],
        )
        assert upload.status_code == 200
        attachment_id = upload.json()["attachments"][0]["attachment_id"]

        response = client.post(
            "/api/public/chat/messages",
            json={
                "content": "",
                "attachments": [{"type": "image_ref", "attachment_id": attachment_id}],
            },
        )
        assert response.status_code == 200
        assert response.json()["run_id"] == "run-vision-1"
        assert seen["content"] == ""
        resolved = seen["attachments"]
        assert isinstance(resolved, list)
        assert len(resolved) == 1
        assert resolved[0]["type"] == "image_url"
        assert str(resolved[0]["image_url"]["url"]).startswith("data:image/png;base64,")


def test_public_chat_usage_reports_google_limit():
    with TestClient(app) as client:
        user_id = _attach_session_cookie(client, user_id=f"web:quota-google:{secrets.token_hex(4)}")
        store = get_store()
        asyncio.run(
            store.record_api_usage(
                user_id=user_id,
                api_key_id=None,
                method="POST",
                path="/api/public/chat/messages",
                status=200,
                latency_ms=12,
                request_bytes=10,
                response_bytes=20,
                meta_json='{"source":"test"}',
            )
        )
        asyncio.run(
            store.record_api_usage(
                user_id=user_id,
                api_key_id=None,
                method="POST",
                path="/api/public/chat/messages",
                status=200,
                latency_ms=15,
                request_bytes=11,
                response_bytes=21,
                meta_json='{"source":"test"}',
            )
        )

        response = client.get("/api/public/chat/usage")
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "google"
        assert data["limit"] == 20
        assert data["used"] == 2
        assert data["remaining"] == 18
        assert data["used_session_raw"] == 2
        assert data["used_api_key_raw"] == 0


def test_public_chat_usage_issues_guest_limit(monkeypatch):
    _enable_guest_chat(monkeypatch)

    with TestClient(app) as client:
        first = client.get("/api/public/chat/usage")
        assert first.status_code == 200
        data = first.json()
        assert data["provider"] == "guest"
        assert data["limit"] == 3
        assert data["used"] == 0
        assert data["remaining"] == 3


def test_public_chat_title_guest_returns_summary(monkeypatch):
    _enable_guest_chat(monkeypatch)

    async def fake_title(*, content: str, max_len: int, lang: str) -> str:
        assert "YonerAI" in content
        assert max_len == 20
        assert lang == "ja"
        return "YonerAIって何者？"

    monkeypatch.setattr(endpoints, "_generate_public_chat_title", fake_title)

    with TestClient(app) as client:
        response = client.post(
            "/api/public/chat/title",
            json={"content": "君は誰 YonerAI ってどんなの？", "max_len": 20, "lang": "ja"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "YonerAIって何者？"
        assert data["max_len"] == 20
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["provider"] == "guest"


def test_public_chat_message_rejects_when_daily_limit_reached(monkeypatch):
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()
    endpoints._PUBLIC_CHAT_IDEMPOTENCY.clear()

    def fail_if_started(**_kwargs):
        raise AssertionError("run should not start after quota is exhausted")

    monkeypatch.setattr(endpoints, "_start_agent_run", fail_if_started)

    with TestClient(app) as client:
        user_id = _attach_session_cookie(client, user_id=f"web:quota-hit:{secrets.token_hex(4)}")
        store = get_store()
        for _ in range(20):
            asyncio.run(
                store.record_api_usage(
                    user_id=user_id,
                    api_key_id=None,
                    method="POST",
                    path="/api/public/chat/messages",
                    status=200,
                    latency_ms=10,
                    request_bytes=9,
                    response_bytes=18,
                    meta_json='{"source":"test"}',
                )
            )

        response = client.post(
            "/api/public/chat/messages",
            json={"content": "limit?"},
        )
        assert response.status_code == 429
        detail = response.json()["detail"]
        assert detail["code"] == "CHAT_LIMIT_EXCEEDED"
        assert detail["limit"] == 20
        assert detail["used"] == 20
        assert detail["remaining"] == 0


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


def test_public_chat_message_binds_conversation_id(monkeypatch):
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()
    endpoints._PUBLIC_CHAT_IDEMPOTENCY.clear()

    seen: dict[str, object] = {}

    def fake_start_agent_run(*, content: str, available_tools, provider_id: str, attachments, conversation_id=None, runtime_kind: str = "default"):
        seen["provider_id"] = provider_id
        seen["conversation_id"] = conversation_id
        return "run-conv-1"

    monkeypatch.setattr(endpoints, "_start_agent_run", fake_start_agent_run)

    with TestClient(app) as client:
        user_id = _attach_session_cookie(client, user_id=f"web:test-user:{secrets.token_hex(4)}")
        response = client.post(
            "/api/public/chat/messages",
            json={"content": "hello", "conversation_id": "thread-123"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["run_id"] == "run-conv-1"
        assert payload["conversation_id"] == "thread-123"
        assert seen["provider_id"] == user_id
        assert seen["conversation_id"] == "thread-123"


def test_managed_cloud_runtime_uses_yonerai_prompt_and_thread_memory(monkeypatch):
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()
    endpoints._PUBLIC_CHAT_IDEMPOTENCY.clear()

    captured: dict[str, object] = {}

    class FakeLLMClient:
        def __init__(self, base_url, api_key, model, session=None):
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            captured["model"] = model

        async def chat(self, messages, temperature=0.7, **kwargs):
            captured["messages"] = messages
            return "new answer", None, {}

    monkeypatch.setattr("src.utils.llm_client.LLMClient", FakeLLMClient)
    monkeypatch.setattr(
        endpoints,
        "_load_agent_runtime_config",
        lambda *, runtime_kind: endpoints.SimpleNamespace(
            llm_base_url="http://example.invalid/v1",
            llm_api_key="EMPTY",
            llm_model="gpt-5-mini",
            openai_base_url="http://example.invalid/v1",
            profile="private",
            admin_user_id=None,
            sub_admin_ids=set(),
        ),
    )

    with TestClient(app):
        store = get_store()
        asyncio.run(
            store.add_conversation(
                user_id="web:memory-user",
                conversation_id="conv-a",
                platform="web",
                message="first question",
                response="first answer",
            )
        )
        asyncio.run(
            store.add_conversation(
                user_id="web:memory-user",
                conversation_id="conv-b",
                platform="web",
                message="other question",
                response="other answer",
            )
        )
        run_id = "run-memory-scoped"
        endpoints._RUN_QUEUES[run_id] = asyncio.Queue()
        endpoints._RUN_TOOL_OUTPUTS[run_id] = asyncio.Queue()

        asyncio.run(
            endpoints.run_agent_loop(
                run_id,
                "what did we discuss?",
                [],
                "web:memory-user",
                [],
                "conv-a",
                "managed_cloud_web",
            )
        )

        messages = captured["messages"]
        system_message = str(messages[0]["content"])
        assert "YonerAI" in system_message
        assert "ORA (Unified GPT-5 Environment)" not in system_message
        assert any(
            m.get("role") == "system" and "[Current Thread Memory]" in str(m.get("content") or "")
            for m in messages
        )
        assert any(m.get("role") == "user" and m.get("content") == "first question" for m in messages)
        assert any(m.get("role") == "assistant" and m.get("content") == "first answer" for m in messages)
        assert not any(m.get("role") == "user" and m.get("content") == "other question" for m in messages)

        rows = asyncio.run(
            store.get_conversations(user_id="web:memory-user", conversation_id="conv-a", limit=5)
        )
        assert any(row["message"] == "what did we discuss?" and row["response"] == "new answer" for row in rows)


def test_managed_cloud_runtime_prefers_openai_web_model(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("LLM_MODEL", "mistralai/ministral-3-14b-reasoning")
    monkeypatch.delenv("OPENAI_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("MANAGED_CLOUD_LLM_MODEL", raising=False)
    monkeypatch.delenv("WEB_LLM_MODEL", raising=False)

    cfg = endpoints._load_managed_cloud_runtime_config()
    assert cfg.llm_base_url == "https://api.openai.com/v1"
    assert cfg.llm_model == "gpt-5-mini"


def test_managed_cloud_runtime_persists_and_reuses_conversation(monkeypatch):
    endpoints._RUN_QUEUES.clear()
    endpoints._RUN_TOOL_OUTPUTS.clear()
    endpoints._RUN_OWNERS.clear()
    endpoints._PUBLIC_CHAT_IDEMPOTENCY.clear()

    captured: dict[str, object] = {}

    class FakeLLMClient:
        def __init__(self, base_url, api_key, model, session=None):
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            captured["model"] = model

        async def chat(self, messages, temperature=0.7, **kwargs):
            captured["messages"] = messages
            return "新しい返答", None, {}

    monkeypatch.setattr("src.utils.llm_client.LLMClient", FakeLLMClient)
    monkeypatch.setattr(
        endpoints,
        "_load_agent_runtime_config",
        lambda *, runtime_kind: endpoints.SimpleNamespace(
            llm_base_url="http://example.invalid/v1",
            llm_api_key="EMPTY",
            llm_model="gpt-5-mini",
            openai_base_url="http://example.invalid/v1",
            profile="private",
            admin_user_id=None,
            sub_admin_ids=set(),
        ),
    )

    with TestClient(app):
        store = get_store()
        asyncio.run(
            store.add_conversation(
                user_id="web:memory-user",
                platform="web",
                message="前の質問",
                response="前の返答",
            )
        )
        run_id = "run-memory"
        endpoints._RUN_QUEUES[run_id] = asyncio.Queue()
        endpoints._RUN_TOOL_OUTPUTS[run_id] = asyncio.Queue()

        asyncio.run(
            endpoints.run_agent_loop(
                run_id=run_id,
                content="今回の質問",
                available_tools=[],
                provider_id="web:memory-user",
                attachments=[],
                conversation_id=None,
                runtime_kind="managed_cloud_web",
            )
        )

        messages = captured["messages"]
        assert any(m.get("role") == "user" and m.get("content") == "前の質問" for m in messages)
        assert any(m.get("role") == "assistant" and m.get("content") == "前の返答" for m in messages)

        rows = asyncio.run(store.get_conversations(user_id="web:memory-user", limit=5))
        assert any(row["message"] == "今回の質問" and row["response"] == "新しい返答" for row in rows)


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
