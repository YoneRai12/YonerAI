import asyncio
import os
import io
import uuid
import logging
import discord
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy imports are key here.
# We do NOT import browser_manager or config at top level if possible,
# or we accept they are imported when this module is imported (which is only strictly when needed).
# However, for type hinting/cleanliness, top level imports are fine IF this file is only imported lazily.
# Since registry.py only references strings, this file won't be imported until execution.

from src.utils.browser import browser_manager
from src.utils.temp_downloads import create_temporary_download, ensure_download_public_base_url


def _fmt_size_mb(size_bytes: Optional[int]) -> str:
    if not size_bytes:
        return "unknown"
    return f"{(int(size_bytes) / (1024 * 1024)):.1f}MB"


def _fmt_duration_sec(seconds: Optional[float]) -> str:
    if seconds is None:
        return "unknown"
    try:
        return f"{int(round(float(seconds)))}s"
    except Exception:
        return "unknown"

def _guess_image_ext(image_bytes: bytes) -> str:
    try:
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if image_bytes.startswith(b"\xff\xd8"):
            return "jpg"
    except Exception:
        pass
    return "png"


def _build_download_message_lines(
    *,
    label: str,
    title: str,
    duration_sec: Optional[float],
    width: Optional[int],
    height: Optional[int],
    size_bytes: Optional[int],
    format_id: Optional[str],
    estimated_size_bytes: Optional[int],
    source_url: str,
    filename: str,
    link_url: Optional[str] = None,
    next_start: Optional[int] = None,
) -> list[str]:
    resolution = f"{width}x{height}" if width and height else "-"
    lines = [
        f"💾 **{label} saved**",
        f"**Title** {title}",
        f"**Duration** {_fmt_duration_sec(duration_sec)}",
        f"**Resolution** {resolution}",
        f"**Size** {_fmt_size_mb(size_bytes)}",
        f"**Format** {format_id or '-'}",
        f"**Est. size** {_fmt_size_mb(estimated_size_bytes or size_bytes)}",
        f"**File** `{filename}`",
    ]
    if source_url:
        lines.append(f"**Source** <{source_url}>")
    if link_url:
        lines.append(f"🔗 **30分限定DLページ** {link_url}")
    if next_start:
        lines.append(f"✂️ **Next chunk start** `{next_start}`")
    return lines

