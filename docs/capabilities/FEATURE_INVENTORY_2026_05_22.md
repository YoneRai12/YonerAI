# YonerAI Feature Inventory 2026-05-22

Status: public-safe static inventory for the public repository. This is a releaseability map input, not a production-readiness claim.

## Scope

This inventory covers the public repository source tree, tests, docs, and temporary web surface. Private runtime and official control-plane repositories are referenced only as contract boundaries.

Classification values:

- `RELEASE_READY`: already part of a public checkpoint with tests and docs.
- `CONTRACT_READY`: contract shape exists, but runtime exposure still needs dedicated gate review.
- `TESTABLE_INTERNAL`: implementation exists and has some tests, but is not a public release surface.
- `PUBLIC_SAFE_BUT_NEEDS_DOCS`: public-safe code exists, but release wording/tests are incomplete.
- `PRIVATE_ONLY`: belongs behind private runtime or official runtime boundaries.
- `CONTROL_PLANE_ONLY`: belongs in official control-plane or host supervision lanes.
- `RETIRE`: remove from active product surface or keep only as historical context.
- `UNKNOWN`: do not expose until inspected in a dedicated lane.

## Inventory

| feature | files | current behavior | tests | releaseability | design area | risks | next action |
|---|---|---|---|---|---|---|---|
| Core API health smoke | `core/src/ora_core/main.py`, `tests/test_public_runnable_smoke.py` | `GET /health` returns `{"ok": true}` without provider keys. | health smoke test | `RELEASE_READY` | public Core baseline | Only proves local API is importable and reachable. | Keep as public runnable gate. |
| Public mock/offline message | `core/src/ora_core/api/routes/public_messages.py`, `core/src/ora_core/api/schemas/public_messages.py`, `tests/test_public_core_message_mvp.py` | `POST /v1/public/messages` returns deterministic offline mock reply. | public message tests | `RELEASE_READY` | public message contract | Not live AI, no memory, no tools. | Preserve stable response shape. |
| Conversation Session Scaffold | `core/src/ora_core/sessions.py`, `core/src/ora_core/api/routes/public_messages.py`, `tests/test_public_conversation_session_mvp.py` | Groups public messages by `session_id` / `conversation_id` and returns turn metadata. | new session scaffold tests | `RELEASE_READY` for non-persistent scaffold | same-experience session metadata | In-memory only; process restart clears it. | Use as base for later memory/identity contract, not as memory. |
| Loopback local LLM mode | `core/src/ora_core/providers/local_llm.py`, public message route, local LLM tests | `mode: "local"` calls loopback-only local runtimes. | provider and endpoint tests | `RELEASE_READY` | provider independence | Local runtime quality and model availability are external to YonerAI. | Add optional loopback-only model listing later. |
| Ollama provider | `core/src/ora_core/providers/local_llm.py` | Calls local Ollama-style `/api/chat`. | provider tests | `RELEASE_READY` | local provider adapter | No guarantee that a local model is installed. | Keep defaults conservative. |
| OpenAI-compatible local provider | `core/src/ora_core/providers/local_llm.py` | Calls loopback OpenAI-compatible `/v1/chat/completions` servers such as LM Studio, llama.cpp server, text-generation-webui, or LocalAI. | provider tests | `RELEASE_READY` | provider independence | Remote and LAN URLs must remain rejected. | Keep loopback guard as a release gate. |
| Temporary Web Chat MVP | `clients/web/app/page.tsx`, `clients/web/next.config.ts`, `clients/web/README.md` | Local smoke/demo UI can send mock/offline and local LLM messages to public Core. | lint/build expected for touched UI | `RELEASE_READY` as temporary demo only | Web smoke surface | Not final Web UI; old dashboard/login routes remain separate. | Keep labeled as temporary and avoid auth/memory expansion. |
| `clients/web` stale dashboard/login surfaces | `clients/web/app/login`, `clients/web/app/dashboard*`, dashboard components | Historical dashboard/auth code remains in the same Next app. | lint/type checks only | `TESTABLE_INTERNAL` | Web/admin boundary | Could be mistaken for complete product login/dashboard. | Dedicated cleanup or isolation lane. |
| Protected Core run API | `core/src/ora_core/api/routes/messages.py`, `core/src/ora_core/api/schemas/messages.py` | Auth-gated `/v1/messages` can create persisted runs/conversations. | distribution/idempotency tests | `TESTABLE_INTERNAL` | internal API / run lifecycle | Broader than public MVP and touches DB/background worker. | Keep separate from public `/v1/public/messages`. |
| Memory history route | `core/src/ora_core/api/routes/memory.py` | Auth-gated memory/history endpoint exists. | partial protected-route coverage | `PRIVATE_ONLY` until a memory policy scaffold lands | memory | Persistent memory is explicitly not claimed. | Do not expose through public MVP. |
| Core database/repository | `core/src/ora_core/database/*` | Users, identities, conversations, messages, runs, tool calls, file tickets. | distribution and repo-oriented tests | `TESTABLE_INTERNAL` | persistence | Too broad for public session scaffold. | Use only after memory/identity policy docs. |
| Access/auth boundary | `core/src/ora_core/api/dependencies/auth.py`, `core/src/ora_core/api/middleware/cloudflare_auth.py`, tests | Loopback/token gate and optional Cloudflare access strategy. | access/security tests | `CONTRACT_READY` | identity/security | Real login and official cloud auth are not complete. | Keep out of public smoke claim. |
| Google auth route | `core/src/ora_core/api/routes/google_auth.py` | OAuth-related route code exists but is not a public MVP claim. | older/partial tests | `UNKNOWN` / `PRIVATE_ONLY` | identity | Would imply real Google login if exposed. | Dedicated Google login lane only. |
| Public self-evolution proposal-only | `src/self_evolution/*`, `docs/SELF_EVOLUTION_*`, tests | Uses public/synthetic fixtures to create owner-reviewable proposals. | proposal-only tests | `CONTRACT_READY` / `RELEASE_READY` for proposal-only slice | self-evolution | Not real telemetry, no auto mutation. | Keep proposal-only wording strict. |
| Official control-plane contracts | `docs/contracts/CROSS_REPO_SAME_EXPERIENCE_MATRIX_2026_05_20.md`, `docs/contracts/OFFICIAL_CLOUD_CONTROL_PLANE_MVP_2026_05_20.md` | Public-safe contract for official cloud/control-plane boundary. | docs validation only | `CONTRACT_READY` | official cloud / same experience | Not deployed, not official-cloud complete. | Align future envelope/memory policy with these docs. |
| Distribution node contracts | `core/src/ora_core/distribution/*`, `docs/DISTRIBUTION_NODE_MVP.md`, distribution tests | Signed release verification, capability manifest, file refs, SSE event boundaries. | distribution tests | `CONTRACT_READY` | self-host/distribution | Wider release gate remains separate. | Keep as contract lane, not product completion. |
| Skills and MCP tooling | `src/skills/*`, `src/cogs/mcp.py`, `src/utils/mcp_client.py`, `core/src/ora_core/mcp/*` | Tool loading, external tool calls, capability and lease concepts exist. | mixed security/unit tests | `TESTABLE_INTERNAL` | tools/capabilities | Tool execution can cross private/control-plane boundaries. | Manifest-first public exposure only. |
| Policy, moderation, safety helpers | `src/utils/access_control.py`, `src/utils/policy_engine.py`, `src/utils/risk_scoring.py`, `src/utils/redaction.py`, `src/utils/safe_shell.py` | Runtime access control, risk scoring, redaction, safe shell helpers. | mixed tests | `CONTRACT_READY` / `TESTABLE_INTERNAL` | security/audit | Enforcement depends on caller; some paths need fail-closed review. | Keep as shared contracts until runtime gates are reviewed. |
| Approval/audit code | `src/utils/approvals.py`, `src/cogs/approvals_admin.py`, `src/storage.py`, tests | Approval request and audit mechanics exist. | approval API tests | `TESTABLE_INTERNAL` / `PRIVATE_ONLY` | approval gate | Private/runtime admin behavior and redaction need stricter gate. | Do not expose in public Core session scaffold. |
| Discord gateway/cogs | `src/cogs/*`, especially `src/cogs/ora.py` and handlers | Discord runtime, tools, SafeShell, tunnel, browser/media/moderation responsibilities are mixed. | many legacy tests, incomplete boundary tests | `PRIVATE_ONLY` / `UNKNOWN` | Discord/private runtime/control-plane | `src/cogs/ora.py` remains unresolved residue. | Do not edit; extract in dedicated boundary PRs only. |
| Legacy/static web runtime | `src/web/static/*`, `src/web/endpoints.py` | Legacy setup/operator/dashboard/browser-control surfaces. | limited tests | `PRIVATE_ONLY` / `CONTROL_PLANE_ONLY` / `UNKNOWN` | private web/operator surface | Could expose operator/admin behavior if treated as public UI. | Reclassify before any public use. |
| Retired `ora-ui` | retirement docs and removed package manifests | Removed from active public surface. | docs/security triage | `RETIRE` | UI/security hygiene | Do not resurrect as product foundation. | Keep closed unless owner reopens. |
| `reference_clawdbot` gitlink | `reference_clawdbot` | Historical/broken gitlink inventory only. | none | `UNKNOWN` / do-not-fix | legacy reference | Broken metadata should not block public Core. | Do not fix in this lane. |

## Current Releaseability Takeaway

The public repo is larger than the current public MVP. The releasable path is the narrow Core API contract plus local/mock provider boundaries, temporary web smoke, proposal-only self-evolution, and public-safe contracts. Discord, operator web, memory persistence, auth/login, and broad tool execution already have code fragments, but they are not release-ready public product features.
