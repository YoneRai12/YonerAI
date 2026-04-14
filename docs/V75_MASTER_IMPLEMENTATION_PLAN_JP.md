# v7.5 実装マスタープラン

作成日: 2026-04-11  
対象期限: 2026-04-23  
対象 repo: `C:\Users\YoneRai12\Desktop\ORADiscordBOT-main3`

## 1. この計画の目的

この計画は、実装前に「何を、どの順で、どの完了条件で進めるか」を固定するためのもの。
`YonerAI_v7.5_clean.pdf` 全体をそのまま作業指示書として使わず、現在の repo に存在する code / docs / tests に接続できる実装計画へ落とす。

この計画では次を守る。

- 複雑な部分を先に終わらせる
- 4月23日までに到達すべき状態を明文化する
- 妥協しない
- 省略しない
- 実ファイル移動より先に boundary と contract を固定する
- `Distribution Node MVP` lane の禁止事項を破らない

## 2. この計画の基準文書

計画の正本は次のファイルに置く。

- `docs/whitepaper/YonerAI_Architecture_v7_5_SOURCE.md`
- `docs/DISTRIBUTION_NODE_MVP.md`
- `MIGRATION_PLAN.md`
- `PATH_CLASSIFICATION.csv`
- `REPO_TARGET_TREES.md`
- `CONTRACT_GAPS.md`
- `RISK_NOTES.md`
- `docs/V75_EXECUTION_CHECKLIST_JP.md`

PDF は参照物であり、実装の直接編集対象ではない。

## 3. 4月23日までの到達目標

4月23日時点で到達すべき状態を、実装完了状態と準完了状態に分けて定義する。

### 3.1 実装完了として必要なもの

- `Distribution Node MVP` の shared contract が code / docs / tests で一致している
- shared contract は次の 3 endpoint のみで固定されている
  - `POST /v1/messages`
  - `GET /v1/runs/{run_id}/events`
  - `POST /v1/runs/{run_id}/results`
- run API が file bytes を返さない
- files API が short-lived URL 前提で owner-scope / no-store / audit 前提になっている
- signed release verification が fail-closed で通る
- capability policy が default deny で強制される
- Oracle 固有 control-plane 依存が public relay / public contract に直接混ざらない
- public repo と private repo の境界に必要な contract docs が揃っている
- Pass 2 実施可否を docs と validation だけで判定できる

### 3.2 4月23日までに「未実施でもよい」が、未整理のまま放置してはいけないもの

- 3 repo への完全移動そのもの
- private 本番 exactness の全面公開
- live operational ledger の versioning
- control-plane live schema dump の versioning
- `src/cogs/ora.py` を含む別 lane の runtime landing

これらは「やらない」のではなく、「今回の lane で混ぜない」。

## 4. 非交渉ルール

- `src/cogs/ora.py` は触らない
- `core/src/ora_core/brain/process.py` の dirty band0 clamp hunk は復活させない
- route policy widening をしない
- arbitrary shell / arbitrary SQL / arbitrary file write / high-risk control-plane 実行を MVP に含めない
- PDF バイナリを直接直さない
- `.env`, secrets, 実 DB, logs, backups, live exact inventory, break-glass 実物を commit しない
- public から private internals を直接 import する方向へ進めない
- Oracle host 依存を public repo に残さない

## 5. 複雑度ランキング

実装難易度と依存性から、先に終わらせる順を固定する。

### Rank 1: `src/web/endpoints.py`

- 約 4855 行
- mixed concern
  - shared run API
  - public chat
  - auth / OAuth
  - setup / settings
  - dashboard
  - approvals
  - audit
  - operator actions
- repo split の最大障害
- SSE contract と auth boundary の中心

### Rank 2: `src/storage.py`

- 約 2196 行
- 単一 SQLite ストアに以下が混在
  - user/session
  - public chat feedback
  - api usage
  - scheduled tasks
  - tool audit
  - approval requests
  - dashboard token
- public-safe subset と private runtime truth の分離が必要

### Rank 3: `src/cogs/tools/tool_handler.py`

- 約 1800 行
- mixed concern
  - tool dispatch
  - skill loading
  - risk scoring
  - policy decision
  - approval flow
  - Discord reply side effect
  - media/browser behavior
- public tool metadata と private Discord execution の切り分け中心

### Rank 4: `src/utils/temp_downloads.py`

- temp manifest contract と web/tunnel auto-start が混在
- file ref 契約と Oracle expose 境界の混線点

### Rank 5: `src/relay/main.py`

- 行数は少ないが boundary 汚染が濃い
- public relay 起動が `expose_cloudflare` を直接 import している

### Rank 6: `core/src/ora_core/tools/discord_proxy.py`

- public core が official Discord runtime tool set を暗黙前提にしている
- allowed client / proxy interface の整理が必要

