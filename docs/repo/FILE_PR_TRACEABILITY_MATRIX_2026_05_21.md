# File / PR Traceability Matrix 2026-05-21

Status: public-safe repository presentation and traceability matrix for the v7.7 public repo.

This matrix explains GitHub root-visible entries without mass-touching files to manipulate the GitHub "last commit message" column. GitHub shows the latest commit that touched each path; it is not a custom description field. Professional presentation should come from clear docs, narrow commits, and reviewed PRs.

## Verification Inputs

- `origin/main`: `e64299142bb68a731245b03678e8531dc18b36a9`
- Verified open PR count at the companion reality check: `36`
- Root list source: `git ls-tree --name-only origin/main`
- Last commit source: `git log -1 --format=%h %s origin/main -- <path>`
- Companion ledgers:
  - `docs/maintenance/CURRENT_PR_BRANCH_REALITY_2026_05_21.md`
  - `docs/maintenance/OPEN_PR_TRIAGE_2026_05_20.md`
  - `docs/repo/PUBLIC_FILE_INDEX.md`
  - `docs/repo/ROOT_SURFACE_INVENTORY_2026_05_21.md`

## Root Traceability Table

| path | what it is | public status | classification | latest relevant PR / commit evidence | GitHub last commit subject observed | stay in root | next safe action | owner decision | do-not-touch reason |
|---|---|---|---|---|---|---|---|---|---|
| `.env.example` | Sample environment template | Public-safe placeholder | `KEEP_ROOT` | `1fa7fbc` local provider checkpoint | `feat: OpenAI...local LLM provider...` | yes | Keep scrubbed; never add real values. | no | n/a |
| `.github` | Workflows/templates | Public automation config | `KEEP_ROOT` | PR #126-era public node bootstrap | `[codex] public node initial boot... (#126)` | yes | Review workflow dependency PRs separately. | no | n/a |
| `.gitignore` | Ignore policy | Repository config | `KEEP_ROOT` | public presentation cleanup | `docs: clean public GitHub presentation` | yes | Keep. | no | n/a |
| `AGENTS.md` | Repo operating instructions | Contributor guidance | `KEEP_ROOT` | public presentation cleanup | `docs: clean public GitHub presentation` | yes | Keep durable rules only. | no | n/a |
| `CHANGELOG.md` | Historical changelog | Public history | `KEEP_ROOT` | PR #126-era public node bootstrap | `[codex] public node initial boot... (#126)` | yes | Keep; use release notes for current checkpoints. | no | n/a |
| `CONTRIBUTING.md` | Contribution guide | Public process | `KEEP_ROOT` | rebrand documentation pass | `Docs: rebrand ORA to YonerAI` | yes | Keep. | legal/process if changed | n/a |
| `Dockerfile` | Container entrypoint | Runtime config | `KEEP_ROOT` | compose support commit | `feat: docker compose support...` | yes | Do not move without container validation. | yes for deploy semantics | n/a |
| `LICENSE` | License | Legal root file | `KEEP_ROOT` | license hardening era | `Step 4 complete...` | yes | Keep; legal changes need owner decision. | yes | n/a |
| `PRODUCT_NAME` | Product identity marker | Public identity | `KEEP_ROOT` | release branding commit | `Release branding + relay external verification script` | yes | Keep. | no | n/a |
| `README.md` | English first screen | Public product surface | `KEEP_ROOT` | PR #201 inventory / presentation stream | `docs: large codebase inventory...` | yes | Keep product-first; link traceability docs when useful. | no | n/a |
| `README_JP.md` | Japanese first screen | Public product surface | `KEEP_ROOT` | PR #201 inventory / presentation stream | `docs: large codebase inventory...` | yes | Needs a separate UTF-8/public-presentation cleanup lane. | no | n/a |
| `VERSION` | Version marker | Repository metadata | `KEEP_ROOT` | PR #126-era public node bootstrap | `[codex] public node initial boot... (#126)` | yes | Keep. | no | n/a |
| `assets` | Shared assets | Public resources | `KEEP_ROOT` | cleanup organization commit | `chore: Deep Cleanup...` | yes | Inventory if asset count grows. | no | n/a |
| `clients` | CLI and Web public client surfaces | Public MVP clients | `KEEP_ROOT` | PR #216 fresh security/runtime patch | `fix: security runtime backlog...` | yes | Keep API/CLI/Web lanes separate. | no | n/a |
| `config` | Config directory | Mixed config helpers/data | `KEEP_ROOT` | distribution node fail-closed baseline | `Distribution Node MVP...` | yes | Review with config lane before moving files. | maybe | n/a |
| `config.yaml` | Legacy root config | Active legacy config | `KEEP_ROOT` | old optimization arc commit | `S1-S8 Optimization Arc Completion...` | yes for now | Do not move until loader references are redesigned/tested. | yes | n/a |
| `core` | Public Core API package | Public active core | `KEEP_ROOT` | PR #216 fresh security/runtime patch | `fix: security runtime backlog...` | yes | Keep as API contract authority. | no | n/a |
| `docker-compose.prod.yml` | Production-named compose profile | Runtime config | `KEEP_ROOT` | obsolete ora-ui cleanup commit | `chore: obsolete ora-ui...` | yes for now | Keep but avoid production-readiness claims. | yes | n/a |
| `docker-compose.yml` | Local compose profile | Runtime config | `KEEP_ROOT` | obsolete ora-ui cleanup commit | `chore: obsolete ora-ui...` | yes | Keep until compose lane validates moves. | maybe | n/a |
| `docs` | Contracts, releases, repo policy, architecture | Public docs | `KEEP_ROOT` | PR #218 merge branch integration | `Merge remote-tracking branch...root-surface...` | yes | Keep organized by topic. | no | n/a |
| `main.py` | Runtime entrypoint | Active entrypoint | `KEEP_ROOT` | lint/junk cleanup commit | `chore: force fix linting...` | yes | Do not move without Docker/scripts/test updates. | yes | n/a |
| `memory` | Memory-related package/data surface | Not public memory completion | `CONNECT_CANDIDATE` | old optimization arc commit | `S1-S8 Optimization Arc Completion...` | yes for now | Keep non-claiming; review in memory policy lane. | yes | n/a |
| `pyproject.toml` | Python project config | Tooling config | `KEEP_ROOT` | core tool loop/release versioning commit | `fix: stabilize core tool loop...` | yes | Keep. | no | n/a |
| `pytest.ini` | Test config | Test config | `KEEP_ROOT` | initial clean release | `Initial release (Clean)` | yes | Keep. | no | n/a |
| `reference_clawdbot` | Gitlink/submodule-like residue | Not fixed | `DO_NOT_TOUCH` | old import/config commit | `fix(core): Resolve import errors...` | yes until owner-approved cleanup | Do not initialize, repair, remove, replace, or stage. | yes | Do-not-touch explicit owner boundary. |
| `requirements-optional-memory.txt` | Optional memory dependencies | Optional dependency lane | `KEEP_ROOT` | PR #126-era public node bootstrap | `[codex] public node initial boot... (#126)` | yes | Review with memory/dependency lane. | maybe | n/a |
| `requirements.txt` | Python dependency entrypoint | Runtime/test dependency root | `KEEP_ROOT` | public Web UI mock chat checkpoint | `feat: public Web UI mock chat...` | yes | Dependency PRs need lane validation. | no | n/a |
| `scripts` | Mixed setup/debug/runtime scripts | Mixed tools | `KEEP_ROOT` | obsolete ora-ui cleanup commit | `chore: obsolete ora-ui...` | yes | Continue moving only validated helpers. | maybe | n/a |
| `src` | Legacy/runtime/private-adjacent code | Mixed boundary surface | `CONNECT_CANDIDATE` | self-evolution proposal-only MVP | `feat: self-evolution proposal-only MVP...` | yes for now | Do not treat all `src` as public-ready. | yes | `src/cogs/ora.py` remains separate boundary lane. |
| `start.sh` | Shell launcher | Active legacy launcher | `KEEP_ROOT` | professional hardening commit | `chore: professional repository hardening...` | yes | Move only after setup wizard/reference validation. | maybe | n/a |
| `start_all.bat` | Windows launcher wrapper | Uncertain active helper | `UNKNOWN` | public runnable smoke checkpoint | `test: public runnable MVP smoke...` | yes for now | Leave until expected owner workflow is confirmed. | yes | n/a |
| `start_vllm.bat` | Local model launcher | Active local helper | `KEEP_ROOT` | voice/music restore commit | `feat: Restored Voice & Music...` | yes | Keep local/loopback framing; do not overclaim providers. | maybe | n/a |
| `start_windows.bat` | Windows launcher | Active legacy launcher | `KEEP_ROOT` | professional hardening commit | `chore: professional repository hardening...` | yes | Move only after setup wizard/reference validation. | maybe | n/a |
| `templates` | Prompts/templates | Public/reference resources | `KEEP_ROOT` | cleanup organization commit | `chore: Deep Cleanup...` | yes | Inventory before wiring runtime behavior. | maybe | n/a |
| `tests` | Regression tests | Validation surface | `KEEP_ROOT` | PR #216 fresh security/runtime patch | `fix: security runtime backlog...` | yes | Keep tests tied to narrow lanes. | no | n/a |
| `tools` | Maintenance/debug/media helpers | Public maintenance folder | `KEEP_ROOT` | PR #218 root helper move | `chore: validated root helper...` | yes | Continue validated helper moves here. | no | n/a |

