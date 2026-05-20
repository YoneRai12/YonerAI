# v7.7 Next Implementation Lanes 2026-05-21

Status: public-safe implementation lane board. This document turns the large-codebase inventory into actionable v7.7 follow-up lanes. It does not implement integrations, delete code, deploy, or start v7.8.

## Evidence Baseline

- `origin/main`: `e64299142bb68a731245b03678e8531dc18b36a9`
- Tracked files counted: `794`
- Largest current surfaces by rough line count:
  - `src/`: `185` files / about `46,109` lines, excluding line-level inspection of `src/cogs/ora.py`
  - `docs/`: `216` files / about `15,066` lines
  - `core/`: `55` files / about `9,391` lines
  - `tests/`: `76` files / about `8,518` lines
  - `clients/`: `29` files / about `8,121` lines
  - `tools/`: `98` files / about `6,099` lines
  - `scripts/`: `88` files / about `5,142` lines
- Current public active lanes remain Core API, local LLM loopback mode, local CLI smoke, Web smoke, hybrid policy fixture, capability boundary, Tools/MCP safe-subset contract, and self-evolution proposal-only.

## Top Connect Candidates

| rank | lane | affected paths | why it matters | risk | tests needed | owner approval | expected PR size | claim after completion | must not claim |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | API run error/schema refinement | `core/src/ora_core/api`, `tests/test_surface_api_run_contract.py`, API docs | API is contract authority for CLI/Web/local UI | leaking private errors or changing public routes | API run contract tests, public smoke, runtime env loader | no | small | public run contract is clearer and more deterministic | production API completion |
| 2 | CLI packaging/install smoke | `clients/cli`, README snippets, CLI tests | CLI is command authority for local public smoke | remote origin widening, secret output | CLI smoke tests, public smoke, secret scan | no | small/medium | local smoke CLI has better install/run UX | final CLI or native Japanese CLI completion |
| 3 | Web capability display smoke | `clients/web`, `docs/contracts/web-surface-capability-manifest-0.1.md` | Web is product surface; it should show current capability truth | final UI overclaim, Google/login drift | web lint/build, public smoke, capability fixture tests | no | medium | Web smoke surface aligns with capability manifest | final Web UI |
| 4 | Memory donation review fixture | `core/src/ora_core/hybrid`, memory policy docs/tests | v7.7 requires privacy-preserving learning and quarantine-first memory | accidental persistence | hybrid policy tests, memory quarantine tests | no | small | memory candidates remain quarantine-first with better fixture evidence | persistent memory |
| 5 | Self-evolution approval queue contract | `src/self_evolution`, docs/tests | self-evolution must stay proposal-only and approval-gated | automatic mutation / auto PR impression | proposal-only tests, audit shape tests | maybe | small | proposal queue contract is clearer | automatic self-evolution |
| 6 | Tools/MCP decision fixture | `docs/contracts/tools-mcp-safe-subset-0.1.md`, possible safe fixture tests | Tools/MCP needs deny-by-default evidence without runtime execution | accidental shell/tool enablement | docs scan, optional deny fixture tests | no | small | Tools/MCP safe subset has stronger evidence | Tools/MCP complete |
| 7 | Local provider model metadata fixture | `core/src/ora_core/llm`, local provider tests | Provider independence needs safe local metadata without external calls | provider ecosystem overclaim | local provider tests, no external call checks | no | small | local loopback metadata is safer | provider ecosystem completion |
| 8 | Public file/artifact contract hardening | `core/src/ora_core/distribution`, files tests | artifact references are security-sensitive | path traversal or file exposure | files API/distribution tests | no | small | public file refs are better constrained | private file ingestion |
| 9 | Root launcher migration pilot | `start_all.bat` or one launcher group, `scripts/launchers` | root professionalism with validated moves | breaking owner workflow | reference scan, public smoke, CLI smoke if relevant | yes for active launchers | small | one launcher is moved safely | root fully clean |
| 10 | README_JP UTF-8 restoration | `README_JP.md`, text hygiene docs | public first screen is visibly mojibake in local output | mistranslation or overclaim | mojibake/hidden Unicode scan, docs diff check | no | small | Japanese public first screen is readable | product completion |

## Top Retire Candidates

These are not delete-now items. They need owner review or a dedicated replacement lane.

