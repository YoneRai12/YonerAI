# YonerAI System Changelog

See also: `docs/RELEASE_NOTES.md` (curated summary, v5.0.0 -> current).

## v0.15.0-alpha.1 (2026-06-03) - Status API Bridge
- Added the public Status API bridge through PR #500, covering status,
  components, incidents, releases, install state, and rate-limit status for
  status.yonerai.com and future private/AWS backend alignment.
- Added fixture-only CLI/TUI readers: `yonerai status check`,
  `yonerai api status`, TUI `/状態`, and doctor status summary integration.
- Added public status fixtures, JSON schemas, and AWS status API handoff docs
  without adding production AWS, production Oracle/cloud runtime, production
  Google login, live Discord, provider keys, or private runtime inventory.
- Hardened the Status API bridge through PR #501 so local or allowlisted status
  feeds reject private/reserved IP URLs, internal hostnames, AWS ARNs, local
  paths, and secret-like markers before printing public JSON.
- Local status-source read and JSON parse failures now return controlled CLI
  errors without echoing local absolute paths or raw private endpoints.

## v0.14.0-alpha.1 (2026-06-02) - Official API Contract
- Added the public official API contract through PR #498, covering status,
  account, rate-limit, conversation, sync preview/approve, Oracle run, and
  self-evolution proposal endpoints.
- Added JSON schemas, a fixture, and conformance tests for the official API
  contract while keeping production AWS, production Oracle, production Google
  login, and private content upload out of the public repo.
- Added `yonerai api status`, `yonerai api contract`, and
  `yonerai api rate-limit`, plus TUI `/API`, `/api`, and `/公式`.
- Added `docs/private_handoff/AWS_OFFICIAL_API_HANDOFF.md` and
  `docs/policy/API_RATE_LIMIT_POLICY.md` for the private/AWS implementation
  lane and public quota-contract behavior.
- Included the read-only/live-boundary fix from PR #497 so displayed live state
  matches the effective local safety boundary.
- Release notes now support a hidden `release-title` metadata comment so the
  GitHub Release title is not duplicated as a visible body heading.

## v0.13.0-alpha.2 (2026-06-02) - Agent Console Dogfood Patch
- Published a narrow dogfood patch through PR #494 after v0.13.0-alpha.1
  testing found permission/profile and preview mismatches.
- Made `/権限 read-only` and `/権限 dry-run-only` clear existing
  live-provider and network permissions so older `/live on` or `/network on`
  state is not preserved by stricter profiles.
- Made `/計画 <task>` and `/レビュー <text>` show public-safe
  planner/reviewer previews instead of only switching modes.
- Batched permission profile config updates into one load/save path.
- Added regression coverage for live/network clearing and `@researcher`
  previews.
- Stable promotion remains deferred: memory and agent-console UX still need
  more dogfood before v0.7.0 stable.

## v0.13.0-alpha.1 (2026-06-01) - Agent Console Runtime
- Added a Codex/opencode-style interaction layer through PR #492: command
  palette (`/コマンド`, `/パレット`, `/palette`), agent modes, planning/review
  screens, approval profile display, and documented English aliases.
- Added public-safe `@planner`, `@reviewer`, and `@researcher` previews. They
  show role/task framing and safety reminders without spawning autonomous
  workers, browsing, executing shell commands, pushing GitHub changes, creating
  releases, deploying, or calling live providers by default.
- Added regression coverage for `/mode plan`, `/mode build`, read-only aliases,
  hyphenated `/permissions` aliases, and read-only -> dry-run-only approval
  reset behavior.
- Preserved boundaries: no production Oracle/cloud runtime, no production
  Google login, no OpenAI shared traffic runtime, no live Discord, no
  automatic local-to-cloud private upload, no deploy/public tunnel, no
  arbitrary shell/file/tool execution, no provider key output/storage, no
  production signing/trust store, and no production network installer.

