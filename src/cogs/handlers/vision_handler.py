import base64
import asyncio
import io
import ipaddress
import logging
import socket
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles  # type: ignore
import aiohttp
import discord
from PIL import Image

logger = logging.getLogger(__name__)


MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
_MAX_EMBED_IMAGE_REDIRECTS = 3
_BLOCKED_EMBED_IMAGE_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "metadata.azure.internal",
}
_BLOCKED_EMBED_IMAGE_HOST_SUFFIXES = (".localhost", ".local", ".internal")
_BLOCKED_EMBED_IMAGE_NETS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)
_BLOCKED_EMBED_IMAGE_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("169.254.170.2"),
    ipaddress.ip_address("100.100.100.200"),
}


def _normalize_embed_image_host(host: str) -> str:
    return str(host or "").strip().lower().rstrip(".")


def _is_blocked_embed_image_host(host: str) -> bool:
    normalized = _normalize_embed_image_host(host)
    if not normalized:
        return True
    if normalized in _BLOCKED_EMBED_IMAGE_HOSTS:
        return True
    return normalized.endswith(_BLOCKED_EMBED_IMAGE_HOST_SUFFIXES)


def _parse_embed_image_ip_literal(host: str) -> ipaddress._BaseAddress | None:
    try:
        return ipaddress.ip_address(_normalize_embed_image_host(host))
    except Exception:
        return None


def _is_blocked_embed_image_ip(ip_obj: ipaddress._BaseAddress) -> bool:
    if ip_obj in _BLOCKED_EMBED_IMAGE_METADATA_IPS:
        return True
    if (
        ip_obj.is_loopback
        or ip_obj.is_private
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    ):
        return True
    return any(ip_obj in net for net in _BLOCKED_EMBED_IMAGE_NETS)


async def _resolve_embed_image_host_ips(host: str) -> set[str]:
    ip_literal = _parse_embed_image_ip_literal(host)
    if ip_literal is not None:
        return {str(ip_literal)}

    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(_normalize_embed_image_host(host), None, type=socket.SOCK_STREAM)
    ips: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        if isinstance(sockaddr, tuple) and sockaddr:
            ips.add(str(sockaddr[0]))
    if not ips:
        raise ValueError("embed image host resolution failed")
    return ips


async def _assert_safe_embed_image_url(url: str) -> tuple[str, set[str]]:
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValueError("invalid embed image url")
    if parsed.username or parsed.password:
        raise ValueError("invalid embed image url")

    host = _normalize_embed_image_host(parsed.hostname or "")
    if _is_blocked_embed_image_host(host):
        raise ValueError("embed image host not allowed")

    ips = await _resolve_embed_image_host_ips(host)
    for raw_ip in ips:
        if _is_blocked_embed_image_ip(ipaddress.ip_address(raw_ip)):
            raise ValueError("embed image host not allowed")

    netloc = f"[{host}]" if ":" in host else host
    if parsed.port is not None:
        netloc = f"{host}:{parsed.port}"
        if ":" in host:
            netloc = f"[{host}]:{parsed.port}"
    normalized = urllib.parse.urlunsplit((scheme, netloc, parsed.path or "/", parsed.query or "", ""))
    return normalized, ips


def _iter_embed_peer_ip_candidates(resp: aiohttp.ClientResponse):
    try:
        conn = getattr(resp, "connection", None)
        transport = getattr(conn, "transport", None) if conn else None
        peer = transport.get_extra_info("peername") if transport else None
        if isinstance(peer, tuple) and peer:
            yield str(peer[0])
    except Exception:
        return


def _assert_embed_peer_ip_safe(resp: aiohttp.ClientResponse, resolved_ips: set[str]) -> None:
    for raw_peer in _iter_embed_peer_ip_candidates(resp):
        try:
            ip_obj = ipaddress.ip_address(raw_peer)
            if _is_blocked_embed_image_ip(ip_obj):
                raise ValueError("embed image host not allowed")
            if resolved_ips and str(ip_obj) not in resolved_ips:
                raise ValueError("embed image host not allowed")
        except ValueError:
            raise
        except Exception:
            continue


