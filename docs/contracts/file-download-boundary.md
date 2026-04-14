# File Download Boundary Contract

Status:

- planning gate durable doc
- current anchor: `v7.6`
- fixed anchor: `YonerAI Internal Run API v0.1 Draft`
- lane: `Distribution Node MVP`

## Purpose

この文書は、run contract と files contract の境界を固定する。
主目的は「run API は file-ref-only」「実ダウンロードは files boundary 側」という分離を durable にすること。

## Scope

この文書が固定するもの:

- run API file-ref-only rule
- files ownership boundary
- `short-lived URL`
- `owner-scope`
- `Cache-Control: no-store`
- audit 前提
- no raw bytes in run API

この文書が固定しないもの:

- files API の exact response schema
- redirect の exact status code
- ticket payload の exact field naming
- single-use を topmost truth として採用すること

## Run API Is File-Ref-Only

固定 truth:

- run API は raw file bytes を返さない
- run events / continuation result は file reference を扱う
- download authority は files boundary 側に分離する

この rule は次に適用される。

- `POST /v1/messages`
- `GET /v1/runs/{run_id}/events`
- `POST /v1/runs/{run_id}/results`

補足:

- local tool result は run contract を越える前に file reference へ正規化される
- exact file reference string shape は current implementation に依存しており、canonical wire exactness は `UNRESOLVED`

## Files Ownership Boundary

固定 truth:

- files download authority は owner-scoped
- authenticated owner check を前提にする
- Distribution Node mode では unauthenticated ticket issuance を reject する

この phase で exactness が未固定なもの:

- owner mismatch 時の exact status code
- owner identity の error body shape

Status:

- ownership boundary = fixed
- exact reject schema = `GAP`

## Minimal Files Surfaces

tracked docs で確認できる最小 surface:

- `POST /v1/files/{file_id}/download-url`
- `GET /v1/files/download/{ticket}`

この文書で固定するのは boundary だけであり、wire exactness ではない。

未固定:

- `POST` が直に URL を返すか ticket を返すか
- `GET` が redirect するか body を返すか
- exact field names

Status:

- endpoint existence = partial
- wire exactness = `GAP`

## Short-Lived URL

固定 truth:

- download authority は short-lived URL 前提

未固定:

- TTL の exact duration
- renewal policy

Status:

- short-lived requirement = fixed
- TTL exactness = `GAP`

## Cache-Control

固定 truth:

- files download surface は `Cache-Control: no-store` を前提にする

未固定:

- 他 cache header の exact set

Status:

- no-store = fixed
- companion header exactness = `GAP`

## Audit Boundary

固定 truth:

- ticket issue と download は audit 対象

未固定:

- audit row schema
- retention policy
- operator read surface

Status:

- audit required = fixed
- audit schema = `UNRESOLVED`

## Single-Use Note

tracked doc の一つは single-use ticket に言及している。
ただし、この phase の current topmost truth は

- `short-lived URL`
- `owner-scope`
- `Cache-Control: no-store`
- `audit`

であり、single-use はそこに昇格していない。

したがって、この文書は single-use を fixed truth として採用しない。

Status:

- single-use = `UNRESOLVED`

## Request / Response / Redirect Examples

以下は boundary example であり、exact wire schema ではない。

### Ticket issuance example

```yaml
method: POST
path: /v1/files/file_abc/download-url
headers:
  Authorization: "Bearer <token>"
```

illustrative response:

```yaml
status: 200
body:
  download_url: "<short-lived URL or indirection target>"
  expires_at: "<timestamp>"
```

補足:

- exact field names は `GAP`
- URL 直返しと ticket 返しの exact split は `UNRESOLVED`

### Download resolution example

```yaml
method: GET
path: /v1/files/download/ticket_xyz
```

補足:

- redirect semantics は tracked docs に存在するが exact status code は固定しない
- redirect vs body return の exact behavior は `GAP`

## Error Cases

固定または明示できるもの:

- unauthenticated file ticket issuance は reject
- non-owner access は reject 対象
- expired or invalid ticket は failure になる
- run API に raw bytes を戻すことは boundary violation

この phase で未固定:

- expired ticket の exact status code
- invalid ticket の exact response body
- redirect failure の exact wire behavior

## Non-Goals

- files implementation detail を canonical run contract に混ぜること
- raw bytes fallback を許可すること
- single-use を topmost truth として先走って固定すること
- control-plane file transport をこの lane に含めること

## Open Gaps

- `GAP`: ticket issuance response schema
- `GAP`: redirect exact semantics
- `GAP`: owner mismatch exact error schema
- `GAP`: short-lived URL の exact TTL
- `UNRESOLVED`: file reference string exact shape
- `UNRESOLVED`: single-use を future fixed truth に上げるか

## Anchor Set

- `docs/V76_TRUTH_SYNC_PACKET_JP.md`
- `docs/DISTRIBUTION_NODE_MVP.md`
- `YonerAI Internal Run API v0.1 Draft`
