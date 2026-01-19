import asyncio
import logging
import os
import tempfile
from typing import Optional, Tuple

import yt_dlp

logger = logging.getLogger(__name__)


def _get_youtube_audio_stream_url_sync(query: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
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


async def get_youtube_audio_stream_url(query: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Async wrapper for _get_youtube_audio_stream_url_sync"""
    return await asyncio.to_thread(_get_youtube_audio_stream_url_sync, query)


def _download_youtube_audio_sync(query: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """
    Download audio from a YouTube video or search query to a temporary file (Synchronous).
    Returns: (file_path, title, duration_seconds)
    """
    # Create a temporary file to store the download
    fd, temp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    # We need to remove it because yt-dlp expects to create the file (or we configure it to overwrite)
    os.remove(temp_path)

    temp_dir = tempfile.gettempdir()

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
        logger.error(f"Error downloading YouTube audio: {e}")
        return None, None, None


async def download_youtube_audio(query: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Async wrapper for _download_youtube_audio_sync"""
    return await asyncio.to_thread(_download_youtube_audio_sync, query)
