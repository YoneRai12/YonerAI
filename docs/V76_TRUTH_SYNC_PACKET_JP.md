# v7.6 Truth Sync Packet

作成目的:

- このファイルは、`GPT-5.4pro` / ユーザー / `Codex` の 3 者で current truth を同期するための正本である
- ここで同期が取れるまで、実装計画を確定しない
- ここで同期が取れるまで、Pass 2 の実移動判断に入らない

## 1. この同期のゴール

今回の最大目的は次の 1 点。

- 3 者が同じ current truth を見ている状態を作ること

この段階では、まだ「実装を急ぐ」ことが主目的ではない。
先に以下を固定する。

- 今何が landed 済みか
- 今何が safe pause か
- 今回 lane で何を触ってよいか
- 4/23 までの到達目標は何か
- どこで止まるべきか

## 2. authoritative current truth

この同期では、次を authoritative input として扱う。

- `docs/whitepaper/YonerAI_Architecture_v7_5_SOURCE.md`
- `docs/DISTRIBUTION_NODE_MVP.md`
- `docs/V75_MASTER_IMPLEMENTATION_PLAN_JP.md`
- `docs/V75_EXECUTION_CHECKLIST_JP.md`
- `MIGRATION_PLAN.md`
- `PATH_CLASSIFICATION.csv`
- `REPO_TARGET_TREES.md`
- `CONTRACT_GAPS.md`
- `RISK_NOTES.md`
- v7.6 delta の current truth
- YonerAI Internal Run API v0.1 Draft

補足:

- PDF は参照用
- 実装上の正本は repo 内 markdown
- v7.6 は 2026-04-08 以降の durable current truth を統合する current anchor
- v7.5 は v7.4 内容保持の design cleanup 版

## 3. 今回の lane の current anchor

今回の lane は `Distribution Node MVP` だけに限定する。

この lane の current anchor:

- common request normalization
- minimal Internal Run API v0.1

Internal Run API v0.1 の shared contract:

- `POST /v1/messages`
- `GET /v1/runs/{run_id}/events`
- `POST /v1/runs/{run_id}/results`

この contract について固定する truth:

- run API は file bytes を返さない
- files は short-lived URL
- files は owner-scope
- files は `Cache-Control: no-store`
- files は audit 前提
- arbitrary shell は MVP に含めない
- arbitrary SQL は MVP に含めない
- arbitrary file write は MVP に含めない
- high-risk control-plane 実行は MVP に含めない

## 4. landed / rejected / safe pause

### landed 済みとして扱うもの

- Wave 1
- B2
- narrowed B3a
- band2 / SSE hardening baseline
- deny-only capability baseline
- signed release verification baseline

### reject 済みとして扱うもの

- `core/src/ora_core/brain/process.py` の dirty band0 clamp

補足:

- これは reopen しない
- route policy widening をしない

### safe pause として扱うもの

- `src/cogs/ora.py`
- current branch 全体

補足:

- current code lane は completion ではない
- safe pause point であり、完了主張をしない

## 5. 今回の到達目標

4/23 までの到達目標は次で固定する。

- Distribution Node MVP の shared contract が docs / code / tests で一致
- shared contract は 3 endpoint のみ
- run API は file-ref-only
- files API は short-lived URL / owner-scope / no-store / audit
- signed release verification は fail-closed
- capability policy は default deny
- Oracle 固有 control-plane 依存が public relay / public contract に直接混ざらない
- public/private 境界に必要な contract docs が揃う
- Pass 2 実施可否を docs と validation だけで判断できる

今回の到達目標に含めないもの:

- 3 repo への実移動完了
- private live truth の全面 versioning
- control-plane live exact schema dump
- `src/cogs/ora.py` landing
- full product completion 主張

## 6. 不変条件

今回の同期で、不変条件として固定するもの:

