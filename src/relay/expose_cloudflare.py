from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.utils.cloudflare_tunnel import extract_latest_public_tunnel_url_from_log


@dataclass(frozen=True)
class CloudflaredHandle:
    proc: subprocess.Popen
    log_path: str


def resolve_cloudflared_bin() -> Optional[str]:
    """
    Resolve a usable cloudflared binary.
    Priority:
    1) ORA_CLOUDFLARED_BIN
    2) ./tools/cloudflare/cloudflared.exe
    3) ./cloudflared.exe
    4) PATH cloudflared
    """
    explicit = (os.getenv("ORA_CLOUDFLARED_BIN") or "").strip()
    if explicit:
        p = Path(explicit)
        if p.exists():
            return str(p)
        if shutil.which(explicit):
            return explicit

    candidates = [
        os.path.join(os.getcwd(), "tools", "cloudflare", "cloudflared.exe"),
        os.path.join(os.getcwd(), "cloudflared.exe"),
        "cloudflared",
    ]
    for c in candidates:
        if os.path.isabs(c) and os.path.exists(c):
            return c
        if shutil.which(c):
            return c
    return None


def start_quick_tunnel(*, local_url: str, log_path: str) -> Optional[CloudflaredHandle]:
    """
    Start a Cloudflare Quick Tunnel: `cloudflared tunnel --url <local_url>`.
    Writes stdout/stderr to `log_path` so other components can discover the public URL.
    """
    cf_bin = resolve_cloudflared_bin()
    if not cf_bin:
        return None

    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    out = open(log_path, "w", encoding="utf-8", errors="ignore")
    try:
        proc = subprocess.Popen(
            [cf_bin, "tunnel", "--no-autoupdate", "--url", str(local_url)],
            stdout=out,
            stderr=subprocess.STDOUT,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except Exception:
        try:
            out.close()
        except Exception:
            pass
        return None

    return CloudflaredHandle(proc=proc, log_path=log_path)


def wait_for_public_url(*, log_path: str, timeout_sec: int = 25) -> Optional[str]:
    """
    Poll the cloudflared log until it contains a public URL.
    """
    deadline = time.time() + max(3, int(timeout_sec))
    while time.time() < deadline:
        url = extract_latest_public_tunnel_url_from_log(log_path)
        if url:
            return url.rstrip("/")
        time.sleep(0.5)
    return None


def write_public_url_file(*, url_file: str, public_url: str) -> None:
    if not url_file:
        return
    p = Path(url_file)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        p.write_text((public_url or "").strip().rstrip("/") + "\n", encoding="utf-8")
    except Exception:
        return