async def _download_safe_embed_image(url: str) -> bytes | None:
    next_url, resolved_ips = await _assert_safe_embed_image_url(url)
    timeout = aiohttp.ClientTimeout(total=5, connect=3)
    headers = {
        "User-Agent": "YonerAI embed vision",
        "Accept": "image/*,*/*;q=0.8",
    }
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        for _ in range(_MAX_EMBED_IMAGE_REDIRECTS + 1):
            async with session.get(next_url, allow_redirects=False) as resp:
                _assert_embed_peer_ip_safe(resp, resolved_ips)
                if resp.status in {301, 302, 303, 307, 308}:
                    location = resp.headers.get("Location")
                    if not location:
                        return None
                    next_url, resolved_ips = await _assert_safe_embed_image_url(
                        urllib.parse.urljoin(next_url, location)
                    )
                    continue
                if resp.status != 200:
                    return None
                content_type = (resp.headers.get("Content-Type") or "").lower()
                if content_type and not content_type.startswith("image/"):
                    return None
                content_length = resp.headers.get("Content-Length")
                if content_length and content_length.isdigit() and int(content_length) > MAX_IMAGE_BYTES:
                    return None
                image_data = await resp.content.read(MAX_IMAGE_BYTES + 1)
                if len(image_data) > MAX_IMAGE_BYTES:
                    return None
                return image_data
    return None


class VisionHandler:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.supported_text_ext = {
            ".txt",
            ".md",
            ".py",
            ".js",
            ".json",
            ".html",
            ".css",
            ".csv",
            ".xml",
            ".yaml",
            ".yml",
            ".sh",
            ".bat",
            ".ps1",
        }
        self.supported_img_ext = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

    async def process_attachments(
        self, attachments: List[discord.Attachment], is_reference: bool = False
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Process attachments and return (prompt_suffix, image_payloads).
        """
        prompt_suffix = ""
        image_payloads = []

        for i, attachment in enumerate(attachments):
            ext = "." + attachment.filename.split(".")[-1].lower() if "." in attachment.filename else ""

            # TEXT PROCESSING
            if ext in self.supported_text_ext or (attachment.content_type and "text" in attachment.content_type):
                if attachment.size > 1024 * 1024:
                    continue
                try:
                    content = await attachment.read()
                    text_content = content.decode("utf-8", errors="ignore")
                    header = (
                        f"[Referenced File: {attachment.filename}]"
                        if is_reference
                        else f"[Attached File: {attachment.filename}]"
                    )
                    prompt_suffix += f"\n\n{header}\n{text_content}\n"
                except Exception:
                    pass

            # IMAGE PROCESSING
            elif ext in self.supported_img_ext:
                if attachment.size > 8 * 1024 * 1024:
                    continue

                try:
                    image_data = await attachment.read()

                    # Cache to disk
                    timestamp = int(time.time())
                    safe_filename = f"{timestamp}_{attachment.filename}"
                    cache_path = self.cache_dir / safe_filename
                    async with aiofiles.open(cache_path, "wb") as f:
                        await f.write(image_data)

                    # Optimize & Encode
                    b64_img = await self._optimize_and_encode(image_data)
                    if b64_img:
                        payload = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                        image_payloads.append(payload)

                        header = (
                            f"[Referenced Image: {attachment.filename}]"
                            if is_reference
                            else f"[Attached Image {i + 1}: {attachment.filename}]"
                        )
                        prompt_suffix += f"\n\n{header}\n(Image loaded into LLM Vision Context)\n"

                except Exception as e:
                    logger.error(f"Image process failed: {e}")

        return prompt_suffix, image_payloads

    async def process_embeds(
        self, embeds: List[discord.Embed], is_reference: bool = False
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Process images in embeds.
        """
        prompt_suffix = ""
        image_payloads = []

        for embed in embeds:
            image_url = None
            if embed.image and embed.image.url:
                image_url = embed.image.url
            elif embed.thumbnail and embed.thumbnail.url:
                image_url = embed.thumbnail.url

            if not image_url:
                continue

            try:
                image_data = await _download_safe_embed_image(image_url)
                if not image_data:
                    continue

                # Optimize & Encode
                b64_img = await self._optimize_and_encode(image_data)
                if b64_img:
                    payload = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                    image_payloads.append(payload)
                    prompt_suffix += "\n\n[Embed Image]\n(Image loaded into LLM Vision Context)\n"

            except Exception as e:
                logger.warning("Failed to process embed image: %s", e)

        return prompt_suffix, image_payloads

    async def _optimize_and_encode(self, image_data: bytes) -> Optional[str]:
        """Resize logic."""
        try:
            if len(image_data) > MAX_IMAGE_BYTES:
                return None

            # Load image with PIL
            with Image.open(io.BytesIO(image_data)) as img:
                if img.width * img.height > MAX_IMAGE_PIXELS:
                    return None

                # Convert to RGB (in case of RGBA/PNG)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Resize if too large (Max 1024x1024)
                max_size = 1024
                if max(img.size) > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                # Save to buffer as JPEG
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                optimized_data = buffer.getvalue()

            return base64.b64encode(optimized_data).decode("utf-8")
        except Exception as e:
            logger.error(f"Vision Encode Error: {e}")
            return None
