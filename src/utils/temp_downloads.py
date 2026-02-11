import json
import os
import re
import shutil
import time
import uuid
import asyncio
import sys
import logging
import socket
import subprocess
from typing import Any, Dict, Optional

from src.config import TEMP_DIR
from src.utils.cloudflare_tunnel import extract_latest_public_tunnel_url_from_log

_TOKEN_RE = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")
logger = logging.getLogger(__name__)

SHARED_ROOT = os.path.join(TEMP_DIR, "shared_downloads")


def _ensure_root() -> None:
    os.makedirs(SHARED_ROOT, exist_ok=True)


def _safe_filename(name: str) -> str:
    name = (name or "download.bin").strip()
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", "_", name)
    return name[:180] or "download.bin"


def _token_dir(token: str) -> str:
    return os.path.join(SHARED_ROOT, token)


def _manifest_path(token: str) -> str:
    return os.path.join(_token_dir(token), "manifest.json")


def cleanup_expired_downloads(now_ts: Optional[int] = None) -> int:
    """Delete expired token directories. Returns number of removed entries."""
    _ensure_root()
    now_ts = int(now_ts or time.time())
    removed = 0

    for token in os.listdir(SHARED_ROOT):
        tdir = _token_dir(token)
        if not os.path.isdir(tdir):
            continue

        mpath = _manifest_path(token)
        try:
            with open(mpath, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            expires_at = int(manifest.get("expires_at", 0))
        except Exception:
            expires_at = 0

        if expires_at <= now_ts:
            try:
                shutil.rmtree(tdir, ignore_errors=True)
                removed += 1
            except Exception:
                pass

    return removed


def create_temporary_download(
    source_file: str,
    *,
    download_name: Optional[str] = None,
    source_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ttl_seconds: int = 1800,
) -> Dict[str, Any]:
    """Move a file into shared temp storage and return tokenized manifest."""
    if not source_file or not os.path.exists(source_file):
        raise FileNotFoundError(f"Source file not found: {source_file}")

    _ensure_root()
    cleanup_expired_downloads()

    ttl_seconds = max(60, int(ttl_seconds))
    token = uuid.uuid4().hex[:16]
    tdir = _token_dir(token)
    os.makedirs(tdir, exist_ok=True)

    original_name = download_name or os.path.basename(source_file)
    original_name = _safe_filename(original_name)

    _, ext = os.path.splitext(original_name)
    payload_name = f"payload{ext}" if ext else "payload.bin"
    payload_path = os.path.join(tdir, payload_name)

    shutil.move(source_file, payload_path)
    size_bytes = os.path.getsize(payload_path)

    now_ts = int(time.time())
    manifest = {
        "token": token,
        "created_at": now_ts,
        "expires_at": now_ts + ttl_seconds,
        "download_name": original_name,
        "payload_name": payload_name,
        "size_bytes": int(size_bytes),
        "source_url": source_url or "",
        "metadata": metadata or {},
    }

    with open(_manifest_path(token), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest


def get_download_manifest(token: str) -> Optional[Dict[str, Any]]:
    """Load manifest if token exists and not expired."""
    if not token or not _TOKEN_RE.match(token):
        return None

    cleanup_expired_downloads()
    mpath = _manifest_path(token)
    if not os.path.exists(mpath):
        return None

    try:
        with open(mpath, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return None

    if int(manifest.get("expires_at", 0)) <= int(time.time()):
        delete_download_entry(token)
        return None

    return manifest


def get_download_file_path(token: str) -> Optional[str]:
    manifest = get_download_manifest(token)
    if not manifest:
        return None
    payload_name = manifest.get("payload_name")
    if not isinstance(payload_name, str):
        return None
    fpath = os.path.join(_token_dir(token), payload_name)
    if not os.path.exists(fpath):
        return None
    return fpath


def delete_download_entry(token: str) -> None:
    if not token or not _TOKEN_RE.match(token):
        return
    shutil.rmtree(_token_dir(token), ignore_errors=True)


def extract_latest_tunnel_url(log_path: str) -> Optional[str]:
    return extract_latest_public_tunnel_url_from_log(log_path)


def resolve_public_download_base_url(bot=None) -> Optional[str]:
    """
    Resolve a reachable public base URL for download links.
    Priority:
    1) Explicit override (DOWNLOAD_PUBLIC_BASE_URL)
    2) recent cf_download quick tunnel log
    3) recent cf_browser quick tunnel log
    4) named tunnel hostname (optional fallback)
    """
    cfg = getattr(bot, "config", None) if bot else None

    explicit = (os.getenv("DOWNLOAD_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit

    log_dirs = []
    if cfg and getattr(cfg, "log_dir", None):
        log_dirs.append(cfg.log_dir)
    log_dirs.append(os.path.join(os.getcwd(), "logs"))

    for ldir in log_dirs:
        candidate = extract_latest_tunnel_url(os.path.join(ldir, "cf_download.log"))
        if candidate:
            return candidate

    for ldir in log_dirs:
        candidate = extract_latest_tunnel_url(os.path.join(ldir, "cf_browser.log"))
        if candidate:
            return candidate

    tunnel_host = getattr(cfg, "tunnel_hostname", None) if cfg else None
    if isinstance(tunnel_host, str) and tunnel_host.strip():
        return f"https://{tunnel_host.strip().strip('/')}"

    return None


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.7)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def _start_web_api_server_if_needed(bot=None) -> None:
    if _is_port_open("127.0.0.1", 8000):
        return

    cfg = getattr(bot, "config", None) if bot else None
    log_dir = getattr(cfg, "log_dir", None) if cfg else os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "api_server_download.log")

    try:
        with open(log_path, "a", encoding="utf-8", errors="ignore") as out:
            # Cross-platform and venv-friendly: use the current interpreter to run uvicorn.
            # This avoids machine-specific paths (e.g. L:\...) and works on VPS/Linux.
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"],
                cwd=os.getcwd(),
                stdout=out,
                stderr=subprocess.STDOUT,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        logger.info("Started web API server for temporary downloads.")
    except Exception as e:
        logger.warning("Failed to auto-start web API server for downloads: %s", e)


def _launch_quick_tunnel(log_path: str) -> None:
    # Prefer explicit config, then repo-local exe, then PATH.
    cf_bin = (os.getenv("ORA_CLOUDFLARED_BIN") or "").strip() or "cloudflared"
    if os.path.exists("cloudflared.exe") and cf_bin == "cloudflared":
        cf_bin = os.path.abspath("cloudflared.exe")

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8", errors="ignore") as out:
        subprocess.Popen(
            [cf_bin, "tunnel", "--url", "http://localhost:8000"],
            stdout=out,
            stderr=subprocess.STDOUT,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )


async def ensure_download_public_base_url(bot=None, timeout_sec: int = 22) -> Optional[str]:
    """
    Return a public base URL for temporary download links.
    - Prefer existing quick tunnel URL.
    - Auto-start local API server on 8000 if needed.
    - Auto-spawn a dedicated Cloudflare quick tunnel (cf_download.log) when absent.
    """
    existing = resolve_public_download_base_url(bot)
    if existing:
        return existing

    _start_web_api_server_if_needed(bot)

    # Give API a short boot window.
    for _ in range(6):
        if _is_port_open("127.0.0.1", 8000):
            break
        await asyncio.sleep(1.0)

    cfg = getattr(bot, "config", None) if bot else None
    log_dir = getattr(cfg, "log_dir", None) if cfg else os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "cf_download.log")

    # Reuse recent tunnel URL if already there.
    url = extract_latest_tunnel_url(log_path)
    if url:
        return url

    try:
        _launch_quick_tunnel(log_path)
    except Exception as e:
        logger.warning("Failed to launch quick tunnel for downloads: %s", e)
        return resolve_public_download_base_url(bot)

    deadline = time.time() + max(6, int(timeout_sec))
    while time.time() < deadline:
        await asyncio.sleep(1.0)
        url = extract_latest_tunnel_url(log_path)
        if url:
            return url

    return resolve_public_download_base_url(bot)
