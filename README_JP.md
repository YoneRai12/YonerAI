# YonerAI

YonerAI は、公式環境・ローカル環境・self-hosted 環境が変わっても、同じ体験と同じ契約境界を保つためのプロバイダー非依存 AI 実行基盤です。

[English README](README.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Release checkpoint](docs/releases/v2026.5.18-public-progress-checkpoint.md)

## YonerAI とは

YonerAI は、利用するモデルプロバイダー、UI、ローカル実行環境、self-hosted profile が変わっても、ユーザー体験と contract boundary を維持するための長寿命 AI runtime foundation です。

単なる Discord bot でも、単なる model router でもありません。Discord、Web、relay、API、CLI、native Japanese CLI、SNS distribution、self-evolution は、それぞれ失敗モードと承認条件が違う別 lane です。

この README は公開向けの contract surface を説明するためのものです。内部運用詳細、credential、live route、host-specific fact を公開する文書ではありません。

## 現在の checkpoint

現在の design anchor は v7.7 です。

- provider independence
- official / local / self-hosted 方向での same experience
- approval gate 付き product intelligence としての self-evolution
- contract-first な public boundary
- 内部運用詳細を公開せず、contract で public / private / control-plane を分ける方針

`v2026.5.18` は public progress checkpoint であり、production release ではありません。

この repository は shipping completeness、production readiness、official cloud completion、live operations completion、full product completion を主張しません。

Pass 2 は stopped / not landed です。`src/cogs/ora.py` は private/runtime/control-plane boundary residue のままであり、狭い public patch で解決済みとして扱いません。

## 3つの利用形態

YonerAI は、同じ contract-first foundation を次の3つの使い方で扱えるように設計しています。

- Full Private Self-Host: ユーザーが runtime boundary を管理する形態。
- Official Hybrid Private: 公式の governance と local/private runtime を明示的な contract でつなぐ形態。
- Official Managed Cloud: その lane が準備できたときに、同じ体験を managed surface として提供する形態。

これは product mode の説明であり、repository map ではありません。public docs では、private operational detail ではなく contract と user experience を説明します。

## この公開リポジトリに含まれるもの

public surface で扱うのは、レビュー可能な contract、public-safe な runtime abstraction、capability boundary、connector pattern、client-facing documentation、regression test です。

private runtime behavior、operator-only workflow、live route、deployment truth、raw production inventory、credential、host-specific control-plane detail は、公開 README や public-facing docs に書くものではありません。

境界をまたぐ連携は、API、event、file、auth claim、capability manifest、protocol、schema などの明示的な contract 経由で行います。

raw chain-of-thought は public chat、API、SSE、log、documentation、trace surface に出しません。public trace で扱うのは、安全な summary、label、detail、すでに公開可能な source だけです。

入口として見る文書:

- [Current phase context](docs/CURRENT_PHASE_CONTEXT.md)
- [External Agent API](docs/contracts/external-agent-api.md)
- [SSE Run Events](docs/contracts/sse-run-events.md)
- [v2026.5.18 checkpoint note](docs/releases/v2026.5.18-public-progress-checkpoint.md)
- [Latest traceability matrix](docs/TRACEABILITY_MATRIX_0_19.md)

## Product surface lane

YonerAI では次の lane を分けて扱います。

- API: contract authority
- CLI: command authority
- native Japanese CLI: 曖昧命令の確認と説明責任を持つ別 UX lane
- Web: product surface
- SNS: distribution lane。core blocker ではありません
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
- API / CLI / native Japanese CLI / Web / SNS implementation
- dependency vulnerability remediation
- runtime hardcoded path cleanup
- git history rewrite
- release tag creation
- deployment

## Local development

確認したい範囲に合う最小 profile で起動してください。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` や local secret file は commit しません。`.env.example` は placeholder template であり、production truth ではありません。

Core API:

```powershell
$env:PYTHONPATH = "core\src"
python -m ora_core.main
```

任意の local web/API runtime:

```powershell
.venv\Scripts\Activate.ps1
uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000
```

任意の web client:

```powershell
cd clients\web
npm install
npm run dev
```

Discord adapter work には local Discord credential が必要です。これは local/private profile boundary の内側で扱うもので、public core の確認には必須ではありません。

## Public safety

commit してはいけないもの:

- 実 `.env` file や secret backup
- credential、service-account file、token、private key、tunnel secret
- local SQLite database、WAL/SHM、log、cache、generated audio、local state
- raw production inventory、live route map、operational ledger、break-glass detail、control-plane DDL
- private renderer truth や host-specific operational exactness
- public docs 内の local absolute path や user-machine path

必要な情報が public-safe でない場合は、実体ではなく placeholder、contract、public-safe summary、TODO を置きます。

## Checks

変更した領域に応じたチェックを実行してください。docs-only hygiene 変更の最小確認は以下の通りです。

```powershell
git diff --check
git status --short --branch
```

より広い test / lint / CI は lane ごとに判断します。docs check が通っても production readiness を意味しません。

## Release notes

- [v2026.5.18 public progress checkpoint](docs/releases/v2026.5.18-public-progress-checkpoint.md)
- [Release notes index](docs/RELEASE_NOTES.md)
- [Current phase context](docs/CURRENT_PHASE_CONTEXT.md)
