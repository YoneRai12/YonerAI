# SSE Run Events Contract

Status:

- durable contract doc
- current anchor: `Stage 6p post-PR153 traceability refresh`
- fixed anchor: `YonerAI Internal Run API v0.1 Draft`
- lane: `YonerAI mainline`

## Purpose

This document fixes the canonical `GET /v1/runs/{run_id}/events` SSE semantics.
The fixed surface is event meaning, terminal rule, and safe exposure boundary.
It does not contract legacy queue framing, private operator internals, or raw reasoning.

## Scope

This document fixes:

- canonical SSE purpose
- event catalog
- terminal rule
- unknown event safe-ignore rule
- `reasoning_summary` exposure boundary
- `meta` exposure boundary

This document does not fix:

- exact canonical wire framing
- heartbeat / retry shape
- private operator diagnostics
- hidden routing internals
- raw chain-of-thought

## Canonical SSE Purpose

`GET /v1/runs/{run_id}/events` is the canonical authenticated ordered run event stream.
It exists for user-facing progress, safe summaries, and continuation handoff.
It is not a raw files transport; files cross the boundary through file references.

## Transport Assumptions

Fixed truth:

- transport is SSE
- stream is run-scoped
- terminal event is exactly one of `final` or `error`
- unknown event is safe-ignore

Unresolved:

- exact canonical frame shape
- retry hint
- heartbeat shape

## Event Catalog

| Event | Purpose | Allowed surface | Notes |
| --- | --- | --- | --- |
| `delta` | incremental user-visible output | user-facing text delta | hidden reasoning is not included |
| `reasoning_summary` | safe reasoning summary | `{}` or `{"summary": str}` in delivered public-core scope | raw chain-of-thought is not included |
| `trace` | safe trace labels / details / sources | already-safe backend-emitted trace material only | hidden internals are not included |
| `meta` | non-terminal run metadata | bounded metadata only | exact field set remains unresolved |
| `tool_result_submit` | continuation handoff | tool continuation request only | client returns through `POST /v1/runs/{run_id}/results` |
| `final` | terminal success | final user-safe result | terminal event |
| `error` | terminal failure | user-safe error result | terminal event |

## Terminal Rule

Fixed truth:

- terminal event is `final` or `error`
- terminal event occurs exactly once
- user-visible events do not continue after the terminal event

Unresolved:

- detailed `final` / `error` status split
- terminal error body schema

## Unknown Event Safe-Ignore Rule

Clients may safe-ignore unknown events.
The existence of an unknown event must not make the whole stream fail.

Fixed negative predicate:

- unknown event does not prevent a terminal event
- unknown event does not itself require canonical contract widening

Status:

- safe-ignore = fixed
- client observability details = `GAP`
- server-side handling owner = `UNRESOLVED`

## Reasoning Summary Exposure Boundary

`reasoning_summary` is limited to public-safe summary data.

Fixed negative predicate:

- raw chain-of-thought must not pass
- raw prompt / raw prompts must not pass
- hidden routing rationale must not pass
- dirty band0 / route policy internals must not pass
- operator-only diagnostics must not pass
- private admin state must not pass

Post-PR153 fixed truth for delivered public-core scope:

- accepted public-core shape is `{}` or `{"summary": str}`
- producer/event-bus shaping is accepted in `core/src/ora_core/engine/simple_worker.py`
- public SSE boundary shaping is accepted in `core/src/ora_core/api/routes/runs.py`
- durable negative and producer-boundary evidence exists in `tests/test_distribution_node_mvp.py`

Status:

- negative exposure boundary = fixed
- producer owner = `confirmed for delivered public-core scope`
- exact payload schema = `confirmed for delivered public-core scope`
- broader summary length / UX structure exactness = `not claimed`

## Meta Exposure Boundary

`meta` is limited to bounded metadata and must not become an open-ended dump.

Allowed:

- lifecycle bounded metadata
- user-safe progress metadata
- safe correlation metadata

Forbidden:

- operator-only diagnostics
- private admin state
- hidden router budgets
- dirty band0 / route policy internals
- raw prompts
- raw chain-of-thought

Observed source-side evidence:

- serializer-boundary sanitization evidence exists in `core/src/ora_core/api/routes/runs.py`
- current boundary sanitization removes forbidden keys from `meta` payload before SSE serialization
- durable negative test evidence exists in `tests/test_distribution_node_mvp.py::test_distribution_node_sse_meta_does_not_expose_forbidden_probe_fields`

Status:

- exposure boundary = fixed
- serializer-boundary sanitization evidence = observed
- exact field list = `UNRESOLVED`

## Hidden Internals Not Contractized

The canonical SSE contract does not include:

- raw chain-of-thought
- private routing rationale
- route policy widening data
- dirty band0 clamp data
- operator-only diagnostics
- Oracle host / control-plane internals

## Open Gaps

- `UNRESOLVED`: canonical SSE wire framing
- `UNRESOLVED`: `meta` exact field set
- `UNRESOLVED`: unknown event safe-ignore server-side handling owner
- `GAP`: heartbeat / retry exact contract
- `GAP`: unknown event observability details
- `GAP`: error body exact schema

## Anchor Set

- `docs/CURRENT_PHASE_CONTEXT.md`
- `docs/REASONING_SUMMARY_EXACTNESS_ACCEPTANCE_0_1.md`
- `docs/TRACEABILITY_MATRIX_0_17.md`
- `YonerAI Internal Run API v0.1 Draft`
