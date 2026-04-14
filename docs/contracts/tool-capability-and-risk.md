# Tool Capability And Risk Contract

Status:

- planning gate durable doc
- current anchor: `v7.6`
- fixed anchor: `YonerAI Internal Run API v0.1 Draft`
- lane: `Distribution Node MVP`

## Purpose

この文書は、Distribution Node MVP における capability / risk / policy / approval の boundary を固定する。
主目的は、shared contract に含めてよい capability truth と、private runtime exactness とを分離することにある。

## Scope

この文書が固定するもの:

- capability policy は default deny
- allowed vs excluded capability classes の大枠
- risk scoring / policy / approval の boundary
- capability manifest boundary
- release verification との relation のうち、tracked docs に既にある部分

この文書が固定しないもの:

- risk scoring algorithm の exact formula
- approval transport の exact wire shape
- runtime trust level の exact enum set
- Discord / browser / media side effect 実装
- private operator policy implementation

## Non-Goals

- capability 実装順の確定
- risky capability を v0.1 shared contract に追加すること
- private runtime exactness を public contract に昇格させること
- route policy widening
- `src/cogs/ora.py` reopen

## Capability Default Deny

固定 truth:

- capability policy は default deny
- undeclared capability は reject 対象
- Distribution Node MVP で allow される capability は manifest に明示されるものに限る

tracked docs にある schema:

- `schema_version = yonerai-distribution-capabilities/v1`
- `profile = distribution_node_mvp`
- `default_action = deny`
- `capabilities = { "<capability>": true|false }`

Status:

- default deny = fixed
- manifest schema exact evolution policy = `UNRESOLVED`

## Allowed vs Excluded Capability Classes

### Allowed Reading

この phase で contract 化してよいのは次の coarse policy まで。

- default-safe capability manifest
- explicit allow / deny declaration
- continuation-result に必要な bounded capability handoff

### Excluded Capability Classes

Distribution Node MVP に含めないもの:

- `arbitrary shell`
- `arbitrary SQL`
- `arbitrary file write`
- `high-risk control-plane execution`

この excluded set は shared run contract に含めない。
また、これらを alias / relay / files boundary から迂回的に再導入しない。

Status:

- excluded class list = fixed
- exact enforcement location = `UNRESOLVED`

## Risk Scoring / Policy / Approval Boundary

この lane で contract 化する boundary は次。

- capability metadata は public-safe boundary に寄せる
- policy decision は deny-first で解釈する
- approval surface は canonical 3 endpoint contract の外側に残す
- operator/admin approval の exact runtime は shared contract に含めない

固定 truth:

- approval は canonical shared run contract そのものではない
- risk scoring の存在は boundary として扱うが、exact formula は contract 化しない
- policy / approval / privileged execution の混在は future boundary cleanup 対象

未固定:

- risk score numeric scale
- trust level exact taxonomy
- approval token / challenge の exact schema

Status:

- boundary separation = fixed
- runtime exactness = `UNRESOLVED`

## Capability Manifest Boundary

capability manifest は public-safe contract 側に置ける truth を持つ。
ただし、privileged adapter 実装そのものは shared contract ではない。

固定 truth:

- manifest は capability allow/deny の declarative boundary
- private internals を直接 import しない
- cross-repo interaction は contract 経由だけ

未固定:

- manifest refresh flow
- manifest signing / rotation policy
- manifest distribution transport exactness

Status:

- manifest boundary = fixed
- manifest lifecycle exactness = `GAP`

## Release Verification Relation

tracked docs で既に固定されている relation は次のみ。

- signed release verification は fail-closed
- release verification は capability manifest digest binding を含む最小 path を使う

この文書で固定しないもの:

- release verification の内部手順 exactness
- multi-key / threshold / transparency log rollout

Status:

- fail-closed relation = fixed
- deeper release/runtime coupling = `UNRESOLVED`

## Open Gaps

- `GAP`: excluded capability classes の dedicated test coverage
- `GAP`: manifest lifecycle / rotation exactness
- `UNRESOLVED`: risk scoring formula
- `UNRESOLVED`: approval runtime exact wire behavior
- `UNRESOLVED`: policy enforcement path exact code ownership

## Anchor Set

- `docs/V76_TRUTH_SYNC_PACKET_JP.md`
- `docs/DISTRIBUTION_NODE_MVP.md`
- `docs/contracts/external-agent-api.md`
- `YonerAI Internal Run API v0.1 Draft`
