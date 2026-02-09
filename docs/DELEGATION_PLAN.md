# ORA Delegation Plan (Gemini/Other AI Ready)

Date: 2026-02-09  
Repo: `c:\Users\YoneRai12\Desktop\ORADiscordBOT-main3`

This document is written to be *decision-complete*: another model/engineer can implement tasks without making design decisions.

---

## 0. What You Are Building (One Sentence)

ORA is a distributed "personal node" assistant: each user runs a **Node** on their PC; **Clients** (Web/iOS/Android/Windows/Mac/Discord) connect via **Relay**; risky actions are gated by **Policy + Approvals**; the system stays useful even when downloads fail via safe fallbacks.

---

## 1. Non-Negotiables (Safety + Repo Hygiene)

1. Never commit `.env` or secrets.
1. Never stage the `reference_clawdbot` submodule (gitlink may appear dirty).
1. No auto-execution of downloaded code. Sandbox tooling is *static inspection only*.
1. Router must not silently widen capability (no surprise `web_download`, no surprise remote browser control).
1. All new behavior must be controllable via `.env` flags with safe defaults.

Recommended staging command when pushing docs/code:

```powershell
git add README.md README_JP.md AGENTS.md docs/ src/ core/ tests/ .env.example
```

---

## 2. Current System Snapshot (Facts)

### 2.1 Roles

1. Node: runs on user PC; holds data; executes tools; runs approvals/policy gates.
1. Client: UI only (Web/iOS/Android/Windows/Mac/Discord).
1. Relay: routes traffic; should store metadata only; avoid body persistence.

### 2.2 Implemented Guardrails (Already In Repo)

1. Router download guard: `ORA_ROUTER_REQUIRE_EXPLICIT_DOWNLOAD=1` blocks accidental `WEB_FETCH`.
1. Optional auto-sandbox for GitHub review prompts: `ORA_ROUTER_AUTO_SANDBOX_GITHUB_REVIEW=1` enables SANDBOX without enabling `web_download`.
1. Sandbox ZIP download fallback: `ORA_SANDBOX_FALLBACK_ON_DOWNLOAD_FAIL=1` falls back to GitHub API read-only.
1. Approvals QoL knobs: owner approvals configurable via env (private/shared/global).
1. Mermaid diagram stability: README uses SVG generated from `docs/diagrams/*.mmd` to avoid GitHub theme issues.

---

## 3. “Dial” Design: When To Download vs When To Just Review

Goal: keep your best experience ("I see the conversation and do the right thing") while staying safe-by-default.

### 3.1 Three Intents (Treat Separately)

1. **Evaluate/Compare**: user wants analysis; downloads are optional.
1. **Verify/Scan**: user wants static checking; safe sandbox is appropriate.
1. **Fetch/Download**: user explicitly wants to download/store artifacts.

### 3.2 Decision Table (Must Implement As Rules)

Rules apply **before** tool execution.

1. If user does not explicitly request download/save/clone:
1. Then do not expose/choose `web_download` (already enforced).
1. If prompt contains 1+ GitHub repo URLs and words like "比較/評価/review":
1. Then choose sandbox tool(s) instead of web tools.
1. If sandbox ZIP download fails:
1. Then fall back to GitHub API read-only (already implemented).

### 3.3 User-Control Overrides (UX)

1. If user says "サンドボックスで" or "静的解析して" -> enable SANDBOX even if auto-sandbox is off.
1. If user says "ダウンロードして" -> allow sandbox ZIP download.
1. If user says "ダウンロードしないで" -> forbid downloads and sandbox ZIP; only read-only GitHub API + on-page reading.

Implementation location for final decision logic:

1. Tool selection: `src/cogs/handlers/tool_selector.py`
1. Tool execution gating: `src/cogs/tools/tool_handler.py`

---

## 4. Next Milestones (What To Build Next)

This is the recommended order to keep “事故らない”:

1. M2.6 Relay authentication hardening (node auth, double-connect policy, keepalive)
1. M2.7 Client protocol stability (request_id mux spec, backwards compatibility)
1. M2.8 Multi-platform clients baseline (shared protocol + thin UIs)
1. M3+ E2EE phased rollout (Relay can’t read plaintext)

---

## 5. Work Packages (Delegate-Friendly)

Each package includes: scope, exact files, steps, done criteria, tests.

### WP-A: Relay Keepalive + Disconnect Cleanup (M2.6)

Scope:

1. Implement WS ping/keepalive (server and clients where applicable).
1. On node/client disconnect: reject all pending futures; clear routing tables; don’t leak memory.

Files (expected):

1. `src/relay/main.py` or equivalent relay server entry
1. `src/relay/protocol.py` (if exists)
1. tests under `tests/`

Steps:

1. Add server periodic ping (interval env `ORA_RELAY_PING_INTERVAL_SEC`, default 20).
1. Add client-side pong handling if needed.
1. Ensure `pending` map empties on disconnect.

Done Criteria:

1. Disconnect during active requests does not leak: `pending==0` after disconnect.
1. Integration test simulates drop and asserts cleanup.

Tests:

1. Unit test for disconnect cleanup.
1. Optional: websocket integration test if existing test harness exists.

### WP-B: Node Authentication For `/ws/node` (M2.6)

Threat to address:

1. Anyone can connect a fake node to Relay and receive traffic if node_id collisions exist.

Decision (fixed):

