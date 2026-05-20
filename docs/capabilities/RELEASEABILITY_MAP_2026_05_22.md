# YonerAI Releaseability Map 2026-05-22

Status: design-aligned releaseability map for current public repository code. This map is public-safe and intentionally omits private runtime inventory and control-plane internals.

## Already Released Checkpoints

| area | releaseability | design alignment | evidence | boundary |
|---|---|---|---|---|
| Core `/health` | `RELEASE_READY` | public Core baseline | `tests/test_public_runnable_smoke.py` | Credential-free local smoke only. |
| Public mock/offline message | `RELEASE_READY` | same message contract foundation | `tests/test_public_core_message_mvp.py` | No provider, no memory, no tools. |
| Loopback local LLM mode | `RELEASE_READY` | provider independence | `tests/test_local_llm_provider.py` | Loopback-only; no external provider keys. |
| Ollama and OpenAI-compatible local providers | `RELEASE_READY` | provider-neutral local adapter layer | local provider tests and docs | Remote/LAN URLs remain blocked. |
| Temporary `clients/web` Web Chat MVP | `RELEASE_READY` as demo | user-visible smoke surface | web lint/build lane | Not final UI. |
| Public self-evolution proposal-only | `RELEASE_READY` for proposal-only slice | approval-gated self-evolution | self-evolution proposal tests/docs | Synthetic/public fixtures only. |
| Official cloud/control-plane contracts | `CONTRACT_READY` | same-experience / public-private-control boundary | contract docs | Not deployed, not official-cloud complete. |

## Can Be Exposed With More Docs Or Tests

| area | current state | missing gate | next action |
|---|---|---|---|
| Conversation Session Scaffold | implemented as in-memory metadata on public message route | PR review and CI | Keep as non-persistent session metadata, then use as future memory/identity bridge. |
| Safe read-style skills | public-safe helper code exists | explicit API shape and capability docs | Manifest-first tool exposure lane. |
| Distribution node capability contracts | good contract/test slices exist | release gate and owner decision | Keep separate from public message MVP. |
| Local LLM model selection | request/config pass-through works | optional model listing if small | Add loopback-only model listing only after adapter tests. |

## Needs Contract Before Release

| area | reason | next contract |
|---|---|---|
| Memory persistence | public docs explicitly do not claim memory | memory policy scaffold and retention/redaction rules |
| Identity / login | Google/Cloudflare/auth code exists but product lane is incomplete | identity/session envelope with same-experience semantics |
| Protected run lifecycle | DB/background run path is broader than public message MVP | public/private run envelope and owner scope |
| Tool/MCP execution | capability policy exists, but execution can be private/control-plane risky | manifest-first public tool contract with fail-closed tests |
| Approval/audit runtime | useful policy concepts, but private admin behavior leaks risk | public-safe approval event schema and redaction tests |

## Needs Refactor

| area | why | next safe lane |
|---|---|---|
| `src/cogs/ora.py` | mixed Discord gateway, subprocess, tunnel, SafeShell, dynamic tool registry, media/web, moderation | continue `ora.py` boundary extraction plan without behavior changes |
| Legacy `src/web/static` and `src/web/endpoints.py` | operator/admin/dashboard/browser-control surfaces mixed with user web | classify private/control-plane vs public web before changing |
| `clients/web` stale dashboard/login routes | temporary chat page is usable, but historical routes remain | isolate or remove stale routes in a dedicated UI hygiene PR |
| Skill loader fallback behavior | import-time tool loading and fallback schema are not enough for public release | manifest-first registry and no fallback for public tools |

## Private Or Control-Plane Only

| area | target boundary | reason |
|---|---|---|
| Discord cogs and handlers | private runtime / official runtime | Discord token, guild state, runtime behavior, and operator tools are not public Core. |
| SafeShell / process / system control | private runtime or control-plane | Host-specific execution and supervision must not become public product surface. |
| Tunnels, deploy, rollback, supervision | control-plane | Oracle/VPS/host-specific facts belong in the control-plane lane. |
| Operator web/admin screens | private runtime/control-plane | Admin, browser-control, and settings surfaces need privileged boundaries. |

## Retire

| area | status | next action |
|---|---|---|
| `ora-ui` | retired from active public surface | Keep retired unless owner explicitly reopens. |
| obsolete dependency/security PRs for retired UI | not active product path | Close only with clear evidence and reason. |

## Unknown

| area | why unknown | safe action |
|---|---|---|
| `reference_clawdbot` | broken gitlink/submodule metadata observed historically | Inventory only; do not fix in public Core lanes. |
| old dashboard/auth UX claims | code exists but product and auth semantics are not release-gated | Do not claim until dedicated review. |
| media/video/operator tooling | environment and private runtime coupling likely | Keep internal until public-safe contracts exist. |

## Design Alignment Summary

- Provider independence: current public Core supports offline mock, Ollama local, and OpenAI-compatible local providers without external provider keys.
- Same experience: public message shape now includes session metadata that can align later with official cloud and private runtime envelopes.
- Self-evolution: public repo remains proposal-only; official queue semantics stay contract-bound and approval-gated.
- Public/private/control-plane boundary: public Core session scaffold stores metadata only and does not import private/control-plane internals.
- Release readiness: user-visible releaseable path is still narrow. Existing code is large, but much of it is private, control-plane, or testable-internal rather than public product-ready.
