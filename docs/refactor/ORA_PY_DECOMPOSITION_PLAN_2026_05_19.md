# YonerAI `src/cogs/ora.py` Decomposition Plan 2026-05-19

Status: refactor architecture plan
Scope: boundary-first planning for splitting and renaming `src/cogs/ora.py`
Runtime behavior changed: no
Implementation status: not started

## 1. Summary

`src/cogs/ora.py` is too broad and should not remain the long-term module name.

It is current unresolved mixed runtime/control-plane residue. It coordinates Discord gateway behavior, official runtime behavior, host-control behavior, tool schema exposure, policy/approval boundaries, dynamic skills/MCP expansion, and compatibility surfaces.

This plan does not solve, land, or rename `src/cogs/ora.py`. It defines the smallest safe extraction order for a future implementation lane.

## 2. Current Responsibilities

| responsibility | current role | primary lane | risk |
|---|---|---|---|
| `ORACog` compatibility facade | existing object that other modules call directly | private runtime with public-safe contracts | removing attributes would break handlers and skills |
| Discord commands/events | slash commands, message handling, rank/credits/status/dataset surfaces | private runtime | user-facing behavior can change accidentally |
| chat/run dispatch | delegates prompts, attachments, tool calls, and traces | private runtime / public contracts | can widen capabilities or expose private metadata |
| runtime orchestration | cost manager, unified client, handlers, setup lifecycle | private runtime | constructor and reload behavior are fragile |
| SafeShell / subprocess / tunnel | host actions, process/tunnel control, local shell mediation | control-plane / private runtime | high-risk host control |
| file/code read | listing/search/read code surfaces | private runtime with policy gates | can expose private files or secrets |
| moderation | ban/kick/timeout and owner-only operations | private runtime | irreversible user/server actions |
| media/web tools | screenshots, browser actions, downloads, web/media helpers | private runtime; control-plane for host exposure | can expose private sessions or local state |
| dynamic tool registry | static schemas, dynamic skills, MCP/registry expansion | public manifest contract + private execution | capability widening risk |
| approvals/policy/audit | risk scoring, owner approval, audit decisions | public contract + private enforcement | bypass risk |
| relay/local node bridge | public protocol vs host supervision bridge | public contracts + private/control-plane implementation | hidden coupling between repos |

## 3. Proposed Target Names

| target | purpose | lane |
|---|---|---|
| `src/cogs/yonerai_gateway_cog.py` | thin Discord Cog shell and compatibility facade | private runtime adapter; public repo only while migration is staged |
| `src/cogs/ora_runtime/tool_catalog.py` | public-safe tool schema assembly and context filtering | public contract shape, private execution |
| `src/cogs/ora_runtime/permissions.py` | `_check_permission` wrapper and policy boundary | private runtime |
| `src/cogs/ora_runtime/message_gateway.py` | message trigger classification and ChatHandler delegation | private runtime |
| `src/cogs/ora_runtime/costs.py` | cost manager lifecycle and sync boundaries | private runtime |
| `src/cogs/ora_commands/identity.py` | login, whoami, privacy, account commands | private runtime |
| `src/cogs/ora_commands/datasets.py` | dataset add/list commands | private runtime |
| `src/cogs/ora_commands/system_status.py` | status, info, process and diagnostic commands | private/control-plane boundary |
| `src/safety/` | SafeShell, file/code read, moderation and policy gates | private runtime; public contracts only |
| `src/surfaces/discord/` | Discord-specific formatting and response adapters | private runtime |
| `src/surfaces/web/` | web-specific formatting and response adapters | public-safe client contracts or private runtime |
| `src/tools/registry.py` | dynamic tool registry contract and metadata | public manifest contract |
| `src/control_plane_bridge/` | public-safe interface contracts only | public contracts; no private/control-plane internals |

Private runtime inventory, live route maps, control-plane DDL, operational ledgers, break-glass internals, secret material, and private renderer truth must not move into the public repository.

## 4. Dependency And Responsibility Map

| file | current role | imports from | imported by / called by | risk | lane | refactor target | test coverage needed | notes |
|---|---|---|---|---|---|---|---|---|
| `src/cogs/ora.py` | monolithic Discord/runtime/control-plane residue | clients, handlers, tools, utilities, skills | `src/bot.py`, handlers, skills, tests | high | private runtime + control-plane split | facade shell plus extracted modules | facade contract, command registration, tool schemas | do not edit in this planning PR |
| `src/bot.py` | bot startup and manual `ORACog` construction | `src.cogs.ora` | runtime entrypoints | high | private runtime | keep constructor contract stable | import smoke and constructor tests | `setup(bot)` path must be treated separately |
| `src/cogs/handlers/chat_handler.py` | prompt/tool dispatch and context assembly | `ORACog` methods and `tool_handler` | Discord message flow | high | private runtime | message gateway and tool catalog interfaces | ChatHandler integration tests | depends on `get_context_tools` and tool dispatch shape |
| `src/cogs/handlers/swarm_orchestrator.py` | agent orchestration helper | chat/runtime helpers | chat flow | medium | private runtime | orchestration adapter | targeted unit tests | do not expand scope |
| `src/cogs/tools/tool_handler.py` | tool execution and risk/policy decisions | access control, approvals, handlers | ChatHandler and `ORACog` | high | private runtime | tool execution adapters | approval/policy regression tests | execution should not move before policy tests |
| `src/utils/agent_trace.py` | safe trace metadata helpers | utility code | chat/web trace paths | medium | public-safe summaries only | trace contract helper | no raw chain-of-thought tests | do not expose raw hidden reasoning |
| `core/src/ora_core/brain/process.py` | core processing | core contracts | Core API runtime | medium | public core | leave separate from Discord Cog | Core API smoke | do not couple to Discord runtime |
| `core/src/ora_core/main.py` | public Core API app entrypoint | core routes | public runnable MVP | low | public core | no change | `/health` smoke | current public MVP truth stays `/health` |
| `src/web/app.py` | web app surface | web/runtime helpers | web clients | medium | public/private depending route | surface adapter | route smoke if touched | Web chat is not complete |
| `src/web/static/*` | static web/operator/client files | static assets | web app | medium | public/private split | surface-specific assets | UI smoke if touched | operator surfaces need private boundary review |
| `src/skills/*` | dynamic skills | skill loader/tool code | `ORACog` / tool registry | high | public-safe skills + private adapters | explicit manifest-first packages | loader and manifest tests | arbitrary import behavior needs gating |
| `src/mcp/*` or MCP cog files | MCP dynamic tools | config/env/server metadata | tool registry | high | public contracts + private runtime | MCP policy adapter | default-deny tests | do not enable MCP here |
| `src/self_evolution/*` | proposal-only MVP draft in PR #169 | local fixture/schema only | tests/docs | medium | public-safe only if PR #169 is fixed | keep separate from `ora.py` | PR #169 review fixes | not merged at this checkpoint |
| `tools/ops/*` | operational tooling | local/runtime utilities | operator workflows | high | control-plane/private | control-plane contracts | no live ops in public | classify before any move |

