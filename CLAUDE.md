# CLAUDE.md

Guidance for AI assistants (Claude Code and others) working in this repository.
This is the public, contract-first distribution core of **YonerAI**.

## Read These First (non-negotiable)

Before any scoped work — and always before making release, CLI, API, status,
or production-readiness claims — read:

- `AGENTS.md` — product identity, invariants, lane ownership, validation baseline.
- `CURRENT_TRUTH.md` — the public anchor for current tags, hosts, contracts, and open blockers.
- `docs/process/YONERAI_CODEX_WORKFLOW.md` — the canonical workflow.

For specific work, also read the relevant process docs:
`docs/process/YONERAI_GOAL_TEMPLATE.md`, `YONERAI_LANE_RULES.md`,
`YONERAI_PR_REVIEW_INTAKE.md`, `YONERAI_RELEASE_GOVERNANCE.md` (release/checkpoint work),
and the lane docs under `docs/contracts/`, `docs/architecture/`, `docs/design/`,
`docs/roadmap/`, or `docs/maintenance/`.

This `CLAUDE.md` is a navigation/summary layer. When it conflicts with
`AGENTS.md` or `CURRENT_TRUTH.md`, those files win.

## What YonerAI Is

YonerAI is a provider-independent AI runtime foundation: the goal is one
consistent user experience and one set of contract boundaries across **Full
Private Self-Host**, **Official Hybrid Private**, and **Official Managed Cloud**,
even as the model provider, UI surface, or runtime profile changes.

It is **not** "just a Discord bot" and **not** "just a model router." Discord,
Web, relay, API, CLI (incl. the native Japanese CLI), SNS distribution, and
self-evolution are **separate product lanes** with different risk profiles and
approval requirements.

- Public product name: **YonerAI**.
- **ORA** is a legacy/internal runtime namespace (`ora_core`, `ORACog`, `ORABot`,
  `src/cogs/ora.py`). Do **not** broad-rename ORA symbols without a compatibility
  plan and tests.
- The public repo only describes the **public contract surface**. Private runtime,
  Oracle/control-plane, live routes, and host-specific facts stay behind contracts.

## Repository Layout

```
main.py                  # Entry point -> src.bot.main (Discord bot runtime)
config.yaml              # Operational policy: cost limits, router config, model policies
.env.example             # Public env template (never commit a real .env)

src/                     # Discord bot + web runtime (the "ORA" application layer)
  bot.py                 # ORABot (discord.py commands.Bot); mention + slash UX
  worker_bot.py          # Secondary worker bot process
  config.py              # Config loader (reads config.yaml + env)
  storage.py             # Store: SQLite/aiosqlite persistence
  cogs/                  # discord.py cogs: ora.py (core agent), core, memory, music,
                         #   media, voice_*, mcp, scheduler, system_shell, etc.
  skills/                # Pluggable skills (loader.py + per-skill dirs); new_skill scaffolds
  services/              # layer/visual/voice/relay servers, vector & markdown memory
  managers/              # hardware, resource, game watchers
  utils/                 # Clients & helpers: llm_client, mcp_client, policy_engine,
                         #   redaction, access_control, approvals, safe_shell, etc.
  web/                   # FastAPI app (app.py), routers/, static dashboard, SSE
  relay/ self_evolution/ training/ views/

core/                    # Contract-first runtime core (the "ora_core" package)
  run_core.py            # Core entry
  alembic/ alembic.ini   # DB migrations
  src/ora_core/          # api/, brain/, engine/, execution/, planning/, providers/,
                         #   mcp/ (tool registry), memory/, sessions, distribution/,
                         #   hybrid/, official/, policies/, status_contract.py, three_mode.py

clients/cli/             # `yonerai` CLI package (yonerai_cli): commands/, screens/, tui/, ime/
clients/web/             # Web client assets
tools/                   # Backend tools: comfy, media, remotion, cloudflare, setup, debug
scripts/                 # Dev/CI/verify scripts (setup_wizard, ci_quality_scans, verify_*)
tests/                   # pytest suite (~168 files); conftest.py, fixtures/
docs/                    # Extensive governance, contracts, architecture, process docs
status.yonerai.com/      # Public status site + STATUS_* contracts
cloudflare/ config/ templates/ assets/ memory/
reference_clawdbot/      # DO NOT TOUCH (see boundaries below)
```

## Development Workflow

### Environment & run

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env          # fill PLACEHOLDERS only — never paste real secrets

