# YonerAI

プロバイダーに依存しない AI 実行基盤のための public distribution core です。

[English README](README.md) | [Current phase](docs/CURRENT_PHASE_CONTEXT.md) | [Contracts](docs/contracts) | [Release checkpoint](docs/releases/v2026.4.28-public-progress-checkpoint.md)

## このリポジトリの位置づけ

YonerAI は、利用するプロバイダー、公式 UI、ローカル実行環境、self-host 形態が変わっても、同じ体験と同じ契約境界を保つための長寿命 AI 実行基盤です。

この public リポジトリは distribution core です。public-safe な runtime 抽象、契約文書、schema、capability boundary、connector pattern、client surface を置きます。private runtime や production ops の実体をそのまま公開する場所ではありません。

YonerAI は単なる Discord bot でも、単なる model routing アプリでもありません。Discord、Web、relay、API、CLI、native Japanese CLI、SNS distribution、self-evolution は、それぞれ失敗モードと承認条件が違う別 lane です。

## 現在の状態

現在の design anchor は v7.7 source-of-truth freeze です。

- provider independence
- official / local / self-host 方向での same experience
- approval gate 付き product intelligence としての self-evolution
- contract-first な public boundary
- 3 つの canonical repository

`v2026.4.28` は public progress checkpoint であり、final product release ではありません。このリポジトリは shipping-complete、production-ready、official-cloud complete、live-ops complete、full product complete を主張しません。

Pass 2 は stopped / not landed です。`src/cogs/ora.py` は private/runtime/control-plane boundary residue のままであり、狭い public patch で解決した扱いにはしません。

## 3 つの canonical repository

- `YoneRai12/YonerAI`: public distribution core、public-safe contract、共通 runtime 抽象、public client surface、capability manifest、docs。
- `YoneRai12/YonerAI-private`: official app runtime、official web runtime、official Discord gateway、admin / release / maintenance logic、operator-only surface。
- `YoneRai12/YonerAI-oracle-control-plane`: Oracle VPS の deploy / rollback、supervision、health orchestration、cloudflared / hook、将来の evaluator / healing control-plane。

`YonerAI-VPS-private` は all-in-one private repo ではありません。古いメモに出てくる場合は、control-plane seed の可能性としてだけ扱います。

public artifact は private internals を直接 import しません。repo 間の連携は API、event、file、auth claim、capability manifest、protocol、schema などの contract 経由で行います。

## public contract の方向性

public core は contract-first です。現在の主な契約領域は次の通りです。

- Internal Run API と event stream contract
- file reference / download boundary
- capability / risk policy boundary
- storage / relay boundary
- public-safe reasoning summary constraint
- approval / audit surface

raw chain-of-thought は public chat、API、SSE、log、doc、trace surface に出しません。public trace は安全に見せられる summary、label、detail、source だけを扱います。

入口として見るべき文書:

- [Current phase context](docs/CURRENT_PHASE_CONTEXT.md)
- [External Agent API](docs/contracts/external-agent-api.md)
- [SSE Run Events](docs/contracts/sse-run-events.md)
- [Release checkpoint](docs/releases/v2026.4.28-public-progress-checkpoint.md)
- [Latest traceability matrix](docs/TRACEABILITY_MATRIX_0_19.md)

## product surface lane

YonerAI では次の lane を分けて扱います。

- API: contract authority
- CLI: command authority
- native Japanese CLI: 曖昧命令の確認、説明責任、UX を扱う別 lane
- Web: product surface
- SNS: distribution lane。core blocker ではありません
- self-evolution: product intelligence と proposal scoring。未承認の code mutation ではありません
- private runtime / control-plane: execution authority、supervision、operator-only behavior

これらを 1 つの実装 batch にまとめても、public-core readiness の近道にはなりません。

## リポジトリ構成

- `core/`: public-core runtime と distribution contract implementation
- `src/`: mixed legacy runtime code、public-safe helper、skill、adapter、分離中の private/runtime boundary residue
- `clients/`: public / distributable client surface
- `config/distribution/`: public capability profile と manifest
- `docs/`: public-safe contract、phase doc、release note、traceability
- `tests/`: contract / regression test

互換性のため `ORA_*` 名が残る箇所があります。新しい public docs では、既存互換 key を説明するとき以外は YonerAI の用語を優先します。

## local development

確認したい範囲に合う最小 profile で起動してください。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` や local secret file は commit しません。`.env.example` は template であり、production truth ではありません。

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

Discord adapter を使う場合は local Discord credentials が必要です。これは local/private profile 境界の中で扱うもので、public core の確認には必須ではありません。

## public release hygiene

commit してはいけないもの:

- 実 `.env` や secret backup
- credential、service-account file、token、private key、tunnel secret
- local SQLite database、WAL/SHM、log、cache、generated audio、local state
- raw production inventory、live route map、operational ledger、break-glass detail、control-plane DDL
- private renderer truth、Oracle host exactness
- public docs 内の local absolute path や user-machine path

public-safe ではない情報が必要な場合は、実物ではなく template、placeholder、contract、TODO を置きます。

## checks

docs-only hygiene 変更の最小確認:

```powershell
git diff --check
git status --short --branch
```

より広い test / lint / CI は lane ごとに判断します。docs check が通っても production readiness を意味しません。
