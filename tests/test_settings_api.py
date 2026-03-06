import os

from fastapi.testclient import TestClient

from src.web.app import app


def _clear_web_auth_env(monkeypatch):
    for name in (
        "ORA_WEB_API_TOKEN",
        "ORA_REQUIRE_WEB_API_TOKEN",
        "ORA_ALLOW_MISSING_SECRETS",
        "ORA_TRUST_PROXY_HEADERS_FOR_LOCAL_AUTH",
        "ORA_ENV",
        "ORA_APP_ENV",
        "APP_ENV",
        "FASTAPI_ENV",
        "PYTHON_ENV",
        "ENV",
    ):
        monkeypatch.delenv(name, raising=False)


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
    _clear_web_auth_env(monkeypatch)
    with TestClient(app) as client:
        r = client.get("/api/settings/status", headers={"x-forwarded-for": "8.8.8.8"})
        # No token configured + non-loopback forwarded IP => should not allow.
        assert r.status_code == 503


def test_settings_status_rejects_missing_token_on_localhost_in_non_dev_mode(monkeypatch):
    _clear_web_auth_env(monkeypatch)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        r = client.get("/api/settings/status")
        assert r.status_code == 503


def test_settings_status_allows_localhost_without_token_in_dev_mode(monkeypatch):
    _clear_web_auth_env(monkeypatch)
    monkeypatch.setenv("ORA_ALLOW_MISSING_SECRETS", "1")
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        r = client.get("/api/settings/status")
        assert r.status_code == 200
