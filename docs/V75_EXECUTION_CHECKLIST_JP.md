# v7.5 実行チェックリスト

このファイルは、`YonerAI_v7.5_clean.pdf` をそのまま実装タスクにしないための縮約版である。
目的は「全部を一気にやる」ことではなく、現在の repo で安全に前進できる順番を固定すること。

## 0. 先に固定する前提

- PDF は作業元にしない
  - 実行上の基準は `docs/whitepaper/YonerAI_Architecture_v7_5_SOURCE.md`
  - 実装レーンの基準は `docs/DISTRIBUTION_NODE_MVP.md`
- 今の主レーンは `Distribution Node MVP` だけ
  - repo split と同時並行で広げない
- Pass 1 は完了済みとして扱う
  - `MIGRATION_PLAN.md`
  - `PATH_CLASSIFICATION.csv`
  - `REPO_TARGET_TREES.md`
  - `CONTRACT_GAPS.md`
  - `RISK_NOTES.md`
- Pass 2 の実ファイル移動はまだ開始しない
  - 先に contract を抽出する
- 迷ったら移動しない
  - `manual_review` に落とす

## 1. 今日やる 3 手

### 1. External Agent API contract を固定する

対象:

- `src/web/endpoints.py`
- `tests/test_external_agent_api.py`

やること:

- `POST /v1/messages`
- `GET /v1/runs/{run_id}/events`
- `POST /v1/runs/{run_id}/results`

について、最低限これだけを文書化する。

- request schema
- response schema
- SSE event type 一覧
- auth header の扱い
- owner scope の扱い

この手の出口:

- contract がコードから独立して読める
- repo split 後も public 側の正本として残せる

### 2. Relay と Oracle expose を分離する

対象:

- `src/relay/main.py`
- `src/relay/app.py`
- `src/relay/expose_cloudflare.py`
- `docs/PROTOCOL.md`

やること:

- relay server 本体の責務
- expose adapter の責務
- Oracle / Cloudflare 依存

を 1 枚で切り分ける。

この手の出口:

- public relay が Oracle 前提でないと説明できる
- `YonerAI` と `YonerAI-oracle-control-plane` の境界が明文化される

### 3. Tool capability contract を固定する

対象:

- `src/cogs/tools/registry.py`
- `src/cogs/tools/tool_handler.py`

やること:

- tool schema
- capability
- risk metadata
- allowed client / trust level

の 4 点を「public に残すもの」と「private 実行アダプタに残すもの」に分ける。

この手の出口:

- tool metadata と Discord 実行処理を別 repo に切れる見通しが立つ

## 2. 今週やる 5 手

### 1. contract 上位 3 件の docs を追加する

優先順:

1. External Agent API
2. Relay Protocol / Exposure Boundary
3. Tool Capability / Risk Contract

成果物の置き場所:

- `docs/contracts/` 配下を想定

### 2. split 前に切れない 7 ファイルの責務を確定する

対象:

- `src/web/endpoints.py`
- `src/storage.py`
- `src/cogs/tools/tool_handler.py`
- `src/cogs/tools/registry.py`
- `src/relay/main.py`
- `src/utils/temp_downloads.py`
- `core/src/ora_core/tools/discord_proxy.py`

やること:

- 各ファイルに対して
  - public contract
  - private adapter
  - Oracle control-plane adapter
  - split 不可なら `manual_review`

を 1 行で決める。

### 3. Distribution Node MVP の完了条件を固定する

見るもの:

- `docs/DISTRIBUTION_NODE_MVP.md`

完了条件:

- signed release verification が fail-closed
- capability が default deny
- Internal Run API v0.1 の 3 endpoint だけを shared contract とする
- file bytes を run API に載せない
- files API は short-lived URL 前提

### 4. Pass 2 開始条件を決める

開始してよい条件:

- 上位 3 contract docs がある
- split 不能 7 ファイルの扱いが確定している
- `PATH_CLASSIFICATION.csv` の `manual_review` が潰せる範囲まで減っている
- public から private への直接 import を説明できる状態がなくなっている

### 5. sibling repo の作成は最後にやる

順番:

1. contract 固定
2. 境界再確認
3. その後に `git mv`

先に clone だけしてもよいが、実移動はこの順を崩さない。

## 3. 触ってはいけない場所

- `src/cogs/ora.py`
  - Distribution Node MVP lane では触らない
- `core/src/ora_core/brain/process.py` の dirty band0 clamp 系
  - 復活させない
  - route policy widening をしない
- Oracle 固有の deploy / rollback / tunnel / host supervision を public repo に混ぜる変更
- PDF バイナリそのものの直接編集
- `.env`, 実 DB, logs, backups, secrets, live exact inventory の安易な versioning
- control-plane の live exact schema dump や break-glass 実物のコミット

## 4. 判断に迷った時のルール

- public から private を import したくなったら、その時点で contract 抽出に戻る
- Oracle host に依存するなら `YonerAI-oracle-control-plane` 側を疑う
- 公式運用 UI / admin / setup / dashboard は `YonerAI-private` 側を疑う
- 共通 schema / protocol / manifest / public-safe doc は `YonerAI` 側を疑う
- 確信が弱い時は move しない

## 5. この段階の完了条件

この段階で「終わり」と言えるのは次の状態。

- repo split の Pass 1 文書が揃っている
- contract 上位 3 件の抽出方針が固定されている
- MVP lane の禁止事項が守られている
- Pass 2 を始めるかどうかを docs だけで判断できる

まだ終わりではないもの:

- 3 repo への実移動
- import 修正の完了
- Oracle control-plane の本番 exactness 整理
- official runtime 全体の private repo 収容

## 6. 次の一手

次に着手する順番はこれで固定する。

1. `External Agent API contract` の docs 化
2. `Relay Protocol / Exposure Boundary` の docs 化
3. `Tool Capability / Risk Contract` の docs 化
4. split 不能 7 ファイルの責務メモ化
5. ここまで終わってから Pass 2 を再判定

## 7. 参照元

- `MIGRATION_PLAN.md`
- `PATH_CLASSIFICATION.csv`
- `REPO_TARGET_TREES.md`
- `CONTRACT_GAPS.md`
- `RISK_NOTES.md`
- `docs/DISTRIBUTION_NODE_MVP.md`
- `docs/whitepaper/YonerAI_Architecture_v7_5_SOURCE.md`
