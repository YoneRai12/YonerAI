# SSE Run Events Contract

Status:

- durable contract doc
- current anchor: `v7.6`
- fixed anchor: `YonerAI Internal Run API v0.1 Draft`
- lane: `Distribution Node MVP`

## Purpose

この文書は canonical `GET /v1/runs/{run_id}/events` の SSE semantics を固定する。
固定対象は event meaning、terminal rule、safe exposure boundary であり、
legacy queue framing や private operator internals を contract 化することではない。

## Scope

この文書が固定するもの:

- canonical SSE purpose
- event catalog
- terminal rule
- unknown event safe-ignore rule
- `reasoning_summary` exposure boundary
- `meta` exposure boundary

この文書が固定しないもの:

- exact wire framing
- private operator diagnostics
- hidden routing internals
- raw chain-of-thought

## Canonical SSE Purpose

`GET /v1/runs/{run_id}/events` は ordered run event stream を返す canonical surface である。
この stream は user-facing progress と continuation handoff のために存在する。
files raw bytes transport には使わない。files は file reference 経由で boundary を越える。

## Transport Assumptions

固定 truth:

- transport は SSE
- stream は run-scoped
- terminal event は `final` または `error` のどちらか 1 回だけ
- unknown event は safe-ignore

未固定:

- exact canonical frame shape
- retry hint
- heartbeat shape

Status:

- event semantics = fixed
- exact frame shape = `UNRESOLVED`

## Event Catalog

| Event | Purpose | Allowed surface | Notes |
| --- | --- | --- | --- |
| `delta` | incremental user-visible output | user-facing text delta | hidden reasoning は含めない |
| `reasoning_summary` | safe reasoning summary | concise summary only | raw chain-of-thought は含めない |
| `trace` | safe trace labels / details / sources | already-safe backend-emitted trace material only | hidden internals は含めない |
| `meta` | non-terminal run metadata | bounded metadata only | exact field set は `UNRESOLVED` |
| `tool_result_submit` | continuation handoff | tool continuation request only | client は `POST /v1/runs/{run_id}/results` へ戻る |
| `final` | terminal success | final user-safe result | terminal event |
| `error` | terminal failure | user-safe error result | terminal event |

## Terminal Rule

固定 truth:

- terminal event は `final` または `error`
- terminal event は exactly once
- terminal event 後に user-visible event を続けない

未固定:

- `final` と `error` の status split
- terminal error body schema

## Unknown Event Safe-Ignore Rule

client は unknown event を safe-ignore してよい。
unknown event の存在だけで stream 全体を failure にしない。

fixed negative predicate:

- unknown event は terminal event を妨げない
- unknown event はそれ自体を理由に canonical contract widening を要求しない

Status:

- safe-ignore = fixed
- client observability details = `GAP`
- server-side handling owner = `UNRESOLVED`

## Reasoning Summary Exposure Boundary

`reasoning_summary` は safe reasoning summary に限る。

fixed negative predicate:

- raw chain-of-thought を運ばない
- raw prompt / raw prompts を運ばない
- hidden routing rationale を運ばない
- dirty band0 / route policy internals を運ばない
- operator-only diagnostics を運ばない
- private admin state を運ばない

fixed truth:

- `reasoning_summary` は concise summary only
- contract 化するのは user-safe summary surface だけ

observed source-side evidence:

- serializer-boundary sanitization evidence exists in `core/src/ora_core/api/routes/runs.py`
- current boundary sanitization removes forbidden keys from `reasoning_summary` payload before SSE serialization
- durable negative test evidence exists in `tests/test_distribution_node_mvp.py::test_distribution_node_sse_reasoning_summary_does_not_expose_forbidden_probe_fields`

still unresolved:

- producer owner
- exact payload schema
- summary length / structure exactness

Status:

- negative exposure boundary = fixed
- serializer-boundary sanitization evidence = observed
- producer owner = `UNRESOLVED`
- exact payload schema = `UNRESOLVED`

## Meta Exposure Boundary

`meta` は bounded metadata に限る。
open-ended dump にはしない。

allowed:

- lifecycle に関する bounded metadata
- user-safe progress metadata
- safe correlation metadata

forbidden:

- operator-only diagnostics
- private admin state
- hidden router budgets
- dirty band0 / route policy internals
- raw prompts
- raw chain-of-thought

observed source-side evidence:

- serializer-boundary sanitization evidence exists in `core/src/ora_core/api/routes/runs.py`
- current boundary sanitization removes forbidden keys from `meta` payload before SSE serialization
- durable negative test evidence exists in `tests/test_distribution_node_mvp.py::test_distribution_node_sse_meta_does_not_expose_forbidden_probe_fields`

Status:

- exposure boundary = fixed
- serializer-boundary sanitization evidence = observed
- exact field list = `UNRESOLVED`

## Hidden Internals Not Contractized

次は canonical SSE contract に含めない。

- raw chain-of-thought
- private routing rationale
- route policy widening data
- dirty band0 clamp data
- operator-only diagnostics
- Oracle host / control-plane internals

## Open Gaps

- `UNRESOLVED`: canonical SSE wire framing
- `UNRESOLVED`: `meta` exact field set
- `UNRESOLVED`: `reasoning_summary` producer owner
- `UNRESOLVED`: `reasoning_summary` exact payload schema
- `UNRESOLVED`: unknown event safe-ignore server-side handling owner
- `GAP`: heartbeat / retry exact contract
- `GAP`: unknown event observability details
- `GAP`: error body exact schema

## Anchor Set

- `docs/V76_TRUTH_SYNC_PACKET_JP.md`
- `docs/DISTRIBUTION_NODE_MVP.md`
- `V75_INTERNAL_API_ALIGNMENT.md`
- `YonerAI Internal Run API v0.1 Draft`
