# Planning Packet 0.1

Status:

- truth sync = `MATCH`
- planning gate = `OPEN`
- execution gate = `CLOSED`

Scope:

- lane は `Distribution Node MVP` のみ
- この文書は implementation plan ではない
- execution reservation は保持するが、着手順としてはまだ固定しない

## 1. Confirmed Truth

以下は planning gate 中の confirmed truth として扱う。

- current anchor は `v7.6`
- `v7.5` は preserve-design / cleanup line として `v7.6` に従属する
- current branch は completion ではなく safe pause point
- safe pause 対象は `src/cogs/ora.py` と current branch 全体
- current lane は `Distribution Node MVP` のみ
- shared run contract は次の 3 endpoint のみ
  - `POST /v1/messages`
  - `GET /v1/runs/{run_id}/events`
  - `POST /v1/runs/{run_id}/results`
- run API は raw bytes を返さず file-ref-only
- files API の前提は `short-lived URL / owner-scope / Cache-Control: no-store / audit`
- MVP に含めないもの
  - `arbitrary shell`
  - `arbitrary SQL`
  - `arbitrary file write`
  - `high-risk control-plane execution`
- signed release verification は fail-closed
- capability policy は default deny
- Oracle 固有 control-plane 依存は public relay / public contract に直接混ぜない
- `core/src/ora_core/brain/process.py` の dirty band0 clamp は reject 済みで reopen しない
- route policy widening は提案しない
- Pass 2 は今は狙わない。readiness judgment で止める
- hardest files の reservation は次の順
  1. `src/web/endpoints.py`
  2. `src/storage.py`
  3. `src/cogs/tools/tool_handler.py`
- 4/23 までの到達目標は Distribution Node MVP の shared contract が docs / code / tests で一致すること
- 4/23 目標には以下を含めない
  - 3 repo への実移動完了
  - `src/cogs/ora.py` landing
  - full product completion 主張

## 2. Unconfirmed Truth

以下は planning gate 中も `UNCONFIRMED` のまま保持する。

- `docs/contracts/` 配下の最終ファイル粒度
- Pass 2 readiness judgment の exact threshold
- split 後の最終 module 名
- temp-worktree rehearsal を planning gate 中に要求するか
- auth / `user_identity` の exact precedence wording
- SSE terminal event catalog の最終文言
- external alias `/api/v1/agent/*` をどの粒度で docs に分離するか
- `CONTRACT_GAPS.md` と `RISK_NOTES.md` の今回更新粒度

重要:

- `UNCONFIRMED` は current truth の否定ではない
- ただし `UNCONFIRMED` を code change の理由に使わない

## 3. Freeze / No-Go List

### Freeze

- `src/cogs/ora.py`
- current branch 全体の safe-pause 位置づけ
- `core/src/ora_core/brain/process.py` の dirty band0 clamp reject
- shared run contract の 3 endpoint 制約

### No-Go

- implementation plan の確定
- Pass 2 を前提にした `git mv` / split 手順の固定
- demo 用コード
- 暫定 endpoint
- route policy widening
- Oracle host 依存の public contract 混入
- raw bytes を run API に戻す変更
- `src/cogs/ora.py` reopen
- dirty band0 clamp reopen

## 4. Daily MVP Rule

planning gate 中に出してよい daily MVP は、後で捨てないものだけに限定する。

許可:

- docs
- tests
- validation artifact
- traceability artifact

禁止:

- demo code
- temporary endpoint
- throwaway helper
- 後で削除前提の暫定実装

判定ルール:

- 最終成果物にそのまま吸収できないなら出さない
- final completion を遅らせるなら出さない

## 5. Planning Exit Criteria

planning gate を抜けて execution gate 判定へ進んでよい条件は次。

- `docs/V76_TRUTH_SYNC_PACKET_JP.md` と本ファイルの矛盾がない
- shared run contract 3 endpoint が docs 上で一意に読める
- files / policy constraints が docs 上で一意に読める
- docs / tests / code の traceability matrix が埋まっている
- code 着手条件 / 停止条件 / readiness judgment 条件が memo 化されている
- freeze / no-go list に対する例外がない
- execution reservation が reservation としてのみ保持されている

## 6. Execution Reservation

以下は reservation であり、まだ着手順ではない。

1. `src/web/endpoints.py`
2. `src/storage.py`
3. `src/cogs/tools/tool_handler.py`

この順は hardest files の予約順であって、planning gate 中の確定 execution order ではない。
