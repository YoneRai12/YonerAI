# Type Safety Reality Check - 2026-05-21

Status: public-safe maintenance note.

## Finding

The external concern was partly valid: `pyproject.toml` disabled mypy's `syntax` error code. That did not fully hide syntax failures in CI because both Python workflows also run `python -m compileall src/`, but suppressing `syntax` in mypy was still misleading and weakened the type-safety signal.

## Change

- Removed `syntax` from `tool.mypy.disable_error_code`.
- Added `tests/test_mypy_config_guard.py` so the suppression does not return unnoticed.

## Scope

This is not a broad typing cleanup. The existing mypy baseline still contains many temporary suppressions that should be reduced in smaller typed lanes.

## Non-Claims

This does not claim full type safety, production readiness, Discord restoration, persistent memory completion, Google login completion, full hybrid completion, broad ORA rename completion, or `src/cogs/ora.py` resolution.