1. Node must prove identity with a shared secret issued at pairing time.
1. Relay stores only **hash** of node_secret (never plaintext).

Env:

1. `ORA_RELAY_NODE_SECRET_LEN=32` (bytes, base64)
1. `ORA_RELAY_NODE_SECRET_TTL_SEC=31536000` (1y) or rotate by version

Protocol:

1. During pairing: Relay returns `node_secret` once.
1. Node connects with headers: `X-ORA-NODE-ID`, `X-ORA-NODE-AUTH=<HMAC/secret>`.
1. Relay verifies.

Files:

1. Relay pairing endpoint
1. Node connector module
1. Token/hash utilities (reuse existing hashing approach from pairing tokens)

Done Criteria:

1. `/ws/node` without valid secret is rejected.
1. Reusing old secret after rotation fails (if rotation implemented).

Tests:

1. Unit tests for auth verification.

### WP-C: Router “Soft Continue” (No Surprise Downloads)

Goal:

1. If user says "ダウンロードして評価して" and sandbox download fails:
1. System continues with fallback (already in sandbox tool).
1. Router/tool layer should reflect this in messaging: "download failed, used read-only fallback".

Implementation:

1. Ensure tool output includes `fallback_used` flag (already).
1. ChatHandler formats a friendly message when `fallback_used`.

Files:

1. `src/cogs/handlers/chat_handler.py` (tool result formatting)

Done Criteria:

1. Discord reply clearly says: fallback mode used, and what it means.

Tests:

1. Unit test for formatting (if harness exists), else manual verified with mocked tool output.

### WP-D: Multi-Platform Client Protocol Spec (M2.7/M2.8)

Goal:

1. Define a single JSON protocol so Web/iOS/Android/Windows/Mac clients can interop.

Decision (fixed):

1. Transport: WebSocket.
1. Message envelope:

```json
{
  "v": 1,
  "type": "http_proxy",
  "id": "uuid",
  "method": "GET",
  "path": "/api/approvals",
  "headers": {"Authorization": "Bearer ..."},
  "body_b64": null
}
```

Rules:

1. `id` is required; responses must echo same `id`.
1. `body` must be base64 to avoid encoding ambiguity.
1. `ORA_RELAY_MAX_MSG_BYTES` enforced.

Deliverable:

1. Add `docs/PROTOCOL.md` containing spec + examples.
1. Add a reference client in Python (already can exist) and a JS snippet.

Done Criteria:

1. A single protocol doc used by all clients.

### WP-E: Mermaid/Diagrams CI Generation (Optional but Strong)

Goal:

1. Keep README diagrams always readable by generating SVGs in CI.

Decision (fixed):

1. Use Mermaid CLI in GitHub Actions to regenerate `docs/diagrams/*.svg` on changes to `*.mmd`.

Files:

1. `.github/workflows/diagrams.yml` (new)

Done Criteria:

1. PR that changes `.mmd` updates `.svg` automatically.

---

## 6. Acceptance Tests (System-Level Checklist)

Run in this order.

### 6.1 Local checks

```powershell
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m compileall src core\src
.venv\Scripts\python -m pytest -q
```

### 6.2 Sandbox compare behavior

1. Ask: `YonerAI https://github.com/YoneRai12/YonerAI と METEOBOT https://github.com/meteosimaji/METEOBOT を比較して評価して`
1. Expect:
1. No `web_download`.
1. Uses `sandbox_compare_repos` (auto-sandbox when enabled).
1. If download fails, output indicates read-only fallback.

### 6.3 Core health

1. `POST /v1/memory/history` no longer 500s (resolve_conversation signature defaulted).

---

## 7. Delegation Prompts (Copy/Paste For Gemini)

### Prompt Template (Implementation)

Paste this to Gemini when delegating a WP:

```text
You are implementing WP-<X> in ORA repo.
Constraints:
- Do not modify .env (only .env.example).
- Do not stage reference_clawdbot submodule.
- Add/adjust tests so pytest passes.
- Keep safe-by-default; new behavior must be behind env flag with safe default.

Scope:
<paste WP section here>

Deliverables:
- Code changes in specified files
- Tests
- Short doc update if needed

Acceptance:
- ruff check .
- pytest -q
```

### Prompt Template (Doc-only work)

```text
Update docs only. Do not change runtime behavior.
Write: <doc name> with sections: Summary, Threat Model, Config, Protocol, Examples, Troubleshooting.
```

---

## 8. Owner UX Defaults (Recommended `.env` for You)

If you want “my requests don’t constantly require approvals” while keeping guests safe:

1. For solo/private use:
1. `ORA_PROFILE=private`
1. `ORA_PRIVATE_OWNER_APPROVALS=critical_only`

1. For shared use (friends):
1. Keep `ORA_SHARED_OWNER_APPROVALS=high` (don’t bypass in shared).
1. Set `ORA_SHARED_GUEST_ALLOWED_TOOLS=...` explicitly.
1. Optionally raise guest approval threshold:
1. `ORA_SHARED_GUEST_APPROVAL_MIN_SCORE=60` (MEDIUM tools can run without approval if allowlisted).

---

## 9. Open Risks (Known)

1. `Healer` tries to call a local LLM endpoint (seen `[RESTRICTED]:8008` failures). Consider adding an env to disable healer network calls or fallback directly to OpenAI only.
1. Relay still sees plaintext in transit unless E2EE is implemented (planned M3+).
1. Multi-client identity/ownership model needs careful definition before “public” shared use.
