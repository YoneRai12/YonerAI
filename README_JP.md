# YonerAI

YonerAI は、公式・ローカル・self-hosted の実行環境が変わっても、同じ利用体験と同じ契約境界を保つための provider-independent AI execution foundation です。

[English README](README.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Codex / contributor workflow](docs/process/YONERAI_CODEX_WORKFLOW.md) | [Release governance](docs/process/YONERAI_RELEASE_GOVERNANCE.md)

この public repository は public contract surface を説明します。内部運用詳細、credential、live route、host 固有の事実は公開しません。

## YonerAI とは

YonerAI は単なる Discord bot でも、単なる model router でもありません。API、CLI、Web、Discord gateway、relay、native Japanese CLI、SNS distribution、self-evolution は別々の product lane であり、それぞれ risk profile と approval requirement を持ちます。

この public repo で確認できる中核は、公開可能な core contract、Self-host/local surface、Hybrid Local Node contract/dev simulator、proposal-only self-evolution です。

## Quickstart: public demo

clone 後に現在の public-safe slice を見る最短手順は、credential-free の demo command です。Core API server の常駐起動、Discord token、Oracle access、provider API key、Google login、deployment、persistent memory は不要です。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai demo --pretty
yonerai demo --json
```

`yonerai quickstart` は `yonerai demo` の alias です。

`yonerai demo --json` は stable contract `yonerai-public-demo/v1` と `schema_version: "1.0"` を出力します。`yonerai demo --pretty` は同じ内容を release check 用に読みやすく表示します。

demo が表示するもの:

- public Core health、offline mock message、run contract
- mode boundary: Self-host local surface、Hybrid Local Node contract/dev simulator、Managed Cloud external contract-only
- public / private-local / dangerous work の route preview
- test-only Local Node signed manifest、enrollment/session、signed envelope、replay rejection、approval gate
- managed download guard による managed file URL の accept と unsafe URL の reject
- synthetic event から作る proposal-only self-evolution scorecard と approval draft
- explicit limitations: production Oracle、live Discord、persistent memory、Google login、official cloud runtime、provider live generation、deploy は含まれない

## 今動くもの

現在の public MVP は、credential-free local Core API health smoke、offline/mock message contract、loopback-only local LLM conversation contract、public demo command です。完成済みの ChatGPT-like product ではありません。

今確認できること:

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
- external provider live generation
- deployment system
- production readiness / full product completion

## 3 つの product mode

YonerAI は同じ contract-first foundation を次の 3 つの利用形態で扱う設計です。

- Full Private Self-Host: public repo は local/self-hosted public MVP surface を持ち、operator が runtime boundary に責任を持ちます。
- Official Hybrid Private: public repo は Local Node contract、signed-contract test、non-production local-dev simulator を持ちます。official cloud coordination は external/private です。
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

Cross-boundary interaction は API、event、file、auth claim、capability manifest、protocol、schema など明示的な contract 経由だけで行います。

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
