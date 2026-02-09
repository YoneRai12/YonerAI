from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from src.relay.expose_cloudflare import start_quick_tunnel, wait_for_public_url, write_public_url_file


async def _wait_port_open(host: str, port: int, timeout_sec: float = 8.0) -> bool:
    deadline = asyncio.get_running_loop().time() + max(0.5, float(timeout_sec))
    while asyncio.get_running_loop().time() < deadline:
        try:
            _r, w = await asyncio.open_connection(host, port)
            w.close()
            try:
                await w.wait_closed()
            except Exception:
                pass
            return True
        except Exception:
            await asyncio.sleep(0.2)
    return False


async def main_async() -> None:
    # Respect repo-local .env when running Relay directly.
    dotenv_path = (os.getenv("ORA_DOTENV_PATH") or ".env").strip()
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)

    host = (os.getenv("ORA_RELAY_HOST") or "127.0.0.1").strip()
    port = int((os.getenv("ORA_RELAY_PORT") or "9010").strip() or "9010")
    ws_max_size = int((os.getenv("ORA_RELAY_MAX_MSG_BYTES") or "1048576").strip() or "1048576")

    expose_mode = (os.getenv("ORA_RELAY_EXPOSE_MODE") or "none").strip().lower()
    public_url_file = (os.getenv("ORA_RELAY_PUBLIC_URL_FILE") or ".relay_public_url.txt").strip()
    cf_log = (os.getenv("ORA_RELAY_CLOUDFLARED_LOG") or os.path.join("logs", "cf_relay.log")).strip()

    cfg = uvicorn.Config(
        "src.relay.app:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False,
        ws_max_size=ws_max_size,
    )
    server = uvicorn.Server(cfg)

    # Start Relay server.
    server_task = asyncio.create_task(server.serve())

    # Optionally expose via Cloudflare Quick Tunnel (domain-less).
    cf_handle = None
    if expose_mode == "cloudflared_quick":
        ok = await _wait_port_open(host, port, timeout_sec=8.0)
        if ok:
            local_url = f"http://127.0.0.1:{port}"
            cf_handle = start_quick_tunnel(local_url=local_url, log_path=cf_log)
            if not cf_handle:
                print("[relay] cloudflared not found; skipping Quick Tunnel expose.", file=sys.stderr)
            else:
                url = await asyncio.to_thread(wait_for_public_url, log_path=cf_log, timeout_sec=25)
                if url:
                    write_public_url_file(url_file=public_url_file, public_url=url)
                    # Print only the public hostname (no paths) for copy/paste.
                    print(f"[relay] public_url={url}")
                    print(f"[relay] public_url_file={Path(public_url_file).resolve()}")
        else:
            print("[relay] relay port did not open in time; skipping Quick Tunnel expose.", file=sys.stderr)

    try:
        await server_task
    finally:
        if cf_handle:
            try:
                cf_handle.proc.terminate()
            except Exception:
                pass


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

