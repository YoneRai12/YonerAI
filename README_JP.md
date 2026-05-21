# YonerAI

YonerAI は、公式・ローカル・self-hosted の実行環境が変わっても、同じ体験と契約境界を保つための provider-independent AI execution foundation です。

[English README](README.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Latest checkpoint](docs/releases/v2026.5.21.4-implementation-guardrail-compression-checkpoint.md)

## YonerAI とは

YonerAI は長く使う AI runtime foundation です。目的は、利用する model provider、UI surface、local runtime、self-hosted profile が変わっても、ユーザー体験と contract boundary を維持することです。

これは単なる Discord bot でも、単なる model router でもありません。Discord、Web、relay、API、CLI、native Japanese CLI、SNS distribution、self-evolution は、それぞれ risk profile と approval requirement が違う別 lane です。

この README は public contract surface を説明します。内部運用、credential、live route、host-specific fact は公開しません。

## 現在の checkpoint

現在の design anchor は v7.7 です。

- provider independence
- official / local / self-hosted 方向での same experience
- approval gate 付き product intelligence としての self-evolution
- contract-first な public boundary
- private / control-plane の詳細を漏らさず、contract で public と分ける方針

現在の public checkpoint stream は、検証済みの日付と同日 suffix を使います。`v2026.5.21.4` は、implementation-first guardrail compression pass として、`/say` security/runtime patch、Discord contract acceptance tests、three-mode capability harness、`src/cogs/ora.py` extraction planning、ORA pure-helper contract tests を記録します。production release ではありません。

過去に作られた未来日付の checkpoint label は historical artifact として残る場合がありますが、current-date GitHub Release が明示的に supersede するまでは、現在の public/latest checkpoint として扱いません。

この repository は shipping completeness、production readiness、official cloud completion、live operations completion、full product completion を主張しません。

Pass 2 は stopped / not landed のままです。`src/cogs/ora.py` は private/runtime/control-plane boundary residue のままであり、狭い public patch で解決済みとは扱いません。

## 現在の MVP capability

現在の public MVP は、credential-free local Core API health smoke、mock/offline と loopback-only local LLM conversation の message contract、そして `clients/web` の temporary Web Chat MVP / smoke-demo surface です。ChatGPT のような完成済み Web chat product ではありません。

今日確認できること:

- public repository を clone する
- dependency を install する
- local Core API を起動する
- `GET /health` を呼び、`{"ok": true}` を受け取る
- `POST /v1/public/messages` で deterministic offline mock reply を受け取る
- `session_id` / `conversation_id` で一時的な conversation session metadata を返し、次の request に渡せる
- `POST /api/v1/agent/run` で local in-memory run smoke contract を確認し、`events_url` / `results_url` を受け取る
- `POST /v1/public/messages` に `mode: "local"` を指定して、loopback-only local LLM runtime に接続する
- `local_provider: "ollama"` または `local_provider: "openai_compatible_local"` を選ぶ
- `clients/cli` を local smoke CLI として install し、`yonerai health` / `yonerai message --mode mock "hello"` / `yonerai run --mode mock "hello"` を loopback Core に対して実行する
- `clients/web` を temporary Web Chat MVP としてローカルで開く
- `clients/web` から mock/offline、local Ollama、OpenAI-compatible local の smoke check を行う

まだ含まれていないもの:

- final Web product UI
- Google login
- conversation history sync
- persistent natural memory
- cross-device session history
- web search
- Discord chat / Discord gateway completion
- external provider live generation
- official cloud
- deployment
- full product completion
- production readiness

ユーザー向け capability table は [Current MVP Capability Matrix](docs/CURRENT_MVP_CAPABILITY_MATRIX.md) を参照してください。

## 3 つの利用形態

YonerAI は、同じ contract-first foundation を次の 3 つの使い方で扱えるように設計しています。

- Full Private Self-Host: ユーザーが runtime boundary を管理する形態。
- Official Hybrid Private: official governance と local/private runtime が明示的な contract で連携する形態。
- Official Managed Cloud: その lane が準備できたとき、同じ体験を managed surface として提供する形態。

これは product mode の説明であり、repository map ではありません。public docs では private operational detail ではなく、contract と user experience を説明します。

## この public repo に含まれるもの

public surface で扱うものは、review 可能な contract、public-safe runtime abstraction、capability boundary、connector pattern、client-facing documentation、regression test です。

private runtime behavior、operator-only workflow、live route、deployment truth、raw production inventory、credential、host-specific control-plane detail は public-facing docs に書きません。

境界をまたぐ連携は、API、event、file、auth claim、capability manifest、protocol、schema などの明示的な contract 経由で行います。

raw chain-of-thought は public chat、API、SSE、log、documentation、trace surface に出しません。public trace で扱うのは safe summary、label、detail、すでに public-safe な source だけです。

主な入口:

- [Current phase context](docs/CURRENT_PHASE_CONTEXT.md)
- [Codex / contributor workflow](docs/process/YONERAI_CODEX_WORKFLOW.md)
- [Current MVP Capability Matrix](docs/CURRENT_MVP_CAPABILITY_MATRIX.md)
- [Public file index](docs/repo/PUBLIC_FILE_INDEX.md)
- [Cross-repo same-experience matrix](docs/contracts/CROSS_REPO_SAME_EXPERIENCE_MATRIX_2026_05_20.md)
- [Official Cloud Control Plane MVP contract](docs/contracts/OFFICIAL_CLOUD_CONTROL_PLANE_MVP_2026_05_20.md)
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
- Security and backlog triage docs under `docs/security/` and `docs/maintenance/`
- [Latest traceability matrix](docs/TRACEABILITY_MATRIX_0_19.md)

