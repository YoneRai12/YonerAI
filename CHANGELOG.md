# YonerAI System Changelog

See also: `docs/RELEASE_NOTES.md` (curated summary, v5.0.0 -> current).

## v2026.2.15 (2026-02-15) - Discord Web Search/Music Fix + Core SSE Buffer
- Fixed ToolHandler dispatch for `web_search` and added an explicit admin guard for `web_action`.
- Fixed music tool wrappers to correctly resolve `MusicSkill` via `ORACog.tool_handler` (prevents "Music system not accessible").
- Core SSE event stream now buffers early events for late subscribers to prevent clients hanging when runs complete quickly.

## v2026.2.11 (2026-02-11) - Setup UI Overhaul + External API Stabilization + Tunnel Hardening
- Setup UI redesigned into a left-nav + section-card layout with:
  - JP/EN language toggle
  - Quick actions (Roles / Permissions / Approvals / Relay)
  - 4K-aware responsive scaling and improved readability.
- Added stable external agent API routes:
  - `POST /api/v1/agent/run`
  - `GET /api/v1/agent/runs/{run_id}/events`
  - `POST /api/v1/agent/runs/{run_id}/results`
- Hardened Web/API run-state management:
  - active run cap (`ORA_MAX_ACTIVE_RUNS`)
  - TTL cleanup (`ORA_RUN_STATE_TTL_SEC`)
  - loopback detection improved for proxy headers.
- Cloudflare/tunnel lifecycle hardened:
  - child process tracking
  - stale PID cleanup
  - graceful stop on shutdown
  - optional Windows new-console mode (`ORA_TUNNELS_NEW_CONSOLE`).
- Temporary download link path improved:
  - explicit public base URL support (`DOWNLOAD_PUBLIC_BASE_URL`)
  - better quick-tunnel URL reuse/fallback behavior.
- Mention music flow split into dedicated handler:
  - extracted to `mention_music_handler.py`
  - playlist behavior env toggle (`ORA_MUSIC_MENTION_PLAYLIST_MODE`).
- Added deployment/operations docs:
  - `docs/VPS_DEPLOYMENT.md`
  - `docs/DOMAIN_ROUTES.md`
  - `deploy/docker-compose.vps.yml`
  - `Dockerfile.vps`.

## v2026.2.9 (2026-02-09) - Date-Based Release + Distributed Baseline (Node/Relay/Approvals)
- Switched to date-based versioning (`YYYY.M.D`) via `VERSION` (release tag: `v2026.2.9`).
- M1/M1.5/M3: profile isolation (`private/shared`), out-of-band approvals, and shared/guest policy as code.
- M2/M2.5: Relay MVP (WS + pairing + http proxy) + hardening (mux, caps, timeout, cleanup).
- Cloudflare Quick Tunnel expose mode switchable via `.env`.
- Added sandbox repo static inspection tools (download GitHub ZIP, no code execution).
- Added `.env` knobs to reduce approval friction for owner / shared guests while keeping safe defaults.
- Expanded the default non-owner allowlist with "everyday" Discord features (VC join/leave, TTS, music controls) + safe web search.
- Added `web_search_api` (SerpApi/DDG) as a **safe** web search tool (no browser automation, no downloads).
- Music UX improvements (Discord):
  - Mention-based playback now supports: YouTube URL, audio attachments, and plain search queries.
  - Optional Discord-native scroll picker (Select menu) for choosing a track from search results (`ORA_MUSIC_NATIVE_PICKER=1`).
  - Mention + playlist URL now supports queue-all in the background (YouTube playlists + Spotify playlists/albums mapped to YouTube search).
- Tool schemas now include all central registry tools in context (not only `mcp__*`), while runtime allowlists still enforce safety.

## v5.1.14 (2026-02-06) - Audit Secrecy + MCP Guardrails + Browser Observability
- Added centralized redaction helpers for secrets (`src/utils/redaction.py`) and applied them to audit/storage and MCP command logging.
- Audit DB is now bounded by retention/size limits (env-driven), with periodic pruning to prevent unbounded growth.
- Tool audit now stores redacted + size-bounded args/result previews and updates the final result preview after tool execution.
- Hardened MCP tool exposure: deny patterns by default, optional per-server allowlist, and an explicit escape hatch for dangerous tools.
- Web remote control observability: browser API failures now emit an `error_id`, write structured error context logs, and provide an admin-only endpoint to fetch recent error tails.
- Fixed duplicate `/system/refresh_profiles` route and restored correct `Store.create_scheduled_task()` return value (CI: ruff/mypy/smoke).

## v5.1.13 (2026-02-06) - Empty Reply Guard + Less Plan Spam
- Added a chat-level audit table `chat_events` and logs `empty_final_fallback` occurrences (correlation_id/run_id).
- When Core returns an empty final response, ORA now sends a traceable fallback (CID/Run short IDs) instead of a vague message.
- Execution Plan cards are only shown when the request is complex or explicitly asks for a plan.

## v5.1.12 (2026-02-06) - CI Fix (Mypy)
- Fixed missing return in `Store.create_scheduled_task()` so `mypy src/` passes in GitHub Actions.