## v0.12.0-alpha.2 (2026-06-01) - Memory UX and Update Notice
- Published the recovered memory UX work through PR #488: `/記憶`,
  `/メモリ`, `/memory`, focused `/設定 記憶`, memory add/list/forget/sync
  preview actions, and `memory_used` id-only display in TUI/runtime surfaces.
- Kept memory status/settings metadata-only so they show counts and boundary
  flags without printing memory contents; explicit list remains the redacted
  memory-summary path.
- Honored memory settings across TUI and standalone CLI: memory-off blocks
  TUI writes, and `memory_cloud_preview off` blocks cloud-to-local preview.
- Made update notices non-blocking and session-aware: startup checks are reused
  after tasks, and disabling update notices during a session takes effect
  immediately.
- Hardened local memory path redaction for additional Unix-style local roots
  while avoiding slash-command/API false positives.
- Included current-main security and installer trust-root fixes from PRs #486
  and #487 without enabling production cloud memory, Google login, OpenAI
  shared traffic, live Discord, arbitrary shell/file/tool execution, production
  signing/trust, npm/winget, or production installer behavior.

## v0.12.0-alpha.1 (2026-06-01) - Memory Boundary Runtime
- Added the first public local memory boundary runtime with `MemoryRecord`,
  local JSONL storage, redacted summaries, local-private defaults, forget/delete
  support, and explicit audit reasons.
- Added `yonerai memory status`, `yonerai memory add`, `yonerai memory list`,
  `yonerai memory forget`, and `yonerai memory sync preview` for local memory
  inspection and contract-only sync decisions.
- Connected `ask --auto` and the redacted run ledger to memory ids only, so
  allowed procedural/shared preference memory can influence local runtime
  decisions without persisting raw memory content in the ledger.
- Added Japanese TUI memory commands `/記憶` and `/メモリ`.
- Redesigned `/設定` into focused category screens for language, provider,
  model, safety, memory, update, auth, and privacy instead of dumping every
  setting at once.
- Added deferred update policy fields for normal, recommended, security, and
  critical update notices while keeping auto-apply and forced silent update
  disabled.
- Added low-resolution self-evolution signal memory validation that rejects raw
  prompts, PII-like/private path data, and extra fields.
- Preserved boundaries: no production Oracle/cloud runtime, no production
  Google login, no OpenAI shared traffic runtime, no live Discord, no automatic
  local-to-cloud private memory upload, no deploy/public tunnel, no arbitrary
  shell/file/tool execution, no provider key output/storage, no production
  signing/trust store, and no production network installer.

## v0.11.0-alpha.1 (2026-05-31) - Account Sync and Oracle API Foundation
- Added public account identity, Google auth dry-run, cloud/local sync,
  sync-decision, sync-audit, Official API fixture, and rate-limit policy
  contracts.
- Added `yonerai sync status`, `yonerai sync preview`,
  `yonerai sync approve --dry-run`, `yonerai sync api-contract`, and
  `yonerai sync rate-limit`.
- Added `/同期` and `/sync` interactive entries so Japanese-first users can
  inspect the cloud/local sync boundary without enabling production cloud.
- Added a sanitized private YonerAIOracle handoff for future official backend
  alignment without committing private backend code to the public repository.
- Added v0.11 manifest, release note, and yonerai.com release/press/install
  content foundations for account sync and Official API contract testing.
- Preserved boundaries: no production Oracle/cloud runtime, no production
  Google login, no OpenAI shared traffic runtime, no live Discord, no
  automatic local-to-cloud private upload, no deploy/public tunnel, no
  arbitrary shell/file/tool execution, no provider key output/storage, no
  production signing/trust store, and no production network installer.

## v0.10.0-alpha.1 (2026-06-01) - Public Orchestration Boundary
- Added the `/状態` and `/ホーム` interactive entries so Japanese-first users
  can re-open the Mission Control status/header without remembering English
  aliases.
- Improved model/provider value completion while preserving loopback-only local
  LLM guidance and explicit live-provider opt-in.