python main.py                                        # Discord bot runtime
uvicorn src.web.app:app --host 0.0.0.0 --port 8000    # Web/API entry
```

- Python **3.11**. `start.sh` / `*.bat` wrap the run and the setup wizard
  (`scripts/setup_wizard.py`).
- Docker: `docker-compose.yml` (`ora-bot` + `ora-web`), GPU reservations for CUDA.
- After adding modules, verify imports: `python scripts/test_imports.py`.

### Tests & quality (run the smallest relevant set)

```bash
pytest -q                       # full suite (asyncio_mode=auto, testpaths=tests)
pytest tests/test_smoke.py      # CI smoke (set DISCORD_BOT_TOKEN=ci_dummy_token)
ruff check .                    # lint/format (line-length 120, double quotes)
mypy src/ --ignore-missing-imports
python -m compileall src/
python scripts/ci_quality_scans.py --changed   # secret / mojibake / hidden-unicode scan
git diff --check
```

Match the project's **validation baseline** (`AGENTS.md`): `git diff --check`,
targeted tests for touched behavior, public smoke tests when runtime/API/CLI/Web
behavior changes, `ruff` + `compileall` on touched paths, and secret/mojibake
scans on changed public text.

### CI

GitHub Actions: `test.yml` (ruff + mypy + compileall + smoke), `core_test.yml`,
`quality-wall.yml`, `pr-intake-gate.yml`, `release.yml`, `diagrams.yml`.
Required merge checks are enumerated in `docs/process/REQUIRED_CHECKS.md`
(e.g. `build-and-test (3.11)`, `core-test`, `cli-smoke`, `provider-boundary`,
`hybrid-zero-trust`, `security-static`, `release-gate`, `review-intake-required`).

### Git & PRs

- Branch from `main`; never commit directly to `main`. Use feature branch + PR.
- Keep PRs **lane-scoped** — do not mix unrelated lanes in one PR.
- Prefer fresh current-main patches over merging stale PRs.
- Squash merge subject format: `type: concise summary (#PR)` (PR number last).
  Commit subjects in this repo are frequently in Japanese — match surrounding style.
- **Do not** push, open PRs, merge, tag, create releases, deploy, or migrate
  unless the current task explicitly authorizes that action.
- Do not create GitHub Releases/tags for internal checkpoints or docs-only PRs;
  use `docs/changelog/checkpoints/`.

## Coding Conventions

- **Type hints**: built-in generics (`list[str]`, `dict[str, Any]`), not
  `typing.List`/`Dict`.
- **Style**: `ruff` (E, F selected; many legacy codes ignored — see `pyproject.toml`).
  Double quotes, 4-space indent, 120 cols. Legacy modules carry intentional
  ruff/mypy suppressions; don't mass-fix them outside a tracked lane.
- **No broad refactors** without characterization/regression tests.
- **Tools/MCP**: register every tool in `core/src/ora_core/mcp/registry.py`.
  GPU tools set `gpu_required=True`; the Core API must run with `--workers 1`
  so the VRAM-budget `asyncio.Semaphore` works. Tools support `tool_call_id`
  and are scoped by `user_id` (idempotent, 30s polling via `ToolRunner`).
- New skills: scaffold with `scripts/new_skill.py`; register via `src/skills/loader.py`.

## Security & Boundaries (deny-by-default)

- **Never commit** `.env`, real Discord/OpenAI/Cloudflare/OAuth credentials, key
  files, or logs/dumps containing tokens. Redact token-like values in new logs.
- **Never expose** secrets, private runtime truth, live routes, raw production
  inventory, break-glass detail, raw chain-of-thought, or control-plane internals.
- Preserve public / private / control-plane separation and provider independence.
- Dangerous capabilities are deny-by-default. A signed envelope proves
  origin/integrity only — it does **not** imply trust or approval.
- Local private memory/file content must not auto-upload.
- **`reference_clawdbot/`**: do not initialize, repair, remove, replace, stage,
  or edit.
- **`src/cogs/ora.py`**: not forbidden, but edits require characterization tests
  and behavior-preserving extraction scope only.
- Live Discord, real tokens, deploys, production signing/trust stores, persistent
  memory, Google login, and production DB behavior require an explicit
  owner-approved private/live lane.

## Claims Discipline

Do **not** claim production-ready, shipping-complete, official-cloud complete,
Discord restored, persistent memory complete, Google login complete, final Web
UI complete, Tools/MCP complete, full hybrid complete, `src/cogs/ora.py` solved,
or any milestone "done" without explicit evidence and approval. Check
`CURRENT_TRUTH.md` "Open Production Blockers" before stating status.

## Lane Ownership (from `AGENTS.md`)

- **Claude lane**: CLI visual, terminal theme, IME, display polish; design-book
  updates and broad audit narratives (the Claude doc lane).
- **Codex lane**: Control Spine client behavior, auth/session/sync command
  contracts, release gates, manifests, GitHub Releases.
- **GPT-5.5**: manager lane for cross-lane decisions and ownership conflicts.
- Files owned by another lane need an explicit handoff tag before you modify them.
- Review ping-pong: one response round per disputed point, then escalate.

## Reporting

Per `AGENTS.md`, final reports should be in **Japanese** and include exact PRs,
commits, tests, scans, runtime-boundary status, `src/cogs/ora.py` status,
`reference_clawdbot` status, explicit non-claims, blockers, and the next
recommended goal.
