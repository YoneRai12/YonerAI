# YonerAI

Provider-independent AI execution foundation for keeping one reliable AI experience across official, local, and self-hosted runtimes.

[Japanese README](README_JP.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Root file / PR traceability](docs/repo/FILE_PR_TRACEABILITY_MATRIX_CURRENT.md) | [Latest checkpoint archive](docs/releases/v2026.5.21.5-implementation-continuation-checkpoint.md)

## What YonerAI Is

YonerAI is a long-lived AI runtime foundation. Its purpose is to keep the same user-facing experience and the same contract boundaries even when the active model provider, UI surface, local runtime, or self-hosted profile changes.

It is not just a Discord bot and not just a model router. Discord, Web, relay, API, CLI, native Japanese CLI, SNS distribution, and self-evolution are separate product lanes with different risk profiles and approval requirements.

This public README describes the public contract surface. It does not publish internal operations detail, credentials, live routes, or host-specific facts.

## Install and start YonerAI

This is the local CLI runtime path, not a production cloud installer. It installs
the CLI from this checkout and creates the `yonerai` command locally.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai
```

After install, `yonerai` starts the interactive CLI when stdin is a TTY.
`yonerai chat` starts the same screen explicitly. For CI, pipes, and scripted
input, use `yonerai chat --script` or `yonerai ask --auto`.

The interactive CLI is now the YonerAI Mission Control CLI: it shows the
selected provider, route, local node state, ledger state, safety mode, run_id,
task progress, and the deterministic reviewer/subagent plan. It does not start
uncontrolled agents or enable live providers by default.

## Quickstart: Public Demo

After clone, the fastest public-safe way to see the current YonerAI slice is the credential-free demo command. It runs in-process and does not require a Core API server, Discord token, Oracle access, provider API key, Google login, deployment, or persistent memory.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai
yonerai chat
yonerai config show --pretty --lang ja
yonerai start --guided --lang ja
yonerai start --guided --json
yonerai providers --pretty --lang ja
yonerai ask "hello" --auto --pretty --lang ja
yonerai demo --pretty
yonerai demo --json
yonerai doctor --pretty
yonerai doctor --pretty --lang ja
yonerai status --pretty
yonerai manifest verify releases/manifest.example.json --pretty
yonerai plan "summarize public docs" --json
yonerai ask "summarize public docs" --provider mock --json
yonerai hybrid run --pretty
yonerai hybrid run --json
yonerai search mock "YonerAI alpha2" --json
yonerai ops plan git-status --json
yonerai install plan --manifest releases/manifest.example.json --json
```

## First 5 minutes

`yonerai` opens the local interactive terminal when stdin is a TTY.
Use `yonerai chat` for the same screen explicitly. The interactive shell is a
standard-library terminal app, not a full-screen GUI: type a message to run the
same safe `ask --auto` path, or use slash commands.

```text
/settings        show language/provider/safety settings
/providers       show mock/local/API provider readiness without printing keys
/safety          show network/tool/file/provider boundaries
/tasks           show current and recent task progress
/agents          show the planned planner/researcher/reviewer roles
/runs            list redacted local run history
/show <run_id>   show one redacted run
/local-llm       show loopback-only local LLM setup guidance
/language ja|en  change UI language
/provider auto|mock|local|openai-compatible|anthropic|gemini
/ledger on|off   toggle redacted local run ledger
/live on|off     toggle explicit live/local execution permission
/network on|off  toggle explicit network permission
/select <n> <v>  change a numbered setting from the settings screen
/quit            exit
```

On first interactive launch, YonerAI asks for Japanese or English and stores
only non-secret local preferences. Non-TTY use, for example pipes or CI, does
not hang; it prints fallback instructions. Use `yonerai chat --script` when you
intentionally want to feed scripted input.

