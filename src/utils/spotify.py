from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp

import yt_dlp

logger = logging.getLogger(__name__)


def parse_spotify_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse Spotify URL and return (kind, id).

    Supported:
    - https://open.spotify.com/playlist/<id>
    - https://open.spotify.com/album/<id>
    - https://open.spotify.com/track/<id>
    - https://open.spotify.com/artist/<id> (metadata only; not used for queue)
    - spotify:playlist:<id> (URI)
    """
    u = (url or "").strip()
    if not u:
        return None, None

    # Spotify URI
    if u.startswith("spotify:"):
        try:
            parts = u.split(":")
            if len(parts) >= 3 and parts[0] == "spotify":
                kind = parts[1].strip().lower()
                sid = parts[2].strip()
                return (kind or None), (sid or None)
        except Exception:
            return None, None

    if not (u.startswith("http://") or u.startswith("https://")):
        return None, None

    try:
        p = urlparse(u)
        host = (p.hostname or "").lower()
        if host not in {"open.spotify.com", "play.spotify.com"}:
            return None, None
        parts = [x for x in (p.path or "").split("/") if x]
        if len(parts) < 2:
            return None, None
        kind = parts[0].strip().lower()
        sid = parts[1].strip()
        return (kind or None), (sid or None)
    except Exception:
        return None, None


def is_spotify_url(url: str) -> bool:
    kind, sid = parse_spotify_url(url)
    return bool(kind and sid)


def is_spotify_playlist_like(url: str) -> bool:
    """playlist/album are "multi-track" sources."""
    kind, _ = parse_spotify_url(url)
    return kind in {"playlist", "album"}


async def _spotify_get_access_token(session: aiohttp.ClientSession, client_id: str, client_secret: str) -> Optional[str]:
    token_url = "https://accounts.spotify.com/api/token"
    b64 = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    headers = {"Authorization": f"Basic {b64}"}
    data = {"grant_type": "client_credentials"}
    try:
        async with session.post(token_url, headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200:
                txt = await r.text()
                logger.warning("Spotify token request failed: status=%s body=%s", r.status, txt[:200])
                return None
            js = await r.json()
            return js.get("access_token")
    except Exception as e:
        logger.warning("Spotify token request error: %s", e)
        return None


def _track_query(title: str, artists: List[str]) -> str:
    t = (title or "").strip()
    a = " ".join([x.strip() for x in (artists or []) if x and x.strip()]).strip()
    if a and t:
        return f"{a} {t}"
    return t or a


async def get_spotify_tracks(
    url: str,
    *,
    limit: int = 60,
    session: Optional[aiohttp.ClientSession] = None,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Return (title, tracks) for Spotify playlist/album/track.

    Each track is:
      { "title": str, "artists": [str], "duration": Optional[int], "query": str }

    Playback note:
    - We do NOT stream from Spotify (DRM). We use these metadata to search on YouTube.
    """
    kind, sid = parse_spotify_url(url)
    if not kind or not sid:
        return None, []

    try:
        lim = int(limit)
    except Exception:
        lim = 60
    lim = max(1, min(200, lim))

    # Prefer Spotify Web API if credentials are present.
    client_id = (os.getenv("ORA_SPOTIFY_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("ORA_SPOTIFY_CLIENT_SECRET") or "").strip()

    if client_id and client_secret:
        close_session = False
        if session is None:
            session = aiohttp.ClientSession()
            close_session = True
        try:
            token = await _spotify_get_access_token(session, client_id, client_secret)
            if not token:
                raise RuntimeError("no_access_token")

            headers = {"Authorization": f"Bearer {token}"}
            tracks: List[Dict[str, Any]] = []
            title: Optional[str] = None

            if kind == "playlist":
                # Title
                async with session.get(
                    f"https://api.spotify.com/v1/playlists/{sid}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as r0:
                    if r0.status == 200:
                        js0 = await r0.json()
                        title = js0.get("name")

                next_url = f"https://api.spotify.com/v1/playlists/{sid}/tracks?limit=100&offset=0"
                while next_url and len(tracks) < lim:
                    async with session.get(
                        next_url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
                    ) as r:
                        if r.status != 200:
                            txt = await r.text()
                            logger.warning("Spotify playlist tracks failed: %s %s", r.status, txt[:200])
                            break
                        js = await r.json()
                        for it in js.get("items") or []:
                            tr = (it or {}).get("track") or {}
                            if not isinstance(tr, dict):
                                continue
                            name = str(tr.get("name") or "").strip()
                            artists = [str(a.get("name") or "").strip() for a in (tr.get("artists") or []) if isinstance(a, dict)]
                            dur_ms = tr.get("duration_ms")
                            dur = int(dur_ms // 1000) if isinstance(dur_ms, int) else None
                            q = _track_query(name, artists)
                            if not q:
                                continue
                            tracks.append({"title": name or q, "artists": artists, "duration": dur, "query": q})
                            if len(tracks) >= lim:
                                break
                        next_url = js.get("next")

            elif kind == "album":
                # Album title + artists
                async with session.get(
                    f"https://api.spotify.com/v1/albums/{sid}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as r0:
                    if r0.status == 200:
                        js0 = await r0.json()
                        title = js0.get("name")

                next_url = f"https://api.spotify.com/v1/albums/{sid}/tracks?limit=50&offset=0"
                while next_url and len(tracks) < lim:
                    async with session.get(
                        next_url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
                    ) as r:
                        if r.status != 200:
                            txt = await r.text()
                            logger.warning("Spotify album tracks failed: %s %s", r.status, txt[:200])
                            break
                        js = await r.json()
                        for tr in js.get("items") or []:
                            if not isinstance(tr, dict):
                                continue
                            name = str(tr.get("name") or "").strip()
                            artists = [str(a.get("name") or "").strip() for a in (tr.get("artists") or []) if isinstance(a, dict)]
                            dur_ms = tr.get("duration_ms")
                            dur = int(dur_ms // 1000) if isinstance(dur_ms, int) else None
                            q = _track_query(name, artists)
                            if not q:
                                continue
                            tracks.append({"title": name or q, "artists": artists, "duration": dur, "query": q})
                            if len(tracks) >= lim:
                                break
                        next_url = js.get("next")

            elif kind == "track":
                async with session.get(
                    f"https://api.spotify.com/v1/tracks/{sid}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as r:
                    if r.status != 200:
                        txt = await r.text()
                        logger.warning("Spotify track failed: %s %s", r.status, txt[:200])
                    else:
                        js = await r.json()
                        name = str(js.get("name") or "").strip()
                        artists = [str(a.get("name") or "").strip() for a in (js.get("artists") or []) if isinstance(a, dict)]
                        dur_ms = js.get("duration_ms")
                        dur = int(dur_ms // 1000) if isinstance(dur_ms, int) else None
                        q = _track_query(name, artists)
                        if q:
                            title = title or name
                            tracks.append({"title": name or q, "artists": artists, "duration": dur, "query": q})

            else:
                # Unsupported for queue-all, but keep it non-fatal.
                return None, []

            return (str(title) if title else None), tracks[:lim]
        except Exception as e:
            logger.info("Spotify API path failed, falling back to yt-dlp metadata: %s", e)
        finally:
            if close_session and session:
                await session.close()

    # Fallback: yt-dlp metadata (best effort, no creds)
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "ignoreerrors": True,
        "nocheckcertificate": True,
        "logtostderr": False,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        logger.warning("Spotify metadata extract failed: %s", e)
        return None, []

    if not isinstance(info, dict):
        return None, []
    title = info.get("title") or info.get("name")
    entries = info.get("entries") or []
    out: List[Dict[str, Any]] = []
    for e in list(entries)[:lim] if entries else []:
        if not isinstance(e, dict):
            continue
        # yt-dlp may give "title" like "Artist - Track"
        t = str(e.get("title") or "").strip()
        if not t:
            continue
        # Try to split "Artist - Track"
        artists: List[str] = []
        name = t
        if " - " in t:
            a, b = t.split(" - ", 1)
            artists = [a.strip()] if a.strip() else []
            name = b.strip() or t
        q = _track_query(name, artists) or t
        out.append({"title": name or t, "artists": artists, "duration": e.get("duration"), "query": q})
        if len(out) >= lim:
            break

    return (str(title) if title else None), out

