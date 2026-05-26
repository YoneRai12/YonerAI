# YonerAI

YonerAI は、公式・ローカル・self-hosted の実行環境が変わっても、同じ利用体験と同じ境界を保つための provider-independent AI execution foundation です。

[English README](README.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Codex / contributor workflow](docs/process/YONERAI_CODEX_WORKFLOW.md) | [Release governance](docs/process/YONERAI_RELEASE_GOVERNANCE.md)

## ライセンスと配布

YonerAI は source-available / noncommercial を既定とします。OSI open source
ではありません。

- コード: PolyForm Noncommercial License 1.0.0。
- ドキュメントとアセット: 各ファイルで別途指定がない限り CC BY-NC-ND 4.0。
- YonerAI の名称、ロゴ、プロダクト識別子、ドメイン、ブランドアセット: All Rights Reserved。
- 商用利用には YoneRai12 からの別途商用ライセンスが必要です。

[LICENSE](LICENSE)、[LICENSE_JP.md](LICENSE_JP.md)、[NOTICE](NOTICE)、
[License policy](docs/legal/LICENSE_POLICY.md) を確認してください。

この public repository は public contract surface を説明します。内部運用の詳細、credential、live route、host 固有の事実は公開しません。

## YonerAI とは

YonerAI は単なる Discord bot でも、単なる model router でもありません。API、CLI、Web、Discord gateway、relay、native Japanese CLI、SNS distribution、self-evolution は別々の product lane であり、それぞれ risk profile と approval requirement が違います。

この public repo で確認できる中核は、公開可能な core contract、self-host/local surface、Hybrid Local Node contract/dev simulator、proposal-only self-evolution です。

## Install and start YonerAI

### GitHub Release の ZIP を解凍したあと

GitHub Release の `Source code (zip)` をダウンロードして ZIP を展開したら、
PowerShell で展開後のフォルダへ移動してから以下を実行します。フォルダ名は環境に
よって違うので、`cd` は実際の展開先に合わせてください。

```powershell
cd "$HOME\Downloads\YonerAI-0.5.1"
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai
```

展開したアーカイブまたは checkout に `install-local.ps1` が入っている場合は、
仮想環境の手順を手で全部打たずに、ローカルbootstrap helperを使えます。

```powershell
# 計画だけ表示します。インストールはしません。
.\install-local.ps1

# .venv を作り、ローカルCLI packageを入れて、YonerAIを起動します。
.\install-local.ps1 -Execute -Launch
```

`install.ps1` は将来の one-command installer 用の skeleton です。現時点では
dry-run 専用で、実際のlocal bootstrapは `install-local.ps1` に戻します。

```powershell
.\install.ps1
```

PowerShell がローカル script 実行を止める場合は、PC全体の実行ポリシーを変えずに
次の形で実行できます。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-local.ps1 -Execute -Launch
```

この helper はローカル優先です。既定は計画表示だけで、仮想環境の場所が展開した
YonerAIフォルダの外に出る指定は拒否します。PATH変更、registry変更、service install、
admin要求、`irm ... | iex` は行いません。`-Execute` を付けた場合だけ、`pip` が
未cacheのPython依存packageを取得する可能性があります。

Python は 3.11 以上を使ってください。`python --version` が動かない場合は、
先に Python を入れるか、自分のPCで使える Python 起動コマンドに置き換えてください。

`yonerai` が起動したら、最初に `日本語` / `English` を選びます。その後は
普通の文章を入力すればチャットできます。設定は `/設定`、安全設定の確認は
`/安全`、履歴は `/履歴`、終了は `/終了` です。日本語設定でも `/settings`、
`/safety`、`/runs`、`/quit` のような英語コマンドも使えます。

`yonerai` が見つからない場合は、仮想環境が有効になっていない可能性があります。
もう一度 `.\.venv\Scripts\Activate.ps1` を実行してから `yonerai` を実行して
ください。この手順は本番クラウドインストーラーではありません。PATH を恒久変更せず、
`irm ... | iex` も実行せず、リモートスクリプトのダウンロードや実行も行いません。

これは YonerAI CLI Local Runtime をこの checkout から local install する手順です。
production cloud installer ではありません。PATH 変更や remote script 実行は行いません。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai
```