In Japanese mode, the primary slash commands are Japanese (`/設定`, `/タスク`,
`/ローカルLLM`, `/安全`, `/履歴`). English aliases such as `/settings` and
`/tasks` remain available for compatibility.

`yonerai start --guided` is the guided path for a first local run. It is written
for people who want copyable next actions, not for people already familiar with
the internals.

```powershell
yonerai start --guided --lang ja
yonerai chat
yonerai config set language ja
yonerai config show --pretty --lang ja
yonerai start --guided --json
yonerai demo --pretty
yonerai doctor --pretty --lang ja
yonerai ask "hello" --provider mock --json
yonerai hybrid run --pretty
yonerai ask "use this selected sample file" --file sample.txt --workspace .yonerai-sample-workspace --provider mock --json
yonerai ask "hello" --provider mock --json --ledger .yonerai-runs.jsonl
yonerai runs list --ledger .yonerai-runs.jsonl --pretty --lang ja
```

If you already have a local LLM server on loopback, for example Ollama on
`127.0.0.1:11434` or an LM Studio / OpenAI-compatible server on
`127.0.0.1:1234`, `yonerai start --guided` checks only local metadata endpoints.
It does not send a prompt to the model. If a loopback endpoint is detected, the
guided output prints the exact environment variables to set before you choose
the local provider path. After you intentionally enable local execution, you can
try:

```powershell
$env:ORA_LOCAL_LLM_ENABLED = "1"
$env:ORA_LOCAL_LLM_PROVIDER = "ollama"
$env:ORA_LOCAL_LLM_BASE_URL = "http://127.0.0.1:11434"
$env:ORA_LOCAL_LLM_MODEL = "llama3.2"
yonerai ask "hello" --provider local --live --json
```

For LM Studio or another OpenAI-compatible local server, keep the endpoint on
loopback and use:

```powershell
$env:ORA_LOCAL_LLM_ENABLED = "1"
$env:ORA_LOCAL_LLM_PROVIDER = "openai_compatible_local"
$env:ORA_LOCAL_LLM_BASE_URL = "http://127.0.0.1:1234/v1"
$env:ORA_LOCAL_LLM_MODEL = "local-model"
yonerai ask "hello" --provider local --live --json
```

What this first path explains:

- `yonerai` / `yonerai chat` starts a Japanese-first interactive shell with
  chat, provider status, safety settings, and run history slash commands.
- `yonerai config show/set` stores only local non-secret preferences such as
  language, provider preference, approval mode, and file-access mode.
- `yonerai start --guided --lang ja` prints a mock-first path, Local LLM status,
  workspace file guard example, ledger example, and current limitations.
- `yonerai providers --pretty --lang ja` shows which provider paths are usable
  now, which require explicit `--live`, and which setup step is missing.
- `yonerai ask "hello" --auto --pretty --lang ja` classifies the task, chooses a
  safe route, shows the selected provider, and explains whether a ledger was
  written.
- `yonerai demo --pretty` shows the current alpha slice without credentials.
- `yonerai doctor --pretty --lang ja` checks local setup without installing or
  mutating PATH.
- `yonerai hybrid run --pretty` runs a local-dev Hybrid slice: route preview,
  verified test Local Node session, in-memory relay transport, mock provider
  execution, redacted ledger events, and an Oracle stub request/result envelope.
- Local LLM detection is loopback-only and metadata-only.
- Mock `ask` returns a public-safe `run_id`.
- `--ledger <local.jsonl>` is optional and writes redacted local-only run
  history.
- `yonerai runs list/show --pretty --lang ja` reads only the explicitly selected
  local ledger path or `YONERAI_RUN_LEDGER_PATH`; it does not upload history.
- Workspace file support is a Workspace File Access Guard: it reads only an
  explicitly selected UTF-8 text file inside an explicit workspace allowlist.
  The sample command expects you to create `.yonerai-sample-workspace/sample.txt`
  yourself; `yonerai start --guided` does not create files, read files, or write
  a ledger.