- lane は `Distribution Node MVP` のみ
- 別 lane を混ぜない
- repo split の実ファイル移動より先に boundary と contract を固める
- public artifacts は private internals を直接 import しない
- cross-repo interaction は contract 経由だけ
- Pass 1 は docs で完了済み
- Pass 2 は明示承認後のみ
- `src/cogs/ora.py` は触らない
- `core/src/ora_core/brain/process.py` の dirty band0 clamp は復活させない
- route policy widening をしない
- PDF バイナリを直接編集しない
- `.env`, secrets, live DB, logs, backups, live exact inventory, break-glass 実物を commit しない
- Oracle host 依存を public repo に残さない

## 7. 複雑度の高い箇所

3 者同期の前提として、難所の順序も固定する。

### 1. `src/web/endpoints.py`

- shared run API
- public chat
- auth / OAuth
- settings / setup
- dashboard
- approvals
- audit
- operator actions

最重要理由:

- shared contract と common request normalization の中心

### 2. `src/storage.py`

- users
- sessions
- public chat feedback
- api usage
- scheduled tasks
- tool audit
- approval requests
- dashboard token

最重要理由:

- state boundary を切らないと contract も repo split readiness も曖昧なままになる

### 3. `src/cogs/tools/tool_handler.py`

- tool dispatch
- skill loading
- risk scoring
- policy decision
- approval flow
- Discord reply
- media/browser side effect

最重要理由:

- public metadata と private runtime side effect の分離点

### 4. `src/utils/temp_downloads.py`

- temp manifest contract
- web auto-start
- tunnel auto-start

### 5. `src/relay/main.py`

- public relay 起動
- `expose_cloudflare` 直接依存

### 6. `core/src/ora_core/tools/discord_proxy.py`

- public core が official Discord runtime tool set を暗黙前提

### 7. release / migration / validation

- `scripts/create_release.py`
- `core/src/ora_core/database/models.py`
- `tests/test_distribution_node_mvp.py`
- `tests/test_distribution_migration_contract.py`

## 8. いま planning に入ってよい条件

以下が 3 者で一致した時だけ、実装計画に入ってよい。

- v7.6 が current anchor である
- v7.5 は preserve-design / cleanup line として従属する
- current branch は safe pause point であり completion ではない
- shared run contract は 3 endpoint に固定する
- `src/cogs/ora.py` は freeze 対象である
- dirty band0 clamp は reject 済みで reopen しない
- Pass 2 は直ちに狙わない
- hardest files は `src/web/endpoints.py` → `src/storage.py` → `src/cogs/tools/tool_handler.py` の順で扱う

## 9. まだ未確定のもの

この同期段階で未確定として残してよいもの:

- Pass 2 readiness 判定の exact threshold
- split 後の最終 module 名
- docs/contracts 配下のファイル粒度
- temp-worktree rehearsal を 4/22 にやるかどうか

重要:

- これらは未確定でよい
- ただし current truth 自体は未確定のままにしない

## 10. この同期での禁止事項

3 者同期前にやってはいけないこと:

- 実装計画を固定する
- Pass 2 を前提に `git mv` 計画へ進む
- `src/cogs/ora.py` を current lane に戻す
- Oracle/control-plane code を public contract 側へ混ぜる
- shared contract を 3 endpoint より広げる
- files を raw bytes 返却前提に戻す

## 11. 同期確認チェック

3 者が次に同じ答えを返せれば、同期完了とみなす。

1. current anchor は何か
2. safe pause は何か
3. reject 済みで reopen しないものは何か
4. shared run contract は何か
5. MVP に含めないものは何か
6. hardest files の順序は何か
7. Pass 2 を今狙うべきか

## 12. 同期完了の判定

次の状態を同期完了とする。

- `GPT-5.4pro`
- ユーザー
- `Codex`

の 3 者が、少なくとも以下に一致している。

- current anchor
- safe pause
- reject 済み項目
- 4/23 までの到達目標
- freeze 対象
- hardest files の順序
- Pass 2 を readiness 判定で止める方針

## 13. 同期完了後に初めてやること

同期完了後に最初にやることは planning である。
その planning は次の順で始める。

1. `src/web/endpoints.py` の shared API / SSE / auth boundary
2. `src/storage.py` の state boundary
3. `src/cogs/tools/tool_handler.py` の capability / approvals / runtime boundary

それまでは、計画を確定しない。
