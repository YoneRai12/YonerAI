import asyncio
import io
import logging
import os
import re
import tempfile
import uuid
from typing import Any, Optional, Tuple

import aiohttp
import discord
from PIL import Image

from src.utils.temp_downloads import create_temporary_download, ensure_download_public_base_url

logger = logging.getLogger(__name__)


TOOL_SCHEMA = {
    "name": "image_crop_upscale",
    "description": (
        "Discord上の画像（添付/直近の画像）を指定アスペクトで中央クロップし、指定解像度へアップスケールして返します。"
        "10MB以内はDiscord添付、超過時は30分限定DLページを発行します。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image_url": {"type": "string", "description": "処理対象画像URL（省略可。省略時は直近の画像を自動検出）。"},
            "target": {
                "type": "string",
                "enum": ["1080p", "2k", "4k", "8k", "original"],
                "description": "出力解像度プリセット。既定4k。",
            },
            "width": {"type": "integer", "description": "出力幅（targetより優先）。"},
            "height": {"type": "integer", "description": "出力高（targetより優先）。"},
            "aspect": {
                "type": "string",
                "description": "クロップ比率。例: 16:9, 9:16, 1:1, original。既定16:9。",
            },
            "mode": {
                "type": "string",
                "enum": ["center_crop", "contain"],
                "description": "center_crop=中央を切り抜き / contain=余白を付けて収める。既定center_crop。",
            },
            "format": {
                "type": "string",
                "enum": ["png", "jpg"],
                "description": "出力形式。既定png（ただし10MB超過時はjpgに自動フォールバック）。",
            },
            "jpg_quality": {"type": "integer", "description": "JPG品質(40-95)。既定88。"},
            "history_limit": {"type": "integer", "description": "直近検索件数。既定25。"},
        },
        "required": [],
    },
    "tags": ["image", "edit", "crop", "upscale", "4k"],
}


def _parse_aspect(aspect: str) -> Optional[float]:
    if not aspect:
        return None
    a = aspect.strip().lower()
    if a in {"orig", "original", "keep"}:
        return None
    if ":" in a:
        try:
            w, h = a.split(":", 1)
            wf = float(w.strip())
            hf = float(h.strip())
            if wf > 0 and hf > 0:
                return wf / hf
        except Exception:
            return None
    try:
        v = float(a)
        if v > 0:
            return v
    except Exception:
        return None
    return None


def _target_wh(target: str) -> Optional[Tuple[int, int]]:
    t = (target or "").strip().lower()
    if t in {"orig", "original"}:
        return None
    if t == "1080p":
        return 1920, 1080
    if t == "2k":
        return 2560, 1440
    if t == "4k":
        return 3840, 2160
    if t == "8k":
        return 7680, 4320
    return 3840, 2160


def _is_image_attachment(att: discord.Attachment) -> bool:
    try:
        if getattr(att, "content_type", None) and str(att.content_type).startswith("image/"):
            return True
    except Exception:
        pass
    name = (getattr(att, "filename", "") or "").lower()
    return any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"))


async def _find_image_url(message: discord.Message, history_limit: int) -> Optional[str]:
    # 1) explicit reply target
    try:
        if message.reference and message.reference.message_id:
            ref = await message.channel.fetch_message(message.reference.message_id)
            for att in getattr(ref, "attachments", []) or []:
                if _is_image_attachment(att):
                    return att.url
            for emb in getattr(ref, "embeds", []) or []:
                if getattr(emb, "image", None) and getattr(emb.image, "url", None):
                    return emb.image.url
                if getattr(emb, "thumbnail", None) and getattr(emb.thumbnail, "url", None):
                    return emb.thumbnail.url
    except Exception:
        pass

    # 2) current message attachments
    try:
        for att in getattr(message, "attachments", []) or []:
            if _is_image_attachment(att):
                return att.url
    except Exception:
        pass

    # 3) recent channel history (prefer the most recent image)
    try:
        lim = max(5, min(int(history_limit or 25), 80))
        async for m in message.channel.history(limit=lim):
            for att in getattr(m, "attachments", []) or []:
                if _is_image_attachment(att):
                    return att.url
            for emb in getattr(m, "embeds", []) or []:
                if getattr(emb, "image", None) and getattr(emb.image, "url", None):
                    return emb.image.url
                if getattr(emb, "thumbnail", None) and getattr(emb.thumbnail, "url", None):
                    return emb.thumbnail.url
    except Exception:
        pass

    return None


