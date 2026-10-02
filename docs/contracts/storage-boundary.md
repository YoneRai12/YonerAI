# Storage Boundary Contract

Status:

- planning gate durable doc
- current anchor: `v7.6`
- fixed anchor: `YonerAI Internal Run API v0.1 Draft`
- lane: `Distribution Node MVP`

## Purpose

この文書は、Distribution Node MVP lane における storage boundary を固定する。
主目的は shared contract state と private runtime state と operator-admin state を分離して読むための durable boundary を作ることにある。

## Scope

この文書が固定するもの:

- shared contract state / private runtime state / operator-admin state の区別
- shared run / conversation / tool_call / file state に属する範囲
- migration contract との relation

この文書が固定しないもの:

- exact DDL
- production DB exactness
- live operational schema dump
- private runtime persistence の全列挙

## Non-Goals

- physical DB split の実施
- schema migration plan の確定
- operator/admin DB truth を public/shared contract に昇格させること
- exact table / column / index naming の固定

## State Classes

### 1. Shared Contract State

shared contract state に入るのは、canonical 3 endpoint と files boundary を支える最小 state だけ。

含めてよい読み:

- run state
- conversation linkage
- tool_call continuation linkage
- file / ticket / audit のうち files boundary に必要な最小 state

この class は docs / tests / code で説明可能である必要がある。
ただし exact schema naming はこの phase では固定しない。

current observed minimum:

- `tool_calls`
- `distribution_files`
- `distribution_file_tickets`
- `distribution_file_audit`

これらは migration contract と core models の双方で追跡される shared-facing minimum state である。

### 2. Private Runtime State

private runtime state は official runtime 実装都合で持つ state であり、shared contract state と同一視しない。

例:

- official session / runtime cache
- public chat implementation detail
- scheduler / maintenance / unofficially mixed runtime helpers
- runtime-local persistence detail

current observed examples in local store:

- `public_chat_feedback`
- `scheduled_tasks`
- `scheduled_task_runs`
- `chat_events`
- `api_usage`

### 3. Operator-Admin State

operator-admin state は canonical shared run contract の外側に残す。

例:

- approvals
- audit read surfaces
- dashboard/admin tokens
- operator setup / maintenance state

current observed examples in local store:

- `approval_requests`
- `tool_audit`
- `dashboard_tokens`
- `web_sessions`
- permission/admin role surfaces carried by local user state

この class は token-gated / operator-gated surface と結びつくが、shared run contract には入れない。

## What Belongs In Shared Run / Conversation / Tool Call / File State

この phase で shared class に含めるのは次。

- message submission から `run_id` へ至る最小 state
- run event stream の continuity に必要な最小 state
- continuation-only result submission に必要な `tool_call` linkage
- files boundary に必要な file / ticket / audit 最小 state

補足:

- `tool_calls` は migration contract 上の tracked prerequisite
- distribution file tables は migration contract 上の tracked requirement
- current observed minimum connection to local store is identifier-level
  - `tool_call_id`
  - `run_id`
  - `core_run_id`
- exact table decomposition は `UNRESOLVED`

## What Must Not Be Treated As Public / Shared Contract State

次は shared contract state として扱わない。

- approvals workflow exactness
- dashboard/admin token state
- private session internals
- operator-only audit exactness
- live operational storage truth
- Cloudflare / Oracle host specific control state

current observed note:

- `approval_requests.expected_code` は local storage に raw で保持されうる
- したがって `expected_code` の非露出は storage schema contract ではなく approvals web/API boundary contract で扱う

## Relation To Migration Contract

tracked docs で固定されている relation:

- migration revision は `tool_calls` と distribution file tables を含む
- clean init / alembic upgrade は tracked docs に存在する
- live operational database を自動変異したと主張しない

この phase で固定しないもの:

- exact DDL text
- migration branching policy
- backward compatibility window

Status:

- migration inclusion rule = fixed
- exact DDL = `GAP`
- exact upgrade semantics in every env = `UNRESOLVED`

## Minimum Connection To Migration Contract

この phase で固定できる最低接続点は次。

- core migration contract は `tool_calls` と distribution file tables を追う
- local mixed store は approval/runtime/admin state を持つ
- 両者の current observed 接点は shared schema merge ではなく identifier-level linkage に留まる

この phase で固定しないもの:

- cross-store foreign key exactness
- single authoritative runtime store
- final repo ownership by module/file

## Shared vs Private Boundary Notes

shared/public-safe docs に残してよいのは boundary と schema class の説明まで。
private runtime truth を public-safe contract へ直接 import しない。

固定 truth:

- public artifacts は private internals を直接 import しない
- cross-repo interaction は contract 経由だけ

## Open Gaps

- `GAP`: shared contract state の exact schema doc
- `GAP`: approvals / operator state の durable schema doc exactness
- `GAP`: files audit schema exactness
- `GAP`: ambiguous local tables (`users`, `user_identities` など) の durable class assignment
- `UNRESOLVED`: current mixed storage responsibilities の final decomposition
- `UNRESOLVED`: identifier-level linkage beyond `tool_call_id` / `run_id` / `core_run_id`
- `UNRESOLVED`: exact table ownership by repo after Pass 2

## Anchor Set

- `docs/V76_TRUTH_SYNC_PACKET_JP.md`
- `docs/DISTRIBUTION_NODE_MVP.md`
- `CONTRACT_GAPS.md`
- `REPO_TARGET_TREES.md`
- `YonerAI Internal Run API v0.1 Draft`
