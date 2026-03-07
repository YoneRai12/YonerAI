from __future__ import annotations

import asyncio

import pytest

from src.skills.image_crop_upscale import tool as crop_tool


def test_assert_safe_image_url_rejects_private_targets() -> None:
    with pytest.raises(ValueError):
        asyncio.run(crop_tool._assert_safe_image_url("http://127.0.0.1/a.png"))


def test_assert_safe_image_url_rejects_blocked_host() -> None:
    with pytest.raises(ValueError):
        asyncio.run(crop_tool._assert_safe_image_url("https://metadata.google.internal/a.png"))


def test_assert_safe_image_url_allows_public_host(monkeypatch) -> None:
    async def _fake_resolve(host: str) -> set[str]:
        assert host == "example.com"
        return {"93.184.216.34"}

    monkeypatch.setattr(crop_tool, "_resolve_host_ips", _fake_resolve)

    normalized, ips = asyncio.run(crop_tool._assert_safe_image_url("https://example.com/img.png?x=1"))

    assert normalized == "https://example.com/img.png?x=1"
    assert ips == {"93.184.216.34"}
