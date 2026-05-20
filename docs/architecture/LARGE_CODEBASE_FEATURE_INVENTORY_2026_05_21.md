# Large Codebase Feature Inventory 2026-05-21

Status: public-safe inventory. This document classifies existing tracked code and docs against the v7.7 public boundary. It does not delete, wire, deploy, or claim completion of hidden functionality.

## Snapshot

- Tracked files at this inventory commit: 788
- Text-like lines counted, excluding `src/cogs/ora.py`: about 100,810
- `src/cogs/ora.py`: `DO_NOT_TOUCH`; excluded from line-level inspection in this pass.
- Current public posture: API/CLI/Web smoke surfaces are active, while Discord, memory, broad tools/MCP, deploy, private runtime, and control-plane integration remain separate lanes.

## Top-Level Inventory

| path | rough files | rough lines | purpose | classification | current public connection | risks | next safe action |
|---|---:|---:|---|---|---|---|---|
| `core/` | 55 | 9,325 | Public Core API, contracts, hybrid/public capability helpers | `PUBLIC_ACTIVE` | Health, public messages, run contract, local provider boundary, hybrid policy tests | Must not grow private/control-plane imports | Keep as API contract authority; add tests per narrow lane. |
| `clients/cli/` | 5 | 253 | Local smoke CLI; also included in the broader `clients/` total | `PUBLIC_ACTIVE` | `yonerai health`, `yonerai message`, `yonerai run` | Not final CLI; remote origins denied by policy | Keep local-only; native Japanese CLI remains separate. |
| `clients/web/` | 24 | 7,764 | Temporary Web Chat MVP / smoke-demo; also included in the broader `clients/` total | `PUBLIC_PARTIAL` | Mock/offline and loopback local provider smoke | Not final Web UI; dependency PRs remain open | Keep smoke scope; do not add Google login/final UI here. |
| `clients/` | 29 | 8,017 | Public client surfaces | `PUBLIC_PARTIAL` | CLI and Web smoke surfaces | Mixed web/node dependency state | Maintain lane separation: API, CLI, Web, Japanese CLI. |
| `docs/` | 210 | 13,733 | Contracts, release notes, maintenance, policies | `PUBLIC_ACTIVE` | Main public truth surface | Stale/future-dated historical notes and overclaim risk | Keep style guide and text hygiene scans active. |
| `tests/` | 76 | 8,423 | Public regression and contract tests | `PUBLIC_ACTIVE` | Smoke, security, hybrid, capability, CLI/API tests | Some tests describe non-public surfaces | Use targeted tests per lane; do not infer completion from mentions. |
| `src/` | 185 | 46,104 | Legacy/runtime/private-adjacent application code | `SECURITY_REVIEW_REQUIRED` | Some public docs refer to boundaries, but not public-ready as a whole | Discord/private/runtime/deploy/tool surfaces are mixed | Keep as inventory target; do not wire broadly. |
| `src/cogs/` | 39 | 15,487 | Discord cogs and runtime handlers; also included in the broader `src/` total, with `src/cogs/ora.py` excluded from line count | `PRIVATE_OR_CONTROL_PLANE_BOUNDARY` | Not part of current public Core MVP | Auth, Discord, command, and private runtime risks | Dedicated Discord/private runtime security review only. |
| `src/cogs/ora.py` | 1 | 0 | legacy boundary residue; intentionally excluded from line-level inspection | `DO_NOT_TOUCH` | Explicitly not solved | Large mixed runtime/control-plane surface | Separate extraction lane only. |
| `scripts/` | 88 | 5,037 | setup, debug, runtime, migration helpers | `SECURITY_REVIEW_REQUIRED` | Some setup/dev utility | Shell/deploy/local machine assumptions | Move only reference-validated helpers; no shell/tool execution expansion. |
| `tools/` | 97 | 6,031 | maintenance, debug, media, setup helpers | `CONNECT_CANDIDATE` | Public maintenance folder | Debug/deploy/helper code can look product-active | Keep categorized; add tool safe-subset contracts before runtime wiring. |
| `.github/` | 8 | 300 | CI and automation | `PUBLIC_ACTIVE` | Required checks on PRs | Dependency workflow PR backlog | Handle in dependency lane. |
| `config/` and `config.yaml` | 7 | 757 | runtime config | `SECURITY_REVIEW_REQUIRED` | Read by current legacy runtime code | Moving can break launchers; may expose legacy assumptions | Keep root config until references are redesigned. |
| `main.py` | 1 | 14 | runtime entrypoint | `CONNECT_CANDIDATE` | Docker/scripts reference it | Moving breaks launch path | Keep root until runtime entrypoint lane. |
| launch scripts | 4 | 61 | root start helpers | `UNKNOWN` | Local legacy launch workflows | User workflows and setup wizard references | Do not move without reference validation. |
| compose files | 2 | 67 | local/container profiles | `CONNECT_CANDIDATE` | Docker/local run support | `prod` wording can overclaim | Keep, clarify non-production. |
| `memory/` and optional memory requirements | 2 | 25 | memory-related package/dependencies | `PUBLIC_CONTRACT_ONLY` | Memory policy docs only | Persistent-memory overclaim risk | Keep quarantine/policy wording; no persistent memory. |
| `templates/` | 4 | 1,692 | prompts/templates | `CONNECT_CANDIDATE` | Not current public MVP | May imply agent/tool behavior | Inventory before exposing. |
| `assets/` | 2 | 0 | static assets | `PUBLIC_PARTIAL` | Public resources | Ownership and product branding review | Keep. |
| `reference_clawdbot` | 1 | 0 | gitlink/submodule residue | `DO_NOT_TOUCH` | None | Broken or external reference risk | Do not initialize, repair, remove, replace, or stage. |