- Fixed public Google OAuth web routes to return a dry-run contract response
  instead of attempting a production OAuth redirect or token exchange.
- Hardened Quality Wall scans across push/PR ranges, release-gate checks,
  local-path scanning, hidden Unicode/mojibake detection, and secret allowlists.
- Added v0.9/v0.10 yonerai.com release/press content foundations and moved the
  plan-only `install.ps1` default manifest/artifact to the current prerelease.
- Preserved boundaries: no production Oracle/cloud runtime, no production
  Google login, no OpenAI shared traffic runtime, no live Discord, no
  deploy/public tunnel, no arbitrary shell/file/tool execution, no provider key
  output/storage, no production signing/trust store, and no production network
  installer.

## v0.9.0-alpha.1 (2026-05-31) - TUI Value Completion and Quality Wall
- Added context-aware slash-command value completion for the Japanese-first
  interactive TUI, including provider, language, approval, workspace file
  access, ledger, live-provider, network, update-notice, and numbered settings.
- Kept English slash aliases compatible while keeping Japanese mode visually
  Japanese-first.
- Fixed provider value completion so suggested Anthropic/Gemini choices are
  accepted through the existing value canonicalization path.
- Hardened pre-v0.9 provider/local LLM/auth/privacy/hybrid/self-evolution/
  release-gate boundaries and expanded Quality Wall coverage.
- Preserved boundaries: no production Oracle/cloud runtime, no production
  Google login, no OpenAI shared traffic runtime, no live Discord, no
  deploy/public tunnel, no arbitrary shell/file/tool execution, no provider key
  output/storage, no production signing/trust store, and no production network
  installer.

## v0.8.0-alpha.1 (2026-05-31) - Official Install/Auth Boundary
- Hardened `install.ps1` as a plan-only installer skeleton that can read a
  local manifest and display artifact, SHA256, signature, and trust status
  without downloading, installing, mutating PATH, or executing remote code.
- Added v0.8 install/auth/privacy/self-evolution boundary planning and
  yonerai.com release/press/install content foundations.
- Added an official self-evolution boundary contract and a private/official
  YonerAIOracle handoff stub.
- Cleaned Japanese-first interactive CLI wording around provider/auth/privacy/
  safety/self-evolution/update surfaces while preserving English aliases.
- Preserved boundaries: no production Oracle/cloud runtime, no production
  Google login, no OpenAI shared traffic runtime, no live Discord, no
  deploy/public tunnel, no arbitrary shell/file/tool execution, no provider key
  output/storage, no production signing/trust store, and no production network
  installer.

## v0.7.0-alpha.1 (2026-05-31) - Official Bridge Foundation
- Added public-safe self-evolution proposal queue foundation with synthetic
  low-resolution signals only.
- Added `yonerai evolve status`, `yonerai evolve simulate`, and
  `yonerai evolve proposals list/show`.
- Added interactive `/自己進化` and `/evolve` status entry points.
- Added v0.7 prerelease release/site/press content foundations and a local
  prerelease manifest contract.
- Preserved boundaries: no production Oracle/cloud runtime, no production
  Google login, no OpenAI shared traffic runtime, no live Discord, no
  deploy/public tunnel, no arbitrary shell/file/tool execution, no provider key
  output/storage, no production signing/trust store, and no production network
  installer.

## v0.6.0 (2026-05-27) - CLI Local Runtime
- Promoted the v0.6 TUI runtime from alpha to a stable local CLI runtime slice.
- Added post-alpha product polish for the interactive home, settings, provider,
  local LLM, auth, privacy, history, task, agent, and update screens.
- Added Google OAuth dry-run and OpenAI shared-traffic status visibility while
  keeping production Google login, refresh-token storage, and shared traffic
  disabled.
- Added `update_notice_enabled` as a local non-secret setting; default remains
  off.
- Preserved Japanese-first slash suggestions while keeping English aliases
  compatible.
