import asyncio
import logging
import os
import tempfile
import uuid
import glob
from typing import Optional, Tuple, Dict, Any

import yt_dlp

logger = logging.getLogger(__name__)


def _get_ora_temp_dir() -> str:
    """
    ORA uses a configurable temp directory (often on a large drive like L:\\).
    Avoid writing downloads into the repo root on C:\\, which can silently fill the OS disk.
    """
    try:
        from src.config import TEMP_DIR  # Config constant (respects ORA_TEMP_DIR/ORA_DATA_ROOT)
        base = TEMP_DIR
    except Exception:
        base = os.path.join(os.getcwd(), "data", "temp")

    # Keep yt-dlp artifacts in a dedicated subfolder for easier cleanup.
    d = os.path.join(base, "yt_dlp")
    os.makedirs(d, exist_ok=True)
    return d


def _cleanup_prefix(temp_dir: str, prefix: str, keep: Optional[str] = None) -> None:
    """Best-effort cleanup of temp files created by yt-dlp/ffmpeg for a given filename prefix."""
    try:
        for p in glob.glob(os.path.join(temp_dir, f"{prefix}*")):
            if keep and os.path.abspath(p) == os.path.abspath(keep):
                continue
            try:
                os.remove(p)
            except Exception:
                pass
    except Exception:
        pass


def _get_youtube_audio_stream_url_sync(query: str, proxy: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """
    Get the audio stream URL for a YouTube video or search query (Synchronous).
    Returns: (stream_url, title, duration_seconds)
    """
    # Explicitly handle search queries
    if not query.startswith("http"):
        # If it looks like a search, force ytsearch prefix to be safe
        if not query.startswith("ytsearch"):
            # ytsearch5: gets 5 results, we pick first.
            # but ytsearch1: is faster if we only need one.
            query = f"ytsearch1:{query}"

    logger.info(f"Resolving YouTube URL for: {query}")

    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "default_search": "ytsearch",
        "extract_flat": False,  # We need stream URL, so full extraction needed?
        # extract_flat: 'in_playlist' is better for search to get ID, then extract again?
        # For simplicity, extract full info.
        "extractor_args": {"youtube": {"player_client": ["default"]}},
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "logtostderr": False,
        "no_warnings": True,
    }

    if proxy:
        ydl_opts["proxy"] = proxy

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)

            if not info:
                logger.warning(f"yt-dlp returned no info for {query}")
                return None, None, None

            if "entries" in info:
                # It's a search result or playlist, take the first item
                if not info["entries"]:
                    logger.warning(f"yt-dlp returned empty entries for {query}")
                    return None, None, None
                info = info["entries"][0]

            # Additional check for 'url'
            if not info.get("url"):
                logger.warning(f"yt-dlp info has no URL: {info.keys()}")
                return None, info.get("title"), info.get("duration")

            return info.get("url"), info.get("title"), info.get("duration")
    except Exception as e:
        logger.error(f"Error getting YouTube stream URL: {e}")
        return None, None, None


