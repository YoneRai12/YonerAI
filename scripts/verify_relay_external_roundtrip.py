from __future__ import annotations

import asyncio
import base64
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import aiohttp


def _repo_root() -> Path:
    # scripts/verify_relay_external_roundtrip.py -> repo root
    return Path(__file__).resolve().parent.parent


def _find_python() -> str:
    # Prefer venv python if present.
    root = _repo_root()
    vpy = root / ".venv" / "Scripts" / "python.exe"
    if vpy.exists():
        return str(vpy)
    return sys.executable


def _find_cloudflared() -> Optional[str]:
    root = _repo_root()
    # Priority: ORA_CLOUDFLARED_BIN, tools/cloudflare, repo root
    explicit = (os.getenv("ORA_CLOUDFLARED_BIN") or "").strip()
    if explicit:
        p = Path(explicit)
        if p.exists():
            return str(p)
        return explicit  # rely on PATH
    for cand in [root / "tools" / "cloudflare" / "cloudflared.exe", root / "cloudflared.exe"]:
        if cand.exists():
            return str(cand)
    return "cloudflared"


async def _wait_http_ok(url: str, timeout_sec: float = 15.0) -> bool:
    deadline = time.time() + max(1.0, float(timeout_sec))
    async with aiohttp.ClientSession() as s:
        while time.time() < deadline:
            try:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status < 500:
                        return True
            except Exception:
                pass
            await asyncio.sleep(0.25)
    return False


async def _wait_public_relay(public_url: str, timeout_sec: float = 30.0) -> None:
    # Quick Tunnel DNS/edge propagation can lag slightly; retry until /health is reachable.
    url = public_url.rstrip("/") + "/health"
    deadline = time.time() + max(1.0, float(timeout_sec))
    last_err = ""
    async with aiohttp.ClientSession() as s:
        while time.time() < deadline:
            try:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=6), headers={"User-Agent": "ORA-Verify"}) as resp:
                    if resp.status == 200:
                        return
                    last_err = f"status={resp.status}"
            except Exception as e:
                last_err = f"{type(e).__name__}:{e}"
            await asyncio.sleep(0.6)
    raise RuntimeError(f"public_relay_unreachable:{last_err}")


async def _read_public_url(url_file: Path, timeout_sec: float = 30.0) -> str:
    deadline = time.time() + max(1.0, float(timeout_sec))
    while time.time() < deadline:
        try:
            raw = url_file.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            raw = ""
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw.rstrip("/")
        await asyncio.sleep(0.25)
    raise RuntimeError("public_url_file_timeout")


def _ws_url_from_public(public_url: str, path: str) -> str:
    u = public_url.rstrip("/")
    if u.startswith("https://"):
        u = "wss://" + u[len("https://") :]
    elif u.startswith("http://"):
        u = "ws://" + u[len("http://") :]
    return u + path