install 後は `yonerai` だけで対話 CLI が起動します。明示したい場合は
`yonerai chat`、script/CI では `yonerai chat --script` または
`yonerai ask --auto` を使います。

この対話 CLI は YonerAI ミッションコントロール CLI です。プロバイダー、経路、
ローカルノード、履歴、安全モード、実行ID、進行状況、計画係/レビュー係などの
担当計画を表示します。実サブエージェントを勝手に起動したり、ライブプロバイダー
を初期値で呼び出したりはしません。

### Interactive CLI controls

v0.6 TUI runtime では、対応している端末なら `prompt_toolkit` による
slash command 候補と Rich panel 表示を使います。対応していない端末、CI、
pipe入力では従来の1行入力に戻ります。

日本語モードでは `/` を入力すると、日本語の候補を優先して表示します。
`prompt_toolkit` が有効な場合は Tab / 矢印キーで候補を選べます。

```text
/設定       設定
/モデル     モデルとローカルLLM
/提供元     AI接続先
/安全       安全境界
/履歴       履歴
/タスク     進行状況
/エージェント 担当計画
/更新       更新確認
/終了       終了
```

よく使う確認コマンド:

```powershell
yonerai
yonerai chat
yonerai update check --pretty
yonerai update check --json
yonerai config set model llama3.1 --pretty --lang ja
yonerai providers --pretty --lang ja
```

`yonerai update check` はローカルの `VERSION` とローカルmanifestだけを読みます。
download、install、PATH変更、remote code実行、admin要求は行いません。

## Quickstart: public demo

