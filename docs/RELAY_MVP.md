# ORA Relay MVP (M2, Owner-only)

Goal: allow a user PC (Node) behind NAT to be reached from Web/Mobile clients via a Relay, without exposing Node ports directly.

This is an MVP:
- Relay keeps **only metadata** (in-memory). No plaintext persistence.
- Pairing is **Owner-only** (one-time code).
- Routing is **minimal**: a client can proxy HTTP requests to the Node's local Web API.

## Start Relay

```powershell
# from repo root
python -m src.relay.main
```

Health:

```powershell
curl http://127.0.0.1:9010/health
```

## Start Node Connector (Outbound)

This connector keeps an outbound WebSocket connection to the Relay and accepts proxy requests.

```powershell
$env:ORA_RELAY_URL="ws://127.0.0.1:9010"
$env:ORA_NODE_API_BASE_URL="http://127.0.0.1:8000"  # your node Web API
python -m src.services.relay_node
```

It prints a `pairing_code=...` to the console. This code is short TTL; re-run to rotate.

## Pair (Owner-only)

```powershell
curl -X POST http://127.0.0.1:9010/api/pair -H "Content-Type: application/json" -d "{\"code\":\"<PAIRING_CODE>\"}"
```

Response includes `{token, node_id}`.

## Client WebSocket (HTTP proxy)

Connect to:
- `ws://127.0.0.1:9010/ws/client?token=<TOKEN>`

Send:

```json
{"type":"http_proxy","id":"req1","method":"GET","path":"/api/approvals","headers":{"x-ora-token":"<ORA_WEB_API_TOKEN>"}}
```

Relay will forward to the Node connector, which calls `ORA_NODE_API_BASE_URL + path` locally and returns:

```json
{"type":"http_response","id":"req1","status":200,"headers":{...},"body_b64":"..."}
```

Notes:
- `body_b64` is base64-encoded bytes. Cap is `ORA_RELAY_MAX_HTTP_BODY_BYTES`.
- Pairing codes are **one-time**: after a successful `/api/pair`, the same code is invalid.
- Relay has basic DoS guards: `ORA_RELAY_MAX_PENDING`, message size caps, and per-request timeouts (`ORA_RELAY_CLIENT_TIMEOUT_SEC`).
- For internet exposure, also enforce WebSocket frame/message size limits at the edge (Caddy/nginx/Cloudflare), not just in-app.

## Security Notes

- Relay stores only hashes of pairing codes and session tokens (memory only).
- Relay is not meant to be directly exposed to the open internet without additional auth and TLS.
- Use Cloudflare Named Tunnel + domain for stable URLs later.