## 5. Extraction Order

### Step 0: no-op import map and tests

Pin the current external `ORACog` facade:

- `handle_prompt`
- `get_context_tools`
- `_check_permission`
- `tool_handler`
- `vision_handler`
- `chat_handler`
- `cost_manager`
- `safe_shell`

No module move should occur until this compatibility contract is tested.

### Step 1: extract pure constants, config, and schema data

Move only pure values and schema metadata that have no side effects. Confirm imported data is identical.

### Step 2: extract pure formatting helpers

Move Discord/Web text formatting helpers only after snapshot-style tests prove output parity.

### Step 3: extract policy and approval wrappers

Wrap permission and approval checks without changing policy decisions.

### Step 4: extract tool registry adapter

Move tool schema assembly and context filtering into `tool_catalog`. Compare owner/non-owner/web/Discord tool lists before and after.

### Step 5: extract file/code read safety boundary

Move file/code read capability only after owner-only and denial tests exist.

### Step 6: extract subprocess and SafeShell boundary

Classify host-control behavior before moving it. Public repo should keep interfaces and contracts only; host execution belongs to private/control-plane lanes.

### Step 7: extract media/web boundary

Separate public-safe response formatting from browser/download/recording execution.

### Step 8: rename remaining Cog shell

Rename the thin Discord shell to `yonerai_gateway_cog.py` only after compatibility tests and import references are stable.

### Step 9: add compatibility shim if needed

Keep `src/cogs/ora.py` as a shim temporarily if import compatibility requires it.

### Step 10: remove shim after evidence

Remove the shim only after tests and docs prove no references remain.

## 6. Required Tests Per Step

| step | required validation |
|---|---|
| all steps | `git diff --check`, secret scan, local path scan, forbidden claim scan |
| Step 0 | import smoke, facade attribute contract, command registration smoke |
| Step 1 | pure schema equality tests |
| Step 2 | formatting parity tests |
| Step 3 | owner/sub-admin/user permission tests |
| Step 4 | tool list filtering tests for owner, non-owner, web, Discord |
| Step 5 | file/code read denial and owner-only tests |
| Step 6 | host-control negative tests; no subprocess/tunnel behavior change |
| Step 7 | browser/media/download safety tests |
| Step 8 | import compatibility and extension reload tests |
| Step 9 | deprecation warning and compatibility tests |
| Step 10 | no-reference scan and full targeted tests |

Public Core API `/health` smoke should remain green throughout, but it is not enough to prove Discord/runtime behavior.

## 7. Branch Plan

Use one extraction PR per boundary. Do not make a giant refactor PR.

| branch | goal |
|---|---|
| `refactor/ora-py-import-map` | add no-op import/dependency map and facade contract tests |
| `refactor/ora-py-formatting-helpers` | extract pure formatting helpers |
| `refactor/ora-py-policy-boundary` | extract permission/approval wrappers |
| `refactor/ora-py-tool-registry` | extract tool schema/catalog adapter |
| `refactor/ora-py-files-safeshell` | extract file/code read and SafeShell boundary after tests |
| `refactor/ora-py-discord-gateway-rename` | rename remaining thin Cog shell with compatibility shim |

## 8. Stop Conditions

Stop before implementation if any of these appear:

- a test failure requires behavior changes rather than test coverage
- private/control-plane implementation would be imported into public artifacts
- a capability would be widened
- a broad dependency cycle appears
- live secrets, live Discord, provider keys, deployment, tunnel, or VPS checks are required
- slash command names, SSE/chat behavior, or public Core API contracts would change
- `src/cogs/ora.py` must be edited before the no-op import map exists
- hidden reasoning, private route maps, operational ledgers, break-glass internals, or private renderer truth would need to be documented publicly

## 9. Non-Claims

- `src/cogs/ora.py` is not solved.
- `src/cogs/ora.py` is not landed.
- Pass 2 is not landed or completed.
- This plan does not implement Web chat, Google login, memory sync, Discord gateway completion, API completion, CLI completion, native Japanese CLI, SNS automation, official cloud, deployment, or production readiness.
