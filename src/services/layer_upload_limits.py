import io
import warnings

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_IMAGE_WIDTH = 8192
MAX_IMAGE_HEIGHT = 8192
MAX_IMAGE_PIXELS = 40_000_000
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024


def is_layer_attachment_too_large(attachment, max_bytes: int = MAX_UPLOAD_BYTES) -> bool:
    size = getattr(attachment, "size", None)
    return size is not None and size > max_bytes


async def read_limited_upload(file: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read an upload without allowing unbounded memory growth."""
    chunks: list[bytes] = []
    total = 0

    while True:
        remaining = max_bytes + 1 - total
        if remaining <= 0:
            raise HTTPException(
                status_code=413,
                detail="Image upload exceeds the configured byte limit.",
            )
        chunk = await file.read(min(UPLOAD_READ_CHUNK_BYTES, remaining))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="Image upload exceeds the configured byte limit.",
            )
        chunks.append(chunk)

    if total == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image upload is empty.")

    return b"".join(chunks)


def validate_layer_image(
    image_data: bytes,
    *,
    max_width: int = MAX_IMAGE_WIDTH,
    max_height: int = MAX_IMAGE_HEIGHT,
    max_pixels: int = MAX_IMAGE_PIXELS,
) -> Image.Image:
    """Validate uploaded image bytes before layer decomposition work starts."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DecompressionBombWarning)

            with Image.open(io.BytesIO(image_data)) as probe:
                width, height = probe.size
                if width > max_width or height > max_height or width * height > max_pixels:
                    raise HTTPException(
                        status_code=413,
                        detail="Image dimensions exceed the configured layer service limit.",
                    )
                probe.verify()

            with Image.open(io.BytesIO(image_data)) as image:
                return image.convert("RGB")
    except HTTPException:
        raise
    except (DecompressionBombError, DecompressionBombWarning, UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image upload.") from exc