clone 後に現在の public-safe slice を見る最短手順は、credential-free の demo command です。Core API server の常時起動、Discord token、Oracle access、provider API key、Google login、deployment、persistent memory は不要です。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai
yonerai chat
yonerai config show --pretty --lang ja
yonerai start --guided --lang ja
yonerai start --guided --json
yonerai demo --pretty
yonerai demo --json
yonerai doctor --pretty --lang ja
yonerai status --pretty --lang ja
yonerai manifest verify releases/manifest.v0.5.1.json --pretty --lang ja
yonerai install plan --manifest releases/manifest.v0.5.1.json --pretty --lang ja
yonerai update check --manifest releases/manifest.v0.5.1.json --pretty --lang ja
yonerai update plan --manifest releases/manifest.v0.5.1.json --pretty --lang ja
```

`yonerai quickstart` は `yonerai demo` の alias です。

## 最初の5分

`yonerai` は local interactive terminal を起動します。明示したい場合は
`yonerai chat` を使います。これは full-screen GUI ではなく、標準ライブラリ
だけで動く安全な対話 shell です。文章を入力すると `ask --auto` と同じ安全
経路で実行し、slash command で設定や履歴を見られます。

```text
/設定                 設定を見る
/提供元               プロバイダー（AI接続先）の状態を見る。キーは表示しません
/安全                 ネットワーク（外部通信）/ツール（操作機能）/ファイルアクセス（ファイル読み取り）の境界を見る
/タスク               現在/最近のタスク進行を見る
/エージェント         計画係 / 調査係 / レビュー係などの担当計画を見る
/履歴                 実行履歴（redacted local run history）を見る
/表示 <実行ID>        1件の実行を見る
/ローカルLLM          PC内モデルの接続方法を見る
/言語 日本語|英語     表示言語を変更
/提供元選択 自動|モック|ローカル|オープンAI互換|アンソロピック|ジェミニ
/承認 確認|拒否       危険操作の扱いを変更
/ファイル ワークスペース内のみ|無効
/履歴記録 オン|オフ    秘匿済みローカル履歴の記録を変更
/ライブ接続 オン|オフ 外部/ローカル実行の明示許可を変更
/ネットワーク オン|オフ 外部通信の明示許可を変更
/選択 <番号> <値>      設定画面の番号で変更
/終了                 終了
```

日本語モードでも `/settings`、`/providers`、`/safety`、`/tasks`、`/runs`、`/local-llm`、
`/provider mock`、`/quit` のような英語 slash command は互換 alias として使えます。ただし、画面に
出す説明は日本語優先です。

初回の対話起動では、日本語 / English を選びます。保存するのは language、
provider preference、approval mode、file access mode などの非secret設定
だけです。pipe や CI のような non-TTY ではハングせず、使い方だけを表示し
ます。script入力を意図する場合は `yonerai chat --script` を使います。

`yonerai start --guided` は、YonerAI を初めて触る人のための案内 command です。内部 label を並べるのではなく、次に何を実行すればよいかを表示します。

```powershell
yonerai
yonerai chat
yonerai config set language ja
yonerai config show --pretty --lang ja
yonerai start --guided --lang ja
yonerai start --guided --json
yonerai demo --pretty
yonerai doctor --pretty --lang ja
yonerai ask "hello" --provider mock --json
yonerai hybrid run --pretty
yonerai hybrid run --json
yonerai ask "use this selected sample file" --file sample.txt --workspace .yonerai-sample-workspace --provider mock --json
yonerai ask "hello" --provider mock --json --ledger .yonerai-runs.jsonl
yonerai runs list --ledger .yonerai-runs.jsonl --json
```

この流れで分かること:

- `yonerai` / `yonerai chat` は、日本語優先の対話 shell を起動します。chat、
  provider状態、safety設定、run historyをslash commandで確認できます。
- `yonerai config show/set` は、secretを保存せず、local preferenceだけを
  扱います。
- `yonerai start --guided --lang ja` は、mock provider で安全に試す手順、local LLM の状態、ワークスペース内ファイルアクセス制御の例、ledger の例、現在の制限を表示します。
- `yonerai demo --pretty` は、現在の alpha slice を credential なしで表示します。
- `yonerai doctor --pretty --lang ja` は、ローカル setup、manifest、provider setup、安全境界を確認します。
- `yonerai start --guided --lang ja` は、Ollama / LM Studio 風の local LLM endpoint を loopback の metadata 確認だけで検出します。
- mock `ask` は public-safe な `run_id` を返します。
- `--ledger <local.jsonl>` を付けた場合だけ、redacted な local-only run history を書きます。
- Workspace file support は「ワークスペース内ファイルアクセス制御」です。明示した workspace の中にある、明示した UTF-8 text file だけを読みます。
  サンプルコマンドは `.yonerai-sample-workspace/sample.txt` を自分で用意してから実行する前提です。`yonerai start --guided` 自体はファイル作成、ファイル読み取り、ledger 書き込みを行いません。

Local LLM server がすでに loopback で動いている場合だけ、明示的に有効化してから local provider を試せます。

Ollama 例:

```powershell
$env:ORA_LOCAL_LLM_ENABLED = "1"
$env:ORA_LOCAL_LLM_PROVIDER = "ollama"
$env:ORA_LOCAL_LLM_BASE_URL = "http://127.0.0.1:11434"
$env:ORA_LOCAL_LLM_MODEL = "llama3.2"
yonerai ask "hello" --provider local --live --json
```

LM Studio / OpenAI-compatible local server 例:

```powershell
$env:ORA_LOCAL_LLM_ENABLED = "1"
$env:ORA_LOCAL_LLM_PROVIDER = "openai_compatible_local"
$env:ORA_LOCAL_LLM_BASE_URL = "http://127.0.0.1:1234/v1"
$env:ORA_LOCAL_LLM_MODEL = "local-model"
yonerai ask "hello" --provider local --live --json
```

Local LLM は loopback-only です。`localhost`、`127.0.0.1`、`::1` 以外の endpoint、LAN host、tunnel、credential 入り URL、query string、fragment は拒否します。`yonerai start` は prompt を model に送りません。

## v0.1.0-alpha.2 で試せること

v0.1.0-alpha.2 は local public alpha slice です。完成品の YonerAI ではありません。provider credential、Discord token、production service、live network call なしで、次を試せます。

- Mock provider execution: `yonerai ask "summarize public docs" --provider mock --json`
- Run ID: mock `ask` は public-safe な `run_id` を返します。
- Workspace File Access Guard: `yonerai ask "use this selected file" --file <path> --workspace <dir> --provider mock --json`
- Mock search: `yonerai search mock "YonerAI alpha2" --json`
- SafeShell plan: `yonerai ops plan git-status --json`
- Local memory: `yonerai memory add "local note" --store <local.jsonl> --confirm-local --json`
- Synthetic Discord boundary: `yonerai discord synthetic "hello" --json`
- Status fixture: `yonerai status --source fixture --json`
- Installer dry-run planning: `yonerai install plan-windows --json`
- Local manifest verify: `yonerai manifest verify releases/manifest.example.json --json`

External provider adapter と local LLM execution はありますが、明示 opt-in が必要です。External provider は `--live` と provider-specific environment flag が必要です。Local LLM endpoint は loopback-only で、remote URL は拒否します。

## まだ claim してはいけないこと

- production-ready YonerAI runtime
- Official Managed Cloud runtime
- production Oracle control-plane implementation
- live Discord restoration
- live web search by default
- arbitrary shell execution
- arbitrary local file access
- folder crawling
- PDF / image parsing
- automatic file summarization
- installer-ready distribution
- npm / winget distribution
- production signing key / production trust store
- Google login / production DB / telemetry ingestion
- complete persistent memory
- `src/cogs/ora.py` solved

## CLI 診断

`yonerai doctor` と `yonerai status` はオフラインで動く non-mutating diagnostic command です。公開デモの実行可否、Python/CLI の状態、manifest 例、redaction self-check、MCP deny-policy self-check、provider setup を確認します。デモ実行、PATH 変更、インストール、リモートコードのダウンロード、live service 接続は行いません。

`--lang ja` は human-readable な pretty output だけを日本語化します。`--json` のキーは CI / 自動テスト向けに英語のまま安定させます。

`yonerai manifest verify releases/manifest.example.json --pretty --lang ja` はローカルの release manifest を検証するだけです。Artifact のダウンロード、installer 実行、PATH 変更、winget/npm publish は行いません。現在の example manifest は contract-valid ですが、non-production signature placeholder を使うため install-ready ではありません。

## 今動くもの

現在の public MVP は、credential-free local Core API health smoke、offline/mock message contract、loopback-only local LLM conversation contract、public demo command、first-run guide です。完成済みの ChatGPT-like product ではありません。

確認できること:

- public repository を clone する
- `yonerai start --guided --lang ja` を実行する
- `yonerai demo --pretty` / `yonerai demo --json` を実行する
- `yonerai doctor --pretty --lang ja` を実行する
- `yonerai ask "hello" --provider mock --json` で credential-free ask を試す
- local Core API を起動して `GET /health` で `{"ok": true}` を受け取る
- `POST /v1/public/messages` で deterministic offline mock reply を受け取る
- `POST /api/v1/agent/run` で local in-memory run smoke contract を確認する
- loopback-only の local LLM server がある場合だけ、`--provider local --live` で local runtime を試す
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

## 3つの product mode

YonerAI は同じ contract-first foundation を次の 3 つの利用形態で扱う設計です。

- Full Private Self-Host: public repo は local/self-hosted public MVP surface を持ち、operator が runtime boundary に責任を持ちます。
- Official Hybrid Private: public repo は Local Node contract、signed-contract test、non-production local-dev simulator を持ちます。Official cloud coordination は external/private です。
- Official Managed Cloud: product mode として存在しますが、runtime と control plane は official/private infrastructure であり、この public repo には実装されず runnable として扱いません。

これは repository map ではなく product mode の説明です。public docs は private operational detail ではなく、contract と user experience を説明します。

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

Raw chain-of-thought は public chat、API、SSE、log、documentation、trace surface に出しません。public trace で扱うのは safe summary、label、detail、すでに public-safe な source だけです。

## Local development

public demo:

```powershell
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai start --guided --lang ja
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

この README は public-facing な境界説明です。現在の public repo は Official Managed Cloud を runnable として提供しません。`src/cogs/ora.py` はまだ unresolved boundary residue であり、この demo や first-run guide によって解決済みとは主張しません。`reference_clawdbot` は public release train の対象外です。