async def _download_image(url: str, *, max_bytes: int = 25 * 1024 * 1024) -> bytes:
    if not url or not re.match(r"^https?://", url.strip(), re.I):
        raise ValueError("invalid image_url")

    timeout = aiohttp.ClientTimeout(total=30, connect=8)
    headers = {
        "User-Agent": "Mozilla/5.0 (ORA; image_crop_upscale)",
        "Accept": "image/*,*/*;q=0.8",
    }

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                raise RuntimeError(f"download failed: {resp.status}")
            cl = resp.headers.get("Content-Length")
            if cl:
                try:
                    if int(cl) > max_bytes:
                        raise RuntimeError("image too large")
                except Exception:
                    pass
            data = await resp.read()
            if len(data) > max_bytes:
                raise RuntimeError("image too large")
            return data


def _center_crop(im: Image.Image, aspect: float) -> Image.Image:
    w, h = im.size
    if w <= 0 or h <= 0:
        return im
    cur = w / h
    if abs(cur - aspect) < 1e-6:
        return im

    if cur > aspect:
        # too wide -> crop width
        new_w = int(round(h * aspect))
        x0 = max(0, (w - new_w) // 2)
        return im.crop((x0, 0, x0 + new_w, h))
    # too tall -> crop height
    new_h = int(round(w / aspect))
    y0 = max(0, (h - new_h) // 2)
    return im.crop((0, y0, w, y0 + new_h))


def _contain(im: Image.Image, aspect: float, *, bg=(0, 0, 0)) -> Image.Image:
    w, h = im.size
    if w <= 0 or h <= 0:
        return im
    cur = w / h
    if abs(cur - aspect) < 1e-6:
        return im

    if cur > aspect:
        # too wide -> add vertical padding
        new_h = int(round(w / aspect))
        canvas = Image.new("RGB", (w, new_h), color=bg)
        y0 = (new_h - h) // 2
        canvas.paste(im.convert("RGB"), (0, y0))
        return canvas
    # too tall -> add horizontal padding
    new_w = int(round(h * aspect))
    canvas = Image.new("RGB", (new_w, h), color=bg)
    x0 = (new_w - w) // 2
    canvas.paste(im.convert("RGB"), (x0, 0))
    return canvas


def _save_image_bytes(im: Image.Image, fmt: str, jpg_quality: int) -> bytes:
    buf = io.BytesIO()
    if fmt == "jpg":
        q = int(jpg_quality or 88)
        q = max(40, min(q, 95))
        im.convert("RGB").save(buf, format="JPEG", quality=q, optimize=True, progressive=True)
    else:
        # png
        im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def execute(args: dict, message: discord.Message, bot: Any = None) -> Any:
    history_limit = int(args.get("history_limit") or 25)
    image_url = (args.get("image_url") or "").strip()
    if not image_url:
        image_url = await _find_image_url(message, history_limit=history_limit) or ""
    if not image_url:
        return "❌ 対象画像が見つかりませんでした。画像を添付するか、その画像に返信して実行してください。"

    aspect_s = (args.get("aspect") or "16:9").strip()
    aspect = _parse_aspect(aspect_s)  # None => keep original
    mode = (args.get("mode") or "center_crop").strip().lower()
    if mode not in {"center_crop", "contain"}:
        mode = "center_crop"

    width = args.get("width")
    height = args.get("height")
    try:
        width = int(width) if width is not None else None
    except Exception:
        width = None
    try:
        height = int(height) if height is not None else None
    except Exception:
        height = None

    if width and height and width > 0 and height > 0:
        target_w, target_h = width, height
    else:
        preset = _target_wh(args.get("target") or "4k")
        if preset:
            target_w, target_h = preset
        else:
            target_w, target_h = 0, 0  # keep original

    out_fmt = (args.get("format") or "png").strip().lower()
    if out_fmt not in {"png", "jpg"}:
        out_fmt = "png"
    jpg_quality = int(args.get("jpg_quality") or 88)

    # Download + process
    try:
        raw = await _download_image(image_url)
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception as e:
        return f"❌ 画像の取得/読み込みに失敗しました: {e}"

    src_w, src_h = im.size

    if aspect is not None:
        if mode == "contain":
            im2 = _contain(im, aspect)
        else:
            im2 = _center_crop(im, aspect)
    else:
        im2 = im

    if target_w and target_h:
        im2 = im2.resize((int(target_w), int(target_h)), resample=Image.LANCZOS)

    # Save to bytes (auto fallback if too big)
    data = _save_image_bytes(im2, out_fmt, jpg_quality)

    ten_mb = 10 * 1024 * 1024
    guild_limit = message.guild.filesize_limit if getattr(message, "guild", None) else ten_mb
    limit_bytes = min(int(guild_limit or ten_mb), ten_mb)
    safe_upload_limit = max(1, int(limit_bytes * 0.95))

    if len(data) > safe_upload_limit and out_fmt == "png":
        # fallback to jpg if png is too big
        for q in (90, 85, 80, 75, 70):
            data = _save_image_bytes(im2, "jpg", q)
            out_fmt = "jpg"
            jpg_quality = q
            if len(data) <= safe_upload_limit:
                break

    # Output paths
    cfg = getattr(bot, "config", None) if bot else None
    base_temp = getattr(cfg, "temp_dir", None) or os.path.join(os.getcwd(), "data", "temp")
    os.makedirs(base_temp, exist_ok=True)

    ext = "png" if out_fmt == "png" else "jpg"
    out_name = f"crop_{uuid.uuid4().hex[:8]}_{target_w or src_w}x{target_h or src_h}.{ext}"

    with tempfile.TemporaryDirectory(prefix="img_crop_", dir=base_temp) as tdir:
        out_path = os.path.join(tdir, out_name)
        with open(out_path, "wb") as f:
            f.write(data)

        size_bytes = os.path.getsize(out_path)

        if size_bytes <= safe_upload_limit:
            msg = (
                "🖼️ **Image processed**\n"
                f"**From** {src_w}x{src_h}\n"
                f"**To** {(target_w or src_w)}x{(target_h or src_h)}\n"
                f"**Aspect** {aspect_s if aspect is not None else 'original'} ({mode})\n"
                f"**Size** {(size_bytes / (1024*1024)):.2f}MB\n"
                f"**Format** {out_fmt}"
            )
            await message.reply(content=msg, file=discord.File(out_path, filename=out_name))
            return {
                "silent": True,
                "result": f"画像を加工して送信しました（{(target_w or src_w)}x{(target_h or src_h)} / {out_fmt}）。",
                "image_meta": {
                    "source_url": image_url,
                    "src": f"{src_w}x{src_h}",
                    "dst": f"{(target_w or src_w)}x{(target_h or src_h)}",
                    "aspect": aspect_s if aspect is not None else "original",
                    "mode": mode,
                    "format": out_fmt,
                    "size_bytes": size_bytes,
                },
            }

        # Too large -> temp download page (30 min)
        manifest = create_temporary_download(
            out_path,
            download_name=out_name,
            source_url=image_url,
            metadata={
                "src": f"{src_w}x{src_h}",
                "dst": f"{(target_w or src_w)}x{(target_h or src_h)}",
                "aspect": aspect_s if aspect is not None else "original",
                "mode": mode,
                "format": out_fmt,
            },
            ttl_seconds=1800,
        )
        base_url = await ensure_download_public_base_url(bot)
        dl_page_url = f"{base_url}/download/{manifest['token']}" if base_url else ""

        msg = (
            "🖼️ **Image processed** (too large for Discord)\n"
            f"**From** {src_w}x{src_h}\n"
            f"**To** {(target_w or src_w)}x{(target_h or src_h)}\n"
            f"**Size** {(size_bytes / (1024*1024)):.2f}MB\n"
            f"🔗 **30分限定DLページ** {dl_page_url if dl_page_url else '(URL生成失敗)'}"
        )
        await message.reply(content=msg)
        return {
            "silent": True,
            "result": "Discord上限超過のため30分限定DLリンクを発行しました。",
            "image_meta": {
                "download_page_url": dl_page_url,
                "token": manifest.get("token"),
                "size_bytes": size_bytes,
            },
        }