async def main() -> int:
    root = _repo_root()
    py = _find_python()
    cf = _find_cloudflared()

    # Use non-default ports so we don't collide with user's running stack.
    node_port = int(os.getenv("ORA_TEST_NODE_API_PORT") or "18000")
    relay_port = int(os.getenv("ORA_TEST_RELAY_PORT") or "19010")

    url_file = root / "temp" / "relay_public_url_test.txt"
    url_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        url_file.unlink()
    except Exception:
        pass

    pair_code = secrets.token_hex(4)

    env_base = os.environ.copy()
    env_base["PYTHONPATH"] = str(root)
    env_base["ORA_DOTENV_PATH"] = env_base.get("ORA_DOTENV_PATH", ".env")
    env_base["ORA_CLOUDFLARED_BIN"] = env_base.get("ORA_CLOUDFLARED_BIN", str(cf))

    # 1) Start Node API (legacy web api) on node_port.
    node_env = env_base.copy()
    node_cmd = [py, "-m", "uvicorn", "src.web.app:app", "--host", "127.0.0.1", "--port", str(node_port), "--no-access-log"]
    node_proc = subprocess.Popen(
        node_cmd,
        cwd=str(root),
        env=node_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

    # 2) Start Relay with Quick Tunnel (writes public URL to url_file).
    relay_env = env_base.copy()
    relay_env["ORA_RELAY_HOST"] = "127.0.0.1"
    relay_env["ORA_RELAY_PORT"] = str(relay_port)
    relay_env["ORA_RELAY_EXPOSE_MODE"] = "cloudflared_quick"
    relay_env["ORA_RELAY_PUBLIC_URL_FILE"] = str(url_file)
    relay_env["ORA_RELAY_CLOUDFLARED_LOG"] = str(root / "logs" / "cf_relay_test.log")

    relay_cmd = [py, "-m", "src.relay.main"]
    relay_proc = subprocess.Popen(
        relay_cmd,
        cwd=str(root),
        env=relay_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 3) Start Node connector (outbound) pointing to url_file and node api.
    conn_env = env_base.copy()
    conn_env["ORA_RELAY_URL"] = "auto"
    conn_env["ORA_RELAY_URL_FILE"] = str(url_file)
    conn_env["ORA_RELAY_URL_WAIT_SEC"] = "30"
    conn_env["ORA_RELAY_PAIR_CODE"] = pair_code
    conn_env["ORA_RELAY_NODE_ID"] = conn_env.get("ORA_INSTANCE_ID", "test-node")
    conn_env["ORA_NODE_API_BASE_URL"] = f"http://127.0.0.1:{node_port}"
    conn_cmd = [py, "-m", "src.services.relay_node"]
    conn_proc = subprocess.Popen(
        conn_cmd,
        cwd=str(root),
        env=conn_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

    try:
        ok = await _wait_http_ok(f"http://127.0.0.1:{node_port}/", timeout_sec=20)
        if not ok:
            raise RuntimeError("node_api_not_ready")

        ok = await _wait_http_ok(f"http://127.0.0.1:{relay_port}/health", timeout_sec=20)
        if not ok:
            raise RuntimeError("relay_not_ready")

        public_url = await _read_public_url(url_file, timeout_sec=40)
        await _wait_public_relay(public_url, timeout_sec=35)

        # 4) Pair (HTTP) via public URL
        token = ""
        async with aiohttp.ClientSession() as s:
            deadline = time.time() + 40
            last_err = ""
            while time.time() < deadline:
                try:
                    async with s.post(
                        f"{public_url}/api/pair",
                        json={"code": pair_code},
                        timeout=aiohttp.ClientTimeout(total=15),
                        headers={"User-Agent": "ORA-Verify"},
                    ) as resp:
                        body = await resp.text()
                        if resp.status != 200:
                            last_err = f"status={resp.status}:body={body[:120]}"
                            await asyncio.sleep(0.8)
                            continue
                        data = json.loads(body)
                        token = str(data.get("token") or "").strip()
                        if token:
                            break
                        last_err = "no_token"
                except Exception as e:
                    last_err = f"{type(e).__name__}:{e}"
                await asyncio.sleep(0.8)
            if not token:
                raise RuntimeError(f"pair_failed:{last_err}")

        # 5) WS client round-trip using wss public URL.
        ws_url = _ws_url_from_public(public_url, f"/ws/client?token={token}")
        msg = {
            "type": "http_proxy",
            "id": "ext1",
            "method": "GET",
            "path": "/",
            "headers": {},
            "body_b64": "",
        }
        async with aiohttp.ClientSession() as s:
            deadline = time.time() + 40
            last_err = ""
            while time.time() < deadline:
                try:
                    async with s.ws_connect(ws_url, heartbeat=20, timeout=aiohttp.ClientTimeout(total=20)) as ws:
                        await ws.send_str(json.dumps(msg, separators=(",", ":")))
                        r = await ws.receive(timeout=35)
                        if r.type != aiohttp.WSMsgType.TEXT:
                            last_err = f"ws_type:{r.type}"
                            await asyncio.sleep(0.8)
                            continue
                        data = json.loads(r.data)
                        if data.get("type") != "http_response" or data.get("id") != "ext1":
                            last_err = f"bad_response:{data}"
                            await asyncio.sleep(0.8)
                            continue
                        status = int(data.get("status") or 0)
                        body_b64 = str(data.get("body_b64") or "")
                        body = base64.b64decode(body_b64.encode("utf-8"), validate=False) if body_b64 else b""
                        if status < 200 or status >= 500:
                            last_err = f"http_status:{status}"
                            await asyncio.sleep(0.8)
                            continue
                        if len(body) < 20:
                            last_err = "body_too_small"
                            await asyncio.sleep(0.8)
                            continue
                        last_err = ""
                        break
                except Exception as e:
                    last_err = f"{type(e).__name__}:{e}"
                await asyncio.sleep(0.8)
            if last_err:
                raise RuntimeError(f"ws_roundtrip_failed:{last_err}")

        # Print a minimal success line (avoid leaking token or full URL).
        redacted = public_url.replace("https://", "").replace("http://", "")
        if ".trycloudflare.com" in redacted:
            redacted = "<redacted>.trycloudflare.com"
        print(f"OK external round-trip via Quick Tunnel: public={redacted} relay_port={relay_port} node_port={node_port}")
        return 0

    finally:
        # Clean up processes we spawned.
        for p in [conn_proc, relay_proc, node_proc]:
            try:
                if p and p.poll() is None:
                    if os.name == "nt":
                        p.terminate()
                    else:
                        p.send_signal(signal.SIGTERM)
            except Exception:
                pass
        # Give them a moment.
        await asyncio.sleep(0.8)
        for p in [conn_proc, relay_proc, node_proc]:
            try:
                if p and p.poll() is None:
                    p.kill()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