## v5.1.11 (2026-02-06) - Safe Startup Defaults (No Auto-Expose)
- Startup no longer auto-opens local browser UIs unless `ORA_AUTO_OPEN_LOCAL_INTERFACES=1`.
- Startup no longer auto-starts Cloudflare tunnels unless `ORA_AUTO_START_TUNNELS=1`.
- Quick tunnels (trycloudflare) are blocked by default unless `ORA_TUNNELS_ALLOW_QUICK=1`.

## v5.1.10 (2026-02-06) - Portable Logging Paths
- Logging now writes to `config.log_dir` (env-driven) instead of hardcoding `L:\\ORA_Logs`.
- Guild chat logs and LocalLogReader now follow the same portable log directory.

## v5.1.9 (2026-02-06) - Discord Embed Safety + Release Bump
- Prevents Discord API 400s by truncating agent-activity embed titles to the 256-char limit.
- Bumped `VERSION` and README header to match the new tag.

## v5.1.8 (2026-02-06) - Risk-Based Approvals + Tool Audit
- Added risk scoring and an approvals gate at the ToolHandler "execute" boundary.
- Owner also requires approvals for HIGH+ risk; CRITICAL requires a confirmation code (modal).
- Added audit logging (JSONL tracing + SQLite tables `tool_audit` and `approval_requests`).

## v5.1.7 (2026-02-06) - MCP Routing Support
- Tool router now has an `MCP` category so MCP tools can actually be selected when the user asks for MCP usage.

## v5.1.6 (2026-02-06) - MCP Tool Server Support (Client)
### MCP Integration (Disabled by Default)
- Added an MCP stdio client and an `MCPCog` that can connect to MCP servers and expose their tools as ORA tools.
- MCP tools are registered dynamically as `mcp__<server>__<tool>`.
- Execution is routed through ORA's ToolHandler with `tool_name` passed through (backward compatible).
- Config examples: `ORA_MCP_ENABLED=1` and `ORA_MCP_SERVERS_JSON=[{\"name\":\"codex\",\"command\":\"codex mcp-server\"}]`

## v5.1.5 (2026-02-06) - Stability + Server Context Memory
### Final Text Robustness
- Final output now extracts text from multiple Core payload shapes (not only `data.text`), reducing empty replies after tool loops.

### Tool Router Hardening
- Router no longer dumps most tools into a single "SYSTEM_UTIL" bucket.
- Added a hard cap (`ORA_ROUTER_MAX_TOOLS`, default 10) to avoid huge tool lists (e.g., 29 tools).
- Added a `CODEBASE` category so code inspection tools are only exposed for code/repo/debug requests.

### Guild/Server Memory (New)
- Added guild-level memory file `memory/guilds/<guild_id>.json` (public-only aggregation).
- ChatHandler injects `[GUILD MEMORY]` into the system context to bias acronym/domain disambiguation (e.g., VALORANT servers).
- Added a deterministic heuristic profiler that updates guild topics periodically (no LLM calls).

### CI/Test Reproducibility
- Tests can run without real secrets (Config falls back to a dummy token in CI/pytest contexts).
- Added `tests/conftest.py` so `import src...` works without manual `PYTHONPATH` setup.

## v5.1.4 (2026-02-06) - Core SSE Robustness
- Core SSE (`/v1/runs/{id}/events`) stream auto-retries within the timeout window on transient disconnects
  (e.g., chunked transfer errors), with best-effort de-duplication.

## v5.1.3 (2026-02-06) - Secure Automation Scaffold (Owner-Only)
- Added owner-only scheduled tasks stored in SQLite (`scheduled_tasks`, `scheduled_task_runs`).
- Scheduler is disabled by default (`ORA_SCHEDULER_ENABLED=0`).
- Automated runs are LLM-only (`available_tools=[]`) for reproducibility and safety.

## v5.1.2 (2026-02-06) - UX/Router Fixes + Cleanup Guarantees
- Task board is dynamic (no fixed 3-step template).
- Router avoids selecting remote browser/screenshot tools unless explicitly requested.
- Web API runs a periodic cleanup loop for expired temporary download entries (TTL=30 min).

## v5.1.1 (2026-02-06) - CI Fix + Memory/Download Robustness
- GitHub Actions smoke test can run without requiring real secrets.
- Prevents channel memory files from being treated as user files during cloud sync.
- `web_download` backward-compat for older `download_video_smart()` signatures.
- `web_screenshot` embed title is short/stable to avoid Discord's 256-char title hard limit.

## v5.1.0 (2026-02-06) - Diagram Clarity + Release Alignment
- README diagrams updated for readability (sequence diagrams + layered runtime view).
- Local reproducibility steps documented (`ruff`, `mypy`, `compileall`, `pytest smoke`).

## v5.0.0 (2026-02-06) - Core Loop Alignment & Reproducible Release
- Documented Hub/Spoke runtime flow and Mermaid diagrams.
- Release workflow enforces `VERSION` + tag consistency.
- Re-validated secrets are loaded from `.env`/env vars (no hardcoded tokens).

## v4.2 (2026-01-10) - Security Hardening & NERV UI
- Transitioned to env-driven config (no hardcoded secrets).
- Added admin override UI improvements (visual red alert mode + telemetry).
- Healer/system permission checks refactored for multi-host setups.

## v4.1 (2026-01-05) - Agentic Stability & Self-Evolution
- Codex stabilization and routing fixes.
- Context awareness improvements (channel history fallback).
- Logging + pre-flight health checks improvements.