- Included post-alpha Quality Wall/security hardening: network-off live
  suppression, ledger permission hardening, update-check manifest path safety,
  PowerShell shell detection, and CI review fixes.
- Preserved boundaries: no production Oracle/cloud runtime, no live Discord, no
  deploy/public tunnel, no arbitrary shell/file/tool execution, no default live
  provider calls, no provider key output/storage, no production Google login,
  no OpenAI shared traffic, and no production signing/trust store.

## v0.6.0-alpha.1 (2026-05-27) - CLI TUI Runtime
- Added `prompt_toolkit` slash command completion and Rich terminal panels/status
  for the interactive `yonerai` / `yonerai chat` shell, with plain fallback for
  non-TTY and CI.
- Added Japanese-first slash candidates for `/設定`, `/モデル`, `/提供元`, `/安全`,
  `/履歴`, `/タスク`, `/エージェント`, `/更新`, and `/終了` while preserving English
  aliases.
- Added local non-secret model preference support through `yonerai config set
  model ...` and the interactive `/モデル` flow.
- Added `yonerai update check` and TUI `/更新` for local manifest update status
  without download, install, PATH mutation, remote execution, or admin request.
- Added `install.ps1` as a dry-run-only future one-command installer skeleton.
- Synchronized `releases/manifest.v0.6.0-alpha.1.json` with the actual
  workflow-uploaded GitHub Release ZIP asset hash and size, without moving the
  tag or changing the release asset.
- Preserved boundaries: no production Oracle/cloud runtime, no live Discord, no
  deploy/public tunnel, no arbitrary shell/file/tool execution, no default live
  provider calls, no provider key output/storage, and no production
  signing/trust store.

## v0.5.1 (2026-05-26) - Distribution Trust Update
- Hardened the local distribution path after v0.5.0 with a plan-first
  `install-local.ps1` bootstrap helper for extracted archives/checkouts.
- Added `releases/manifest.v0.5.1.json` for local manifest verification,
  install planning, and update planning against the v0.5.1 release asset.
- Made release archive generation content-tree based and excluded
  release-specific manifests from generated source archives so asset hashes can
  be recorded without a manifest/hash feedback loop.
- Added yonerai.com install/release/press content for v0.5.1.
- Kept the license posture source-available and noncommercial: PolyForm
  Noncommercial code, CC BY-NC-ND docs/assets, and reserved brand identity.
- Preserved boundaries: no production installer, no `irm ... | iex`, no remote
  execution, no PATH mutation by default, no production signing/trust store, no
  production Oracle/cloud runtime, no live Discord, and no npm/winget channel.

## v0.5.0 (2026-05-26) - CLI Local Runtime
- Promoted the local CLI runtime slice to the first non-prerelease semantic
  release for `yonerai` install-and-run usage.
- Validated that an installed `yonerai` console script starts the interactive
  CLI from a clean virtual environment.
- Added v0.5 Mission Control commands for task view, Local LLM setup guidance,
  live-provider mode, and network mode while preserving Japanese-first output
  and English aliases.
- Added provider capability negotiation and subagent fallback visibility.
- Fixed post-v0.4 review debt in task progress display and image context
  selection.
- Preserved boundaries: no production Oracle, no Official Managed Cloud runtime,
  no live Discord, no deploy/public tunnel, no arbitrary shell/file/tool
  execution, no default live provider calls, no provider key output/storage, and
  no production installer/signing/trust store.

## v0.4.0-alpha.1 (2026-05-26) - Mission Control CLI Slice
- Added Mission Control status to `yonerai` and `yonerai chat`: provider, route,
  local node, ledger, safety, live-provider state, run_id, progress, and plan.
- Added task progress for `ask --auto` with classify/route/provider/execution/
  review/result steps in JSON and redacted ledger events.
- Added `/エージェント` / `/agents` to show deterministic planner/researcher/
  implementer/tester/reviewer plans without starting uncontrolled agents.
- Hardened interactive pretty output against terminal control characters.
- Fixed current-main image follow-up review debt: stale prior image carryover and
  conflicting broad/follow-up image contracts.
