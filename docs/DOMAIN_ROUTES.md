# Domain / Route Plan (`yonerai.com`)

Use this when running on your **local PC now**, then moving to **VPS later** without changing client URLs.

## Goal

- Keep public URLs stable from day 1.
- Use subdomains for service boundaries.
- Protect sensitive paths with Cloudflare Access + `ORA_WEB_API_TOKEN`.

## Recommended Subdomains

- `admin.yonerai.com` -> `http://127.0.0.1:8000`
  - Setup UI and admin-facing web pages.
- `api.yonerai.com` -> `http://127.0.0.1:8000`
  - External API path (`/api/v1/agent/*`).
- `relay.yonerai.com` -> `http://127.0.0.1:9010`
  - Relay WebSocket endpoint.
- `core.yonerai.com` -> `http://127.0.0.1:8001` (optional)
  - Core service endpoint.

Cloudflare Tunnel note:
- The `127.0.0.1:*` target is from the machine running `cloudflared`.
- For now that's your PC.
- Later on VPS, keep the same hostnames and only move tunnel connector.

## Path Design (Public API)

Use these stable external paths:

- `POST /api/v1/agent/run`
- `GET /api/v1/agent/runs/{run_id}/events`
- `POST /api/v1/agent/runs/{run_id}/results`

Auth:
- `Authorization: Bearer <ORA_WEB_API_TOKEN>`

## Local `.env` (Domain-enabled)

```ini
# Public URLs
DOWNLOAD_PUBLIC_BASE_URL=https://admin.yonerai.com
ORA_RELAY_URL=wss://relay.yonerai.com

# API hardening
ORA_WEB_API_TOKEN=REPLACE_WITH_LONG_RANDOM_TOKEN
ORA_REQUIRE_WEB_API_TOKEN=1
```

## Cloudflare Access (Recommended)

- Protect `admin.yonerai.com/*` with Access policy (you only).
- Keep token auth enabled for `/api/*` even with Access.
- Optionally protect `api.yonerai.com/*` with Access while testing.

## Migration To VPS (Later)

No URL changes needed:

1. Start same services on VPS.
2. Move `cloudflared` connector from PC to VPS.
3. Keep the same hostnames (`admin/api/relay/core.yonerai.com`).
4. Update `.env` only for local/private addresses behind the tunnel.

