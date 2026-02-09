# ORA Relay External Test Runbook (Quick Tunnel / No Domain)

Date: 2026-02-09  
Applies to: `src/relay/app.py`, `src/relay/main.py`, `src/services/relay_node.py`

Goal: prove that Relay can be exposed without a domain (Cloudflare Quick Tunnel) and that an **external** client can complete **one HTTP proxy round-trip** to the Node API.

This runbook is intentionally small and deterministic. If it fails, it should be obvious *where* it failed (Relay / Node connector / Node API).

---

## 0. Preconditions

1. Python venv active (recommended): `.venv`
1. You can start a local Node API (legacy Web API) on `http://127.0.0.1:8000`
1. Your repo has `cloudflared.exe` (or you set `ORA_CLOUDFLARED_BIN`)

Env vars (from `.env`):

- Relay:
  - `ORA_RELAY_HOST=127.0.0.1`
  - `ORA_RELAY_PORT=9010`
  - `ORA_RELAY_EXPOSE_MODE=cloudflared_quick`
  - `ORA_RELAY_PUBLIC_URL_FILE=.relay_public_url.txt`
  - `ORA_CLOUDFLARED_BIN=...` (optional; auto-resolve works if `./cloudflared.exe` exists)
- Node connector:
  - `ORA_RELAY_URL=auto`
  - `ORA_RELAY_URL_FILE=.relay_public_url.txt`
  - `ORA_NODE_API_BASE_URL=http://127.0.0.1:8000`
- Auth (Node API token for `/api/approvals`):
  - `ORA_WEB_API_TOKEN=...`

---

## 1. Start Node API (local)

If you already run the legacy Web API, skip this.

```powershell
# from repo root
uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

Sanity check:

```powershell
curl.exe -i http://127.0.0.1:8000/
```

---

## 2. Start Relay (with Quick Tunnel)

```powershell
$env:ORA_RELAY_EXPOSE_MODE="cloudflared_quick"
$env:ORA_RELAY_PUBLIC_URL_FILE=".relay_public_url.txt"

python -m src.relay.main
```

Expected:

- Relay prints `public_url=https://<random>.trycloudflare.com`
- The same URL is written to `.relay_public_url.txt`

Sanity check (local):

```powershell
curl.exe -i http://127.0.0.1:9010/health
```

---

## 3. Start Node Connector (outbound WS to Relay)

Open a new terminal:

```powershell
$env:ORA_RELAY_URL="auto"
$env:ORA_RELAY_URL_FILE=".relay_public_url.txt"
$env:ORA_NODE_API_BASE_URL="http://127.0.0.1:8000"

python -m src.services.relay_node
```

Expected:

- It prints:
  - `pairing_code=...`
  - `node_id=...`

Copy the `pairing_code` for the next step.

---

## 4. Pair (get session token)

Use the Quick Tunnel public URL (HTTPS) to call `/api/pair`.

PowerShell easiest:

```powershell
$public = (Get-Content .relay_public_url.txt -TotalCount 1).Trim().TrimEnd("/")
$code = "<PAIRING_CODE>"

$resp = Invoke-RestMethod -Method Post -Uri "$public/api/pair" -ContentType "application/json" -Body (@{code=$code} | ConvertTo-Json)
$resp | ConvertTo-Json
```

Expected:

- Response contains `token` and `node_id`

---

## 5. External Client WS Round-Trip (HTTP proxy)

This sends one `http_proxy` message via `wss://.../ws/client?token=...`, and expects a `http_response`.

Note:

- This uses `aiohttp` (already a dependency in this repo).
- It calls the Node API path: `GET /api/approvals` and passes `x-ora-token`.
- If `ORA_WEB_API_TOKEN` is missing/wrong, you may get 401/403 but the round-trip still proves the tunnel + WS routing works.

```powershell
$public = (Get-Content .relay_public_url.txt -TotalCount 1).Trim().TrimEnd("/")
$token  = $resp.token
$env:ORA_WEB_API_TOKEN = $env:ORA_WEB_API_TOKEN  # ensure it's set in this shell

@'
import asyncio, json, os, base64
import aiohttp

public = os.environ.get("ORA_PUBLIC_URL", "").strip().rstrip("/")
token = os.environ.get("ORA_SESSION_TOKEN", "").strip()
api_token = os.environ.get("ORA_WEB_API_TOKEN", "").strip()

if not public or not token:
    raise SystemExit("missing ORA_PUBLIC_URL or ORA_SESSION_TOKEN")

ws_url = public.replace("https://", "wss://").replace("http://", "ws://") + f"/ws/client?token={token}"
msg = {
    "type": "http_proxy",
    "id": "ext1",
    "method": "GET",
    "path": "/api/approvals",
    "headers": {"x-ora-token": api_token} if api_token else {},
    "body_b64": "",
}

async def main():
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(ws_url, heartbeat=20) as ws:
            await ws.send_str(json.dumps(msg, separators=(",", ":")))
            r = await ws.receive(timeout=40)
            if r.type != aiohttp.WSMsgType.TEXT:
                print("unexpected ws msg type:", r.type)
                return
            data = json.loads(r.data)
            print(json.dumps(data, ensure_ascii=False, indent=2))

asyncio.run(main())
'@ | python -  | Out-Null
```

Set envs for the snippet:

```powershell
$env:ORA_PUBLIC_URL   = $public
$env:ORA_SESSION_TOKEN = $token
python -c "print('ok')"
```

If everything is wired:

- You get back a JSON like:
  - `{"type":"http_response","id":"ext1","status":200,...}`
  - or a 401/403 if token is missing, but still `http_response` indicates success routing.

---

## 6. “Real external” check (mobile network)

Do the same pairing + WS step from:

- another PC
- or your phone via Termux/Pydroid (Python)

What matters:

1. Pair via `https://<random>.trycloudflare.com/api/pair`
1. Connect via `wss://<random>.trycloudflare.com/ws/client?token=...`

---

## 7. Troubleshooting

Common failures and meaning:

1. `/api/pair` returns `node not connected`:
   - Node connector is not connected, or node_id mismatch.
1. WS client returns `invalid token` / close 4403:
   - Token expired or wrong.
1. `http_response` with `timeout`:
   - Node connector is connected but Node API call to `ORA_NODE_API_BASE_URL` did not return in time.
1. `message_too_large`:
   - You exceeded `ORA_RELAY_MAX_MSG_BYTES`.

---

## 8. Record The Evidence (Recommended)

When you succeed once, append a short note to `docs/RELAY_EXTERNAL_TEST.md` (below this line) with:

- date/time
- public_url domain (you can redact most of it)
- status code you received
- any error strings

This makes regressions easy to spot later.

---

## 9. Automated Test (Recommended)

If you want a one-command verification (starts its own temporary ports, uses Quick Tunnel, does 1 round-trip, then cleans up):

```powershell
python scripts/verify_relay_external_roundtrip.py
```

It prints a redacted success line like:

`OK external round-trip via Quick Tunnel: public=<redacted>.trycloudflare.com relay_port=19010 node_port=18000`

### Evidence Log

- 2026-02-09: OK external round-trip via Quick Tunnel (redacted), `relay_port=19010`, `node_port=18000`
