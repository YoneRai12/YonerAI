# Validation Bundle Outcome 0.1

Status:

- latest full validation bundle snapshot
- docs-only
- records the accepted remaining validation bundle result

## Exact Branch / Worktree State

- exact current branch ref = `refs/heads/codex/model-gpt-5-4`
- switched branch in the bundle batch = `no`
- keep-set branch = `yes`
- worktree state at outcome capture = `dirty`
- no git / stage / commit

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
  - `behavioral failure`
  - `1 failed, 2 passed, 24 warnings`

## Exact Current Blocker

- `tests/test_approvals_api.py::test_approvals_surface_uses_dedicated_approval_handle`
- observed failure:
  - `sqlite3.OperationalError: no such table: approval_requests`

## Classification

- bundle is no longer env/import blocked
- bundle is currently blocked by approvals behavioral failure
- current blocker is not `sqlalchemy`, import resolution, or missing test dependency

## Bundle Notes

- `POST /v1/messages` auth precedence row remains cleared
- `GET /v1/runs/{run_id}/events` meta exposure row remains cleared
- `GET /v1/runs/{run_id}/events` reasoning_summary safe exposure remains `partial`
- broader execution remains not justified

## Bottom Line

- 5 bundle commands all ran
- 4 commands passed
- 1 approvals suite failed behaviorally
- the active blocker moved from env/import to approvals validation fallout