async def navigate(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """Navigate to a URL."""
    url = args.get("url")
    if not url:
        return "❌ Missing URL."

    if status_manager: await status_manager.next_step(f"Navigating to {url}...")

    # We rely on browser_manager singleton, but it's good to ensure permission logic was done by ToolHandler or here.
    # ToolHandler was managing permission via '_check_permission'.
    # The registry doesn't enforce permission. We must check strict permission here if needed.
    # But usually Router/Registry defines "ADMIN ONLY" implicitly? No, Router just routes.
    # We should re-implement checks if we want strict security, or rely on ToolHandler gating before calling?
    # ToolHandler implementation of lazy load replaced the specific "elif tool_name == 'web_navigate'".
    # Current Lazyl Load does NOT check permission unless we add it inside the function.

    # CRITICAL: We need permission check.
    if bot:
        # Check permission
        user_id = message.author.id
        # Simple Admin Check
        if user_id != bot.config.admin_user_id:
            # Check Owner ID
            return "⛔ Access Denied: Admin Only."

    try:
        await browser_manager.navigate(url)
        return f"Navigated to {url}. [SILENT_COMPLETION]"
    except Exception as e:
        return f"❌ Navigation failed: {e}"

async def screenshot(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """Take a screenshot."""
    if status_manager:
        await status_manager.next_step("Processing screenshot request...")

    try:
        # Ensure active
        await browser_manager.ensure_active()

        # Optional Navigation
        target_url = args.get("url")
        if target_url:
             target_url = target_url.strip().strip('"').strip("'").strip("<").strip(">")

        # View Settings
        dark_mode = args.get("dark_mode")
        width = args.get("width")
        height = args.get("height")
        scale = args.get("scale")
        delay = int(args.get("delay", 2))
        full_page = bool(args.get("full_page", False))

        # Resolution Mapping
        resolution = args.get("resolution")
        orientation = args.get("orientation", "landscape")

        RES_MAP = {
            "SD": (640, 480), "HD": (1280, 720), "FHD": (1920, 1080),
            "2K": (2560, 1440), "4K": (3840, 2160), "8K": (7680, 4320)
        }

        if resolution and resolution in RES_MAP:
            base_w, base_h = RES_MAP[resolution]
            if orientation == "portrait" and base_w > base_h:
                width = base_h
                height = base_w
            else:
                width = base_w
                height = base_h

        if args.get("mobile"):
            width = 375
            height = 812
            scale = 1.0

        if any([width, height, dark_mode is not None, scale]):
            await browser_manager.set_view(width=width, height=height, dark_mode=dark_mode, scale=scale)

        if target_url:
            if status_manager: await status_manager.next_step(f"Navigating to {target_url}...")
            await browser_manager.navigate(target_url)

        if delay > 0:
            await asyncio.sleep(delay)

        if status_manager: await status_manager.update_current("Capturing screenshot...")

        # PNG-first keeps diagrams crisp. Down-convert later only if needed for size.
        image_bytes = await browser_manager.get_screenshot(full_page=full_page, prefer_png=True)
        if not image_bytes:
            return "❌ No screenshot data returned."

        # Save Logic
        final_dir = bot.config.temp_dir if bot else os.getcwd()
        # Prefer L drive temp if available (User Pref)
        if os.path.exists("L:\\"):
            try:
                os.makedirs(r"L:\ORA_Temp", exist_ok=True)
                final_dir = r"L:\ORA_Temp"
            except: pass

        ext = _guess_image_ext(image_bytes)
        filename = f"screenshot_{uuid.uuid4().hex[:8]}.{ext}"
        file_path = os.path.join(final_dir, filename)

        with open(file_path, "wb") as f:
            f.write(image_bytes)

        # Compression / Fallback to temporary download page
        limit_bytes = 10 * 1024 * 1024
        if message.guild:
            limit_bytes = int(getattr(message.guild, "filesize_limit", limit_bytes) or limit_bytes)
        safe_limit = max(1, int(limit_bytes * 0.95))

        def _size(p: str) -> int:
            try:
                return int(os.path.getsize(p))
            except Exception:
                return 0

        chosen_path = file_path
        chosen_name = filename
        chosen_size = _size(chosen_path)

        # If too large, down-convert to JPEG (diagrams may lose sharpness, but will deliver reliably).
        if chosen_size > safe_limit:
            if status_manager:
                await status_manager.update_current(
                    f"Compressing image ({chosen_size/1024/1024:.1f}MB > {safe_limit/1024/1024:.1f}MB)..."
                )
            try:
                import subprocess

                jpg_path = os.path.splitext(file_path)[0] + "_comp.jpg"
                # q:v: 2(best) .. 31(worst). 4-6 is a good compromise.
                cmd = ["ffmpeg", "-y", "-i", file_path, "-q:v", "5", jpg_path]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                if os.path.exists(jpg_path) and _size(jpg_path) and _size(jpg_path) < chosen_size:
                    chosen_path = jpg_path
                    chosen_name = os.path.basename(jpg_path)
                    chosen_size = _size(chosen_path)
            except Exception:
                pass

        # Context
        challenge_detected = False
        challenge_label = ""
        try:
            obs = await browser_manager.agent.observe()
            title = obs.title
            current_url = obs.url
            blob = f"{title}\n{current_url}\n{getattr(obs, 'aria', '')}".lower()
            markers = [
                "i'm not a robot",
                "unusual traffic",
                "captcha",
                "verify you are human",
                "recaptcha",
            ]
            if any(m in blob for m in markers):
                challenge_detected = True
                challenge_label = "CAPTCHA/anti-bot challenge detected"
        except:
            title = "Web Page"
            current_url = target_url or "Current Page"

        # If still too big, host a 30-min temp download and post the link instead of failing.
        link_url = None
        if chosen_size > safe_limit:
            try:
                base = await ensure_download_public_base_url(bot)
                if base:
                    manifest = create_temporary_download(
                        chosen_path,
                        download_name=chosen_name,
                        source_url=current_url,
                        metadata={"kind": "web_screenshot", "title": title, "url": current_url},
                        ttl_seconds=1800,
                    )
                    token = manifest.get("token")
                    if token:
                        link_url = f"{base}/download/{token}"
                        # chosen_path is moved; do not cleanup it below.
                        chosen_path = ""
            except Exception:
                link_url = None

        # Build message
        f_obj = discord.File(chosen_path, filename=chosen_name) if chosen_path else None

        safe_title = (title or "Web Page").strip()
        if len(safe_title) > 250:
            safe_title = safe_title[:247] + "..."
        safe_url = (current_url or "").strip()
        if len(safe_url) > 2000:
            safe_url = safe_url[:2000]

        # Discord embed title hard limit is 256 chars. Use a short stable title and move
        # page metadata into description to avoid intermittent 400s on long/odd titles.
        page_title = safe_title
        if len(page_title) > 500:
            page_title = page_title[:497] + "..."

        desc_parts = []
        if page_title:
            desc_parts.append(f"**Title** {page_title}")
        if safe_url:
            desc_parts.append(f"**URL** <{safe_url}>")
        if challenge_detected:
            desc_parts.append(f"**Notice** {challenge_label}")
        if link_url:
            desc_parts.append(f"🔗 **30分限定DLページ** {link_url}")

        embed = discord.Embed(title="ORA Screenshot", description="\n".join(desc_parts)[:3900], color=0x00FF00)
        if f_obj:
            embed.set_image(url=f"attachment://{chosen_name}")
        embed.set_footer(text=f"ORA Browser • {width or 'Default'}x{height or 'Default'}")

        try:
            if f_obj:
                await message.reply(embed=embed, file=f_obj)
            else:
                await message.reply(embed=embed)
        finally:
            # Cleanup: always try to delete local artifact after use.
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
            try:
                if chosen_path and os.path.exists(chosen_path):
                    os.remove(chosen_path)
            except Exception:
                pass

        # [AGENTIC] Return dict with string result AND base64 for AI logic
        import base64
        b64_img = base64.b64encode(image_bytes).decode("utf-8")

        result_text = "Screenshot sent successfully to Discord."
        if challenge_detected:
            result_text += f" {challenge_label}."
        if link_url:
            result_text += " (Large file: posted temporary download link.)"

        return {
            "result": result_text,
            "image_b64": b64_img,
            "challenge_detected": challenge_detected,
            "challenge_label": challenge_label,
        }

    except Exception as e:
        # Best-effort cleanup for partially created files
        try:
            if "file_path" in locals() and file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        return f"❌ Screenshot failed: {e}"

async def download(args: dict, message: discord.Message, status_manager, bot=None):
    """Download video/audio."""
    from src.utils.youtube import download_video_smart, download_youtube_audio
    from src.config import Config

    url = args.get("url")
    if not url:
        if browser_manager.is_ready():
             try:
                 obs = await browser_manager.agent.observe()
                 url = obs.url
             except: pass

    if not url:
         return "❌ No URL specified and no active browser session."

    download_fmt = args.get("format", "video")
    start_time = int(args.get("start_time", 0))
    split_strategy = args.get("split_strategy", "auto")

    if status_manager: await status_manager.next_step(f"Downloading {download_fmt}...")

    cfg = Config.load()
    proxy = cfg.browser_proxy

    try:
        width = None
        height = None
        format_id = None
        estimated_size_bytes = None
        source_url = url
        duration_sec = None

        if download_fmt == "audio":
            final_path, title, duration = await download_youtube_audio(url, proxy=proxy)
            next_start = None
            duration_sec = duration
            format_id = "mp3"
        else:
            limit_bytes = message.guild.filesize_limit if message.guild else 10*1024*1024
            safe_limit_mb = (limit_bytes / (1024*1024)) - 0.5
            if safe_limit_mb < 5: safe_limit_mb = 5

            # Backward/forward compatibility: older deployments may not yet support split_strategy.
            try:
                result = await download_video_smart(
                    url,
                    start_time=start_time,
                    max_size_mb=safe_limit_mb,
                    proxy=proxy,
                    split_strategy=split_strategy,
                )
            except TypeError as e:
                if "split_strategy" not in str(e):
                    raise
                result = await download_video_smart(
                    url,
                    start_time=start_time,
                    max_size_mb=safe_limit_mb,
                    proxy=proxy,
                )
            final_path = result["path"]
            title = result["title"]
            next_start = result.get("next_start_time")
            width = result.get("width")
            height = result.get("height")
            format_id = result.get("format_id")
            estimated_size_bytes = result.get("estimated_size_bytes")
            source_url = result.get("source_url") or url
            duration_sec = result.get("duration_seconds") or result.get("original_duration")

        if not final_path or not os.path.exists(final_path):
             return "❌ Download failed."

        size_bytes = os.path.getsize(final_path)
        filename = os.path.basename(final_path)
        limit_bytes = message.guild.filesize_limit if message.guild else 10 * 1024 * 1024
        safe_upload_limit = max(1, int(limit_bytes * 0.95))
        label = "Audio" if download_fmt == "audio" else "Video"

        if size_bytes <= safe_upload_limit:
            content_lines = _build_download_message_lines(
                label=label,
                title=title,
                duration_sec=duration_sec,
                width=width,
                height=height,
                size_bytes=size_bytes,
                format_id=format_id,
                estimated_size_bytes=estimated_size_bytes,
                source_url=source_url,
                filename=filename,
                next_start=next_start,
            )
            await message.reply(content="\n".join(content_lines), file=discord.File(final_path, filename=filename))
            try:
                os.remove(final_path)
            except Exception:
                pass

            assistant_summary = (
                f"保存完了。{title} / {_fmt_duration_sec(duration_sec)} / "
                f"{(str(width) + 'x' + str(height)) if (width and height) else '-'} / {_fmt_size_mb(size_bytes)}"
            )
            return {
                "silent": True,
                "result": assistant_summary,
                "download_meta": {
                    "title": title,
                    "duration_sec": duration_sec,
                    "resolution": f"{width}x{height}" if width and height else "-",
                    "size_mb": _fmt_size_mb(size_bytes),
                    "format": format_id or "-",
                    "source_url": source_url,
                    "assistant_summary": assistant_summary,
                    "next_start": next_start,
                },
            }

        # Too large for Discord -> create temporary download page.
        manifest = create_temporary_download(
            final_path,
            download_name=filename,
            source_url=source_url,
            metadata={
                "title": title,
                "duration_sec": duration_sec,
                "width": width,
                "height": height,
                "format_id": format_id,
                "estimated_size_bytes": estimated_size_bytes,
            },
            ttl_seconds=1800,
        )

        base_url = await ensure_download_public_base_url(bot)
        dl_page_url = f"{base_url}/download/{manifest['token']}" if base_url else None

        content_lines = _build_download_message_lines(
            label=label,
            title=title,
            duration_sec=duration_sec,
            width=width,
            height=height,
            size_bytes=size_bytes,
            format_id=format_id,
            estimated_size_bytes=estimated_size_bytes,
            source_url=source_url,
            filename=manifest.get("download_name", filename),
            link_url=dl_page_url,
            next_start=next_start,
        )
        if not dl_page_url:
            content_lines.append("⚠️ DL公開URLを生成できませんでした。`cloudflared` の実行可否と `logs/cf_download.log` を確認してください。")

        await message.reply(content="\n".join(content_lines))

        assistant_summary = (
            f"Discord上限超過のため30分限定DLリンクを発行。"
            f"{title} / {_fmt_duration_sec(duration_sec)} / {_fmt_size_mb(size_bytes)}"
        )

        return {
            "silent": True,
            "result": assistant_summary,
            "download_meta": {
                "title": title,
                "duration_sec": duration_sec,
                "resolution": f"{width}x{height}" if width and height else "-",
                "size_mb": _fmt_size_mb(size_bytes),
                "format": format_id or "-",
                "source_url": source_url,
                "download_page_url": dl_page_url or "",
                "assistant_summary": assistant_summary,
                "next_start": next_start,
            },
        }

    except Exception as e:
        return f"❌ Download failed: {e}"

async def record_screen(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    # Check Admin
    if bot and message.author.id != bot.config.admin_user_id:
        return "⛔ Admin Only."

    duration = args.get("duration", 10)
    await browser_manager.ensure_active()

    if status_manager: await status_manager.next_step(f"Recording for {duration}s...")

    # Placeholder for actual record logic (Simulated or via browser_manager if implemented)
    # browser_manager doesn't have native record yet exposed in standard API, usually handled via playwright tracing or extension
    # For now, return mock or error if not implemented
    return "❌ Screen recording not fully implemented in this lightweight tool version yet."

async def jump_to_profile(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    # ... Implementation ...
    return "Not implemented yet."

async def set_view(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    # Check Admin
    if bot and message.author.id != bot.config.admin_user_id: return "⛔ Admin Only."

    width = args.get("width")
    height = args.get("height")
    await browser_manager.set_view(width=width, height=height)
    return f"View set to {width}x{height}. [SILENT_COMPLETION]"
