# Root Surface Inventory 2026-05-21

Status: current root surface recheck for the v7.7 public repository after PR #218.

This inventory supersedes the root-status facts in the 2026-05-20 inventory for current presentation decisions. It does not move or delete files.

## Verified Root Entries

`git ls-tree --name-only origin/main` shows these root-visible entries:

`.env.example`, `.github`, `.gitignore`, `AGENTS.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `Dockerfile`, `LICENSE`, `PRODUCT_NAME`, `README.md`, `README_JP.md`, `VERSION`, `assets`, `clients`, `config`, `config.yaml`, `core`, `docker-compose.prod.yml`, `docker-compose.yml`, `docs`, `main.py`, `memory`, `pyproject.toml`, `pytest.ini`, `reference_clawdbot`, `requirements-optional-memory.txt`, `requirements.txt`, `scripts`, `src`, `start.sh`, `start_all.bat`, `start_vllm.bat`, `start_windows.bat`, `templates`, `tests`, `tools`.

## Current Changes Since Prior Inventory

- `remove_legacy.ps1` is absent from root.
- `tools/maintenance/remove_legacy.ps1` exists and remains `DO_NOT_RUN` / `RETIRE_CANDIDATE`.
- `debug_state.py`, `video_utils.py`, and `run_dashboard_backend.py` remain absent from root.
- `config.yaml`, `main.py`, launchers, compose files, and `reference_clawdbot` remain visible.
- A 2026-05-21 physical-cleanup pass rechecked the remaining root candidates and made no move because references or owner-workflow uncertainty remain. See [Root Physical Cleanup Decision 2026-05-21](ROOT_PHYSICAL_CLEANUP_DECISION_2026_05_21.md).

## Classification Summary

| classification | paths |
|---|---|
| `KEEP_ROOT` | `.env.example`, `.github`, `.gitignore`, `AGENTS.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `Dockerfile`, `LICENSE`, `PRODUCT_NAME`, `README.md`, `README_JP.md`, `VERSION`, `assets`, `clients`, `config`, `core`, `docker-compose.yml`, `docker-compose.prod.yml`, `docs`, `main.py`, `pyproject.toml`, `pytest.ini`, `requirements.txt`, `requirements-optional-memory.txt`, `scripts`, `start.sh`, `start_vllm.bat`, `start_windows.bat`, `templates`, `tests`, `tools` |
| `CONNECT_CANDIDATE` | `memory`, `src` |
| `UNKNOWN` | `start_all.bat` |
| `DO_NOT_TOUCH` | `reference_clawdbot` |
| `MOVE_CONFIG` candidate only after validation | `config.yaml` |

## Next Safe Move Decisions

| candidate | current decision | reason |
|---|---|---|
| `start_all.bat` | Leave in root for now | No clear static references, but owner workflow is uncertain. |
| `start.sh` | Leave in root | Setup wizard and docs may rely on root launcher behavior. |
| `start_windows.bat` | Leave in root | Setup wizard and Windows quick-start behavior may rely on root launcher behavior. |
| `start_vllm.bat` | Leave in root | Referenced by local model/resource-management helpers. |
| `config.yaml` | Leave in root | Runtime loaders and MCP-related code expect working-directory config behavior. |
| `main.py` | Leave in root | Referenced by Dockerfile, compose, pyproject, scripts, and docs. |
| compose files | Leave in root | Conventional root placement and active documentation references. |
| `reference_clawdbot` | Do not touch | Explicit do-not-touch boundary. |

## Physical Cleanup Rule

Future root cleanup should move exactly one small, reference-validated group at a time. Each move needs:

- reference scan before moving;
- `git mv`;
- reference updates;
- public smoke tests;
- CLI tests if launchers are touched;
- targeted ruff/compileall if Python files move;
- secret and local-path scans;
- explicit confirmation that `src/cogs/ora.py` and `reference_clawdbot` remain unchanged.

## Non-Claims

This inventory does not claim production readiness, deployment readiness, final root cleanup, private runtime completion, official cloud completion, provider ecosystem completion, persistent memory, Google login, Discord gateway completion, Tools/MCP completion, Pass 2 landing, or `src/cogs/ora.py` resolution.