## Moved / Non-Root Helper Traceability

| path | current status | latest relevant PR / commit | next safe action |
|---|---|---|---|
| `tools/maintenance/remove_legacy.ps1` | moved out of root; `DO_NOT_RUN` / `RETIRE_CANDIDATE` | PR #218 / `e64299142bb68a731245b03678e8531dc18b36a9` | Keep out of root; do not run without owner-approved `src/cogs/ora.py` extraction lane. |
| `tools/maintenance/run_dashboard_backend.py` | moved out of root | PR #191 | Keep documented as maintenance helper. |
| `tools/debug/debug_state.py` | moved out of root | PR #184 / earlier root cleanup | Keep out of root. |
| `tools/media/video_utils.py` | moved out of root | PR #184 / earlier root cleanup | Keep out of root. |

## Current Presentation Decision

- Do not mass-touch root files to change GitHub's last-commit column.
- Do not move `config.yaml`, `main.py`, launchers, compose files, `src`, `memory`, or `reference_clawdbot` in this traceability lane.
- Use narrow future PRs for actual file moves after reference scans and tests.
- Keep PR numbers in traceability sections rather than README headlines or release titles.

## Non-Claims

This matrix does not claim production readiness, shipping completeness, official cloud completion, live operations completion, full product completion, hybrid completion, persistent memory completion, Google login, Discord gateway completion, provider ecosystem completion, final Web UI completion, Tools/MCP completion, all security backlog resolution, all dependency backlog resolution, Pass 2 landing, v7.8 start/completion, or `src/cogs/ora.py` resolution.
