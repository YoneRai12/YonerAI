# YonerAI

Provider-independent AI execution foundation for keeping one reliable AI experience across official, local, and self-hosted runtimes.

[Japanese README](README_JP.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Latest checkpoint](docs/releases/v2026.5.20.5-public-surface-release-hygiene-checkpoint.md)

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

The current public checkpoint stream uses the verified 2026-05-20 date with same-day suffixes. `v2026.5.20.5` records the public surface and release hygiene cleanup for this lane. It is a checkpoint note, not a production release.

Older future-dated checkpoint labels can remain as historical artifacts, but they should not be used as the current public/latest checkpoint unless a current-date GitHub Release explicitly supersedes them.

This repository does not claim shipping completeness, production readiness, official cloud completion, live operations completion, or full product completion.

Pass 2 remains stopped / not landed. `src/cogs/ora.py` remains unresolved private/runtime/control-plane boundary residue and is not treated as a narrow public patch target.

## Current MVP Capability

The current public MVP is a credential-free local Core API health smoke plus message contracts for mock/offline and loopback-only local LLM conversation. It is not a ChatGPT-like finished product.

What works today:

- clone the public repository
- install dependencies
- start the local Core API
- call `GET /health` and receive `{"ok": true}`
- call `POST /v1/public/messages` and receive a deterministic offline mock reply
- send follow-up public messages with `session_id` / `conversation_id` and receive non-persistent turn metadata
- call `POST /v1/public/messages` with `mode: "local"` to reach a loopback-only local LLM runtime
- choose `local_provider: "ollama"` or `local_provider: "openai_compatible_local"` for supported local server styles
- open `clients/web` locally as a temporary Web Chat MVP / smoke-demo surface
- from `clients/web`, send `mock` / `offline` messages through that endpoint
- from `clients/web`, select local Ollama or OpenAI-compatible local mode when the Core API and local model server are already running on loopback

Not included yet: final Web product UI, Google login, conversation history sync, persistent natural memory, web search, Discord chat, external provider live generation, official cloud, deployment, or full product completion. The public session scaffold is in-memory metadata only; it is not persistent memory or cross-device history.

See [Current MVP Capability Matrix](docs/CURRENT_MVP_CAPABILITY_MATRIX.md) for the user-facing capability table.

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
- [Current MVP Capability Matrix](docs/CURRENT_MVP_CAPABILITY_MATRIX.md)
- [Cross-repo same-experience matrix](docs/contracts/CROSS_REPO_SAME_EXPERIENCE_MATRIX_2026_05_20.md)
- [Official Cloud Control Plane MVP contract](docs/contracts/OFFICIAL_CLOUD_CONTROL_PLANE_MVP_2026_05_20.md)
- Feature inventory and releaseability map under `docs/capabilities/`
- [External Agent API](docs/contracts/external-agent-api.md)
- [SSE Run Events](docs/contracts/sse-run-events.md)
- [v2026.5.20.5 Public surface and release hygiene checkpoint note](docs/releases/v2026.5.20.5-public-surface-release-hygiene-checkpoint.md)
- [Root surface policy](docs/repo/ROOT_SURFACE_POLICY.md)
- [Release date hygiene policy](docs/repo/RELEASE_DATE_HYGIENE_POLICY.md)
- [Public presentation policy](docs/repo/PUBLIC_PRESENTATION_POLICY.md)
- [Zero-trust practicality matrix](docs/security/ZERO_TRUST_PRACTICALITY_MATRIX.md)
- [v2026.5.20.1 Official Cloud Control Plane MVP planning checkpoint](docs/releases/v2026.5.20.1-official-cloud-control-plane-mvp-planning-checkpoint.md)
- [v2026.5.20 Web UI mock-chat checkpoint note](docs/releases/v2026.5.20-web-ui-mock-chat-security-checkpoint.md)
- [v2026.5.20 Local LLM conversation checkpoint note](docs/releases/v2026.5.20-local-llm-conversation-mvp-checkpoint.md)
- [Dependabot triage 2026-05-20](docs/security/DEPENDABOT_TRIAGE_2026_05_20.md)
- Security and backlog triage docs under `docs/security/` and `docs/maintenance/`
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
- full API / CLI / native Japanese CLI / Web / SNS product implementation
- full dependency vulnerability remediation
- runtime hardcoded path cleanup
- git history rewrite
- signed production release
- deployment
- official cloud runtime

## Local Development

Use the smallest profile that matches the area you are reviewing.

### Verified public runnable MVP path

The current public runnable checkpoint is the local Core API smoke path plus credential-free mock/offline messaging and an optional loopback-only local LLM mode. It does not require Discord credentials, a cloud model provider API key, a private repository, VPS access, deployment, or a release tag.

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

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/v1/public/messages `
  -ContentType "application/json" `
  -Body '{"message":"hello","mode":"mock"}'
```

To group follow-up messages in one temporary public session, pass the returned `session_id` back on the next request:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/v1/public/messages `
  -ContentType "application/json" `
  -Body '{"message":"follow up","mode":"mock","session_id":"session-smoke","conversation_id":"public-smoke"}'
```

If you have a local Ollama-compatible runtime listening on loopback, try local mode:

```powershell
$env:ORA_LOCAL_LLM_PROVIDER = "ollama"
$env:ORA_LOCAL_LLM_BASE_URL = "http://127.0.0.1:11434"
$env:ORA_LOCAL_LLM_MODEL = "llama3.2"
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/v1/public/messages `
  -ContentType "application/json" `
  -Body '{"message":"hello","mode":"local"}'
```

For an OpenAI-compatible local server such as LM Studio, llama.cpp / llama-cpp-python server, text-generation-webui with OpenAI API enabled, or LocalAI, keep the server on loopback and select the compatible provider:

```powershell
$env:ORA_LOCAL_LLM_PROVIDER = "openai_compatible_local"
$env:ORA_LOCAL_LLM_BASE_URL = "http://127.0.0.1:1234/v1"
$env:ORA_LOCAL_LLM_MODEL = "local-model"
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/v1/public/messages `
  -ContentType "application/json" `
  -Body '{"message":"hello","mode":"local","local_provider":"openai_compatible_local","model":"local-model"}'
```

Expected health body:

```json
{"ok": true}
```

Expected public message response includes:

```json
{
  "ok": true,
  "mode": "mock",
  "session_id": "session-smoke",
  "turn_index": 1,
  "history_count": 1,
  "memory_persisted": false,
  "provider": "offline-mock",
  "requires_approval": false
}
```

Expected local LLM response includes:

```json
{
  "ok": true,
  "mode": "local",
  "provider": "local-ollama",
  "requires_approval": false
}
```

For OpenAI-compatible local mode, `provider` is `local-openai-compatible`.

Local mode is loopback-only. The configured local LLM URL must be `localhost`, `127.0.0.1`, or `::1`; arbitrary remote URLs, LAN hosts, external provider APIs, tunnels, embedded credentials, query strings, fragments, and control-plane endpoints are rejected by default. Model availability depends on the local server. YonerAI passes the requested local model name through; it does not hardcode model families.

This message endpoint does not persist memory, run tools, complete the Web/Discord chat product, or call external OpenAI, Anthropic, Gemini, web search, SNS, or Discord services. Session metadata is kept in the running Core API process only and is cleared on process restart.

To try the temporary Web Chat MVP, keep the Core API running on port `8001`, then start the web client from another shell:

```powershell
cd clients\web
npm ci
npm run dev
```

Open `http://127.0.0.1:3000` and send a short message. The page posts to `/api/public/messages`, which is rewritten locally to `/v1/public/messages`. The page can use mock/offline mode, local Ollama mode, or OpenAI-compatible local mode. It does not expose arbitrary provider URLs; local provider base URLs stay under Core API loopback validation. This remains a temporary smoke/demo surface, not the final product UI foundation.

If another local process already occupies Core API port `8001`, start the current Core API on a different loopback port and set `YONERAI_CORE_API_ORIGIN` before running `npm run dev`. That rewrite origin is loopback-only and rejects remote hosts.

Do not commit `.env` or local secret files. Treat `.env.example` as a placeholder template, not production truth. Copying `.env.example` to `.env` is optional for local experiments, but the public smoke path above intentionally runs without real secrets.

Additional public-safe contract smoke:

```powershell
pytest tests/test_distribution_node_mvp.py -q
pytest tests/test_public_core_message_mvp.py tests/test_ora_import_map.py -q
```

Optional local web/API runtime:

```powershell
.venv\Scripts\Activate.ps1
uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000
```

Optional web client:

```powershell
cd clients\web
npm ci
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
pytest tests/test_public_core_message_mvp.py tests/test_ora_import_map.py -q
cd clients\web; npm ci; npm run lint; npm run build; npm audit --omit=dev
```

## Release Notes

- [v2026.5.20.5 Public surface and release hygiene checkpoint](docs/releases/v2026.5.20.5-public-surface-release-hygiene-checkpoint.md)
- [v2026.5.20.4 Hybrid Connector Fixture and Memory Policy checkpoint](docs/releases/v2026.5.20.4-hybrid-connector-fixture-memory-policy-checkpoint.md)
- [v2026.5.20.3 Hybrid Signed Envelope Donation Policy checkpoint](docs/releases/v2026.5.20.3-hybrid-signed-envelope-donation-policy-checkpoint.md)
- [v2026.5.20.2 Conversation Session Scaffold checkpoint](docs/releases/v2026.5.20.2-conversation-session-scaffold-checkpoint.md)
- [v2026.5.20.1 Official Cloud Control Plane MVP planning checkpoint](docs/releases/v2026.5.20.1-official-cloud-control-plane-mvp-planning-checkpoint.md)
- [v2026.5.20 Web UI mock-chat security checkpoint](docs/releases/v2026.5.20-web-ui-mock-chat-security-checkpoint.md)
- [v2026.5.20 public core message MVP checkpoint](docs/releases/v2026.5.20-public-core-message-mvp-checkpoint.md)
- [v2026.5.19 public runnable MVP checkpoint](docs/releases/v2026.5.19-public-runnable-mvp-checkpoint.md)
- [v2026.5.18 public progress checkpoint](docs/releases/v2026.5.18-public-progress-checkpoint.md)
- [Release notes index](docs/RELEASE_NOTES.md)
- [Current phase context](docs/CURRENT_PHASE_CONTEXT.md)
