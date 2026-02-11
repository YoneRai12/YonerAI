# VPS Deployment (Hybrid Control Plane)

This guide makes YonerAI run on a VPS as the **always-on control plane**, while your main PC stays a **pull-worker** for high-privilege + GPU work.

## Target Architecture

- VPS:
  - Relay (WebSocket router)
  - Web API + Setup UI (`/setup`)
  - Core (optional, but recommended)
  - Discord bot (optional, but recommended for 24/7)
  - Browser sandbox (Playwright: screenshots/recording) runs inside the VPS image
- Main PC:
  - Pull-worker (connects outbound to Relay; no inbound ports on your PC)

## Prereqs (VPS)

- Ubuntu 24.04 LTS (recommended)
- Docker + Docker Compose plugin installed
- (Recommended) Cloudflare Tunnel + Access for public exposure

## Region Notes (Latency Reality)

You can run the control plane in Singapore if that's what you can get right now.

- Cloudflare (Tunnel / reverse proxy) helps with TLS, auth, and routing stability.
- It does **not** magically remove physics: WebSockets will still feel the extra round-trip time to Singapore.
- For “always-on” control (Discord bot, jobs, approvals, downloads), Singapore is usually fine.
- For “interactive remote control” (tight UI loops), Tokyo/Osaka will feel better if/when available.

## 1) Get The Repo On The VPS

```bash
git clone https://github.com/YoneRai12/YonerAI.git
cd YonerAI
cp .env.example .env
```

Do **not** commit `.env`.

## 2) Minimal `.env` For VPS

Required:
- `DISCORD_BOT_TOKEN`
- `ADMIN_USER_ID`

Recommended:
- `ORA_WEB_API_TOKEN` (required if you expose `/setup` / `/api` to the internet)
- `DOWNLOAD_PUBLIC_BASE_URL=https://app.yourdomain.com` (or your tunnel hostname)

Relay:
- `ORA_RELAY_HOST=0.0.0.0`
- `ORA_RELAY_PORT=9010`

Web API:
- `ORA_WEB_HOST=0.0.0.0`
- `ORA_WEB_PORT=8000`

## 3) Run The VPS Control Plane (Docker)

From the repo root:

```bash
docker compose -f deploy/docker-compose.vps.yml up -d --build
```

You should now have:
- Web API: `http://<vps-ip>:8000`
- Relay: `ws://<vps-ip>:9010`
- Core: `http://<vps-ip>:8001`

## 4) Expose Publicly (Recommended: Cloudflare Tunnel + Access)

Do not open your admin/setup APIs to the world without auth.

Recommended approach:
- Keep VPS firewall strict (SSH only).
- Expose only via Cloudflare Tunnel.
- Protect with Cloudflare Access (GitHub/Google/Apple).

In addition:
- Set `ORA_WEB_API_TOKEN` and require it.
- Set `DOWNLOAD_PUBLIC_BASE_URL` to your public hostname so temporary download links are stable.

### Domain-less dev option (Quick Tunnel)

If you don't have a domain yet and just want to test “public access” quickly:

- Relay: set `ORA_RELAY_EXPOSE_MODE=cloudflared_quick`
  - Relay will write a random `trycloudflare.com` URL to `ORA_RELAY_PUBLIC_URL_FILE`.
- Downloads: YonerAI can also spawn a dedicated quick tunnel for the downloads server when needed.

Notes:
- Quick Tunnel URLs change every time, and have no uptime guarantees. Use for dev/testing only.
- For anything serious, use a Named Tunnel + your own domain.

## 5) Main PC Pull-Worker (Connects To VPS Relay)

On your main PC, configure:
- `ORA_RELAY_URL=ws://<vps-ip>:9010` (or `wss://...` when tunneled)
- Keep approvals/policy enabled; keep CRITICAL on PC-only tools.

## Troubleshooting

- Large videos: YonerAI already falls back to a 30-minute temporary download link.
  - Router: `src/web/routers/downloads.py`
  - Storage: `src/utils/temp_downloads.py`
  - Set `DOWNLOAD_PUBLIC_BASE_URL` to get stable URLs.
- If Playwright fails in the VPS container: ensure the image was built with `Dockerfile.vps`.
