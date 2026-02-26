import os

from fastapi.testclient import TestClient

from src.web.app import app


def test_settings_endpoints_require_token_when_configured(monkeypatch):
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "t")
    with TestClient(app) as client:
        r = client.get("/api/settings/status")
        assert r.status_code == 403

        r = client.get("/api/settings/status", headers={"Authorization": "Bearer t"})
        assert r.status_code == 200
        data = r.json()
        assert "secrets_present" in data


def test_settings_status_never_returns_secret_values(monkeypatch):
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "t")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-should-not-leak")
    with TestClient(app) as client:
        r = client.get("/api/settings/status", headers={"Authorization": "Bearer t"})
        assert r.status_code == 200
        txt = r.text
        assert "sk-test-should-not-leak" not in txt


def test_settings_status_rejects_forwarded_public_ip_without_token(monkeypatch):
    monkeypatch.delenv("ORA_WEB_API_TOKEN", raising=False)
    monkeypatch.delenv("ORA_REQUIRE_WEB_API_TOKEN", raising=False)
    with TestClient(app) as client:
        r = client.get("/api/settings/status", headers={"x-forwarded-for": "8.8.8.8"})
        # No token configured + non-loopback forwarded IP => should not allow.
        assert r.status_code == 503


def test_dev_ui_status_requires_token_when_configured(monkeypatch):
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "t")
    with TestClient(app) as client:
        r = client.get("/api/platform/dev-ui/status", params={"user_id": "123456"})
        assert r.status_code == 403

        r = client.get(
            "/api/platform/dev-ui/status",
            params={"user_id": "123456"},
            headers={"Authorization": "Bearer t"},
        )
        assert r.status_code == 200
        assert r.json().get("dev_ui_enabled") in {True, False}


def test_dev_ui_status_roundtrip(monkeypatch):
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "t")
    user_id = "987654321012345678"
    with TestClient(app) as client:
        set_on = client.post(
            "/api/platform/dev-ui/status",
            headers={"Authorization": "Bearer t"},
            json={"user_id": user_id, "enabled": True},
        )
        assert set_on.status_code == 200
        assert set_on.json().get("dev_ui_enabled") is True

        read_back = client.get(
            "/api/platform/dev-ui/status",
            params={"user_id": user_id},
            headers={"Authorization": "Bearer t"},
        )
        assert read_back.status_code == 200
        assert read_back.json().get("dev_ui_enabled") is True

        set_off = client.post(
            "/api/platform/dev-ui/status",
            headers={"Authorization": "Bearer t"},
            json={"user_id": user_id, "enabled": False},
        )
        assert set_off.status_code == 200
        assert set_off.json().get("dev_ui_enabled") is False