| rank | candidate | affected paths | why retire candidate | current blocker |
|---:|---|---|---|---|
| 1 | legacy removal helper | `tools/maintenance/remove_legacy.ps1` | can rewrite runtime files if executed | owner-approved `src/cogs/ora.py` extraction lane required |
| 2 | obsolete root launcher wrapper | `start_all.bat` | unclear active workflow, root clutter | owner workflow uncertainty |
| 3 | production-named compose profile wording | `docker-compose.prod.yml` | public repo must avoid production-ready impression | compose/deploy lane needed |
| 4 | dashboard direct maintenance helper | `tools/maintenance/run_dashboard_backend.py` | operator-ish helper, not product surface | dashboard boundary lane needed |
| 5 | broad setup/download scripts | `tools/setup/*` | local model/setup helpers can imply provider ecosystem completion | setup lane and non-claim framing needed |
| 6 | legacy debug scripts | `tools/debug/*`, `scripts/debug*` | useful for developers but noisy as product signal | tool/debug taxonomy lane needed |
| 7 | legacy memory package shape | `memory/`, optional memory requirements | can imply persistent memory | memory policy/storage gate needed |
| 8 | private-adjacent Discord runtime | `src/cogs/*`, `src/bot.py` | not public Core MVP | Discord/private runtime security lane needed |
| 9 | broad scripts with shell/process behavior | `scripts/*`, selected `src/utils/*` | Tools/MCP must not enable shell by default | safe-subset/tool audit lane needed |
| 10 | `reference_clawdbot` residue | `reference_clawdbot` | not part of public product surface | explicit do-not-touch without owner approval |

## Top Security-Review-Required Areas

| rank | area | affected paths | why review is required | next safe action |
|---:|---|---|---|---|
| 1 | Discord command authorization | `src/cogs/*`, open PRs #129/#131/#135 | auth and channel restrictions are security-sensitive | inspect without touching `src/cogs/ora.py`; patch only isolated non-forbidden files |
| 2 | Media/image fetching | open PRs #60/#132/#133, media paths | SSRF/DoS risk | reproduce current-main paths and patch small current-main issues |
| 3 | Local LLM access/loopback | open PRs #206/#207, `core` local provider paths | request-controlled endpoint and auth opt-in concerns | compare with merged #192/#216 tests; patch only if current-main gap remains |
| 4 | Dashboard/admin surfaces | `src/web`, dashboard helpers, PR #128 | path traversal/auth risk | reproduce current-main dashboard route before close/patch |
| 5 | Tools/MCP/shell/process helpers | `tools`, `scripts`, `src/utils` | no unrestricted shell/tool execution | keep contract-only until safe subset tests exist |
| 6 | Deploy/Cloudflare/tunnel helpers | `tools/cloudflare`, `scripts/install_cloudflared.ps1`, tunnel scripts | live ops and route-map risk | route to private/control-plane docs only |
| 7 | Memory/vector/Chroma | `memory`, `src/services/vector_memory.py`, optional deps | persistent memory and private data risk | quarantine-first storage policy before wiring |
| 8 | Provider/media dependencies | open dependency PRs #147/#148/#150 | runtime compatibility and external provider implications | lane-specific dependency validation |
| 9 | GitHub Actions release workflow | PRs #6/#7/#34/#156 | release automation can mutate repo/releases | workflow lane with dry-run or docs-only evidence |
| 10 | `src/cogs/ora.py` | `src/cogs/ora.py` | explicit mixed boundary residue | owner-approved extraction lane only |

## Immediate Next Lanes

1. `codex/security-runtime-deep-pass-1`: inspect #206/#207 and local LLM current-main behavior; create a fresh patch only if current-main still has a reproducible gap.
2. `codex/security-runtime-deep-pass-2`: inspect media/dashboard PRs #128/#132/#133/#60; patch only isolated current-main issues that do not touch forbidden surfaces.
3. `codex/dependency-pr-lane-drain`: split GitHub Actions, Python runtime, Discord/crypto, provider/media, optional memory dependency PRs; close only superseded/no-alert items with evidence.
4. `codex/root-surface-physical-cleanup-pass`: try one reference-validated launcher or helper move only after file-to-PR traceability is merged.
5. `codex/release-alignment-current-checkpoint`: align GitHub Release presentation with markdown checkpoint stream after active docs PRs settle.
6. `codex/public-repo-presentation-pass`: restore `README_JP.md` readable UTF-8 and add/refresh PR template or SECURITY.md if needed.

## v7.8 Readiness

This board does not justify v7.8. It shows that v7.7 implementation evidence is still being accumulated. A v7.8 decision needs actual runtime/config/schema/test/release evidence, not only gap analysis.

## Non-Claims

This lane board does not claim production readiness, shipping completeness, official-cloud completion, live-ops completion, full product completion, hybrid completion, persistent memory completion, Google login, Discord gateway completion, provider ecosystem completion, final Web UI completion, Tools/MCP completion, all security backlog resolution, all dependency backlog resolution, Pass 2 landing, v7.8 start/completion, or `src/cogs/ora.py` resolution.