### Rank 7: release/files/runtime hardening

- `scripts/create_release.py`
- `core/src/ora_core/database/models.py`
- `tests/test_distribution_node_mvp.py`
- `tests/test_distribution_migration_contract.py`

ここは難所というより「完成判定の中心」。

## 6. 実行順の原則

順番は次で固定する。

1. contract を決める
2. mixed file の責務を分解する
3. テストで shared behavior を固定する
4. それから最小コード変更に入る
5. 最後に Pass 2 の実ファイル移動を判定する

つまり、repo split より先に boundary hardening を終わらせる。

## 7. 実装トラック

全作業を 6 トラックに分ける。

### Track A: Shared API / SSE / auth boundary

対象:

- `src/web/endpoints.py`
- `src/utils/core_client.py`
- `tests/test_external_agent_api.py`
- `tests/test_distribution_node_mvp.py`

やること:

- shared run API を private/dashboard/public chat から論理分離する
- request/response schema を文書化する
- SSE event contract を固定する
- owner-scope の要求を明文化する
- external alias `/api/v1/agent/*` と canonical `/v1/*` の関係を固定する

出口:

- shared API 部分だけ別 repo へ運べる説明が成立する
- auth/header/origin ルールが code 依存ではなく文書依存になる

### Track B: Storage boundary

対象:

- `src/storage.py`
- `core/src/ora_core/database/models.py`

やること:

- DB concerns を分類する
  - shared contract state
  - private runtime state
  - operator/admin/audit state
- public 化可能な schema と private-only schema を切る
- approvals/audit/public chat/session/dashboard/scheduled tasks を区別する
- future split で残す API surface を決める

出口:

- `src/storage.py` の分割方針が 1 ファイル 1 役割まで落ちる
- distribution file tables と old sqlite tables の役割差が説明できる

### Track C: Tool capability / approvals / Discord runtime boundary

対象:

- `src/cogs/tools/registry.py`
- `src/cogs/tools/tool_handler.py`
- `src/utils/risk_scoring.py`
- `src/utils/policy_engine.py`
- `src/utils/approvals.py`
- `core/src/ora_core/tools/discord_proxy.py`

やること:

- tool metadata contract を抽出する
- approval / risk / policy を runtime side effect から分離する
- Discord reply / file send / browser/media side effect を private adapter 側へ寄せる
- allowed client / trust level を contract として固定する

出口:

- public repo に残すものが明確になる
- `discord_proxy` が public core から見て interface 化できる

### Track D: Files / download / tunnel boundary

対象:

- `src/utils/temp_downloads.py`
- `src/web/routers/downloads.py`
- `src/utils/cloudflare_tunnel.py`

やること:

- temp manifest contract と serving runtime を分ける
- auto-start web server / quick tunnel 起動を contract から切り離す
- distribution node files API の owner-scope と整合させる

出口:

- file ref / download ticket / tunnel expose が別責務になる

### Track E: Relay / Oracle control-plane boundary

対象:

- `src/relay/main.py`
- `src/relay/app.py`
- `src/relay/expose_cloudflare.py`
- `docs/PROTOCOL.md`

やること:

- relay server entry と expose adapter を分離する
- Oracle-specific code を control-plane に押し出す前提を固める
- public URL file contract を定義する

出口:

- public relay は self-host 可能で Oracle 前提でないと説明できる

### Track F: Signed release / capability closed / migration validation

対象:

- `scripts/create_release.py`
- `core/src/ora_core/distribution/runtime.py`
- `core/alembic/versions/9d2e4c3c0f31_add_distribution_file_tables.py`
- `tests/test_distribution_node_mvp.py`
- `tests/test_distribution_migration_contract.py`

やること:

- signed release path を fail-closed の完了条件に合わせる
- capability manifest digest binding を検証する
- freshness / rollback / deny default のテスト保証を確認する
- migration contract を shared lane の完了条件に入れる

出口:

- Distribution Node MVP の hardening 完了を機械的に判定できる

## 8. 依存関係

複雑部分を先に終わらせるため、依存関係を先に固定する。

### 8.1 先に終わっていないと後続が進まないもの

- Track A
- Track B
- Track C

この 3 つは critical path。

### 8.2 Track A に依存するもの

- Track D
- Track F

理由:

- files API や external alias は shared run API の境界定義に依存するため

### 8.3 Track B/C に依存するもの

- Pass 2 の repo split 実施判断

理由:

- mixed file の移動先を先に固定できないため

### 8.4 Track E の位置づけ

- Track A ほど大きくはないが、boundary 汚染が明白なので中盤で先に終える

## 9. 日付付きスケジュール

期限は 2026-04-23。
複雑部分先行のため、前半に hardest items を集中させる。

### 2026-04-11

目的:

- 計画凍結

成果物:

