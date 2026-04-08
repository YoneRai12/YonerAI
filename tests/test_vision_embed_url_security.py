from pathlib import Path

import pytest

from src.cogs.handlers.vision_handler import VisionHandler


@pytest.mark.asyncio
async def test_embed_url_rejects_localhost_and_private_ips() -> None:
    vh = VisionHandler(Path('.'))

    assert await vh._is_safe_public_image_url('http://localhost/image.png') is False
    assert await vh._is_safe_public_image_url('http://127.0.0.1/image.png') is False
    assert await vh._is_safe_public_image_url('http://10.0.0.1/image.png') is False
    assert await vh._is_safe_public_image_url('file:///etc/passwd') is False