## Product surface lane

YonerAI では次の lane を分けて扱います。

- API: contract authority
- CLI: command authority
- native Japanese CLI: 曖昧命令の確認と説明責任を持つ別 UX lane
- Web: product surface
- SNS: distribution lane。Core blocker ではありません
- self-evolution: product intelligence と proposal scoring。未承認の code mutation ではありません
- private runtime / control plane: execution authority、supervision、operator-only behavior

これらを 1 つの実装 batch にまとめても、public-core readiness の近道にはなりません。

## 含まれないもの / 主張しないもの

この public checkpoint は、次のものを含まず、また主張しません。

- production readiness
- shipping completeness
- official cloud completion
- live operations completion
- full product completion
- `src/cogs/ora.py` implementation
- runtime split implementation
- full API / CLI / native Japanese CLI / Web / SNS product implementation
- final Web product UI
- full dependency vulnerability remediation
- runtime hardcoded path cleanup
- git history rewrite
- signed production release
- deployment
- official cloud runtime

## Local development

確認したい範囲に合う最小 profile で起動してください。

### 検証済み public runnable MVP path

現在の public runnable checkpoint は、local Core API smoke path、credential-free mock/offline message contract、optional loopback-only local LLM mode、temporary Web Chat MVP です。Discord credential、cloud model provider API key、private repository、VPS access、deployment、release tag は不要です。

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

次に local Core API を起動し、別 shell から health を確認します。

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

同じ一時 session に follow-up message を送る場合は、返ってきた `session_id` を次の request に渡します。これは local process 内の metadata だけで、persistent memory や cross-device history ではありません。

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/v1/public/messages `
  -ContentType "application/json" `
  -Body '{"message":"follow up","mode":"mock","session_id":"session-smoke","conversation_id":"public-smoke"}'
```

Ollama-compatible runtime が loopback で起動している場合だけ、local mode を試せます。

```powershell
$env:ORA_LOCAL_LLM_PROVIDER = "ollama"
$env:ORA_LOCAL_LLM_BASE_URL = "http://127.0.0.1:11434"
$env:ORA_LOCAL_LLM_MODEL = "llama3.2"
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/v1/public/messages `
  -ContentType "application/json" `
  -Body '{"message":"hello","mode":"local","local_provider":"ollama","model":"llama3.2"}'
```

LM Studio、llama.cpp / llama-cpp-python server、OpenAI API mode を有効にした text-generation-webui、LocalAI などの OpenAI-compatible local server を使う場合も、server は loopback に置いてください。

```powershell
$env:ORA_LOCAL_LLM_PROVIDER = "openai_compatible_local"
$env:ORA_LOCAL_LLM_BASE_URL = "http://127.0.0.1:1234/v1"
$env:ORA_LOCAL_LLM_MODEL = "local-model"
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/v1/public/messages `
  -ContentType "application/json" `
  -Body '{"message":"hello","mode":"local","local_provider":"openai_compatible_local","model":"local-model"}'
```

local mode は loopback-only です。設定できる local LLM URL は `localhost`、`127.0.0.1`、`::1` に限定されます。任意の remote URL、LAN host、外部 provider API、tunnel、credential 埋め込み、query string、fragment、control-plane endpoint は default で拒否されます。

### Local CLI smoke

Core API を loopback で起動したまま、temporary local CLI smoke surface を試す場合:

```powershell
python -m pip install -e clients/cli
yonerai health
yonerai message --mode mock "hello"
yonerai run --mode mock "hello"
```

この CLI は default で `http://127.0.0.1:8001` を使い、remote API origin を拒否します。deploy、shell execution、persistent memory、Google login、external provider live generation、production packaging は追加しません。

### Temporary Web Chat MVP

Core API を port `8001` で起動したまま、別 shell で web client を起動します。

```powershell
cd clients\web
npm ci
npm run dev
```

`http://127.0.0.1:3000` を開き、短い message を送ってください。画面は `/api/public/messages` に POST し、local rewrite で `/v1/public/messages` に接続します。

この画面では、mock/offline、local Ollama、OpenAI-compatible local を選べます。任意の provider URL 入力は持たせていません。local provider base URL は Core API 側の loopback validation に残します。

Core API port `8001` が別の local process で使われている場合は、現在の Core API を別の loopback port で起動し、`npm run dev` の前に `YONERAI_CORE_API_ORIGIN` を設定します。この rewrite origin も loopback-only で、remote host は拒否します。

これは temporary smoke/demo surface であり、final product UI foundation ではありません。

`.env` や local secret file は commit しません。`.env.example` は placeholder template であり、production truth ではありません。

## Public safety

commit してはいけないもの:

- real `.env` file や secret backup
- credential、service-account file、token、private key、tunnel secret
- local SQLite database、WAL/SHM、log、cache、generated audio、local state
- raw production inventory、live route map、operational ledger、break-glass detail、control-plane DDL
- private renderer truth や host-specific operational exactness
- public docs 内の local absolute path や user-machine path

必要な情報が public-safe でない場合は、実体ではなく placeholder、contract、public-safe summary、TODO を置きます。

## Checks

変更した領域に応じた check を実行してください。docs-only hygiene の最小確認は次です。

```powershell
git diff --check
git status --short --branch
```

public runnable MVP の検証済み最小 check は次です。

```powershell
git diff --check
pytest tests/test_public_runnable_smoke.py tests/test_runtime_env_loader.py -q
pytest tests/test_distribution_node_mvp.py -q
pytest tests/test_public_core_message_mvp.py tests/test_ora_import_map.py -q
cd clients\web; npm ci; npm run lint; npm run build; npm audit --omit=dev
```

## Release notes

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