- 本ファイル
- `docs/V75_EXECUTION_CHECKLIST_JP.md`

完了条件:

- 実装前の順序、禁止事項、完了条件が固定されている

### 2026-04-12

目的:

- Track A の設計完了

成果物:

- External Agent API contract doc
- SSE event contract doc
- alias/canonical relationship note

完了条件:

- `/v1/messages`, `/v1/runs/{run_id}/events`, `/v1/runs/{run_id}/results` の shared contract が docs 上で確定

### 2026-04-13

目的:

- Track A のコード分解方針確定
- Track B の監査完了

成果物:

- `src/web/endpoints.py` の responsibility map
- `src/storage.py` の schema partition map

完了条件:

- endpoint と storage の cut line が 1 行単位で説明できる

### 2026-04-14

目的:

- Track B の contract 固定
- Track C の設計着手

成果物:

- storage boundary doc
- approvals/audit/session/public-chat の分類表

完了条件:

- public-safe subset と private runtime subset の区別が docs 化されている

### 2026-04-15

目的:

- Track C の contract 固定

成果物:

- tool capability / risk / privilege contract doc
- Discord proxy boundary note

完了条件:

- `registry.py` と `tool_handler.py` をどう分けるかが確定

### 2026-04-16

目的:

- Track A/B/C のコード着手開始

成果物:

- smallest safe refactor 1
- 必要テスト追加または既存テスト修正

完了条件:

- critical path の first landing が通る

### 2026-04-17

目的:

- Track A/B/C の main refactor

成果物:

- endpoint 側の shared/private 論理切り分け
- storage helper の責務分割
- tool approval/policy/runtime adapter の切り分け

完了条件:

- mixed concern が減り、次の Track D/E に進める

### 2026-04-18

目的:

- Track D 実装
- Track E 設計完了

成果物:

- temp download contract と expose/autostart の分離
- relay/expose boundary doc

完了条件:

- file ref contract と Oracle expose が分けて説明できる

### 2026-04-19

目的:

- Track E 実装
- Track F 確認開始

成果物:

- relay main の boundary hardening
- Oracle expose 依存の切り離し

完了条件:

- public relay から Oracle-specific import を直接持たない構造に近づく

### 2026-04-20

目的:

- Track F 実装/検証

成果物:

- signed release path の確認
- capability closed path の確認
- migration contract の確認

完了条件:

- Distribution Node MVP hardening の必須テストが通る

### 2026-04-21

目的:

- integration day

成果物:

- Track A-F の接続不整合修正
- docs 更新

完了条件:

- shared contract と code と tests の不一致が潰れている

### 2026-04-22

目的:

- full validation
- Pass 2 実施可否判定

成果物:

- validation summary
- repo split readiness verdict

完了条件:

- Pass 2 を始めてよいか、まだ docs only で止めるべきかを判断できる

### 2026-04-23

目的:

- final review
- residual risk 固定

成果物:

- implementation readiness report
- remaining manual-review list
- next-branch / next-pass recommendation

完了条件:

- 妥協なしで、どこまで完了したか・何が未完か・なぜ未完かが明確

## 10. 各トラックの詳細完了条件

### Track A 完了条件

- `tests/test_external_agent_api.py` が通る
- `tests/test_distribution_node_mvp.py` の run API 関連が通る
- docs 上で canonical contract と alias contract が区別される
- `src/web/endpoints.py` から setup/dashboard/operator と shared run API の責務が分離される設計が成立している

### Track B 完了条件

- `src/storage.py` の concern partition 表がある
- `tool_audit`, `approval_requests`, `web_sessions`, `public_chat_feedback`, `dashboard_tokens`, `scheduled_tasks` の repo 配置方針が確定している
- public 側に残す schema が contract として説明できる

### Track C 完了条件

- `TOOL_REGISTRY` で public-safe metadata と runtime side effect を分離する方針が確定している
- `tool_handler.py` から policy/risk/approval と Discord/media reply の切り分け方針が確定している
- `core/src/ora_core/tools/discord_proxy.py` の allowed client / proxy interface が contract として説明できる

### Track D 完了条件

- temp manifest schema が docs 化されている
- `ensure_download_public_base_url` が担っている複数責務を整理できている
- files API と quick tunnel 自動起動が別物として扱われる

### Track E 完了条件

- `src/relay/main.py` が public relay entry として説明できる
- Cloudflare expose を optional adapter として扱える
- public URL file contract が定義されている

### Track F 完了条件

- `tests/test_distribution_node_mvp.py`
  - idempotency
  - exactly-one terminal SSE
  - continuation-only results
  - fail-closed release verification
  - deny-default capability
  - unauthenticated file ticket reject
  - unauthenticated run events reject
  - unauthenticated run results reject
  が通る