Still not included: production readiness, Official Managed Cloud runtime,
production Oracle, live Discord restoration, arbitrary shell execution,
arbitrary local file access, folder crawling, PDF/image parsing, automatic file
summarization, production installer, npm/winget distribution, Google login,
production DB behavior, complete persistent memory, or a solved
`src/cogs/ora.py`.

## What you can try in v0.1.0-alpha.2

v0.1.0-alpha.2 is a local public alpha slice, not a finished YonerAI product.
You can try these surfaces without provider credentials, Discord tokens,
production services, or live network calls:

- Mock provider execution: `yonerai ask "summarize public docs" --provider mock --json`
- Run trace preview/history surface: mock `ask` returns a public-safe `run_id`.
- Workspace File Access Guard: `yonerai ask "use this selected file" --file <path> --workspace <dir> --provider mock --json`
- Mock search: `yonerai search mock "YonerAI alpha2" --json`
- SafeShell plan: `yonerai ops plan git-status --json`
- Local memory: `yonerai memory add "local note" --store <local.jsonl> --confirm-local --json`
- Synthetic Discord boundary: `yonerai discord synthetic "hello" --json`
- Status fixture: `yonerai status --source fixture --json`
- Installer dry-run planning: `yonerai install plan --manifest releases/manifest.example.json --json`

External provider adapters and local LLM execution exist behind explicit opt-in
gates. External providers require `--live` and provider-specific environment
flags; local LLM endpoints must be loopback-only.

Not included in alpha2: production readiness, Official Managed Cloud runtime,
production Oracle control-plane behavior, live Discord restoration, live web
search by default, arbitrary shell execution, arbitrary file access,
installer-ready distribution, npm/winget packages, production signing/trust
material, Google login, production DB behavior, complete persistent memory, or a
claim that `src/cogs/ora.py` is solved.

`yonerai quickstart` is an alias for the same demo.

The JSON output uses the stable `yonerai-public-demo/v1` contract with
`schema_version: "1.0"` so CI, docs, and release checks can assert the same
public demo shape.

`yonerai doctor` and `yonerai status` are offline, non-mutating diagnostics for
the public demo and installer-readiness surface. `--lang ja` changes only the
human-readable output; JSON remains English-keyed and stable for tests and CI.
Pretty diagnostics also support `--color auto|never|always`; JSON output never
includes terminal color codes.
`yonerai manifest verify <path>` validates a local release manifest only. It
does not download artifacts, execute installers, mutate PATH, or connect to live
services.

The demo shows one visible vertical slice:

- public Core health, offline mock message, and run contract
- public mode boundary: Self-host local surface, Hybrid Local Node contract/dev simulator, Managed Cloud external contract-only
- route preview for public, private/local, and dangerous work
- test-only Local Node signed manifest, enrollment/session, signed envelope, replay rejection, and approval gate
- managed download guard accepting managed file URLs and rejecting arbitrary unsafe URLs
- synthetic proposal-only self-evolution scorecard and approval draft
- alpha2 capability boundaries for opt-in providers, loopback local LLM, Workspace File Access Guard, mock search, SafeShell planning, explicit local memory, synthetic Discord, status contracts, and installer dry-run planning
- explicit limitations: no production Oracle, live Discord restoration, default/cloud memory, Google login, official cloud runtime in this repo, default live provider generation, arbitrary shell, arbitrary file access, or deploy

## Current Checkpoint

The active design anchor is v7.7:

- provider independence
- the same experience across official, local, and self-hosted directions
- self-evolution as approval-gated product intelligence
- contract-first public boundaries
- public/private/control-plane separation by contract, not by leaking internal operations detail

The latest runnable semantic pre-release note is `docs/releases/0.1.0-alpha.2.md`. The latest historical checkpoint note is `v2026.5.21.5`, which records layer upload hardening, the first behavior-preserving `src/cogs/ora.py` pure-helper extraction, ORA/YonerAI naming compatibility policy, and a three-mode docs-only capability acceptance harness extension. The alpha2 note is a public alpha capability slice; the checkpoint archive note is not a production release.

