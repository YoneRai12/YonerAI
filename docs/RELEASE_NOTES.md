# ORA Release Notes

This page is a curated summary of what changed across releases (beyond GitHub’s auto-generated notes).

## v5.0.0 -> v2026.2.9 (2026-02-09)

### Big Picture (What You Actually Got)
- **Hub/Spoke agent runtime stabilized**: thin client (Discord/Web) delegates the reasoning loop to ORA Core; tools execute locally and results are fed back to Core.
- **Security posture tightened**: fewer “surprise side effects” at startup; approvals/audit added so powerful tooling doesn’t silently become dangerous as features grow.
- **Multi-platform direction clarified**: Discord bot is no longer “the product”; it’s one client for a broader ORA API + web dashboards + future mobile/desktop clients.
 - **Distribution-ready baseline**: profile isolation (`private/shared`) + Relay MVP enables a “user PC as the node” architecture without port-forwarding.

### Security & Safety (High Impact)
- **Risk-based approvals gate + audit trail**:
  - Tool execution is gated at the ToolHandler boundary (skills, dynamic tools, MCP tools all funnel through one checkpoint).
  - **Owner is NOT exempt**: HIGH requires approval; CRITICAL requires 2-step confirmation (button + code).
  - SQLite tables `tool_audit` and `approval_requests` store “who did what, when, with what args (redacted), and what happened”.
- **Safe startup defaults (no auto-expose)**:
  - Bot no longer auto-opens local browser UIs unless explicitly enabled.
  - Bot no longer auto-starts Cloudflare tunnels unless explicitly enabled.
  - Quick tunnels (trycloudflare) blocked by default unless explicitly enabled.

### Distribution / Relay (New)
- **Profile isolation (M1)**:
  - Introduces `ORA_PROFILE=private|shared` with profile-scoped `state_root` (DB/logs/memory/secrets/tmp).
  - Adds `instance_id` persistence so each installed node is stably identifiable.
- **Shared/guest policy as code (M3)**:
  - Shared guests are allowlist-based and CRITICAL is blocked by default.
  - Unknown tools default to HIGH risk to avoid accidental exposure.
- **Relay MVP + hardening (M2/M2.5)**:
  - WebSocket routing + pairing + HTTP proxy to the local node API.
  - Mux (`id -> Future`), caps, timeouts, and disconnect cleanup to survive real-world networks.
- **Cloudflare Quick Tunnel**:
  - Domain-less external testing can be enabled via `.env` expose mode.

### Static Verification (Sandbox)
- **Sandbox repo inspection tools**:
  - `sandbox_download_repo` downloads GitHub ZIPs into the temp sandbox and runs static inspection only (no execution).
  - `sandbox_compare_repos` compares two repos at a high level (files/size/languages/suspicious hits).

### Approvals QoL (Configurable)
- Owner/guest approval friction can be tuned via `.env` while keeping safe defaults.
  - Owner global knobs: `ORA_OWNER_APPROVALS`, `ORA_OWNER_APPROVAL_SKIP_TOOLS`.
  - Shared guest threshold knob: `ORA_SHARED_GUEST_APPROVAL_MIN_SCORE`.

### Tooling & Extensibility
- **MCP client support (stdio)**:
  - ORA can connect to configured MCP servers and expose their tools as ORA tools named like `mcp__<server>__<tool>`.
  - MCP tools are routed through the same approvals/audit gate.
- **MCP trust boundary tightened (safe-by-default)**:
  - Default deny patterns for dangerous tool names (delete/remove/wipe/push/publish/exec, etc.).
  - Optional per-server `allowed_tools` allowlist and an explicit escape hatch for dangerous tools when you really want it.
- **Router/tool selection hardening**:
  - Caps tool exposure to avoid massive tool lists.
  - Adds categories so “codebase inspection” tools are only exposed when appropriate.
  - Avoids selecting remote browser tools unless the user explicitly asks for screenshot/control.

### Memory (User + Server Context)
- **Guild/server context memory**:
  - Adds guild-level hints to bias acronym/domain disambiguation (example: VALORANT servers).
  - Keeps it deterministic (no extra LLM calls) and injects into system context.

### Web / Media / UX Fixes That Matter
- **Discord embed hard limit fix**:
  - Prevents 400 errors caused by embed title length > 256.
- **Remote browser errors are diagnosable now**:
  - Browser API failures return an `error_id` and write contextual error logs, so “nothing shows up” can be triaged from logs.
- **Downloads & screenshots cleanup**:
  - Temp artifacts (screenshots/download files) are deleted after use in tool implementations.
  - Large downloads can be delivered via temporary link pages when Discord limits are exceeded (TTL based).

### Observability & Reproducibility
- **Portable logging paths**:
  - Logging now follows `config.log_dir` (env-driven) rather than hardcoding `L:\...` paths.
  - Guild logs and local log reader follow the same base directory.
- **Audit log secrecy + retention**:
  - Audit logs redact secret-like strings and bound args/result sizes.
  - Audit tables are pruned by retention/row limits (env-driven), with a periodic pruning loop in the web app.
- **CI/release pipeline made stricter and reproducible**:
  - Release workflow verifies tag == `VERSION`.
  - CI runs `ruff`, `mypy`, `compileall`, smoke tests without requiring real secrets.

### Upgrade Notes (If You Want Old Behavior)
If you previously relied on “startup auto-open” and “startup auto-tunnel”, set these in your `.env`:
- `ORA_AUTO_OPEN_LOCAL_INTERFACES=1`
- `ORA_AUTO_START_TUNNELS=1`
- `ORA_TUNNELS_ALLOW_QUICK=1` (only if you explicitly want quick tunnels without a named token)

## Per-Version Highlights (Quick Index)
- **v2026.2.9**: date-based releases + node/relay/approvals baseline + sandbox static repo inspection + approvals QoL knobs.
- **v5.1.14**: audit redaction + retention; MCP guardrails; browser error_id + error log endpoint.
- **v5.1.13**: empty final response fallback + less plan spam.
- **v5.1.12**: CI mypy fix (`Store.create_scheduled_task()` return).
- **v5.1.11**: Startup safety defaults (no auto browser/tunnels unless enabled).
- **v5.1.10**: Portable logging paths (no L:\ hardcoding).
- **v5.1.9**: Discord embed title length safety.
- **v5.1.8**: Risk-based approvals gate + tool audit (SQLite).
- **v5.1.6 / v5.1.7**: MCP tool server support + routing category.
- **v5.1.5**: Guild memory + router cap + final response robustness + CI convenience.
- **v5.1.4**: Core SSE retry robustness.
- **v5.1.3**: Owner-only scheduler scaffold (disabled by default).
- **v5.1.2**: Dynamic task board; cleanup guarantees; download page cleanup loop.
- **v5.1.0 / v5.0.0**: Architecture diagrams + reproducible release alignment.
