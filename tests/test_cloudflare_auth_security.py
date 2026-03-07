from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from ora_core.api.middleware import cloudflare_auth as auth_module


class DummyHeaders(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class DummyRepo:
    async def get_or_create_user_by_email(self, email: str):
        return {"email": email}


class DummyJWKClient:
    def __init__(self, _url: str):
        self.url = _url

    def get_signing_key_from_jwt(self, _token: str):
        return SimpleNamespace(key="dummy")


@pytest.mark.asyncio
async def test_cloudflare_auth_rejects_missing_required_headers(monkeypatch):
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=SimpleNamespace(auth_strategy="cloudflare"))),
        headers=DummyHeaders({}),
    )

    with pytest.raises(HTTPException) as exc:
        await auth_module.get_current_user_from_header(request, DummyRepo())

    assert exc.value.status_code == 401
    assert "Missing Cloudflare Access headers" in exc.value.detail


@pytest.mark.asyncio
async def test_cloudflare_auth_validates_jwt_and_email(monkeypatch):
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", "example.cloudflareaccess.com")
    monkeypatch.setenv("CF_ACCESS_AUDIENCE", "test-audience")
    monkeypatch.setattr(auth_module, "PyJWKClient", DummyJWKClient)
    monkeypatch.setattr(
        auth_module,
        "jwt",
        SimpleNamespace(
            decode=lambda *_args, **_kwargs: {"email": "victim@example.com", "aud": "test-audience"}
        ),
    )
    auth_module._jwks_clients.clear()

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=SimpleNamespace(auth_strategy="cloudflare"))),
        headers=DummyHeaders(
            {
                "Cf-Access-Authenticated-User-Email": "victim@example.com",
                "Cf-Access-Jwt-Assertion": "header.payload.sig",
            }
        ),
    )

    user = await auth_module.get_current_user_from_header(request, DummyRepo())
    assert user == {"email": "victim@example.com"}


@pytest.mark.asyncio
async def test_cloudflare_auth_rejects_header_claim_mismatch(monkeypatch):
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", "example.cloudflareaccess.com")
    monkeypatch.setenv("CF_ACCESS_AUDIENCE", "test-audience")
    monkeypatch.setattr(auth_module, "PyJWKClient", DummyJWKClient)
    monkeypatch.setattr(
        auth_module,
        "jwt",
        SimpleNamespace(decode=lambda *_args, **_kwargs: {"email": "other@example.com"}),
    )
    auth_module._jwks_clients.clear()

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=SimpleNamespace(auth_strategy="cloudflare"))),
        headers=DummyHeaders(
            {
                "Cf-Access-Authenticated-User-Email": "victim@example.com",
                "Cf-Access-Jwt-Assertion": "header.payload.sig",
            }
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await auth_module.get_current_user_from_header(request, DummyRepo())

    assert exc.value.status_code == 401
    assert "identity mismatch" in exc.value.detail.lower()
