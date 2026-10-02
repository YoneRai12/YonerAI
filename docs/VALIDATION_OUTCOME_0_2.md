# Validation Outcome 0.2

Status:

- latest validation snapshot
- docs-only
- supersedes `docs/VALIDATION_OUTCOME_0_1.md`

## Exact Branch Status

- exact current branch ref = `refs/heads/codex/model-gpt-5-4`
- switched branch in the repair batch = `no`
- keep-set branch = `yes`
- worktree state at outcome capture = `dirty`
- no stage / commit

## Exact Commands Run

1. `python -m compileall core/src`
2. `pytest tests/test_distribution_node_mvp.py -q`

## Exact Result

- `python -m compileall core/src`
  - success
- `pytest tests/test_distribution_node_mvp.py -q`
  - `16 passed, 50 warnings`

## Warning Classification

- current warnings are not treated as current-batch blockers
- present evidence points to SQLAlchemy `datetime.utcnow()` deprecation warnings
- no evidence in this outcome shows they were introduced by the accepted bounded repair

## Validation State

- validation is no longer env-blocked
- validation target currently passes
- this outcome supersedes `docs/VALIDATION_OUTCOME_0_1.md` as the latest validation snapshot

## Why Broader Execution Is Still Not Justified

- the accepted repair cleared two concrete failing rows only
- `reasoning_summary safe exposure` remains `partial`
- producer owner and exact payload schema remain unresolved
- broader execution requires more than a passing narrow target test

## Bottom Line

- latest accepted validation snapshot = `16 passed, 50 warnings`
- env-only blocker state is retired
- broader execution remains not justified
