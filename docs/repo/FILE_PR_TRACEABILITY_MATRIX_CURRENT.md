# Current File / PR Traceability Matrix

Status: current public-safe file-to-PR traceability pointer for the YonerAI public repository.

This file is the maintained traceability entrypoint. Dated matrices remain historical snapshots. The goal is to explain root-visible files and important public surfaces without mass-touching files only to alter GitHub root "Last commit message" rows. That GitHub column reports the latest commit that touched each path; it is not a file description field.

## Verification Snapshot

- Current main at matrix creation: `e54dc975e7f6ba7e99d3f250e98817b9019b49f6`
- Latest GitHub Release observed in this goal: `v2026.5.21.5`
- GitHub Release/tag action in this goal: none
- Recent merged traceability/process PR: #260
- Recent public runnable smoke PRs: #256, #257, #258, #259
- Existing root cleanup evidence: `docs/repo/ROOT_PHYSICAL_CLEANUP_DECISION_2026_05_21.md`
- Historical dated matrix: `docs/repo/FILE_PR_TRACEABILITY_MATRIX_2026_05_21.md`

## Current Matrix

| path | what it is | current status | latest relevant PR / evidence | latest security/hardening PR if known | latest professionalization PR if known | stay in root | next safe action | owner decision required |
|---|---|---|---|---|---|---|---|---|
| `.env.example` | Sample environment template | Public-safe placeholder | Existing public template | Earlier secret-scrub work; current goal made no env changes | Public presentation stream | yes | Keep scrubbed; never add real values. | no |
| `.github` | Workflows and PR template | Public automation config | #260 updates PR template traceability checklist | n/a | #260 | yes | Keep workflow/template changes narrow. | no |
| `.gitignore` | Ignore policy | Repository config | Existing root index | n/a | Public presentation stream | yes | Keep. | no |
| `AGENTS.md` | Repo operating instructions | Contributor guidance | #260 merge-subject policy | Release governance reset stream | #260 | yes | Keep durable rules only; avoid phase-specific truth. | no |
| `CHANGELOG.md` | Historical changelog | Public history | Existing root index | n/a | Release governance stream | yes | Keep; prefer checkpoint notes under `docs/changelog/checkpoints/` when needed. | no |
| `CONTRIBUTING.md` | Contribution guide | Public process | Existing root index | n/a | Public presentation stream | yes | Keep. | maybe for legal/process wording |
| `Dockerfile` | Container entrypoint | Runtime config | Existing root index | n/a | Root surface stream | yes | Do not move without container validation. | yes |
| `LICENSE` | License | Legal root file | Existing root index | n/a | n/a | yes | Keep. | yes |
| `PRODUCT_NAME` | Product identity marker | Public identity | Existing root index | n/a | Public naming stream | yes | Keep. | no |
| `README.md` | English first screen | Public product surface | #252 home consistency; this matrix link | Release governance reset stream | #252 | yes | Keep product-first and link current traceability. | no |
| `README_JP.md` | Japanese first screen | Public product surface with known mojibake debt | #252 home consistency; this matrix link | n/a | #252 | yes | Separate UTF-8/mojibake cleanup lane; do not rewrite in traceability PR. | no |
| `VERSION` | Version marker | Repository metadata | Existing root index | n/a | Release governance stream | yes | Keep until a real public runnable release lane updates it. | no |
| `assets` | Shared assets | Public resources | Existing root index | n/a | Root surface stream | yes | Inventory only when asset surface grows. | no |
| `clients/cli` | Public CLI package | Public MVP CLI surface | #258 adds `yonerai smoke`; prior CLI commands | #258 avoids credential/live provider requirements | #258 | yes | Keep CLI smoke connected to public MVP contract. | no |
| `clients/web` | Temporary public Web smoke-demo surface | Public MVP demo, not final Web UI | Earlier Web MVP stream; current goal no web changes | n/a | Public MVP stream | yes | Keep non-claiming; validate before final Web claims. | no |
| `config` | Config helpers/data directory | Mixed config helpers | Existing root index | n/a | Root surface stream | yes | Review config path migration separately. | maybe |
| `config.yaml` | Legacy root config read by current code | Active legacy config | Root cleanup decision 2026-05-21 | n/a | Root surface stream | yes for now | Do not move until `src/config.py` and MCP config loading support a new path with tests. | yes |
| `core` | Public Core API package | Public active core | #257 managed download smoke; #255 env isolation | #254 managed final-download URL restrictions | #257 | yes | Keep API contract authority and public smoke coverage. | no |
| `core/src/ora_core/brain/process.py` | Agent/file-result bridge behavior | Public contract-adjacent core | #254 restricts final downloads to managed file URLs; #257 smoke covers contract | #254 | #257 | n/a | Keep managed-download guard covered by public smoke tests. | no |
| `docker-compose.yml` | Local compose profile | Runtime config | Existing root index | n/a | Root surface stream | yes | Keep conventional root placement until compose validation lane. | maybe |
| `docker-compose.prod.yml` | Production-named compose profile | Runtime config, not a production-readiness claim | Existing root index | n/a | Root surface stream | yes for now | Review name/placement in deploy-boundary lane. | yes |
| `docs` | Contracts, process, repo policy, architecture | Public docs | #260 and current matrix | Release governance reset stream | #260 | yes | Keep topic-organized; avoid GitHub Releases for checkpoints. | no |
| `docs/repo/FILE_PR_TRACEABILITY_MATRIX_CURRENT.md` | Maintained root/file traceability pointer | Current traceability source | Current PR | n/a | Current PR | n/a | Update this file instead of creating new root-touch churn. | no |
| `docs/process/YONERAI_CODEX_WORKFLOW.md` | Durable Codex workflow | Process source of truth | #260 merge subject policy | Release governance reset stream | #260 | n/a | Keep delivery rules current and stable. | no |
| `main.py` | Runtime entrypoint | Active entrypoint | Root cleanup decision 2026-05-21 | n/a | Root surface stream | yes | Do not move without Docker, compose, scripts, docs, and tests changing together. | yes |
| `memory` | Memory-related package/data surface | Not public persistent-memory completion | Existing root index | Memory quarantine/public boundary streams | Public MVP stream | yes for now | Keep non-claiming; no persistent memory additions without approved lane. | yes |
| `pyproject.toml` | Python project config | Tooling config | Existing root index | #256 optional test dependency behavior depends on test tooling | Root surface stream | yes | Keep. | no |
| `pytest.ini` | Test config | Test config | Existing root index | #256, #257, #258, #259 all rely on pytest lanes | Public MVP stream | yes | Keep. | no |
| `reference_clawdbot` | Gitlink/submodule-like residue | Explicit do-not-touch boundary | Existing root index | n/a | Root surface stream | yes until owner-approved cleanup | Do not initialize, repair, remove, replace, stage, or edit. | yes |
| `requirements-optional-memory.txt` | Optional memory dependencies | Optional dependency lane | Existing root index | n/a | Memory policy stream | yes | Review with memory/dependency lane only. | maybe |
| `requirements.txt` | Python dependencies | Runtime/test dependency root | #256 made Playwright optional instead of forcing dependency | #256 | Public MVP stream | yes | Avoid broad dependency churn. | no |
| `scripts/dev/public_mvp_smoke.py` | Credential-free public smoke harness | Public runnable MVP entrypoint | #257 managed download smoke; #253 output; #255 env isolation | #254 and #257 | #253, #257 | n/a | Keep deterministic and credential-free. | no |
| `scripts` | Setup/debug/runtime helpers | Mixed tools | Existing root index | n/a | Root surface stream | yes | Continue only validated helper moves. | maybe |
| `src` | Legacy/runtime/private-adjacent code | Mixed boundary surface | Multiple security/runtime lanes | #259 MCP deny policy; prior #216 security/runtime stream | Public repo cleanup stream | yes for now | Do not treat all `src` as public-ready. | yes |
| `src/cogs/mcp.py` | MCP runtime integration | Runtime integration with default-deny policy | #259 runtime deny policy coverage | #259 | #259 | n/a | Keep policy helpers tested; no live MCP execution required for public smoke. | no |
| `src/cogs/mcp_policy.py` | MCP pure policy helpers | Public-safe policy helper module | #259 introduced default-deny policy coverage | #259 | #259 | n/a | Add narrow pure-helper tests for future changes. | no |
| `src/cogs/ora.py` | Large legacy ORA cog | Unresolved private/runtime/control-plane boundary residue | #244 first pure-helper extraction; current goal read-only | Earlier admin/security guard streams | Large-codebase inventory streams | n/a | Only touch with characterization tests and behavior-preserving extraction scope. | yes |
| `start.sh` | Shell launcher | Active legacy launcher | Root cleanup decision 2026-05-21 | n/a | Root surface stream | yes | Move only after setup wizard/reference validation or root shim decision. | maybe |
| `start_all.bat` | Windows launcher wrapper | Uncertain owner workflow entrypoint | Root cleanup decision 2026-05-21; current re-audit found no safe shimless move | n/a | Root surface stream | yes for now | Owner workflow confirmation or compatibility shim required before moving. | yes |
| `start_vllm.bat` | Local model launcher | Active local helper referenced by resource manager | Root cleanup decision 2026-05-21 | n/a | Root surface stream | yes | Redesign `src/managers/resource_manager.py` reference before moving. | yes |
| `start_windows.bat` | Windows launcher | Active legacy launcher | Root cleanup decision 2026-05-21 | n/a | Root surface stream | yes | Setup wizard and Windows quick-start migration required before moving. | maybe |
| `templates` | Prompts/templates | Public/reference resources | Existing root index | n/a | Root surface stream | yes | Inventory before wiring runtime behavior. | maybe |
| `tests` | Regression tests | Validation surface | #256, #257, #258, #259 public smoke/runtime tests | #254, #259 | #256-#259 | yes | Keep narrow tests tied to specific lanes. | no |
| `tools` | Maintenance/debug/media helpers | Public maintenance folder | Earlier validated root helper moves | n/a | Root cleanup stream | yes | Keep moved helpers out of root; do not run unsafe maintenance helpers without owner approval. | no |

## Root Cleanup Decision

No root-visible file should be moved only for visual cleanup. The current safe next actions are:

- `start_all.bat`: owner workflow confirmation or root compatibility shim before move.
- `start.sh` / `start_windows.bat`: update `scripts/setup_wizard.py`, docs, and launcher smoke before move.
- `start_vllm.bat`: update resource-manager and local model launcher references before move.
- `config.yaml`: add tested config-path fallback before move.
- `main.py`: update Docker, compose, scripts, docs, and tests together before move.

## Non-Claims

This matrix does not claim production readiness, shipping completeness, official cloud completion, Discord restored, persistent memory complete, Google login complete, final Web UI complete, Tools/MCP complete, full hybrid completion, broad ORA rename completion, `src/cogs/ora.py` resolution, all security backlog resolution, all dependency backlog resolution, Pass 2 landing, or v7.8 start.