## Feature Marker Counts

These are keyword counts by tracked file presence, not proof of release-ready capability.

| marker | file count | interpretation |
|---|---:|---|
| `API` | 354 | API language is central; public Core is active, but old runtime APIs also exist. |
| `CLI` | 325 | CLI is now a smoke surface plus docs; not final CLI. |
| `Web` | 277 | Web docs/client/runtime surfaces are broad; current public web is smoke-only. |
| `Discord` | 267 | Large Discord legacy/runtime surface remains. |
| `auth` | 190 | Auth appears across core, web, runtime, and docs; Google/login is not complete. |
| `memory` | 153 | Memory is heavily referenced but not persistent public memory. |
| `provider` | 150 | Provider independence is central; external live provider generation remains out. |
| `tools` | 142 | Tools surface exists conceptually; runtime Tools/MCP remains bounded/disabled. |
| `Google` | 130 | Google appears in legacy/runtime/docs; no Google login claim. |
| `OpenAI` | 100 | Provider references exist; not provider ecosystem completion. |
| `image` | 91 | Media/image functionality exists but needs security review. |
| `deploy` | 86 | Deploy/ops references exist; public repo does not deploy. |
| `shell` | 83 | Shell/process helpers exist; public Tools/MCP denies shell execution by default. |
| `vision` | 67 | Vision/multimodal code exists but not public-ready as a full lane. |
| `MCP` | 63 | MCP appears in contracts/config; safe subset is contract-only. |
| `dashboard` | 56 | Dashboard surfaces exist; public product surface is not complete. |
| `self-evolution` | 44 | Public self-evolution is proposal-only. |
| `video` | 35 | Video/media helper code exists; not current public MVP. |
| `Gemini` | 27 | Provider/review mentions exist. |
| `Ollama` | 27 | Local LLM provider lane is active for loopback local mode. |
| `Anthropic` | 17 | Provider references exist; no live external provider claim. |
| `telemetry` | 17 | Telemetry references exist; no real telemetry collection added in public MVP. |
| `control plane` | 12 | Control-plane contract references exist; no official cloud runtime completion. |

## Can Be Deleted Now

No. This pass is inventory-only. Deleting or wiring large legacy surfaces would require owner decisions and focused tests.

## Can Be Connected Now

Only existing narrow public surfaces remain connected:

- public Core API health/message/run smoke;
- local CLI smoke;
- temporary Web smoke surface;
- local LLM loopback-only modes;
- proposal-only self-evolution;
- hybrid signed-envelope fixture/policy tests;
- public capability and Tools/MCP contract boundaries.

Everything else needs a fresh v7.7 lane with tests and boundary review.
