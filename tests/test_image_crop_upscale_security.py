from __future__ import annotations

import asyncio

import pytest

from src.skills.image_crop_upscale import tool as crop_tool


def test_assert_allowed_image_url_rejects_non_discord_host() -> None:
    with pytest.raises(ValueError):
        asyncio.run(crop_tool._assert_allowed_image_url("https://example.com/a.png"))


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/a.png",
        "https://localhost/a.png",
        "file:///tmp/a.png",
    ],
)
def test_assert_allowed_image_url_rejects_unsafe_targets(url: str) -> None:
    with pytest.raises(ValueError):
        asyncio.run(crop_tool._assert_allowed_image_url(url))


def test_assert_allowed_image_url_allows_discord_cdn(monkeypatch) -> None:
    async def _fake_resolve(host: str) -> set[str]:
        assert host == "cdn.discordapp.com"
        return {"162.159.130.233"}

    monkeypatch.setattr(crop_tool, "_resolve_host_ips", _fake_resolve)
    normalized = asyncio.run(crop_tool._assert_allowed_image_url("https://cdn.discordapp.com/path/to/img.png?x=1"))
    assert normalized == "https://cdn.discordapp.com/path/to/img.png?x=1"
