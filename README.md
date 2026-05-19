# YonerAI

Provider-independent AI execution foundation for keeping one reliable AI experience across official, local, and self-hosted runtimes.

[Japanese README](README_JP.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Latest checkpoint](docs/releases/v2026.5.19-public-runnable-mvp-checkpoint.md)

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

`v2026.5.19` is a public runnable MVP checkpoint, not a production release.

This repository does not claim shipping completeness, production readiness, official cloud completion, live operations completion, or full product completion.

Pass 2 remains stopped / not landed. `src/cogs/ora.py` remains unresolved private/runtime/control-plane boundary residue and is not treated as a narrow public patch target.

## Product Modes

YonerAI is designed around three high-level ways to use the same contract-first foundation:

- Full Private Self-Host: the user controls the runtime boundary.
- Official Hybrid Private: official governance and a local/private runtime can work together through explicit contracts.
- Official Managed Cloud: the same experience can be offered as a managed surface when that lane is ready.

These are product modes, not a repository map. Public docs should describe the contract and user experience, not private operational detail.

## What Is Included In This Public Repo

The public surface is for reviewable contracts, public-safe runtime abstractions, capability boundaries, connector patterns, client-facing documentation, and regression tests.

Private runtime behavior, operator-only workflows, live routes, deployment truth, raw production inventory, credentials, and host-specific control-plane details do not belong in public-facing documentation.

Cross-boundary interaction should happen through explicit contracts such as APIs, events, files, auth claims, capability manifests, protocols, and schemas.

Raw chain-of-thought must not cross public chat, API, SSE, log, documentation, or trace surfaces. Public traces should expose only safe summaries, labels, details, and already-public sources.

Useful starting points:

- [Current phase context](docs/CURRENT_PHASE_CONTEXT.md)
- [External Agent API](docs/contracts/external-agent-api.md)
- [SSE Run Events](docs/contracts/sse-run-events.md)
- [v2026.5.19 checkpoint note](docs/releases/v2026.5.19-public-runnable-mvp-checkpoint.md)
- [Latest traceability matrix](docs/TRACEABILITY_MATRIX_0_19.md)

## Product Surface Lanes

YonerAI keeps these lanes separate:

- API: contract authority
- CLI: command authority
- native Japanese CLI: ambiguous-command confirmation and explanation responsibility
- Web: product surface
- SNS: distribution lane, not a core blocker
- self-evolution: product intelligence and proposal scoring, not unapproved code mutation
- private runtime / control plane: execution authority, supervision, and operator-only behavior

Combining these lanes into one implementation batch is not a shortcut to public-core readiness.

## What Is Not Included / Not Claimed

This public checkpoint does not include or claim:

- production readiness
- shipping completeness
- official cloud completion
- live operations completion
- full product completion
- `src/cogs/ora.py` implementation
- runtime split implementation
- API / CLI / native Japanese CLI / Web / SNS implementation
- dependency vulnerability remediation
- runtime hardcoded path cleanup
- git history rewrite
- release tag creation
- deployment

## Local Development

Use the smallest profile that matches the area you are reviewing.

### Verified public runnable MVP path

The current public runnable checkpoint is the local Core API smoke path. It does not require Discord credentials, a model provider API key, a private repository, VPS access, deployment, or a release tag.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
$env:PYTHONPATH = "$PWD;$PWD\core\src"
$env:ORA_ALLOW_MISSING_SECRETS = "1"
python scripts/init_core_db.py
pytest tests/test_public_runnable_smoke.py tests/test_runtime_env_loader.py -q
```

Then start the local Core API and check health from another shell:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\core\src"
$env:ORA_ALLOW_MISSING_SECRETS = "1"
python -m ora_core.main
```

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8001/health
```

Expected health body:

```json
{"ok": true}
```

Do not commit `.env` or local secret files. Treat `.env.example` as a placeholder template, not production truth. Copying `.env.example` to `.env` is optional for local experiments, but the public smoke path above intentionally runs without real secrets.

Additional public-safe contract smoke:

```powershell
pytest tests/test_distribution_node_mvp.py -q
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

VPS, tunnel, official route, and deployment flows are not part of this public runnable MVP. Those belong in private/runtime/control-plane lanes.

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

For the public runnable MVP, the verified minimum checks are:

```powershell
git diff --check
pytest tests/test_public_runnable_smoke.py tests/test_runtime_env_loader.py -q
pytest tests/test_distribution_node_mvp.py -q
```

## Release Notes

- [v2026.5.19 public runnable MVP checkpoint](docs/releases/v2026.5.19-public-runnable-mvp-checkpoint.md)
- [v2026.5.18 public progress checkpoint](docs/releases/v2026.5.18-public-progress-checkpoint.md)
- [Release notes index](docs/RELEASE_NOTES.md)
- [Current phase context](docs/CURRENT_PHASE_CONTEXT.md)
