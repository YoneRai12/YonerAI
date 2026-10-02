from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest


repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

if "discord" not in sys.modules:
    discord_stub = types.ModuleType("discord")

    class Attachment:  # pragma: no cover - typing import stub
        pass

    class Embed:
        def __init__(self) -> None:
            self.image = types.SimpleNamespace(url=None)
            self.thumbnail = types.SimpleNamespace(url=None)

        def set_image(self, *, url: str):
            self.image = types.SimpleNamespace(url=url)
            return self

    discord_stub.Attachment = Attachment
    discord_stub.Embed = Embed
    sys.modules["discord"] = discord_stub

if "PIL" not in sys.modules:
    pil_stub = types.ModuleType("PIL")
    image_stub = types.SimpleNamespace(
        open=lambda *_args, **_kwargs: None,
        Resampling=types.SimpleNamespace(LANCZOS=1),
    )
    pil_stub.Image = image_stub
    sys.modules["PIL"] = pil_stub

import discord  # noqa: E402
from src.cogs.handlers import vision_handler  # noqa: E402


def test_embed_image_url_rejects_private_and_metadata_targets() -> None:
    rejected = (
        "http://127.0.0.1/image.png",
        "http://localhost/image.png",
        "http://169.254.169.254/latest/meta-data/image.png",
        "https://metadata.google.internal/image.png",
        "https://service.internal/image.png",
    )

    for url in rejected:
        with pytest.raises(ValueError):
            asyncio.run(vision_handler._assert_safe_embed_image_url(url))


def test_embed_image_url_rejects_non_http_and_userinfo() -> None:
    rejected = (
        "ftp://example.com/image.png",
        "data:image/png;base64,AAAA",
        "https://user:pass@example.com/image.png",
    )

    for url in rejected:
        with pytest.raises(ValueError):
            asyncio.run(vision_handler._assert_safe_embed_image_url(url))


def test_embed_image_url_allows_public_host(monkeypatch) -> None:
    async def fake_resolve(host: str) -> set[str]:
        assert host == "example.com"
        return {"93.184.216.34"}

    monkeypatch.setattr(vision_handler, "_resolve_embed_image_host_ips", fake_resolve)

    normalized, ips = asyncio.run(vision_handler._assert_safe_embed_image_url("https://Example.COM/img.png?x=1#frag"))

    assert normalized == "https://example.com/img.png?x=1"
    assert ips == {"93.184.216.34"}


def test_embed_image_url_preserves_public_ipv6_brackets(monkeypatch) -> None:
    async def fake_resolve(host: str) -> set[str]:
        assert host == "2001:4860:4860::8888"
        return {"2001:4860:4860::8888"}

    monkeypatch.setattr(vision_handler, "_resolve_embed_image_host_ips", fake_resolve)

    normalized, ips = asyncio.run(
        vision_handler._assert_safe_embed_image_url("https://[2001:4860:4860::8888]:443/img.png")
    )

    assert normalized == "https://[2001:4860:4860::8888]:443/img.png"
    assert ips == {"2001:4860:4860::8888"}


def test_process_embeds_skips_private_loopback_image(tmp_path) -> None:
    handler = vision_handler.VisionHandler(tmp_path)
    embed = discord.Embed()
    embed.set_image(url="http://127.0.0.1:8765/private.png")

    prompt_suffix, image_payloads = asyncio.run(handler.process_embeds([embed]))

    assert prompt_suffix == ""
    assert image_payloads == []
