# Final Validation Snapshot 0.1

Status:

- final validation snapshot artifact
- docs-only
- full post-repair bundle snapshot

## Exact Branch / Worktree State

- exact current branch ref = `refs/heads/codex/model-gpt-5-4`
- switched branch in this batch = `no`
- keep-set branch = `yes`
- worktree state at snapshot capture = `dirty`
- no stage / commit

## Exact Commands Run

1. `python -m compileall src core/src`
2. `pytest tests/test_distribution_node_mvp.py -q`
3. `pytest tests/test_external_agent_api.py -q`
4. `pytest tests/test_distribution_migration_contract.py -q`
5. `pytest tests/test_approvals_api.py -q`

## Exact Per-Command Result

- `python -m compileall src core/src`
  - `pass`
- `pytest tests/test_distribution_node_mvp.py -q`
  - `pass`
  - `16 passed, 50 warnings`
- `pytest tests/test_external_agent_api.py -q`
  - `pass`
  - `1 passed, 8 warnings`
- `pytest tests/test_distribution_migration_contract.py -q`
  - `pass`
  - `1 passed`
- `pytest tests/test_approvals_api.py -q`
  - `pass`
  - `3 passed, 24 warnings`

## Validation Summary

- full bundle pass = `yes`
- active validation blocker = `none`
- env/import blocker = `none`

## Warnings Summary

- `tests/test_distribution_node_mvp.py`
  - SQLAlchemy-side `datetime.utcnow()` deprecation warnings
- `tests/test_external_agent_api.py`
  - FastAPI `on_event` deprecation warnings
  - post-run `Task was destroyed but it is pending!` console note was observed, but exit code remained `0`
- `tests/test_approvals_api.py`
  - FastAPI `on_event` deprecation warnings
- current evidence does not classify these warnings as current blockers

## Cleared Rows In This Snapshot

- `POST /v1/messages` auth precedence row
- `GET /v1/runs/{run_id}/events` meta exposure row
- approvals dedicated-handle row in `tests/test_approvals_api.py`

## Residual Partial

- `GET /v1/runs/{run_id}/events`: `reasoning_summary safe exposure`
  - remains `partial`

## Why Broader Execution Is Still Not Justified

- `reasoning_summary safe exposure` remains `partial`
- producer owner remains `UNRESOLVED`
- exact payload schema remains `UNRESOLVED`
- the full validation bundle is green, but the remaining unresolved contract-hardening item still blocks a broader execution judgment

## Bottom Line

- the repo now has a coherent full validation snapshot
- no active validation blocker remains
- broader execution is still not justified
