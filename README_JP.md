# YonerAI

YonerAI は、公式・ローカル・self-hosted の実行環境が変わっても、同じ利用体験と同じ境界契約を保つための provider-independent AI execution foundation です。

[English README](README.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Codex / contributor workflow](docs/process/YONERAI_CODEX_WORKFLOW.md) | [Release governance](docs/process/YONERAI_RELEASE_GOVERNANCE.md)

この public repository は public contract surface を説明します。内部運用詳細、credential、live route、host 固有の事実は公開しません。

## YonerAI とは

YonerAI は単なる Discord bot でも、単なる model router でもありません。API、CLI、Web、Discord gateway、relay、native Japanese CLI、SNS distribution、self-evolution は、それぞれ別の product lane であり、risk profile と approval requirement も異なります。

この public repo で確認できる中核は、公開可能な core contract、self-host/local surface、Hybrid Local Node contract/dev simulator、proposal-only self-evolution です。

## Quickstart: public demo

clone 後に現在の public-safe slice を見る最短手順は、credential-free の demo command です。Core API server の常時起動、Discord token、Oracle access、provider API key、Google login、deployment、persistent memory は不要です。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai demo --pretty
yonerai demo --json
yonerai doctor --pretty --lang ja
yonerai status --pretty --lang ja
yonerai manifest verify releases/manifest.example.json --pretty --lang ja
```

`yonerai quickstart` は `yonerai demo` の alias です。

`yonerai demo --json` は stable contract `yonerai-public-demo/v1` と `schema_version: "1.0"` を出力します。`yonerai demo --pretty` は同じ内容を release check 向けに読みやすく表示します。

## v0.1.0-alpha.2 で今試せること

v0.1.0-alpha.2 は local public alpha slice です。完成品の YonerAI ではありません。provider credential、Discord token、production service、live network call なしで、次を試せます。

- Mock provider execution: `yonerai ask "summarize public docs" --provider mock --json`
- Run ID: mock `ask` は public-safe な `run_id` を返します。
- ワークスペース内ファイルアクセス制御: `yonerai ask "inspect this file" --file <path> --workspace <dir> --provider mock --json`
  - 現状は明示指定した UTF-8 テキストファイルを workspace 境界内で読むだけです。PDF/画像解析、フォルダ巡回、任意ファイルアクセス、実 LLM ファイル要約は未実装です。
- Mock search: `yonerai search mock "YonerAI alpha2" --json`
- SafeShell plan: `yonerai ops plan git-status --json`
- Local memory: `yonerai memory add "local note" --store <local.jsonl> --confirm-local --json`
- Synthetic Discord boundary: `yonerai discord synthetic "hello" --json`
- Status fixture: `yonerai status --source fixture --json`
- Installer dry-run planning: `yonerai install plan-windows --json`
- Local manifest verify: `yonerai manifest verify releases/manifest.example.json --json`

External provider adapter と local LLM execution はありますが、明示 opt-in が必要です。External provider は `--live` と provider-specific environment flag が必要です。Local LLM endpoint は loopback-only で、remote URL は拒否します。

alpha2 で claim してはいけないもの:

- production-ready YonerAI runtime
- Official Managed Cloud runtime
- production Oracle control-plane implementation
- live Discord restoration
- live web search by default
- arbitrary shell execution
- arbitrary local file access
- installer-ready distribution
- npm / winget distribution
- production signing key / production trust store
- Google login / production DB / telemetry ingestion
- complete persistent memory
- `src/cogs/ora.py` solved

## CLI 診断

`yonerai doctor` と `yonerai status` はオフラインで動く non-mutating diagnostic command です。公開デモの実行可否、Python/CLI の状態、manifest 例、redaction self-check、MCP deny-policy self-check を確認します。デモ実行、PATH 変更、インストール、リモートコードのダウンロード、live service 接続は行いません。

`--lang ja` は human-readable な pretty output だけを日本語化します。`--json` のキーは CI / 自動テスト向けに英語のまま安定させます。

`yonerai manifest verify releases/manifest.example.json --pretty --lang ja` はローカルの release manifest を検証するだけです。Artifact のダウンロード、installer 実行、PATH 変更、winget/npm publish は行いません。現在の example manifest は contract-valid ですが、non-production signature placeholder を使うため install-ready ではありません。

## 今動くもの

現在の public MVP は、credential-free local Core API health smoke、offline/mock message contract、loopback-only local LLM conversation contract、public demo command です。完成済みの ChatGPT-like product ではありません。

確認できること:

- public repository を clone する
- `yonerai demo --pretty` / `yonerai demo --json` を実行する
- local Core API を起動して `GET /health` で `{"ok": true}` を受け取る
- `POST /v1/public/messages` で deterministic offline mock reply を受け取る
- `POST /api/v1/agent/run` で local in-memory run smoke contract を確認する
- `clients/cli` を install して `yonerai health`、`yonerai message --mode mock "hello"`、`yonerai run --mode mock "hello"` を loopback Core に対して実行する
- loopback-only の local LLM server がある場合だけ、`mode: "local"` と `local_provider` で local runtime を試す
- `clients/web` を temporary Web Chat MVP / smoke-demo surface として local で開く

含まれないもの:

- Official Managed Cloud runtime / control plane
- production Oracle
- production trust store / production signing keys
- live Discord gateway
- Google login
- persistent natural memory / cross-device history
- real official-cloud telemetry / analytics
- external provider live generation by default
- deployment system
- production readiness / full product completion

## 3 つの product mode

YonerAI は同じ contract-first foundation を次の 3 つの利用形態で扱う設計です。

- Full Private Self-Host: public repo は local/self-hosted public MVP surface を持ち、operator が runtime boundary に責任を持ちます。
- Official Hybrid Private: public repo は Local Node contract、signed-contract test、non-production local-dev simulator を持ちます。Official cloud coordination は external/private です。
- Official Managed Cloud: product mode として存在しますが、runtime と control plane は official/private infrastructure であり、この public repo には実装されず runnable として扱いません。

これは repository map ではなく product mode の説明です。Public docs は private operational detail ではなく、contract と user experience を説明します。

## Public repo の境界

この repository に含めるもの:

- review 可能な public-safe contract
- public-safe runtime abstraction
- capability boundary と connector pattern
- client-facing docs
- regression tests
- Full Private Self-Host の public/local surface
- Official Hybrid Private の Local Node contract/dev simulator surface

この repository に含めないもの:

- official/private runtime behavior
- operator-only workflow
- live route / deployment truth / raw production inventory
- credential / host-specific control-plane detail
- production Oracle / production trust material
- live Discord token or connection
- Google login / persistent memory / deploy

Cross-boundary interaction は API、event、file、auth claim、capability manifest、protocol、schema など、明示的な contract 経由だけで行います。

Raw chain-of-thought は public chat、API、SSE、log、documentation、trace surface に出しません。Public trace で扱うのは safe summary、label、detail、すでに public-safe な source だけです。

## Local development

public demo:

```powershell
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai demo --pretty
```

credential-free public smoke:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\core\src"
$env:ORA_ALLOW_MISSING_SECRETS = "1"
python scripts/dev/public_mvp_smoke.py
```

local Core API:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\core\src"
$env:ORA_ALLOW_MISSING_SECRETS = "1"
python -m ora_core.main
```

## Status

この README は public-facing な境界説明です。現在の public repo は Official Managed Cloud を runnable として提供しません。`src/cogs/ora.py` はまだ unresolved boundary residue であり、この demo によって解決済みとは主張しません。`reference_clawdbot` は public release train の対象外です。