Future internal checkpoint logs belong under `docs/changelog/checkpoints/`, not GitHub Releases. GitHub Releases are reserved for runnable public milestones such as semantic pre-releases.

Older date-suffix GitHub Releases remain historical artifacts. Do not delete, retag, or treat them as evidence of production readiness.

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
- call `POST /api/v1/agent/run` for a local in-memory run smoke contract and read `events_url` / `results_url`
- install `clients/cli` locally and run `yonerai health`, `yonerai message --mode mock "hello"`, and `yonerai run --mode mock "hello"` against loopback Core
- run `yonerai demo --pretty` or `yonerai demo --json` to see the public demo slice without credentials or a running Core API process
- run `yonerai doctor --pretty`, `yonerai doctor --pretty --lang ja`, and `yonerai status --pretty` for offline public-demo diagnostics
- run `yonerai manifest verify releases/manifest.example.json --pretty` for local manifest contract verification without downloading or installing anything
- run `yonerai plan "task"` and `yonerai ask "task" --provider mock` for public-safe planning and mock provider execution
- run `yonerai ask "use this selected file" --file <path> --workspace <dir> --provider mock` for explicit workspace-only text file access guard behavior
- run `yonerai hybrid run --pretty` for a local-dev Hybrid execution slice that
  keeps execution in process/loopback-only, records redacted run events, and
  demonstrates Oracle stub envelopes without production Oracle or official cloud
  runtime
- run `yonerai search mock "query"` for deterministic mock search fixtures
- run `yonerai ops plan git-status` for SafeShell diagnostic planning without arbitrary shell execution
- run `yonerai memory add/list/delete/export --store <local.jsonl>` for explicit opt-in local-only memory records
- run `yonerai discord synthetic "message"` for synthetic Discord gateway boundary checks
- run `yonerai status --source fixture` for official/status contract fixtures with no production service call
- run `yonerai install plan --manifest releases/manifest.example.json` for safe local installer dry-run planning
- run `yonerai install plan-windows` as the Windows-specific dry-run planning alias
- call `POST /v1/public/messages` with `mode: "local"` to reach a loopback-only local LLM runtime
- choose `local_provider: "ollama"` or `local_provider: "openai_compatible_local"` for supported local server styles
- open `clients/web` locally as a temporary Web Chat MVP / smoke-demo surface
- from `clients/web`, send `mock` / `offline` messages through that endpoint
- from `clients/web`, select local Ollama or OpenAI-compatible local mode when the Core API and local model server are already running on loopback

Not included yet: final Web product UI, Google login, conversation history sync, complete persistent natural memory, live web search, live Discord chat restoration, default live external provider generation, official cloud runtime, deployment, arbitrary shell execution, arbitrary local file access, installer-ready distribution, or full product completion. The public session scaffold is in-memory metadata only; explicit local memory v0.1 is local-only and opt-in, not cloud memory or cross-device history.

See [Current MVP Capability Matrix](docs/CURRENT_MVP_CAPABILITY_MATRIX.md) for the user-facing capability table.

## Product Modes

YonerAI is designed around three high-level ways to use the same contract-first foundation:

- Full Private Self-Host: the public repository can support the local/self-hosted public MVP surface, with the operator responsible for the runtime boundary.
- Official Hybrid Private: the public repository can support Local Node contracts, signed-contract tests, and a non-production local-dev simulator; official cloud coordination remains external/private.
- Official Managed Cloud: a product mode whose runtime and control plane are official/private infrastructure, not implemented or runnable in this public repository.

These are product modes, not a repository map. Public docs should describe the contract and user experience, not private operational detail.

## What Is Included In This Public Repo

