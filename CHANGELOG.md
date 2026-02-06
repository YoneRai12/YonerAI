# ORA System Changelog

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
