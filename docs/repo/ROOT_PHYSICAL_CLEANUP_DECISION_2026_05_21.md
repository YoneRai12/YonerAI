# Root Physical Cleanup Decision 2026-05-21

Status: v7.7 public-repository cleanup evidence. This pass performs no file move because the remaining root-visible candidates are active, uncertain owner workflow entrypoints, or conventional root config files.

## Verification

Commands used:

- `git ls-tree --name-only origin/main`
- `rg -n --fixed-strings <candidate> . -g '!reference_clawdbot/**' -g '!src/cogs/ora.py' -g '!*.png' -g '!*.jpg' -g '!*.pdf'`
- `git log --oneline -n 3 -- <candidate>`

The scan excluded `reference_clawdbot` and `src/cogs/ora.py` from inspection beyond boundary confirmation. Neither path was moved, initialized, repaired, staged, or edited.

## Decision

No root file was moved in this pass.

The remaining candidates are not safe physical-move targets without a dedicated runtime or owner-workflow lane. A cosmetic move would make the GitHub root look cleaner, but it would also risk breaking launch paths, Docker behavior, working-directory config loading, or owner-local workflows.

## Candidate Findings

| candidate | classification | reference evidence | decision | blocker before move |
|---|---|---|---|---|
| `start.sh` | `KEEP_ROOT` | `scripts/setup_wizard.py` prints `./start.sh` as the recommended launcher. | Keep at root. | Setup wizard and quick-start behavior need an explicit launcher migration lane. |
| `start_windows.bat` | `KEEP_ROOT` | `scripts/setup_wizard.py` prints `.\\start_windows.bat` as the recommended Windows launcher. | Keep at root. | Setup wizard and Windows quick-start behavior need migration and validation. |
| `start_vllm.bat` | `KEEP_ROOT` | `src/managers/resource_manager.py` resolves `start_vllm.bat`; setup and maintenance helpers also mention it. | Keep at root. | Local model/resource-manager references must be redesigned before moving. |
| `start_all.bat` | `UNKNOWN` | No clear runtime reference found; docs classify it as uncertain active workflow. | Keep at root for now. | Owner workflow is unknown; do not remove or move an entrypoint only because static references are sparse. |
| `config.yaml` | `MOVE_CONFIG` candidate only after validation | `src/config.py` and `src/cogs/mcp.py` load `config.yaml` from the current working directory. | Keep at root. | A config loader lane must support the new path before this can move. |
| `main.py` | `KEEP_ROOT` | `Dockerfile`, compose files, `pyproject.toml`, scripts, and docs reference `python main.py`. | Keep at root. | Entrypoint move requires Docker, scripts, docs, and tests to change together. |
| `docker-compose.yml` | `KEEP_ROOT` | Active local compose profile; docs reference compose behavior. | Keep at root. | Conventional root placement and service path validation. |
| `docker-compose.prod.yml` | `KEEP_ROOT` | Production-named compose profile remains documented as non-production-complete. | Keep at root. | Naming/placement needs deploy-boundary review; do not imply production readiness. |
| `tools/maintenance/remove_legacy.ps1` | `DO_NOT_RUN` / `RETIRE_CANDIDATE` | Already moved out of root by PR #218. Docs warn it can alter legacy runtime files if executed. | Keep out of root and do not run. | Owner-approved `src/cogs/ora.py` extraction lane required before any retirement action. |

## Next Safe Physical Cleanup Lane

The next practical cleanup lane should choose exactly one target group:

1. Launcher migration pilot: move one launcher group to `scripts/launchers` only after updating `scripts/setup_wizard.py`, docs, and smoke tests.
2. Config path migration: teach loaders to prefer `config/config.yaml` with a root fallback, then migrate only after tests prove compatibility.
3. Compose naming review: document or rename production-like compose wording without claiming deploy readiness.

`start_all.bat` is the only low-reference root file, but low reference count is not enough evidence to move it. It remains an owner-workflow decision.

## Non-Claims

This decision does not claim final root cleanup, production readiness, deploy readiness, provider ecosystem completion, persistent memory, Google login, Discord gateway completion, Tools/MCP completion, private runtime completion, official cloud runtime completion, Pass 2 landing, or `src/cogs/ora.py` resolution.
