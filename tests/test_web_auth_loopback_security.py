from __future__ import annotations

from fastapi.testclient import TestClient

from src.web import endpoints
from src.web.app import app


def _clear_loopback_env(monkeypatch) -> None:
    for name in (
        "ORA_WEB_API_TOKEN",
        "ORA_REQUIRE_WEB_API_TOKEN",
        "ADMIN_DASHBOARD_TOKEN",
        "ALLOW_INSECURE_ADMIN_DASHBOARD",
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


def test_loopback_helper_requires_loopback_peer_before_trusting_forwarded_headers(monkeypatch):
    _clear_loopback_env(monkeypatch)
    monkeypatch.setenv("ORA_TRUST_PROXY_HEADERS_FOR_LOCAL_AUTH", "1")

    assert endpoints._is_loopback_client(
        peer_host="203.0.113.10",
        headers={"x-forwarded-for": "127.0.0.1"},
    ) is False


def test_loopback_helper_rejects_forwarded_loopback_by_default(monkeypatch):
    _clear_loopback_env(monkeypatch)

    assert endpoints._is_loopback_client(
        peer_host="127.0.0.1",
        headers={"x-forwarded-for": "127.0.0.1"},
    ) is False


def test_loopback_helper_allows_forwarded_loopback_only_in_trusted_proxy_mode(monkeypatch):
    _clear_loopback_env(monkeypatch)
    monkeypatch.setenv("ORA_TRUST_PROXY_HEADERS_FOR_LOCAL_AUTH", "1")

    assert endpoints._is_loopback_client(
        peer_host="127.0.0.1",
        headers={"x-forwarded-for": "127.0.0.1"},
    ) is True


def test_setup_rejects_local_bypass_without_token_in_non_dev_mode(monkeypatch):
    _clear_loopback_env(monkeypatch)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.get("/setup")
        assert response.status_code == 503


def test_setup_allows_local_bypass_in_dev_mode(monkeypatch):
    _clear_loopback_env(monkeypatch)
    monkeypatch.setenv("ORA_ALLOW_MISSING_SECRETS", "1")

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.get("/setup")
        assert response.status_code == 200


def test_setup_rejects_spoofed_forwarded_loopback_from_public_peer(monkeypatch):
    _clear_loopback_env(monkeypatch)
    monkeypatch.setenv("ORA_ALLOW_MISSING_SECRETS", "1")

    with TestClient(app, client=("203.0.113.10", 50000)) as client:
        response = client.get("/setup", headers={"x-forwarded-for": "127.0.0.1"})
        assert response.status_code == 403