The public surface is for reviewable contracts, public-safe runtime abstractions, capability boundaries, connector patterns, client-facing documentation, and regression tests.

This repository intentionally includes the Full Private Self-Host public/local surface and the Official Hybrid Private Local Node contract/dev-simulator surface. It does not include the Official Managed Cloud runtime, production Oracle/control plane, production trust store, production signing keys, live Discord gateway, Google login, persistent memory, deployment system, real official-cloud telemetry, or production self-evolution.

Self-evolution code in this repository is synthetic and proposal-only. It may score and draft safe improvement proposals from synthetic events, but it does not observe real official-cloud user behavior, ingest support email, open issues or pull requests, merge, deploy, or apply patches.

Private runtime behavior, operator-only workflows, live routes, deployment truth, raw production inventory, credentials, and host-specific control-plane details do not belong in public-facing documentation.

Cross-boundary interaction should happen through explicit contracts such as APIs, events, files, auth claims, capability manifests, protocols, and schemas.

Raw chain-of-thought must not cross public chat, API, SSE, log, documentation, or trace surfaces. Public traces should expose only safe summaries, labels, details, and already-public sources.

Useful starting points:

- [Current phase context](docs/CURRENT_PHASE_CONTEXT.md)
- [Codex / contributor workflow](docs/process/YONERAI_CODEX_WORKFLOW.md)
- [Release governance](docs/process/YONERAI_RELEASE_GOVERNANCE.md)
- [Current MVP Capability Matrix](docs/CURRENT_MVP_CAPABILITY_MATRIX.md)
- [Public file index](docs/repo/PUBLIC_FILE_INDEX.md)
- [Cross-repo same-experience matrix](docs/contracts/CROSS_REPO_SAME_EXPERIENCE_MATRIX_2026_05_20.md)
- [Official Cloud Control Plane MVP contract](docs/contracts/OFFICIAL_CLOUD_CONTROL_PLANE_MVP_2026_05_20.md)
- Feature inventory and releaseability map under `docs/capabilities/`
- [External Agent API](docs/contracts/external-agent-api.md)
- [SSE Run Events](docs/contracts/sse-run-events.md)
- [Native Japanese CLI contract](docs/contracts/native-japanese-cli-contract-0.1.md)
- [Web surface capability manifest](docs/contracts/web-surface-capability-manifest-0.1.md)
- [Capability / Extension Boundary 0.1](docs/contracts/capability-extension-boundary-0.1.md)
- [Tools/MCP Safe Subset 0.1](docs/contracts/tools-mcp-safe-subset-0.1.md)
- [Large codebase feature inventory](docs/architecture/LARGE_CODEBASE_FEATURE_INVENTORY_2026_05_21.md)
- [v7.7 integration map](docs/architecture/V7_7_INTEGRATION_MAP_2026_05_21.md)
- [Growth/SNS claim guardrails](docs/growth/CLAIM_GUARDRAILS_2026_05_20.md)
- [Growth/SNS demo plan](docs/growth/DEMO_PLAN_2026_05_20.md)
- [Growth/SNS FAQ](docs/growth/FAQ_2026_05_20.md)
- [v2026.5.21.5 Implementation continuation checkpoint note](docs/releases/v2026.5.21.5-implementation-continuation-checkpoint.md)
- [v2026.5.21.4 Implementation guardrail compression checkpoint note](docs/releases/v2026.5.21.4-implementation-guardrail-compression-checkpoint.md)
- [v2026.5.21.3 Clean continuation security and Discord preflight checkpoint note](docs/releases/v2026.5.21.3-clean-continuation-security-discord-preflight-checkpoint.md)
- [v2026.5.21.2 Final public presentation checkpoint note](docs/releases/v2026.5.21.2-final-public-presentation-checkpoint.md)
- [v2026.5.21.1 Public repository hardening checkpoint note](docs/releases/v2026.5.21.1-public-repository-hardening-checkpoint.md)
- [v2026.5.20.14 Tools/MCP safe subset contract checkpoint note](docs/releases/v2026.5.20.14-tools-mcp-safe-subset-contract-checkpoint.md)
- [v2026.5.20.13 Capability / Extension Boundary checkpoint note](docs/releases/v2026.5.20.13-capability-extension-boundary-checkpoint.md)
- [v2026.5.20.12 Local LLM error reporting hardening checkpoint note](docs/releases/v2026.5.20.12-local-llm-error-reporting-hardening-checkpoint.md)
- [v2026.5.20.11 Growth/SNS claim guardrails checkpoint note](docs/releases/v2026.5.20.11-growth-sns-claim-guardrails-checkpoint.md)
- [v2026.5.20.10 Web surface capability manifest checkpoint note](docs/releases/v2026.5.20.10-web-surface-capability-manifest-checkpoint.md)
- [v2026.5.20.9 Native Japanese CLI contract checkpoint note](docs/releases/v2026.5.20.9-native-japanese-cli-contract-checkpoint.md)
- [v2026.5.20.8 Surface CLI smoke checkpoint note](docs/releases/v2026.5.20.8-surface-cli-smoke-checkpoint.md)
- [v2026.5.20.7 Surface API run contract checkpoint note](docs/releases/v2026.5.20.7-surface-api-run-contract-checkpoint.md)
- [v2026.5.20.6 Hybrid envelope policy semantics checkpoint note](docs/releases/v2026.5.20.6-hybrid-envelope-policy-semantics-checkpoint.md)
- [Surface/repo strategy checkpoint](docs/strategy/SURFACE_REPO_STRATEGY_2026_05_20.md)
- [Open PR triage checkpoint](docs/maintenance/OPEN_PR_TRIAGE_2026_05_20.md)
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
- Official Managed Cloud runtime or control plane
- production Oracle
- production trust store or production signing keys
- real official-cloud telemetry or analytics
- autonomous self-evolution deployment