async def get_youtube_audio_stream_url(query: str, proxy: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Async wrapper for _get_youtube_audio_stream_url_sync"""
    return await asyncio.to_thread(_get_youtube_audio_stream_url_sync, query, proxy)


def _download_youtube_audio_sync(query: str, proxy: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """
    Download audio from a YouTube video or search query to a temporary file (Synchronous).
    Returns: (file_path, title, duration_seconds)
    """
    # Create a temporary file to store the download
    temp_dir = _get_ora_temp_dir()

    fd, temp_path = tempfile.mkstemp(suffix=".mp3", dir=temp_dir)
    os.close(fd)
    # We need to remove it because yt-dlp expects to create the file
    os.remove(temp_path)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "default_search": "ytsearch",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    if proxy:
        ydl_opts["proxy"] = proxy

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)

            if "entries" in info:
                if not info["entries"]:
                    return None, None, None
                info = info["entries"][0]

            video_id = info["id"]
            expected_path = os.path.join(temp_dir, f"{video_id}.mp3")

            if os.path.exists(expected_path):
                return expected_path, info.get("title"), info.get("duration")

            return None, info.get("title"), info.get("duration")

    except Exception as e:
        # Clean up any partial artifacts for this download, if we can infer an ID.
        try:
            if "info" in locals() and isinstance(info, dict) and info.get("id"):
                _cleanup_prefix(temp_dir, str(info.get("id")))
        except Exception:
            pass
        logger.error(f"Error downloading YouTube audio: {e}")
        return None, None, None


async def download_youtube_audio(query: str, proxy: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Async wrapper for _download_youtube_audio_sync"""
    return await asyncio.to_thread(_download_youtube_audio_sync, query, proxy)


# -----------------------------------------------------------
# YouTube Search (multiple candidates) for Discord-native picker
# -----------------------------------------------------------
def _search_youtube_sync(query: str, limit: int = 10, proxy: Optional[str] = None) -> list[Dict[str, Any]]:
    """
    Search YouTube and return a list of lightweight entries:
      { "title": str, "webpage_url": str, "id": str, "duration": Optional[int] }

    Uses extract_flat=True for speed; resolve stream URL later for the chosen entry.
    """
    q = (query or "").strip()
    if not q:
        return []

    try:
        lim = int(limit)
    except Exception:
        lim = 10
    lim = max(1, min(25, lim))

    if not q.startswith("http") and not q.startswith("ytsearch"):
        q = f"ytsearch{lim}:{q}"

    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "default_search": "ytsearch",
        "noplaylist": True,
        "extract_flat": True,  # lightweight (titles/ids)
        "skip_download": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "logtostderr": False,
        "no_warnings": True,
    }
    if proxy:
        ydl_opts["proxy"] = proxy

    out: list[Dict[str, Any]] = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(q, download=False)
    except Exception as e:
        logger.warning("YouTube search failed: %s", e)
        return []

    if not info:
        return []

    entries = info.get("entries") if isinstance(info, dict) else None
    if not entries:
        # Sometimes extract_info returns a single item dict.
        if isinstance(info, dict) and info.get("id"):
            vid = str(info.get("id"))
            out.append(
                {
                    "id": vid,
                    "title": str(info.get("title") or "(no title)"),
                    "duration": info.get("duration"),
                    "webpage_url": str(info.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}"),
                }
            )
        return out

    for e in entries[:lim]:
        if not isinstance(e, dict):
            continue
        vid = e.get("id") or e.get("url")
        if not vid:
            continue
        vid = str(vid)
        title = str(e.get("title") or "(no title)")
        webpage_url = e.get("webpage_url") or (f"https://www.youtube.com/watch?v={vid}" if len(vid) >= 6 else "")
        if not webpage_url:
            continue
        out.append({"id": vid, "title": title, "duration": e.get("duration"), "webpage_url": str(webpage_url)})

    return out


async def search_youtube(query: str, limit: int = 10, proxy: Optional[str] = None) -> list[Dict[str, Any]]:
    """Async wrapper for _search_youtube_sync."""
    return await asyncio.to_thread(_search_youtube_sync, query, limit, proxy)


