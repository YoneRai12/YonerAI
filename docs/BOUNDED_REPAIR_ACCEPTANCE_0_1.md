# Bounded Repair Acceptance 0.1

Status:

- post-repair acceptance artifact
- docs-only
- accepted outcome for the bounded repair code batch

## Exact Accepted File Set

authorized 3-file set のうち、実際に変更されたのは次の 2 files のみ。

1. `core/src/ora_core/api/routes/runs.py`
2. `tests/test_distribution_node_mvp.py`

未変更:

- `core/src/ora_core/api/routes/messages.py`

## Exact Objective Achieved

achieved objective:

- auth precedence run-owner mismatch on `POST /v1/messages` was cleared
- forbidden field leakage on `meta` at canonical `GET /v1/runs/{run_id}/events` was cleared

## Why `messages.py` Non-Edit Is Acceptable

- accepted repair outcome showed no route precedence break in `core/src/ora_core/api/routes/messages.py`
- concrete auth precedence issue was a test fixture rollback artifact
- the passing validation outcome shows that route edit was not required to satisfy the current minimum observable predicate

## Auth Precedence Row

- status = `cleared`
- failing test no longer fails
- root cause was test fixture rollback artifact, not route precedence break
- accepted repair pre-committed the auth user in `tests/test_distribution_node_mvp.py` so the test observes a durable auth identity instead of a rolled-back transient one

## Meta Exposure Row

- status = `cleared`
- failing test no longer fails
- accepted repair was serializer-boundary sanitization in `core/src/ora_core/api/routes/runs.py`
- the repair closed the current negative predicate without fixing a new exact allowlist as contract truth

## No-Go Violations Avoided

- no edit outside the authorized 3 files
- actual edits stayed within 2 files only
- no edit to `messages.py`
- no edit to auth / repo / models
- no new SSE event type
- no contract widening
- no `reasoning_summary` contract widening
- no `meta` exact allowlist fixation as new truth
- no approvals / storage / relay / alias surface handling
- no route policy widening
- no dirty band0 clamp reopen
- no stage / commit

## Validation Result

- `python -m compileall core/src` = success
- `pytest tests/test_distribution_node_mvp.py -q` = `16 passed, 50 warnings`

## Warnings Summary

- warnings count = `50`
- current observed warnings are SQLAlchemy-side `datetime.utcnow()` deprecation warnings
- they are classified as non-current-batch blockers unless later evidence shows otherwise

## Why Broader Execution Is Still Not Justified

- `reasoning_summary safe exposure` remains `partial`
- producer owner remains `UNRESOLVED`
- exact payload schema remains `UNRESOLVED`
- the bounded repair batch cleared its two target rows, but it did not close the remaining contract-hardening and validation bundle work

## Bottom Line

- bounded repair code batch is accepted
- auth precedence row is cleared
- meta exposure row is cleared
- broader execution remains not justified
