# ruff: noqa: E402, F401, B023, B007, B008
import os
from unittest.mock import MagicMock, patch

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


def test_auth_link_code_happy_path(monkeypatch):
    # Avoid reading google_client_secrets.json by mocking Flow.
    with TestClient(app) as client:
        with patch("src.web.endpoints.Flow") as MockFlow:
            mock_flow = MagicMock()
            MockFlow.from_client_secrets_file.return_value = mock_flow
            mock_flow.authorization_url.return_value = ("http://google.com/auth", "state")

            resp = client.post("/api/auth/link-code", json={"user_id": "123456789"})
            assert resp.status_code == 200
            data = resp.json()
            assert "url" in data
            assert "code" in data


def teardown_module():
    # Best-effort cleanup of the sqlite file created by Store.
    try:
        if os.path.exists("test_ora_web.db"):
            os.remove("test_ora_web.db")
    except Exception:
        pass
