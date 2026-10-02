# Root Surface Inventory 2026-05-20

Status: public-safe root inventory. This checkpoint now includes small validated helper moves.

## 2026-05-21 Recheck

- Public file index added: `docs/repo/PUBLIC_FILE_INDEX.md`.
- Follow-up cleanup moved `remove_legacy.ps1` to `tools/maintenance/remove_legacy.ps1` without running it.
- `debug_state.py`, `video_utils.py`, and `run_dashboard_backend.py` remain out of root.
- `config.yaml`, `main.py`, `start.sh`, `start_all.bat`, `start_vllm.bat`, `start_windows.bat`, compose files, and `reference_clawdbot` remain visible.
- `tools/maintenance/remove_legacy.ps1` remains `RETIRE_CANDIDATE` / `DO_NOT_RUN` because it can alter runtime code.
- `reference_clawdbot` remains `DO_NOT_TOUCH`.
- `start_all.bat` remains `UNKNOWN`; it was not moved because expected owner workflow is not confirmed.

## Summary

The Git-visible root contains normal public repository entrypoints, active packaging/test config, active launchers, legacy runtime helpers, and one gitlink residue.

This pass classifies the surface first. Runtime-moving cleanup is deferred until references can be updated and validated in a dedicated PR. Follow-up cleanup moved only no-reference helper files that do not affect active runtime launch behavior.

## Classification Table

| entry | classification | current evidence | action |
|---|---|---|---|
| `.env.example` | KEEP_ROOT | Standard public-safe environment template. | Keep. |
| `.github` | KEEP_ROOT | GitHub workflows/templates live at root by convention. | Keep. |
| `.gitignore` | KEEP_ROOT | Standard repository control file. | Keep. |
| `AGENTS.md` | KEEP_ROOT | Repository instructions and durable guardrails. | Keep. |
| `CHANGELOG.md` | KEEP_ROOT | Public history entrypoint. | Keep. |
| `CONTRIBUTING.md` | KEEP_ROOT | Standard contributor entrypoint. | Keep. |
| `Dockerfile` | KEEP_ROOT | Referenced root runtime container entrypoint. | Keep unless container lane replaces it. |
| `LICENSE` | KEEP_ROOT | Standard public license file. | Keep. |
| `PRODUCT_NAME` | KEEP_ROOT | Product identity marker. | Keep. |
| `README.md` | KEEP_ROOT | Primary public entrypoint. | Keep. |
| `README_JP.md` | KEEP_ROOT | Japanese public entrypoint. | Keep. |
| `VERSION` | KEEP_ROOT | Public version marker. | Keep. |
| `assets` | KEEP_ROOT | Shared assets. | Keep pending asset ownership audit. |
| `clients` | KEEP_ROOT | Contains temporary Web Chat MVP / smoke-demo client. | Keep. |
| `config` | KEEP_ROOT | Public-safe config directory. | Keep pending config ownership audit. |
| `core` | KEEP_ROOT | Public Core API. | Keep. |
| `docs` | KEEP_ROOT | Public-safe docs and release notes. | Keep. |
| `memory` | UNKNOWN | Memory-related root directory; persistent-memory implications require a dedicated lane. | Do not move in this PR. |
| `pyproject.toml` | KEEP_ROOT | Python packaging and tooling config. | Keep. |
| `pytest.ini` | KEEP_ROOT | Test configuration. | Keep. |
| `requirements.txt` | KEEP_ROOT | Public install dependency entrypoint. | Keep. |
| `requirements-optional-memory.txt` | KEEP_ROOT | Referenced by docs/tests/services for explicit optional memory dependency. | Keep. |
| `scripts` | KEEP_ROOT | Public-safe script directory. | Keep. |
| `src` | KEEP_ROOT | Legacy/runtime code still requires lane-specific extraction. | Keep; do not generic-move. |
| `templates` | KEEP_ROOT | Prompt/templates surface. | Keep pending template ownership audit. |
| `tests` | KEEP_ROOT | Test suite. | Keep. |
| `tools` | KEEP_ROOT | Tooling directory. | Keep. |
| `reference_clawdbot` | DO_NOT_TOUCH | Tracked as gitlink/submodule residue. Owner scope says do not fix. | Do not init, update, remove, replace, or repair. |
| `config.yaml` | KEEP_ROOT | Loaded from process working directory by runtime config and MCP code. | Keep until config lane updates references. |
| `debug_state.py` | MOVE_TOOLS | No static runtime references found; previous root helper contained a local absolute default path. | Moved to `tools/debug/debug_state.py` and changed to env/relative state path lookup. |
| `docker-compose.yml` | KEEP_ROOT | Referenced by docs and pairs with root `main.py`. | Keep. |
| `docker-compose.prod.yml` | KEEP_ROOT | Root production-like compose file; moving could alter operator expectations. | Keep; do not change runtime behavior. |
| `main.py` | KEEP_ROOT | Referenced by Dockerfile, compose files, pyproject, scripts, and docs. | Keep. |
| `tools/maintenance/remove_legacy.ps1` | MOVE_TOOLS / DO_NOT_RUN / RETIRE_CANDIDATE | No clear static references found; script rewrites `src/cogs/ora.py` if executed, so it should not be root-visible as an active helper. | Moved from root to `tools/maintenance/`; do not run without a dedicated owner-approved `src/cogs/ora.py` extraction lane. |
| `run_dashboard_backend.py` | MOVE_TOOLS | No static references found outside this inventory; helper imports dashboard backend directly and is not an active root launcher. | Moved to `tools/maintenance/run_dashboard_backend.py` with repo-root path resolution. |
| `start.sh` | KEEP_ROOT | Referenced by setup wizard as recommended launcher. | Keep. |
| `start_all.bat` | UNKNOWN | No clear static references found. | Do not move without owner confirmation. |
| `start_vllm.bat` | KEEP_ROOT | Referenced by resource manager and maintenance/setup scripts. | Keep. |
| `start_windows.bat` | KEEP_ROOT | Referenced by setup wizard as recommended launcher. | Keep. |
| `video_utils.py` | MOVE_TOOLS | No static runtime references found; generic ffprobe helper. | Moved to `tools/media/video_utils.py`. |

## Local-Only Entries Observed

The working tree also contains local development/cache/state directories such as `.venv`, `.pytest_cache`, `.ruff_cache`, and `data`. They are not GitHub-visible root product surface in this pass and should remain ignored/untracked unless a dedicated storage lane proves otherwise.

## Minimal Cleanup Decision

This cleanup remains intentionally narrow:

- keep root policy
- update inventory
- move only no-reference helper files after reference scan: `debug_state.py`, `video_utils.py`, and `run_dashboard_backend.py`
- do not move active launchers or config files
- do not delete `reference_clawdbot`
- do not touch `src/cogs/ora.py`
- do not change runtime launch behavior

## Next Safe Cleanup Lane

Pick one helper group at a time:

1. remaining no-reference helper: `start_all.bat`
2. active launchers: `start.sh`, `start_windows.bat`, `start_vllm.bat`
3. config surface: `config.yaml`, `config/`
4. optional memory dependencies: `requirements-optional-memory.txt`, `memory/`, related docs

Each move needs reference updates and targeted validation.