- `tests/test_distribution_migration_contract.py` が通る
- `scripts/create_release.py --sign-release` の仕様が docs と一致する

## 11. 実装前に確定させる文書成果物

実装開始前に最低限必要な docs は次。

- `docs/contracts/external-agent-api.md`
- `docs/contracts/sse-run-events.md`
- `docs/contracts/tool-capability-and-risk.md`
- `docs/contracts/storage-boundary.md`
- `docs/contracts/relay-exposure-boundary.md`
- `docs/contracts/file-download-boundary.md`

この 6 本は、後続の refactor と repo split の基準になる。

## 12. 実装時の変更単位

大きい変更を 1 回で入れない。commit 単位ではなく、logical unit 単位で切る。

### Unit 1

- docs only
- contract 正本追加

### Unit 2

- endpoint shared contract 周辺だけ
- tests 同梱

### Unit 3

- storage boundary の helper 分離
- tests / smoke 追加

### Unit 4

- tool capability / approval / Discord runtime separation

### Unit 5

- file download / temp manifest / tunnel 分離

### Unit 6

- relay / Cloudflare expose separation

### Unit 7

- release verification / distribution validation hardening

## 13. 検証コマンド

各段階で少なくとも次を使う。

```powershell
python -m compileall src core/src
pytest tests/test_external_agent_api.py -q
pytest tests/test_distribution_node_mvp.py -q
pytest tests/test_distribution_migration_contract.py -q
pytest tests/test_approvals_api.py -q
```

必要に応じて追加:

```powershell
pytest tests/test_access_control_public_tools.py -q
pytest tests/test_tool_selector_safe_read_mapping.py -q
pytest tests/test_core_effective_route.py -q
```

schema/migration 系:

```powershell
python scripts/init_core_db.py
cd core
alembic upgrade head
```

ただし local env によって `alembic` 実行可否が異なる場合は、revision shape 検証とテストを優先し、未実行なら未実行と明記する。

## 14. Pass 2 に進んでよい条件

次を満たした時だけ Pass 2 に入る。

- Track A-F の docs と tests が揃っている
- `PATH_CLASSIFICATION.csv` の `manual_review` を実作業に耐える程度まで削減している
- public から private への hidden coupling が主要系で消えている
- Oracle-specific 依存が public relay / download / contract から剥がれている
- mixed 7 ファイルについて split 方針が確定している

## 15. Pass 2 でやること

Pass 2 は明示承認後のみ。
この期限までに Pass 2 着手可能でも、Track A-F が甘いなら着手しない。

Pass 2 の中身:

- target repo directory 準備
- `git mv` ベースの移動
- import/path 更新
- `.env.example` / placeholder / boundary docs 追加
- public repo から private internals を参照しない検証追加
- repo ごとの test/lint/build 実行

## 16. 失敗条件

次の状態になったら「進んでいるように見えて実際は失敗」と判定する。

- docs が code と切れている
- shared contract を触るたびに dashboard/setup/admin が壊れる
- public repo に Oracle/control-plane logic が残る
- private runtime 固有 state を public schema として固定してしまう
- `tool_handler.py` の巨大化を維持したまま metadata だけ public 化する
- file download contract と quick tunnel 自動起動が同じ責務のまま残る
- テストが通らず、原因不明のまま次のトラックへ進む

## 17. リスクと対応

### リスク 1

- `src/web/endpoints.py` の責務が多すぎて refactor 着手が遅れる

対応:

- 先に docs で block map を作る
- route ごとの repo target を明文化してから code を触る

### リスク 2

- `src/storage.py` の schema を一気に分けようとして壊す

対応:

- 実 split 前に contract doc と helper 分離だけ先にやる
- 物理 DB 分離は Pass 2 以降

### リスク 3

- approvals/risk/policy と Discord reply が密結合

対応:

- first step は side-effect 分離であり、機能追加ではない
- metadata と adapter の境界を先に作る

### リスク 4

- release/files の hardening が docs と code でズレる

対応:

- `tests/test_distribution_node_mvp.py` を完了条件に採用する

## 18. ユーザーに返す判断材料

この計画承認後、実装に入る前に毎回返すべき判断材料は次。

- 今どのトラックをやるか
- そのトラックの出口は何か
- 何を触らないか
- どのテストで完了判定するか
- Pass 2 に近づいたか、まだ docs/contract 段階か

## 19. この計画の結論

4月23日までに妥協なしで進めるなら、最初にやるべきは repo split ではない。
最初にやるべきは hardest three の fixed order である。

1. `src/web/endpoints.py` の shared API / SSE / auth boundary 固定
2. `src/storage.py` の storage boundary 固定
3. `src/cogs/tools/tool_handler.py` と `registry.py` の capability / approvals / runtime boundary 固定

この 3 つが終わって初めて、download / relay / release / repo split が安全に進む。

この順序は変更しない。
