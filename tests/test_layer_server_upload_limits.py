import asyncio
import io

import pytest
from fastapi import HTTPException, status
from PIL import Image

import src.services.layer_server as layer_server
from src.services.layer_upload_limits import (
    is_layer_attachment_too_large,
    read_limited_upload,
    validate_layer_image,
)


class AsyncUpload:
    def __init__(self, data: bytes):
        self._stream = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


def make_png(width: int = 2, height: int = 2) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(40, 80, 120)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_read_limited_upload_rejects_empty_upload():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(read_limited_upload(AsyncUpload(b""), max_bytes=16))

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


def test_read_limited_upload_rejects_oversized_upload():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(read_limited_upload(AsyncUpload(b"abcdef"), max_bytes=5))

    assert exc_info.value.status_code == 413


def test_validate_layer_image_accepts_small_png():
    image = validate_layer_image(make_png())

    assert image.mode == "RGB"
    assert image.size == (2, 2)


def test_validate_layer_image_rejects_invalid_bytes():
    with pytest.raises(HTTPException) as exc_info:
        validate_layer_image(b"not an image")

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


def test_validate_layer_image_rejects_dimensions_over_limit():
    with pytest.raises(HTTPException) as exc_info:
        validate_layer_image(make_png(width=2, height=2), max_width=1)

    assert exc_info.value.status_code == 413


def test_layer_attachment_size_gate_allows_unknown_or_small_size():
    class Attachment:
        size = None

    assert is_layer_attachment_too_large(Attachment(), max_bytes=10) is False

    Attachment.size = 10
    assert is_layer_attachment_too_large(Attachment(), max_bytes=10) is False


def test_layer_attachment_size_gate_rejects_oversized_attachment():
    class Attachment:
        size = 11

    assert is_layer_attachment_too_large(Attachment(), max_bytes=10) is True


def test_layer_endpoint_uses_non_success_status_when_model_unavailable(monkeypatch):
    async def fake_read(_file):
        return make_png()

    def fake_validate(data):
        assert data
        return Image.new("RGB", (2, 2), color=(1, 2, 3))

    async def fake_get_model():
        return None, None

    monkeypatch.setattr(layer_server, "read_limited_upload", fake_read)
    monkeypatch.setattr(layer_server, "validate_layer_image", fake_validate)
    monkeypatch.setattr(layer_server, "get_model", fake_get_model)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(layer_server.decompose(AsyncUpload(make_png())))

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