- Preserved alpha runtime boundaries: no production Oracle, no Official Managed
  Cloud runtime, no live Discord, no deploy/public tunnel, no arbitrary
  shell/file/tool execution, no default live provider calls, and no provider key
  output or storage.

## v0.3.0-alpha.1 (2026-05-26) - Interactive CLI Slice
- Added `yonerai` and `yonerai chat` as a Japanese-first interactive terminal
  shell backed by the existing `ask --auto` runtime path.
- Added first-launch language selection and local non-secret CLI preferences
  through `yonerai config show/set`.
- Added Japanese slash command UI for settings, provider status, safety
  boundaries, run history, and run display while keeping English slash command
  aliases such as `/settings` available for compatibility.
- Fixed current-main P1/P2 review debt before release: public cloud-contract
  route metadata, SemVer-compatible CLI package version reporting, and
  controlled config/interactive setting errors.
- Hardened additional release-gate review blockers: Oracle stub private/local
  path routing, deployment word variants, relay `auto` URL trust checks, and
  public extension manifest redaction.
- Fixed post-merge P2 review debt before release: unknown extension
  capabilities remain distinct until evaluation while public output stays
  redacted, and relay pretty output treats `auto_resolved_loopback` as a safe
  loopback state.
- Fixed follow-up P1 review debt: duplicate unknown extension capabilities are
  redacted in public decision payloads instead of exposing normalized private
  capability names.
- Fixed local-dev Oracle stub import failures so `ask --auto` returns a
  controlled unavailable report when optional hybrid dependencies are missing.
- This remains a semantic alpha pre-release. It is not the date-tagged
  stable/latest GitHub Release stream (`v2026...`).
- Preserved alpha runtime boundaries: no production Oracle, no Official Managed
  Cloud runtime, no live Discord, no deploy/public tunnel, no arbitrary
  shell/file/tool execution, no default live provider calls, and no provider key
  output or storage.

## v0.2.0-alpha.1 (2026-05-26) - Real CLI Runtime Slice
- Added `yonerai providers` so users can inspect mock, local LLM,
  OpenAI-compatible, Anthropic, and Gemini readiness without printing keys or
  making provider calls.
- Improved `yonerai ask --auto --pretty --lang ja` and
  `yonerai runs list/show --pretty --lang ja` so non-engineers can see route,
  privacy, provider, ledger, and non-action boundaries without reading JSON.
- Reframed mock workspace-file behavior as Workspace File Access Guard, not a
  real file summarization feature.
- Added an AI CLI security/UX matrix and implemented release-gate guardrails
  from current review debt: dangerous risk hints, self-host public reasoning,
  strict bool audit flags, real task route metadata, Oracle ledger env support,
  and Hybrid loopback pretty status.
- Preserved hard boundaries: no production Oracle, no Official Managed Cloud
  runtime, no live Discord, no deploy/public tunnel, no arbitrary
  shell/file/tool execution, no default live provider calls, and no provider key
  output.

## v0.1.0-alpha.4 (2026-05-26) - CLI Auto Runtime Slice
- Added `yonerai ask --auto`, which classifies task difficulty/privacy,
  selects a safe route, executes mock/local-dev paths, returns a `run_id`, and
  records redacted ledger events when a ledger is explicitly requested.
- Connected auto routing to mock provider execution, loopback-only local LLM
  opt-in, mock search, local-dev Oracle stub envelopes, reviewer/subtask
  planning, workspace file access guard boundaries, and dangerous-task deny
  behavior.
- Extended `yonerai demo`, `yonerai doctor`, and `yonerai start --guided` so
  users can see the auto runtime path without live services.
- Preserved hard boundaries: no production Oracle, no Official Managed Cloud
  runtime, no live Discord, no public tunnel/deploy, no arbitrary shell/file/tool
  execution, no default live provider calls, and no private file content sent to
  cloud-contract candidates.

