# ora.py Private Runtime / Control-Plane Boundary Plan 0.1

Status:

- C lane planning output
- docs/inventory only
- no runtime implementation
- no edits to `src/cogs/ora.py`
- no subprocess, tunnel, Discord gateway, approval, or policy behavior change

## Decision

`src/cogs/ora.py` is unresolved private/runtime/control-plane residue.

This plan does not solve, land, unblock, or narrow-patch `src/cogs/ora.py`.
Public narrow patching is insufficient because the file coordinates Discord gateway behavior, host process control, tunnel startup, file/code inspection, moderation, media/web automation, dynamic tools, approval policy, relay/local-node behavior, and MCP/skill expansion.

The next strict code lane must decide private runtime and control-plane boundaries before implementation.

## Current Inventory

| item | current file/path | observed role | public/private/control-plane lane | risk | proposed boundary | do-not-touch note |
|---|---|---|---|---|---|---|
| `src/cogs/ora.py` monolith | `src/cogs/ora.py:46`, `src/cogs/ora.py:176`, `src/cogs/ora.py:1868`, `src/cogs/ora.py:2979` | Discord cog aggregates clients, SafeShell, tool schema definitions, context filtering, dynamic skill/registry injection | private runtime primary; public only contracts/docs; control-plane for host/tunnel pieces | high coupling; unclear ownership; duplicate `_get_tool_schemas`; syntax-risk comments around schema body | split by capability boundary after owner decision: public contract, private Discord runtime adapter, control-plane host executor | do not edit in this lane; do not claim solved |
| Discord gateway/runtime behavior | `src/cogs/ora.py:253`, `src/cogs/handlers/chat_handler.py`, `src/cogs/tools/tool_handler.py:44` | Discord commands and message-driven tool dispatch | private runtime | user-facing gateway behavior can widen capabilities if mixed with public core | keep official Discord gateway in `YoneRai12/YonerAI-private`; public repo keeps schemas/contracts only | no gateway behavior change here |
| subprocess / tunnel startup | `src/cogs/ora.py:286`, `src/cogs/tools/tool_handler.py:587`, `src/cogs/tools/tool_handler.py:780`, `src/relay/main.py:59`, `src/relay/expose_cloudflare.py:50` | starts/kills ngrok, cloudflared, local API support processes | control-plane for host lifecycle; private runtime may request via contract | process kill/start can affect live host; tunnel URLs and logs can leak operational state | move host process authority to control-plane; expose request/status contract to private runtime | do not run or fix tunnel/subprocess behavior here |
| SafeShell | `src/cogs/ora.py:46`, `src/cogs/ora.py:180`, `src/cogs/ora.py:2802` | repo-root constrained file/shell mediation for code tools | private runtime with public-safe contract docs | file/code read can cross public/private boundaries; exact root selection matters | keep implementation private/runtime; public core defines allowed capability manifest and audit contract | do not widen read/write permissions |
| file/code read tools | `src/cogs/ora.py:2800`, `src/cogs/ora.py:2817`, `src/cogs/ora.py:2833`, `src/utils/access_control.py:54` | read/list/search code tools, owner-only classification | private runtime; public only capability names and policy spec | accidental exposure of private code, secrets, or raw production inventory | enforce owner-only/private profile; public repo documents capability and denial contract | do not add public access |
| moderation tools | `src/cogs/ora.py:2696`, `src/cogs/ora.py:2706`, `src/cogs/ora.py:2734`, `src/utils/access_control.py:75` | ban/kick/timeout tool schemas and owner-only policy | private runtime | irreversible server actions; user harm if policy widens | keep in private runtime with explicit approval/policy/audit requirements | no moderation behavior change |
| media/web tools | `src/cogs/ora.py:2421`, `src/cogs/ora.py:2464`, `src/cogs/ora.py:2479`, `src/cogs/ora.py:2494`, `src/cogs/ora.py:2507`, `src/cogs/tools/tool_handler.py:425`, `src/cogs/tools/tool_handler.py:1450` | remote browser, screenshot, search, download, screen record, navigation/action | private runtime for official UX; distribution/SNS only as separate lane; control-plane for tunnel hosting | browser automation, downloads, recording, and public tunnels are high capability | split UI contract from execution; host exposure belongs to control-plane; SNS remains distribution lane | do not implement Web/SNS/API/CLI here |
| dynamic tool registry | `src/cogs/ora.py:2987`, `src/cogs/ora.py:2997`, `src/cogs/tools/tool_handler.py:97` | combines static schemas, dynamic skills, registry metadata, risk scoring | public contract for manifest shape; private runtime for execution | capability widening if dynamic tools bypass registry/policy | require manifest-first registration, default-deny policy, risk metadata, and audit trace before execution | no registry behavior changes |
| skills loader | `src/skills/loader.py:22`, `src/skills/loader.py:51`, `src/skills/loader.py:77`, `src/skills/loader.py:109` | scans `src/skills`, imports `tool.py`, fallback schema, executes dynamic skill | public-safe skills may exist in public; official/private adapters in private runtime | importing arbitrary `tool.py` can run code during load; fallback schema can understate risk | split public-safe skill packages from official/private skills; require explicit manifest and policy metadata | do not move skills in this lane |
| MCP dynamic tools | `src/cogs/mcp.py:17`, `src/cogs/mcp.py:51`, `src/cogs/mcp.py:100`, `src/cogs/mcp.py:143`, `src/cogs/mcp.py:191` | disabled-by-default MCP servers, deny patterns, dynamic registration | public contract may describe config shape; private runtime executes; control-plane may supervise server processes | external tool servers can widen capabilities; env/config can be secret-bearing | keep default deny; require allowed tools, deny patterns, audit, and profile-aware policy before enabling | do not enable or configure MCP |
| approval / policy / tool audit | `src/cogs/tools/tool_handler.py:95`, `src/utils/access_control.py:26`, `src/utils/access_control.py:52`, `src/utils/approvals.py:169` | risk scoring, policy decision, owner-only allowlist, approval request | public policy contract plus private runtime enforcement | policy bypass exposes high-risk tools; approval traces may include sensitive args | keep public contract exact; private implementation stores redacted audit only; control-plane does not bypass approvals | no approval behavior change |
| relay / connector / local node | `src/relay/main.py:30`, `src/relay/expose_cloudflare.py:50`, `src/services/relay_node.py:106` | local relay, quick tunnel exposure, outbound node connector and HTTP proxy | control-plane for host exposure/supervision; private runtime for official node adapter; public for relay protocol | public URL, proxy body, pair code, process lifetime, and body-size limits need strict ownership | public repo keeps protocol/schema; private runtime owns official connector; control-plane owns host supervision and tunnel lifecycle | do not start services or alter relay |
| Internal Run API | `core/src/ora_core/api/routes/messages.py:15`, `core/src/ora_core/api/routes/runs.py:63`, `core/src/ora_core/api/routes/runs.py:97` | canonical `/messages`, `/runs/{run_id}/events`, and `/runs/{run_id}/results` public-core endpoints | public core | private Discord/web execution can be confused with public contract authority | keep endpoint semantics in public core; private/runtime adapters call or implement against the contract | do not widen endpoint scope here |
| SSE / `reasoning_summary` | `core/src/ora_core/api/routes/runs.py:47`, `core/src/ora_core/engine/simple_worker.py:7`, `docs/contracts/sse-run-events.md:99`, `docs/contracts/sse-run-events.md:120` | public-core shaping and sanitization for safe summary data | public-core exactness only | raw chain-of-thought, hidden route rationale, or private meta can leak if producer boundaries blur | keep public-core exactness scoped; private runtime and product UX must conform but are not closed by this plan | do not claim broader SSE/product exactness closure |
| distribution capability runner | `core/src/ora_core/distribution/capabilities.py:15`, `config/distribution/distribution_node_capabilities.json:5`, `core/src/ora_core/mcp/runner.py:45` | default-deny capability manifest and tool runner event boundary | public core for manifest/runner contract; private/control-plane for dangerous handlers | manifest drift can expose arbitrary shell, SQL, download, browser, or host actions | keep manifest-driven default deny; keep dangerous handlers outside public core unless public-safe and declared | do not allow arbitrary shell/write/deploy by default |
| remote/operator web surface | `src/web/static/remote.html:57`, `src/web/static/remote.html:109`, `src/web/static/operator.html:318` | browser API operator UI and remote screenshot/action surface | private runtime product surface; public only if reduced to public-safe client contract | remote browser control and screenshots can expose private sessions or local host state | keep official operator UX private; public artifacts may document safe API shape only | do not implement Web lane here |
| system control / override | `src/cogs/ora.py:2887`, `src/cogs/ora.py:2911`, `src/utils/access_control.py:72` | remote power/UI/volume/system override schemas | private runtime and control-plane only | host control and limiter override are not public-safe | require explicit owner approval and control-plane contract before any public exposure | do not implement or widen |
| public/private/control-plane boundary | `AGENTS.md`, `docs/CURRENT_PHASE_CONTEXT.md`, `docs/TRACEABILITY_MATRIX_0_19.md` | durable repo split and source-of-truth guardrails | all lanes | hidden coupling between repos if split is file-extension based | split by responsibility and contracts: public core, private official runtime, Oracle control-plane | do not import private internals into public artifacts |