# -----------------------------------------------------------
# Smart Video Downloader (Split / Compress)
# -----------------------------------------------------------
def _download_video_smart_sync(
    url: str,
    start_time: int = 0,
    force_compress: bool = False,
    max_size_mb: int = 50,
    temp_dir: str = None,
    proxy: str = None,
    split_strategy: str = "auto",
) -> Dict[str, Any]:
    """
    Downloads video with smart splitting/compression logic.
    Returns:
    {
        "path": str,         # Path to the processed file
        "title": str,        # Video Title
        "next_start_time": int or None, # Start time for next chunk, or None if finished
        "is_last": bool,     # True if this is the final chunk
        "original_duration": float # Total duration
    }
    """
    if not temp_dir:
        temp_dir = _get_ora_temp_dir()

    filename_base = f"vid_{uuid.uuid4().hex[:8]}"
    _cleanup_prefix(temp_dir, filename_base)  # just in case of collision

    # 1. Fetch Info first
    ydl_opts_info = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "noplaylist": True
    }
    if proxy: ydl_opts_info["proxy"] = proxy

    try:
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        err = str(e).lower()
        if proxy and ("403" in err or "forbidden" in err):
            logger.warning("Video info fetch failed via proxy (403). Retrying without proxy...")
            ydl_opts_info.pop("proxy", None)
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
        else:
            raise Exception(f"Failed to fetch video info: {e}")

    title = info.get("title", "Unknown Video")
    duration = info.get("duration", 0)
    source_url = info.get("webpage_url") or info.get("original_url") or url

    if start_time >= duration:
         raise Exception("Start time exceeds video duration.")

    # Estimate splitting strategy
    # If we are continuing (start_time > 0), we want to try and grab a chunk.
    # We can't know exact size before download, but we can try to download 'best' dependent on what we expect.

    # Strategy: Download full high quality if possible (or split range), then post-process.
    # Problem: Downloading 10GB file just to split is bad.
    # yt-dlp has 'download_sections'.

    # Let's try to download from start_time to potential end.
    # If start_time == 0 and duration is short (< 5 min?), try full download.
    # If duration is long, maybe limit to 5-10 minutes chunks?

    chunk_duration_limit = 600 # 10 minutes limit per chunk attempt to avoid massive downloads?
    # Actually, user said: "Send exactly 50MB of high quality".
    # We can use ffmpeg -fs (file size limit) BUT that requires re-encoding on the fly or download piping.
    # Piping yt-dlp stdout -> ffmpeg -fs 50M -> file ??
    # This is capable but complex.

    # SIMPLER APPROACH:
    # 1. Download best format (up to ~300MB buffer?)
    # 2. Check size.
    # 3. If > 50MB:
    #    a. If close (e.g. < 70MB) AND not force_compress -> Compress (CRF).
    #    b. Else -> Cut at 50MB mark (keeping quality) -> Return new end time.

    # yt-dlp args
    small_target = max_size_mb <= 25
    selected_format = (
        "best[ext=mp4][height<=720]/best[height<=720]/best[ext=mp4]/best"
        if small_target
        else "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    )
    ydl_opts = {
        "outtmpl": os.path.join(temp_dir, f"{filename_base}.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "format": selected_format,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 1,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    if proxy: ydl_opts["proxy"] = proxy

    # Partial download if start_time is set or file is huge
    end_time_arg = ""
    # We might want to cap the download attempt to avoid downloading 1 hour of 4k.
    # Let's say we target 2 minutes if we are splitting?
    # Or just download 'best' and rely on post-process if it's not insanely huge.

    if start_time > 0:
        # Use download sections
        # Format: *start-end
        ydl_opts["download_ranges"] = yt_dlp.utils.download_range_func(None, [(start_time, float('inf'))])

    # [Security] Proxy check not here, injected by caller or config?
    # The sync function doesn't know config easily. We assume caller might handle or we default.
    # We'll skip proxy here for simplicity, or add arg if needed.

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            downloaded_info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(downloaded_info)
    except Exception as e:
        err = str(e).lower()
        if proxy and ("403" in err or "forbidden" in err):
            logger.warning("Video download failed via proxy (403). Retrying without proxy...")
            ydl_opts.pop("proxy", None)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                downloaded_info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(downloaded_info)
        else:
            # Clean partials (e.g. .part) to avoid filling disks over time.
            _cleanup_prefix(temp_dir, filename_base)
            raise

    width = downloaded_info.get("width") or info.get("width")
    height = downloaded_info.get("height") or info.get("height")
    format_id = downloaded_info.get("format_id") or downloaded_info.get("format")
    duration_sec = downloaded_info.get("duration") or duration
    estimated_size_bytes = downloaded_info.get("filesize") or downloaded_info.get("filesize_approx")

    if not os.path.exists(filename):
        # Sometimes extension differs (mkv vs mp4)
        base = os.path.splitext(filename)[0]
        found = False
        for ext in [".mp4", ".mkv", ".webm"]:
             if os.path.exists(base + ext):
                 filename = base + ext
                 found = True
                 break
        if not found:
             raise Exception("Download failed, file not found.")

    # Check Size
    file_size_bytes = os.path.getsize(filename)
    file_size_mb = file_size_bytes / (1024 * 1024)
    target_mb = max_size_mb - 0.5 # Safety margin

    final_path = filename
    next_start = None
    is_last = True

    # Prepare FFMPEG
    import subprocess
    ffmpeg_bin = "ffmpeg"
    if os.path.exists("ffmpeg.exe"): ffmpeg_bin = "ffmpeg.exe"

    normalized_strategy = (split_strategy or "auto").strip().lower()
    if normalized_strategy not in {"auto", "compress", "split_all"}:
        normalized_strategy = "auto"

    force_split_all = (normalized_strategy == "split_all")
    if normalized_strategy == "compress":
        force_compress = True

    if file_size_mb > target_mb or force_split_all:

        # User Rule: "15MB (1.5x) -> Compress. 20MB (>1.5x) -> Split."
        # If force_split_all, split immediately regardless of size.

        is_slightly_over = file_size_mb <= (target_mb * 1.5) # e.g. <= 15MB for 10MB limit

        should_compress = (not force_split_all) and (force_compress or is_slightly_over)

        force_split_now = False # Just a flag

        if should_compress:
             # Compress Attempt
             logger.info(f"Compressing video ({file_size_mb:.1f}MB) to fit {target_mb}MB...")
             compressed_path = os.path.splitext(filename)[0] + "_comp.mp4"

             # Calculate required bitrate
             chunk_duration = 0
             try:
                 cmd = [ffmpeg_bin, "-i", filename]
                 proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                 import re
                 m = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", proc.stderr)
                 if m:
                     h_val, m_val, s_val = map(float, m.groups())
                     chunk_duration = h_val*3600 + m_val*60 + s_val
             except:
                 chunk_duration = duration # Fallback

             if chunk_duration > 0:
                 target_bitrate = int((target_mb * 8192) / chunk_duration)
                 target_bitrate = max(target_bitrate, 500) # Floor 500kbps

                 cmd_comp = [
                     ffmpeg_bin, "-y", "-i", filename,
                     "-c:v", "libx264", "-b:v", f"{target_bitrate}k",
                     "-maxrate", f"{int(target_bitrate*1.5)}k", "-bufsize", f"{target_bitrate*2}k",
                     "-c:a", "aac", "-b:a", "128k",
                     compressed_path
                 ]
                 subprocess.run(cmd_comp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                 if os.path.exists(compressed_path):
                      # Check if successful
                      if os.path.getsize(compressed_path) < (target_mb * 1024 * 1024 * 1.05):
                           final_path = compressed_path
                           # Compressed whole file -> no next
                           pass
                      else:
                           logger.warning("Compression failed to reduce enough. Fallback to split.")

                           force_split_now = True
                 else:
                      force_split_now = True
             else:
                 force_split_now = True
        else:
             # Too big (> 1.5x) or split_all requested
             force_split_now = True

        if force_split_now:
            # SPLIT LOGIC
            logger.info("Splitting video to fit target chunk...")

            split_path = os.path.splitext(filename)[0] + "_split.mp4"
            target_bytes = int(target_mb * 1024 * 1024)

            # Using re-encode to ensure size limit (-fs) is respected cleanly
            cmd_split = [
                ffmpeg_bin, "-y", "-i", filename,
                "-fs", str(target_bytes),
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "128k",
                split_path
            ]

            subprocess.run(cmd_split, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(split_path):
                final_path = split_path
                is_last = False

                # Determine where we stopped
                cmd_dur = [ffmpeg_bin, "-i", split_path]
                proc = subprocess.run(cmd_dur, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                import re
                m = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", proc.stderr)
                if m:
                     h_val, m_val, s_val = map(float, m.groups())
                     chunk_len = h_val*3600 + m_val*60 + s_val
                     next_start = start_time + int(chunk_len)
                     if chunk_len < 1:
                         # Safety: If split failed to produce meaningful chunk
                         logger.error("Split chunk too small. Aborting split loop.")
                         next_start = None
                         is_last = True
                else:
                     next_start = start_time + 10
            else:
                 raise Exception("Failed to split video.")

    # Aggressive Cleanup of Intermediate Files
    if final_path != filename and os.path.exists(filename):
        try:
            os.remove(filename)
        except Exception as e:
            logger.warning(f"Failed to remove intermediate file {filename}: {e}")

    final_size_bytes = os.path.getsize(final_path) if os.path.exists(final_path) else file_size_bytes
    final_ext = os.path.splitext(final_path)[1].lstrip(".") or downloaded_info.get("ext")

    # Remove stray partials for this prefix (best-effort) while keeping the final artifact.
    _cleanup_prefix(temp_dir, filename_base, keep=final_path)

    return {
        "path": final_path,
        "title": title,
        "next_start_time": next_start,
        "is_last": is_last,
        "original_duration": duration,
        "duration_seconds": duration_sec,
        "width": width,
        "height": height,
        "format_id": format_id,
        "ext": final_ext,
        "source_url": source_url,
        "estimated_size_bytes": estimated_size_bytes,
        "file_size_bytes": final_size_bytes,
        "file_size_mb": final_size_bytes / (1024 * 1024),
    }

async def download_video_smart(
    url: str,
    start_time: int = 0,
    force_compress: bool = False,
    max_size_mb: int = 50,
    proxy: str = None,
    split_strategy: str = "auto",
) -> Dict[str, Any]:
    """Async wrapper for smart download"""
    try:
        return await asyncio.to_thread(
            _download_video_smart_sync,
            url=url,
            start_time=start_time,
            force_compress=force_compress,
            max_size_mb=max_size_mb,
            temp_dir=None,
            proxy=proxy,
            split_strategy=split_strategy,
        )
    except Exception as e:
        err = str(e).lower()
        if proxy and ("403" in err or "forbidden" in err):
            logger.warning("Retrying video download without proxy due to 403/Forbidden...")
            return await asyncio.to_thread(
                _download_video_smart_sync,
                url=url,
                start_time=start_time,
                force_compress=force_compress,
                max_size_mb=max_size_mb,
                temp_dir=None,
                proxy=None,
                split_strategy=split_strategy,
            )
        raise
