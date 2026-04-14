# External Agent API Contract

Status:

- planning gate durable doc
- current anchor: `v7.6`
- fixed anchor: `YonerAI Internal Run API v0.1 Draft`
- lane: `Distribution Node MVP`

## Purpose

この文書は、Distribution Node MVP lane における外部実行面の durable contract を固定する。
固定対象は canonical run contract と、その外側に残る external alias surface の境界だけである。

この文書は code implementation plan ではない。
また、legacy queue 実装の全挙動を canonical contract に昇格させるものでもない。

## Scope

この文書が固定するもの:

- canonical shared run contract は次の 3 endpoint のみ
  - `POST /v1/messages`
  - `GET /v1/runs/{run_id}/events`
  - `POST /v1/runs/{run_id}/results`
- `POST /v1/messages` の意味
- auth precedence
- idempotency replay rule
- canonical contract と external alias surface の区別

この文書が固定しないもの:

- approvals / admin surface
- control-plane exactness
- files API の wire exactness
- legacy alias payload の完全同値性
- route policy widening
- `src/cogs/ora.py` を含む sensitive runtime reopen

## Canonical Contract vs External Alias Surface

### Canonical Contract

current phase で固定する canonical contract は次の 3 endpoint のみ。

- `POST /v1/messages`
- `GET /v1/runs/{run_id}/events`
- `POST /v1/runs/{run_id}/results`

この 3 本以外は、Distribution Node MVP の shared run contract に含めない。

### External Alias Surface

現在の external alias surface は少なくとも次を含む。

- `POST /api/v1/agent/run`
- `GET /api/v1/agent/runs/{run_id}/events`
- `POST /api/v1/agent/runs/{run_id}/results`

この alias surface について固定する truth は次だけである。

- path existence は維持する
- response URL continuity は維持する
- alias は canonical core contract そのものではない
- alias は legacy queue surface の上に残る stable external surface として扱う

以下はこの phase では固定しない。

- alias payload が canonical payload と完全同一かどうか
- alias が canonical transport framing を使うかどうか
- alias 固有の追加 field 一覧

Status:

- alias exact behavior = `UNRESOLVED`
- alias widening = `NO`

## Canonical Endpoint Semantics

### `POST /v1/messages`

意味:

- 1 回の message submission を受け付ける canonical entry point
- 成功時は run handle を返し、以後の canonical follow-up は
  - `GET /v1/runs/{run_id}/events`
  - `POST /v1/runs/{run_id}/results`
  に限定する

固定 truth:

- auth 済み user があれば body の `user_identity` より auth identity を優先する
- idempotency replay は same `run_id` を返す
- run contract を越えて raw file bytes を渡さない
- file transfer authority は files boundary 側へ分離する

### `GET /v1/runs/{run_id}/events`

意味:

- canonical event stream entry point
- stream semantics の durable definition は [sse-run-events.md](C:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/docs/contracts/sse-run-events.md) に従う

固定 truth:

- unauthenticated access は reject 対象
- terminal event は `final` または `error` のどちらか 1 回だけ

### `POST /v1/runs/{run_id}/results`

意味:

- canonical continuation result entry point
- `tool_result_submit` に対応する follow-up surface

固定 truth:

- continuation-only
- unauthenticated access は reject 対象

Status:

- exact request schema for results payload = `UNRESOLVED`
- exact error code split between malformed vs unauthorized = `GAP`

## Auth Precedence

auth 済み user がある場合、server は auth identity を authoritative identity として扱う。
body の `user_identity` は、その場合 authoritative source ではない。

固定 truth:

- auth identity wins
- body `user_identity` は auth identity を上書きしない

この phase で未固定:

- auth identity と body value が衝突した場合に warning を返すか
- mismatch を dedicated error にするか、それとも黙って auth identity を採用するか

Status:

- precedence rule = fixed
- mismatch response shape = `UNRESOLVED`

## Idempotency Rule

`POST /v1/messages` は replay-safe である必要がある。
同一 idempotency key に対する replay は、同一 logical run として扱い、same `run_id` を返す。

この phase で固定するのは意味だけである。

未固定:

- idempotency key の exact carrier
  - header
  - body field
  - 両対応
- conflicting payload reuse の exact error semantics

Status:

- semantic rule = fixed
- carrier / conflict response = `GAP`

## Request / Response Examples

以下は semantic example であり、full wire schema ではない。
field 名の一部は説明用で、exact naming が未固定な箇所は `GAP` とする。

### Canonical request example

```yaml
method: POST
path: /v1/messages
headers:
  Authorization: "Bearer <token>"
body:
  message: "<user input>"
  user_identity: "body-user-if-no-auth"
  idempotency_key: "req-2026-04-12-001"
```

補足:

- `message` の exact schema はこの文書では固定しない
- authenticated user がある場合、`user_identity` より auth identity を採用する

### Canonical response example

```yaml
status: 202
body:
  run_id: "run_abc123"
  events_endpoint: "/v1/runs/run_abc123/events"
  results_endpoint: "/v1/runs/run_abc123/results"
```

補足:

- `run_id` を返すことは fixed
- endpoint field 名の exact naming は `GAP`
- alias surface の response body exactness は `UNRESOLVED`

## Error Cases

固定または明示できる error case:

- unauthenticated `GET /v1/runs/{run_id}/events` は reject
- unauthenticated `POST /v1/runs/{run_id}/results` は reject
- run contract に raw file bytes を持ち込むことは boundary violation

この phase で exactness が未固定なもの:

- `POST /v1/messages` unauthenticated 時の exact response code
- malformed input の exact response code
- conflicting idempotency replay の exact response code
- alias surface と canonical surface の error body 差分

Status:

- reject-required cases = fixed
- exact status codes / error body schema = `GAP`

## Non-Goals

- external alias surface を canonical contract として語ること
- approvals / operator surface をこの文書に混ぜること
- files redirect / ticket wire semantics をここで確定すること
- high-risk capability surface を v0.1 shared contract に含めること

## Open Gaps

- `GAP`: canonical request body の exact schema
- `GAP`: canonical response field naming
- `GAP`: idempotency key carrier
- `UNRESOLVED`: alias payload exactness
- `UNRESOLVED`: auth mismatch 時の exact response behavior

## Anchor Set

- `docs/V76_TRUTH_SYNC_PACKET_JP.md`
- `docs/DISTRIBUTION_NODE_MVP.md`
- `V75_INTERNAL_API_ALIGNMENT.md`
- `ENDPOINTS_ROUTE_MATRIX.md`
- `YonerAI Internal Run API v0.1 Draft`
