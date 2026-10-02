# Validation Outcome 0.1

Status:

- post-validation artifact
- docs-only
- environment recovery outcome record

## Exact Branch Status

- exact current branch ref = `refs/heads/codex/model-gpt-5-4`
- switched branch in the validation recovery batch = `no`
- keep-set branch = `yes`
- worktree state at outcome capture = `dirty`

## Exact Commands That Were Run

1. `python -m pip install "sqlalchemy>=2.0"`
2. `python -m pip install aiofiles`
3. `python -m pip install pytz`
4. `python -m compileall core/src`
5. `pytest tests/test_distribution_node_mvp.py -q`

## Exact Environment Outcome

- already-declared dependencies were installed without manifest edits
- dependency recovery stayed inside the active Python environment used by `pytest`
- the target test command is no longer blocked at import-time by `sqlalchemy`
- this outcome retired the previous env-only blocker classification

## Exact Test Result

- `pytest tests/test_distribution_node_mvp.py -q`
  - `2 failed, 14 passed`

exact failing tests:

1. `test_distribution_node_messages_auth_precedence_uses_authenticated_user_for_run_owner`
   - observed failure summary = run owner mismatch
2. `test_distribution_node_sse_meta_does_not_expose_forbidden_probe_fields`
   - observed failure summary = meta payload still contains forbidden fields such as `secret prompt`

## Exact Reason This Is No Longer An Env-Only Blocker

- `pytest` reached test execution and returned concrete failing assertions
- the blocker is no longer limited to interpreter-level import failure
- the current narrow validation blocker is now behavioral: auth precedence and meta exposure

## Additional Validation Signal

- `python -m compileall core/src` = success
- `reasoning_summary` negative test did not surface in the final failure list

## Why Broader Execution Is Still Not Justified

- two concrete validation failures remain on canonical contract rows
- `reasoning_summary safe exposure` is still only `partial`
- producer owner and exact payload schema remain unresolved
- no bounded repair batch has been authorized by this docs-only refresh

## Bottom Line

- validation is no longer env-only blocked
- validation is now blocked by two concrete failing tests
- broader execution remains not justified
