# ruff: noqa: E402, F401, B023, B007, B008
import os

from fastapi.testclient import TestClient

# Ensure the app uses a test DB file (Store reads ORA_BOT_DB at startup).
os.environ["ORA_BOT_DB"] = "test_ora_web.db"

from src.web.app import app


def test_root_serves_html_loader():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        # Root serves the remote loader HTML if present.
        assert resp.headers.get("content-type", "").startswith("text/html")
        assert "<!DOCTYPE html" in resp.text


def test_config_limits_endpoint_requires_token(monkeypatch):
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "t")
    with TestClient(app) as client:
        resp = client.get("/api/config/limits")
        assert resp.status_code == 403
        resp = client.get("/api/config/limits", headers={"Authorization": "Bearer t"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


def test_auth_link_code_is_public_disabled_contract(monkeypatch):
    with TestClient(app) as client:
        resp = client.post("/api/auth/link-code", json={"user_id": "123456789"})

    assert resp.status_code == 501
    data = resp.json()

    assert data["schema_version"] == "yonerai-public-google-auth/v0.1"
    assert data["status"] == "disabled"
    assert data["live_oauth_enabled"] is False
    assert data["dry_run_contract_only"] is True
    assert data["required_future_flow"]["pkce_required"] is True
    assert data["required_future_flow"]["state_required"] is True
    assert data["required_future_flow"]["loopback_redirect_only"] is True
    assert data["required_future_flow"]["minimal_scopes"] == ["openid", "email", "profile"]
    assert "no live OAuth redirect" in data["actions_not_performed"]
    assert "no Google token exchange" in data["actions_not_performed"]
    assert "no credential storage" in data["actions_not_performed"]
    assert "no refresh token storage" in data["actions_not_performed"]
    assert "no Drive scope request" in data["actions_not_performed"]
    assert "url" not in data
    assert "code" not in data
    assert "google.com" not in resp.text
    assert "drive.file" not in resp.text


def test_google_auth_routes_do_not_redirect_or_exchange_tokens(monkeypatch):
    with TestClient(app) as client:
        start = client.get("/api/auth/discord?discord_user_id=123456789", follow_redirects=False)
        callback = client.get("/api/auth/google/callback?code=fake-code&state=fake-state", follow_redirects=False)

    for resp in (start, callback):
        assert resp.status_code == 501
        data = resp.json()
        assert data["status"] == "disabled"
        assert data["live_oauth_enabled"] is False
        assert "location" not in {key.lower() for key in resp.headers}
        assert "no Google token exchange" in data["actions_not_performed"]
        assert "google.com" not in resp.text
        assert "drive.file" not in resp.text


def teardown_module():
    # Best-effort cleanup of the sqlite file created by Store.
    try:
        if os.path.exists("test_ora_web.db"):
            os.remove("test_ora_web.db")
    except Exception:
        pass
