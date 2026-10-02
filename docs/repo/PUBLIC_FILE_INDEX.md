# Public File Index

Status: public-safe root surface index for the v7.7 public repository.

## Purpose

This index explains what a reader sees at the GitHub root without pretending every visible file is final product surface. It is documentation only; it does not move, delete, initialize, or repair files.

For maintained file-to-PR traceability and current GitHub last-commit context, see [Current File / PR Traceability Matrix](FILE_PR_TRACEABILITY_MATRIX_CURRENT.md). The dated [File / PR Traceability Matrix 2026-05-21](FILE_PR_TRACEABILITY_MATRIX_2026_05_21.md) remains a historical snapshot. For the current root recheck after PR #218, see [Root Surface Inventory 2026-05-21](ROOT_SURFACE_INVENTORY_2026_05_21.md). For the latest reference-backed no-move decision, see [Root Physical Cleanup Decision 2026-05-21](ROOT_PHYSICAL_CLEANUP_DECISION_2026_05_21.md).

## Classification Key

| class | meaning |
|---|---|
| `KEEP_ROOT` | Belongs at root for common repository navigation or tooling. |
| `MOVE_TOOLS` | Candidate for a future tool/maintenance folder after reference validation. |
| `MOVE_SCRIPTS` | Candidate for a future script folder after launcher/reference validation. |
| `MOVE_CONFIG` | Candidate for config folder only if runtime references are updated and tested. |
| `CONNECT_CANDIDATE` | Useful code exists, but not wired into the current public MVP. |
| `RETIRE_CANDIDATE` | Looks obsolete or unsafe to present as active, but needs owner confirmation before removal. |
| `DO_NOT_TOUCH` | Do not move, repair, delete, initialize, or stage in this lane. |
| `UNKNOWN` | Not enough evidence to move safely. |

## Root File / Folder Index

