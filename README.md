# YonerAI

Public distribution core for a provider-independent AI execution foundation.

[Japanese README](README_JP.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Release checkpoint](docs/releases/v2026.4.28-public-progress-checkpoint.md)

## What This Repository Is

YonerAI is a long-lived AI runtime foundation for keeping the same user-facing
experience and the same contract boundaries even when the active provider,
official UI, local runtime, or self-host profile changes.

This public repository is the distribution core. It contains public-safe runtime
abstractions, contract docs, schemas, capability boundaries, connector patterns,
and client surfaces that can be reviewed without private operations material.

YonerAI is not only a Discord bot, and it is not only a model router. Discord,
web, relay, API, CLI, native Japanese CLI, SNS distribution, and self-evolution
are separate lanes with different failure modes and approval requirements.

## Current Status

The active design anchor is the v7.7 source-of-truth freeze:

- provider independence
- same experience across official, local, and self-host directions
- self-evolution as product intelligence with approval gates
- contract-first public boundaries
- three canonical repositories

`v2026.4.28` is a public progress checkpoint, not a final product release.
This repository does not claim shipping-complete, production-ready,
official-cloud complete, live-ops complete, or full product complete status.

Pass 2 remains stopped / not landed. `src/cogs/ora.py` remains unresolved
private/runtime/control-plane boundary residue and is not treated as a narrow
public patch target.

## Three Repositories

The canonical split is:

- `YoneRai12/YonerAI`: public distribution core, public-safe contracts, common
  runtime abstractions, public client surfaces, capability manifests, and docs.
- `YoneRai12/YonerAI-private`: official app runtime, official web runtime,
  official Discord gateway, admin/release/maintenance logic, and operator-only
  surfaces.
- `YoneRai12/YonerAI-oracle-control-plane`: Oracle VPS deployment, rollback,
  supervision, health orchestration, cloudflared/hooks, and future
  evaluator/healing control-plane work.

`YonerAI-VPS-private` is not the all-in-one private repository. If it appears in
older notes, treat it only as a possible control-plane seed.

Public artifacts must not import private internals directly. Cross-repo
interaction must happen through contracts: APIs, events, files, auth claims,
capability manifests, protocols, or schemas.

## Public Contract Direction

The public core is contract-first. Current contract areas include:

- Internal Run API and event stream contracts
- file reference and download boundaries
- capability and risk policy boundaries
- storage and relay boundaries
- public-safe reasoning summary constraints
- approval and audit surfaces

Raw chain-of-thought must not cross public chat, API, SSE, log, doc, or trace
surfaces. Public traces should expose safe summaries, labels, details, and
already-public sources only.

Useful starting points:

- [Current phase context](docs/CURRENT_PHASE_CONTEXT.md)
- [External Agent API](docs/contracts/external-agent-api.md)
- [SSE Run Events](docs/contracts/sse-run-events.md)
- [Release checkpoint](docs/releases/v2026.4.28-public-progress-checkpoint.md)
- [Latest traceability matrix](docs/TRACEABILITY_MATRIX_0_19.md)

## Product Surface Lanes

YonerAI keeps these lanes separate:

- API: contract authority
- CLI: command authority
- native Japanese CLI: UX, ambiguous-command confirmation, and explanation
  responsibility
- Web: product surface
- SNS: distribution lane, not a core blocker
- self-evolution: product intelligence and proposal scoring, not unapproved
  code mutation
- private runtime / control plane: execution authority, supervision, and
  operator-only behavior

Combining these lanes into one implementation batch is not a public-core
readiness shortcut.

## Repository Layout

- `core/`: public-core runtime and distribution contract implementation
- `src/`: mixed legacy runtime code, public-safe helpers, skills, adapters, and
  private/runtime boundary residue that is being separated by lane
- `clients/`: public/distributable client surfaces
- `config/distribution/`: public capability profiles and manifests
- `docs/`: public-safe contracts, phase docs, release notes, and traceability
- `tests/`: contract and regression tests

Some names still use `ORA_*` for compatibility with older internals. New public
docs should use YonerAI terminology unless they are documenting an existing
compatibility key.

## Local Development

Use the smallest profile that matches the area you are reviewing.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Do not commit `.env` or local secret files. Treat `.env.example` as a template,
not production truth.

Core API:

```powershell
$env:PYTHONPATH = "core\src"
python -m ora_core.main
```

Optional local web/API runtime:

```powershell
.venv\Scripts\Activate.ps1
uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000
```

Optional web client:

```powershell
cd clients\web
npm install
npm run dev
```

Discord adapter work requires local Discord credentials and belongs behind
local/private profile boundaries. It is not required to inspect the public core.

## Public Release Hygiene

Do not commit:

- real `.env` files or secret backups
- credentials, service-account files, tokens, private keys, or tunnel secrets
- local SQLite databases, WAL/SHM files, logs, caches, generated audio, or local
  state
- raw production inventory, live route maps, operational ledgers, break-glass
  details, or control-plane DDL
- private renderer truth or Oracle host exactness
- local absolute paths or user-machine paths in public docs

If a required detail is not public-safe, add a template, placeholder, contract,
or TODO instead of committing the private material.

## Checks

Run targeted checks for the area you change. For docs-only hygiene changes,
minimum validation is:

```powershell
git diff --check
git status --short --branch
```

Broader test, lint, and CI commands depend on the lane. Do not treat passing
docs checks as production readiness.