## Local Development

Use the smallest profile that matches the area you are reviewing.

### Verified public runnable MVP path

The current public runnable MVP path is the local Core API smoke path plus credential-free mock/offline messaging and an optional loopback-only local LLM mode. It does not require Discord credentials, a cloud model provider API key, a private repository, VPS access, deployment, or a release tag.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
$env:PYTHONPATH = "$PWD;$PWD\core\src"
$env:ORA_ALLOW_MISSING_SECRETS = "1"
python scripts/init_core_db.py
pytest tests/test_public_runnable_smoke.py tests/test_runtime_env_loader.py -q
python scripts/dev/public_mvp_smoke.py
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

To try the temporary local CLI smoke surface, install the CLI package locally and keep the Core API running on loopback:

```powershell
python -m pip install -e clients/cli
yonerai demo --pretty
yonerai doctor --pretty
yonerai doctor --pretty --lang ja
yonerai status --pretty
yonerai manifest verify releases/manifest.example.json --pretty
yonerai health
yonerai message --mode mock "hello"
yonerai run --mode mock "hello"
```

The CLI defaults to `http://127.0.0.1:8001`, rejects remote API origins, and does not add deploy, shell execution, persistent memory, Google login, external provider live generation, or production packaging.
The demo, doctor, status, and manifest verification paths are offline/local-only
and do not require a running Core API process.

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
pytest tests/test_public_mvp_smoke_script.py -q
pytest tests/test_public_runnable_smoke.py tests/test_runtime_env_loader.py -q
pytest tests/test_distribution_node_mvp.py -q
pytest tests/test_public_core_message_mvp.py tests/test_ora_import_map.py -q
cd clients\web; npm ci; npm run lint; npm run build; npm audit --omit=dev
```

## Release Notes

- [v2026.5.20.6 Hybrid envelope policy semantics checkpoint](docs/releases/v2026.5.20.6-hybrid-envelope-policy-semantics-checkpoint.md)
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