| root entry | what it is | public status | current action | next safe action |
|---|---|---|---|---|
| `.env.example` | sample environment template | public-safe placeholder | `KEEP_ROOT` | Keep scrubbed; never add real env values. |
| `.github` | GitHub workflows and repo automation | public CI/config | `KEEP_ROOT` | Review dependency workflow PRs in a separate lane. |
| `.gitignore` | ignore policy | repository config | `KEEP_ROOT` | Keep. |
| `AGENTS.md` | repo operating instructions | contributor guidance | `KEEP_ROOT` | Keep stable rules only. |
| `CHANGELOG.md` | historical changelog | public history | `KEEP_ROOT` | Keep; prefer `docs/RELEASE_NOTES.md` for current checkpoints. |
| `CONTRIBUTING.md` | contributor guidance | public process | `KEEP_ROOT` | Keep. |
| `Dockerfile` | container entrypoint | runnable config | `KEEP_ROOT` | Keep until a dedicated deploy/runtime review says otherwise. |
| `LICENSE` | license | legal root file | `KEEP_ROOT` | Keep; legal changes need owner decision. |
| `PRODUCT_NAME` | product name marker | public identity | `KEEP_ROOT` | Keep. |
| `README.md` | English first screen | public product surface | `KEEP_ROOT` | Keep product-first and non-claiming. |
| `README_JP.md` | Japanese first screen | public product surface | `KEEP_ROOT` | Keep UTF-8 verified; avoid PR-number-first wording. |
| `VERSION` | version marker | repository metadata | `KEEP_ROOT` | Keep. |
| `assets` | public/static assets | public resources | `KEEP_ROOT` | Inventory if asset count grows. |
| `clients` | CLI and temporary Web client surfaces | public MVP clients | `KEEP_ROOT` | Keep API/CLI/Web lanes separate. |
| `config` | config helpers/data | mixed config | `KEEP_ROOT` | Review before moving any config. |
| `config.yaml` | legacy runtime config read by current code | active legacy config | `KEEP_ROOT` | Keep until references are redesigned and tested. |
| `core` | public Core API package | public active core | `KEEP_ROOT` | Keep as API contract authority. |
| `docker-compose.prod.yml` | compose profile with production-like name | runtime config | `KEEP_ROOT` | Caution: do not claim production readiness; review naming in deploy lane. |
| `docker-compose.yml` | local compose profile | runtime config | `KEEP_ROOT` | Keep; validate before changing service paths. |
| `docs` | contracts, releases, repo policy, architecture | public docs | `KEEP_ROOT` | Keep organized by contract/repo/security/release/architecture. |
| `main.py` | runtime entrypoint used by Docker/scripts | active entrypoint | `KEEP_ROOT` | Do not move without updating Docker/scripts/tests. |
| `memory` | memory-related package/data surface | not public memory completion | `CONNECT_CANDIDATE` | Keep non-claiming; memory remains not persistent/public-complete. |
| `pyproject.toml` | Python project config | tooling config | `KEEP_ROOT` | Keep. |
| `pytest.ini` | pytest config | test config | `KEEP_ROOT` | Keep. |
| `reference_clawdbot` | gitlink/submodule-like residue | not fixed | `DO_NOT_TOUCH` | Do not initialize, repair, remove, replace, or stage. |
| `requirements-optional-memory.txt` | optional memory dependencies | optional dependency lane | `KEEP_ROOT` | Keep until memory policy lane decides package shape. |
| `requirements.txt` | Python dependencies | runtime/test dependency root | `KEEP_ROOT` | Dependency PRs need separate validation. |
| `scripts` | setup/debug/runtime helper scripts | mixed tools | `KEEP_ROOT` | Continue moving only validated helpers. |
| `src` | legacy/runtime/private-adjacent code | mixed boundary surface | `CONNECT_CANDIDATE` | Caution: do not treat all `src` as public-ready. |
| `start.sh` | shell launcher | active legacy launcher | `KEEP_ROOT` | Do not move without setup wizard/reference validation. |
| `start_all.bat` | Windows launcher wrapper | uncertain active helper | `UNKNOWN` | Leave until owner confirms expected workflow. |
| `start_vllm.bat` | local model launcher referenced by resource manager | active local helper | `KEEP_ROOT` | Keep loopback/local framing; do not claim provider ecosystem completion. |
| `start_windows.bat` | Windows launcher | active legacy launcher | `KEEP_ROOT` | Do not move without setup wizard/reference validation. |
| `templates` | prompts/templates | public/reference resources | `KEEP_ROOT` | Inventory before runtime wiring. |
| `tests` | public regression tests | validation surface | `KEEP_ROOT` | Keep tests tied to narrow lanes. |
| `tools` | maintenance/debug/media helpers | public maintenance folder | `KEEP_ROOT` | Continue moving validated helpers here. |

## Current Root Boundary

- `debug_state.py`, `video_utils.py`, and `run_dashboard_backend.py` are no longer root entries.
- `remove_legacy.ps1` is no longer a root entry; it has moved to `tools/maintenance/remove_legacy.ps1` and remains `DO_NOT_RUN`.
- `config.yaml`, launch scripts, compose files, `main.py`, and `reference_clawdbot` remain visible.
- Remaining visible clutter is classified here rather than hidden by unsafe deletes.

## Moved Maintenance Helpers

| path | what it is | public status | current action | next safe action |
|---|---|---|---|---|
| `tools/maintenance/remove_legacy.ps1` | legacy removal helper that can edit runtime files | unsafe to present as active | `MOVE_TOOLS` / `DO_NOT_RUN` | Keep out of root; do not run without an owner-approved `src/cogs/ora.py` extraction lane. |

## Non-Claims

This file index does not claim production readiness, final Web UI, persistent memory, Google login, Discord gateway completion, Tools/MCP completion, provider ecosystem completion, private runtime completion, official cloud runtime completion, or `src/cogs/ora.py` resolution.
