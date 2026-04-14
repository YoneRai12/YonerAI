# Code Batch Acceptance 0.1

Status:

- post-code refresh artifact
- docs-only
- accepted basis for bounded Track A code batch

## Exact Accepted File Set

authorized 4-file set のうち、実際に変更されたのは次の 2 files のみ。

1. `core/src/ora_core/api/routes/runs.py`
2. `tests/test_distribution_node_mvp.py`

未変更:

- `core/src/ora_core/engine/simple_worker.py`
- `core/src/ora_core/brain/process.py`

## Exact Objective Achieved

achieved objective:

- `reasoning_summary safe exposure owner closure only`

実際に達成した内容:

- canonical `GET /v1/runs/{run_id}/events` 境界で `reasoning_summary` payload に対する serializer-boundary sanitization evidence を `core/src/ora_core/api/routes/runs.py` に追加
- forbidden negative predicate を対象にした durable negative test を `tests/test_distribution_node_mvp.py` に 1 本だけ追加
- exact field allowlist は固定していない
- `meta` / `trace` / `tool_result_submit` contract は変更していない

## Exact No-Go Violations Avoided

- no edit outside the authorized 4 files
- actual edits stayed within 2 files only
- no new SSE event type
- no `meta` / `trace` / `tool_result_submit` contract change
- no approvals / storage / relay / alias surface handling
- no route policy widening
- no dirty band0 clamp reopen
- no `brain/process.py` edit
- no `simple_worker.py` edit
- no stage / commit

## Validation Result Snapshot

- `python -m compileall core/src`
  - success
- `pytest tests/test_distribution_node_mvp.py -q`
  - blocked before test execution by environment dependency
  - `ModuleNotFoundError: sqlalchemy`

## Blocker Movement

- `GET /v1/runs/{run_id}/events`: `reasoning_summary safe exposure`
  - `gap -> partial`

## Why It Did Not Move To Confirmed

- producer owner remains `UNRESOLVED`
- payload schema exactness remains unfixed
- pytest target was blocked by a pre-existing environment dependency

## Bottom Line

- bounded Track A code batch is accepted
- movement is real but bounded
- `reasoning_summary safe exposure` is now `partial`, not `confirmed`