## v0.1.0-alpha.3 (2026-05-26) - Real Hybrid Execution Slice
- Added `yonerai hybrid run --pretty/--json`, a public-safe local-dev Hybrid
  execution slice that connects route preview, verified test Local Node session,
  in-memory relay transport, mock provider execution, redacted ledger events,
  and Oracle stub request/result envelopes with run IDs.
- Extended `yonerai demo`, `yonerai doctor`, and `yonerai start --guided` so
  non-engineers can see what runs locally, what is a stub, and what remains
  outside the public repo.
- Continued Hybrid wire/relay/route/oracle hardening through Local Node posture
  states, relay transport, audit events, extension manifest boundaries, session
  expiry validation, and dangerous cloud-candidate denial.
- Preserved hard boundaries: no production Oracle, no Official Managed Cloud
  runtime, no live Discord, no public tunnel/deploy, no production signing or
  trust store, no arbitrary shell/file/tool execution, and no default live
  provider calls.

## v0.1.0-alpha.2 (2026-05-22) - Capability Slice
- Corrected the existing `v0.1.0-alpha.2` release note into operation-manual
  style with command-by-command run guidance, explicit non-actions, immutable
  tag traceability, post-tag correction traceability, and a shorter GitHub
  Release title to avoid duplicate/overlapping URL preview text.
- Added opt-in external provider adapters for OpenAI-compatible, Anthropic, and Gemini paths while keeping default tests mock-only.
- Connected loopback-only local LLM behavior, mock provider execution, run ledger/history, workspace file summarization, mock search, SafeShell diagnostic planning, explicit local memory, synthetic Discord gateway fixtures, official status contracts, and installer dry-run planning into the CLI/demo surface.
- Expanded `yonerai demo`, `yonerai ask`, `yonerai plan`, `yonerai search`, `yonerai ops`, `yonerai memory`, `yonerai discord synthetic`, `yonerai status`, `yonerai manifest verify`, `yonerai install plan`, and `yonerai install plan-windows` as the public alpha capability slice.
- Reduced stale runtime PR debt after the alpha2 implementation and recorded release-gate evidence.
- Converted Issue #313 into the parent installer/bootstrap tracker and linked child issues #328 through #334 for remaining installer work.
- Preserved hard boundaries: no default live provider calls, no live Discord, no arbitrary shell, no arbitrary file read, no production Oracle/control-plane implementation, no production installer, no production signing keys, and no Official Managed Cloud runtime in the public repo.

## v0.1.0-alpha.1 (2026-05-21) - Public Demo Slice
- Added semantic pre-release tooling and GitHub prerelease workflow support for the first public runnable demo milestone.
- Polished `yonerai demo --pretty`, `yonerai demo --json`, and `yonerai quickstart` as the YonerAI CLI entry point.
- Connected managed download guard and Hybrid memory quarantine fixture outputs to the deterministic demo.
- Added embed image URL SSRF protection for Discord vision handling with regression tests.
- Added release body and readiness evidence while preserving the public boundary: Official Managed Cloud remains external contract-only in this public repository.

## v2026.4.7 (2026-04-07) - Public Node Bootability Hardening
- Removed `chromadb` from the default public-node install path so `pip install -r requirements.txt` no longer blocks initial setup on Windows when ChromaDB native extensions are unavailable.
- Added `requirements-optional-memory.txt` for operators who explicitly want ChromaDB-backed `VectorMemory`.
- Made `src/services/vector_memory.py` import ChromaDB lazily and fail with an actionable message only when semantic memory is actually enabled.
- Documented the optional memory dependency in `README.md` and `docs/ENV_FILES.md`.
- Added a regression test to ensure `VectorMemory` stays import-safe without the optional dependency installed.
- Updated `core-test` workflow triggers so the required branch policy check is emitted for all PRs to `main`, avoiding merge blocks on non-core changes.

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
- Logging now writes to `config.log_dir` (env-driven) instead of a legacy host-specific absolute log path.
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
