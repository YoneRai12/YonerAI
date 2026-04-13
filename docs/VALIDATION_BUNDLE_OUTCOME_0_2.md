# Validation Bundle Outcome 0.2

Status:

- latest validation bundle outcome
- docs-only
- supersedes `docs/VALIDATION_BUNDLE_OUTCOME_0_1.md`

## Exact Branch / Worktree State

- exact current branch ref = `refs/heads/codex/model-gpt-5-4`
- switched branch in the validation snapshot batch = `no`
- keep-set branch = `yes`
- worktree state at outcome capture = `dirty`
- no git / stage / commit

## Exact Commands Run

1. `python -m compileall src core/src`
2. `pytest tests/test_distribution_node_mvp.py -q`
3. `pytest tests/test_external_agent_api.py -q`
4. `pytest tests/test_distribution_migration_contract.py -q`
5. `pytest tests/test_approvals_api.py -q`

## Exact Result

- `python -m compileall src core/src`
  - pass
- `pytest tests/test_distribution_node_mvp.py -q`
  - `16 passed, 50 warnings`
- `pytest tests/test_external_agent_api.py -q`
  - `1 passed, 8 warnings`
- `pytest tests/test_distribution_migration_contract.py -q`
  - `1 passed`
- `pytest tests/test_approvals_api.py -q`
  - `3 passed, 24 warnings`

## Current Bundle State

- full bundle pass = `yes`
- active validation blocker = `none`
- env/import blocker = `none`

## Retired Failure

- prior approvals behavioral failure is retired
- retired blocker:
  - `tests/test_approvals_api.py::test_approvals_surface_uses_dedicated_approval_handle`
  - `sqlite3.OperationalError: no such table: approval_requests`
- retirement basis:
  - the 1-file test-only repair aligned seed timing with startup-driven schema initialization

## Warning Summary

- warnings remain present in the bundle
- current evidence points to:
  - SQLAlchemy `datetime.utcnow()` deprecation warnings
  - FastAPI `on_event` deprecation warnings
- they are not classified as current blockers

## Bottom Line

- the failing-bundle snapshot is superseded
- the current latest bundle outcome is a full pass
