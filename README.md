# YonerAI

Provider-independent AI execution foundation for keeping one reliable AI experience across official, local, and self-hosted runtimes.

[Japanese README](README_JP.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Release checkpoint](docs/releases/v2026.5.18-public-progress-checkpoint.md)

## What YonerAI Is

YonerAI is a long-lived AI runtime foundation. Its purpose is to keep the same user-facing experience and the same contract boundaries even when the active model provider, UI surface, local runtime, or self-hosted profile changes.

It is not just a Discord bot and not just a model router. Discord, Web, relay, API, CLI, native Japanese CLI, SNS distribution, and self-evolution are separate product lanes with different risk profiles and approval requirements.

This public README describes the public contract surface. It does not publish internal operations detail, credentials, live routes, or host-specific facts.

## Current Checkpoint

The active design anchor is v7.7:

- provider independence
- the same experience across official, local, and self-hosted directions
- self-evolution as approval-gated product intelligence
- contract-first public boundaries
- public/private/control-plane separation by contract, not by leaking internal operations detail

`v2026.5.18` is a public progress checkpoint, not a production release.

This repository does not claim shipping completeness, production readiness, official cloud completion, live operations completion, or full product completion.

Pass 2 remains stopped / not landed. `src/cogs/ora.py` remains unresolved private/runtime/control-plane boundary residue and is not treated as a narrow public patch target.

## Public Scope

The public surface is for reviewable contracts, public-safe runtime abstractions, capability boundaries, connector patterns, client-facing documentation, and regression tests.

Private runtime behavior, operator-only workflows, live routes, deployment truth, raw production inventory, credentials, and host-specific control-plane details do not belong in public-facing documentation.

Cross-boundary interaction should happen through explicit contracts such as APIs, events, files, auth claims, capability manifests, protocols, and schemas.

Raw chain-of-thought must not cross public chat, API, SSE, log, documentation, or trace surfaces. Public traces should expose only safe summaries, labels, details, and already-public sources.

Useful starting points:

- [Current phase context](docs/CURRENT_PHASE_CONTEXT.md)
- [External Agent API](docs/contracts/external-agent-api.md)
- [SSE Run Events](docs/contracts/sse-run-events.md)
- [v2026.5.18 checkpoint note](docs/releases/v2026.5.18-public-progress-checkpoint.md)
- [Latest traceability matrix](docs/TRACEABILITY_MATRIX_0_19.md)

## Product Lanes

YonerAI keeps these lanes separate:

- API: contract authority
- CLI: command authority
- native Japanese CLI: ambiguous-command confirmation and explanation responsibility
- Web: product surface
- SNS: distribution lane, not a core blocker
- self-evolution: product intelligence and proposal scoring, not unapproved code mutation
- private runtime / control plane: execution authority, supervision, and operator-only behavior

Combining these lanes into one implementation batch is not a shortcut to public-core readiness.

## Local Development

Use the smallest profile that matches the area you are reviewing.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Do not commit `.env` or local secret files. Treat `.env.example` as a placeholder template, not production truth.

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

Discord adapter work requires local Discord credentials and belongs behind local/private profile boundaries. It is not required to inspect the public core.

## Public Safety

Do not commit:

- real `.env` files or secret backups
- credentials, service-account files, tokens, private keys, or tunnel secrets
- local SQLite databases, WAL/SHM files, logs, caches, generated audio, or local state
- raw production inventory, live route maps, operational ledgers, break-glass details, or control-plane DDL
- private renderer truth or host-specific operational exactness
- local absolute paths or user-machine paths in public docs

If a required detail is not public-safe, add a placeholder, contract, public-safe summary, or TODO instead of publishing private material.

## Checks

Run targeted checks for the area you change. For docs-only hygiene changes, minimum validation is:

```powershell
git diff --check
git status --short --branch
```

Broader test, lint, and CI commands depend on the lane. Passing docs checks does not mean production readiness.
