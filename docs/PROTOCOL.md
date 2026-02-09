# YonerAI Relay Protocol (M2, v1)

Date: 2026-02-09  
Applies to: `src/relay/app.py`, `src/services/relay_node.py`

This is the *wire protocol* between:

- Node Connector (user PC) -> Relay (WebSocket)
- Client (Web/iOS/Android/Desktop) -> Relay (WebSocket)

Notes:

- Relay stores only hashes of pairing codes and session tokens (in memory).
- Relay does not persist message bodies.
- This protocol is designed for multi-platform clients (Web/iOS/Android/Windows/macOS/Linux/Discord tooling).

---

## 1. Endpoints

### 1.1 Node WebSocket

- `GET ws(s)://<relay-host>/ws/node?node_id=<node_id>`
- The Node connector must send a `pair_offer` immediately after connecting.

### 1.2 Pairing (HTTP)

- `POST http(s)://<relay-host>/api/pair`
- Body:

```json
{"code":"<PAIRING_CODE>"}
```

- Response (example):

```json
{"ok":true,"node_id":"node-1","token":"...","expires_at":1730000000}
```

Rules:

- Pairing codes are **one-time**: after a successful `/api/pair`, the same code becomes invalid.
- Pairing codes expire (TTL) even if unused.

### 1.3 Client WebSocket

- `GET ws(s)://<relay-host>/ws/client?token=<SESSION_TOKEN>`
- Token can also be passed via header:
  - `Authorization: Bearer <SESSION_TOKEN>`

---

## 2. Message Types (JSON)

All WebSocket messages are JSON objects (UTF-8).

### 2.1 `pair_offer` (Node -> Relay)

Sent by Node right after connect.

```json
{"type":"pair_offer","code":"abcd1234"}
```

Relay replies:

```json
{"type":"pair_offer_ack","ok":true,"expires_at":1730000000}
```

### 2.2 `http_proxy` (Client -> Relay -> Node)

Client requests the Node connector to proxy a local HTTP call.

```json
{
  "type":"http_proxy",
  "id":"req1",
  "method":"GET",
  "path":"/api/approvals",
  "headers":{"x-ora-token":"<ORA_WEB_API_TOKEN>"},
  "body_b64":""
}
```

Fields:

- `id` (string): request id (required; if missing Relay will generate one, but clients should always set it).
- `method` (string): HTTP method (default `GET`).
- `path` (string): path on Node API base.
- `headers` (object): forwarded headers (best-effort).
- `body_b64` (string): base64 encoded bytes (optional). Relay caps this.

### 2.3 `http_response` (Node -> Relay -> Client)

Node returns the proxied HTTP response. Relay forwards as-is.

```json
{
  "type":"http_response",
  "id":"req1",
  "status":200,
  "headers":{"content-type":"application/json"},
  "body_b64":"eyJvayI6dHJ1ZX0="
}
```

### 2.4 Keepalive: `ping` / `pong`

Client can ping Relay:

```json
{"type":"ping"}
```

Relay responds:

```json
{"type":"pong","ts":1730000000}
```

Node can respond to Relay pings similarly (Node connector in `src/services/relay_node.py` handles `ping`).

### 2.5 Errors

Errors are returned as `http_response` with an `error` field (no exception details by default):

```json
{"type":"http_response","id":"req1","error":"timeout"}
```

Common error strings:

- `node_not_connected`
- `id_in_use`
- `too_many_pending`
- `timeout`
- `relay_error`
- `node_disconnected`
- `message_too_large` (sent as `{"type":"error","error":"message_too_large"}`)

---

## 3. Limits / Hardening (Env)

Relay enforces:

- `ORA_RELAY_MAX_MSG_BYTES` (default 1048576): max WebSocket message size (JSON text).
- `ORA_RELAY_MAX_HTTP_BODY_BYTES` (default 262144): cap for decoded `body_b64` bytes.
- `ORA_RELAY_MAX_PENDING` (default 64): max in-flight requests per node.
- `ORA_RELAY_CLIENT_TIMEOUT_SEC` (default 35): per-request timeout waiting for node response.
- `ORA_RELAY_SESSION_TTL_SEC` (default 3600): session token TTL.
- `ORA_RELAY_PAIR_TTL_SEC` (default 120): pairing code TTL.
- `ORA_RELAY_PAIR_RATE_LIMIT_PER_MIN` (default 30): brute-force guard for `/api/pair`.
- `ORA_RELAY_ENFORCE_ORIGIN` (default 0): when enabled, rejects non-`https://` WS origins for clients.

---

## 4. Client Implementation Notes

- Always generate a unique `id` per request.
- Implement a client-side timeout; don’t wait forever.
- Always base64 encode bodies; treat binary and JSON the same.
- For browser clients in production, use `wss://` (TLS).

---

## 5. Node Connector Notes

- The Node connector is responsible for calling the local Node Web API (`ORA_NODE_API_BASE_URL`).
- It must never execute code from the internet; it only proxies HTTP to its own local services.

---

## 6. Security Roadmap (Not Yet Implemented)

- Node authentication for `/ws/node` (prevent fake nodes).
- E2EE: Relay forwards ciphertext only (no plaintext visibility).
- Session rotation + device management.
