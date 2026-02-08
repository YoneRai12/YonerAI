from __future__ import annotations

import asyncio
import base64
import json
import os
import secrets
import time
from typing import Any, Dict, Optional

import aiohttp


def _now() -> int:
    return int(time.time())


def _safe_json_loads(raw: str) -> dict:
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


async def _http_proxy_call(
    session: aiohttp.ClientSession,
    *,
    base_url: str,
    method: str,
    path: str,
    headers: Dict[str, str] | None,
    body_b64: str | None,
    max_body_bytes: int,
) -> dict:
    url = base_url.rstrip("/") + "/" + (path or "").lstrip("/")
    m = (method or "GET").upper()
    hdrs = {str(k): str(v) for k, v in (headers or {}).items() if k and v is not None}
    data: Optional[bytes] = None
    if body_b64:
        try:
            data = base64.b64decode(body_b64.encode("utf-8"), validate=False)[:max_body_bytes]
        except Exception:
            data = b""

    try:
        async with session.request(m, url, headers=hdrs, data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            b = await resp.read()
            b = b[:max_body_bytes]
            return {
                "status": int(resp.status),
                "headers": {k: v for k, v in resp.headers.items()},
                "body_b64": base64.b64encode(b).decode("ascii"),
            }
    except Exception as e:
        return {"error": f"http_proxy_failed:{type(e).__name__}"}


async def run_node_connector() -> None:
    """
    Node-side outbound connector to ORA Relay (M2 MVP).

    Env:
    - ORA_RELAY_URL: e.g. ws://127.0.0.1:9010
    - ORA_RELAY_NODE_ID: default uses ORA_INSTANCE_ID or "node"
    - ORA_RELAY_PAIR_CODE: if empty, random code printed to stdout
    - ORA_NODE_API_BASE_URL: default http://127.0.0.1:8000 (node web API)
    """
    relay_url = (os.getenv("ORA_RELAY_URL") or "ws://127.0.0.1:9010").strip().rstrip("/")
    node_id = (os.getenv("ORA_RELAY_NODE_ID") or os.getenv("ORA_INSTANCE_ID") or "node").strip()
    api_base = (os.getenv("ORA_NODE_API_BASE_URL") or "http://127.0.0.1:8000").strip()
    max_body = max(4096, min(2 * 1024 * 1024, _env_int("ORA_RELAY_MAX_HTTP_BODY_BYTES", 262144)))

    code = (os.getenv("ORA_RELAY_PAIR_CODE") or "").strip()
    if not code:
        # Short code is easier to type; the relay stores only a hash.
        code = secrets.token_hex(3)

    ws_url = f"{relay_url}/ws/node?node_id={node_id}"
    print(f"[relay-node] node_id={node_id} relay={relay_url}")
    print(f"[relay-node] pairing_code={code} (TTL is enforced by relay; re-run to rotate)")
    print(f"[relay-node] proxy_base={api_base}")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.ws_connect(ws_url, heartbeat=20) as ws:
                    # Register pairing offer immediately.
                    await ws.send_str(json.dumps({"type": "pair_offer", "code": code}, separators=(",", ":")))

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = _safe_json_loads(msg.data)
                            mtype = str(data.get("type") or "")
                            if mtype == "pair_offer_ack":
                                continue
                            if mtype == "http_proxy":
                                req_id = str(data.get("id") or "")
                                method = str(data.get("method") or "GET")
                                path = str(data.get("path") or "/")
                                headers = data.get("headers") if isinstance(data.get("headers"), dict) else {}
                                body_b64 = str(data.get("body_b64") or "")
                                out = await _http_proxy_call(
                                    session,
                                    base_url=api_base,
                                    method=method,
                                    path=path,
                                    headers=headers,  # type: ignore[arg-type]
                                    body_b64=body_b64,
                                    max_body_bytes=max_body,
                                )
                                out_msg = {"type": "http_response", "id": req_id, **out}
                                await ws.send_str(json.dumps(out_msg, ensure_ascii=False, separators=(",", ":")))
                                continue

                            if mtype == "ping":
                                await ws.send_str(json.dumps({"type": "pong", "ts": _now()}, separators=(",", ":")))
                                continue
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except Exception:
                await asyncio.sleep(2.0)


def main() -> None:
    asyncio.run(run_node_connector())


if __name__ == "__main__":
    main()