## Boundary Rules For Next Code Lane

1. Public artifacts must not import private runtime or control-plane internals.
2. Cross-repo interaction must use contracts: API, event, files, auth claims, capability manifest, protocol, or schema.
3. Oracle host deploy/rollback/supervision/cloudflared behavior belongs to `YoneRai12/YonerAI-oracle-control-plane`.
4. Official Discord gateway, official app runtime, official yonerai.com runtime, operator/admin surfaces, and production UX belong to `YoneRai12/YonerAI-private`.
5. Common contracts, public-safe skill descriptions, public capability manifests, relay protocol docs, and public web client surfaces may remain in `YoneRai12/YonerAI`.
6. Capability widening must be default-deny and approval-gated.
7. Raw chain-of-thought, secrets, credentials, raw production inventory, live route maps, break-glass internals, and private renderer truth must not enter public artifacts.
8. SNS, API, CLI, native Japanese CLI, Web, and self-evolution are separate lanes and must not be used to justify `src/cogs/ora.py` runtime implementation in this lane.

## Required Owner Decisions Before Implementation

- which exact `src/cogs/ora.py` capabilities remain in private runtime
- which tunnel/process/supervision pieces move to control-plane
- whether any public-safe abstractions should be extracted before moving runtime code
- exact owner-only, operator-only, shared-user, and public-user tool policy
- approval/audit retention and redaction requirements
- relay/local-node trust boundary and pairing-code handling
- MCP server allowlist and dangerous-tool policy
- validation suite required before any split or code move

## Non-Claims

- `src/cogs/ora.py` has not landed.
- `src/cogs/ora.py` is not solved.
- Pass 2 has not landed.
- This document is not a public narrow patch.
- This document does not implement runtime, subprocess, tunnel, moderation, Web, SNS, API, CLI, native Japanese CLI, MCP, or approval behavior.
- This document does not claim shipping-complete, production-ready, official-cloud complete, live-ops complete, live operations complete, or full product complete.

## Next Strict Move

Open a dedicated implementation-planning batch that converts this inventory into a private/runtime/control-plane ownership map, then stop for owner approval before any `git mv`, import update, process-control change, or runtime behavior change.
