# Node Public/Private Boundaries

目的: public 配布版 Node product と private official runtime の境界を、protocol/contract 単位で固定する。

この文書の原則は次の 2 つ。

1. public/private 間で直接 module import をしない。
2. cross-repo integration は versioned contracts のみで行う。

## Allowed to cross the boundary

### 1. API contracts

許可されるもの:
- HTTP API schema
- request/response JSON schema
- status code contract
- timeout / retry / idempotency contract

例:
- `POST /v1/messages`
- `GET /v1/runs/{run_id}/events`
- files API (`/v1/files`, `/v1/files/{id}/download`, `/v1/files/{id}/share`, `/s/{share_token}`)

禁止:
- public code から private repo の service module を import すること
- private code から public repo の internal python module を import すること

### 2. Event contracts

許可されるもの:
- SSE event schema
- WebSocket relay protocol
- progress/final/error terminal contract
- audit / trace event field schema

例:
- Core SSE: `progress`, `final`, `error`
- Relay protocol: `pair_offer`, `http_proxy`, `http_response`, `ping`, `pong`

禁止:
- event consumer が producer repo の internal class を前提にすること
- Python object pickling / direct function invocation / shared memory coupling

### 3. Auth claims

許可されるもの:
- signed JWT / access token claim schema
- verified admin claims
- node instance identity claims
- device/user binding claims

必須 claim の例:
- `sub`
- `aud`
- `iss`
- `exp`
- `role`
- `mode_id`
- `node_id` or `instance_id`

禁止:
- raw session object sharing
- repo 内 private helper を token validator として直 import すること

### 4. Files contract

許可されるもの:
- `file_id`
- owner check result
- share token TTL semantics
- download URL contract
- `Cache-Control: no-store`

禁止:
- cross-repo で file store implementation を直接 import すること
- token plaintext の cross-repo logging
- private-only storage backend への direct code dependency

### 5. Capability manifest

許可されるもの:
- mode/profile が参照する capability manifest
- enabled skills/connectors/permissions の declarative schema

禁止:
- profile によって import path を分岐させること
- private-only capability を public profile に直接埋め込むこと

## Explicitly forbidden

### Direct imports across repos

以下はすべて禁止。

- public repo -> private repo module import
- private repo -> public repo internal module import
- shared utility と称して git submodule 的に private internals を public build に混ぜること
- path hack (`sys.path`, relative path import, workspace-local absolute path import) による越境

## Integration pattern

cross-repo integration は次の順番に限定する。

1. contract を docs と schema で freeze
2. public/private がそれぞれ contract に合わせて実装
3. synthetic request で schema/behavior を検証
4. 最後に live acceptance を 1 回だけ実施

## Ownership map

### public repo owns
- common node core
- public skills
- local web
- mode/profile schema
- connector clients / protocol adapters
- capability manifest schema

### private repo owns
- official yonerai.com app
- official app shell
- official relay service runtime
- commercial/admin runtime
- ops / portal / cloudflare / production admin surfaces

## Versioning rules

- contracts は semver or explicit contract version を持つ
- breaking change は docs + schema + synthetic test を同時に更新する
- runtime 先行変更で schema を壊さない

## Acceptance checklist

境界が守られていると見なす条件:
- cross-repo direct import が 0
- API/event/auth/files/capability の契約が docs に固定されている
- contract change が synthetic test で再現できる
- live verification は private/public それぞれ 1 回以内で足りる
