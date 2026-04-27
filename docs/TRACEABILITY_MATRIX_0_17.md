# Traceability Matrix 0.17

Status:

- post-PR153 traceability refresh
- docs / tests / code correspondence table
- supersedes `docs/TRACEABILITY_MATRIX_0_16.md`

## Legend

- `confirmed`: docs evidence and delivered code/test evidence agree
- `partial`: evidence exists but unresolved truth remains
- `gap`: evidence is missing
- `n-a`: not applicable

## 1. Shared Run Contract

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| `POST /v1/messages` | authenticated user identity is authoritative over body `user_identity` | `docs/CURRENT_PHASE_CONTEXT.md`, `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_messages_auth_precedence_uses_authenticated_user_for_run_owner` | `core/src/ora_core/api/routes/messages.py` | confirmed |
| `GET /v1/runs/{run_id}/events` | `meta` exposes bounded metadata only and does not expose hidden routing internals | `docs/contracts/sse-run-events.md`, `docs/CURRENT_PHASE_CONTEXT.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_meta_does_not_expose_forbidden_probe_fields` | `core/src/ora_core/api/routes/runs.py::_build_sse_payload` | confirmed |
| `GET /v1/runs/{run_id}/events` | `reasoning_summary` exposes public-safe summary only and does not contract raw chain-of-thought | `docs/contracts/sse-run-events.md`, `docs/REASONING_SUMMARY_EXACTNESS_ACCEPTANCE_0_1.md`, `docs/CURRENT_PHASE_CONTEXT.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_reasoning_summary_does_not_expose_forbidden_probe_fields`, `tests/test_distribution_node_mvp.py::test_distribution_node_sse_reasoning_summary_does_not_expose_raw_reasoning` | `core/src/ora_core/api/routes/runs.py`, `core/src/ora_core/engine/simple_worker.py` | confirmed |

## 2. PR #153 Evidence

| Item | Evidence | Status |
| --- | --- | --- |
| PR #153 merged | `49c18cb9a61ab2cf1b2a9e115c9f030025cbf656` | confirmed |
| Candidate commit | `e35f854357e70444a97029978255fcad16dd1240` | confirmed |
| Changed files | `runs.py`, `simple_worker.py`, `tests/test_distribution_node_mvp.py` | confirmed |
| PR checks | `core-test`, `build-and-test (3.11)` pass | confirmed |
| Checkpoint release | `checkpoint-pr153-reasoning-summary-exactness-2026-04-27` | confirmed |

## 3. Current Blocking Themes

- active validation blocker:
  - `none known from accepted PR #153 checks`
- confirmed-ready rows:
  - `POST /v1/messages` auth precedence
  - `GET /v1/runs/{run_id}/events` meta exposure
  - `GET /v1/runs/{run_id}/events` reasoning_summary public-core exactness
- still not claimed:
  - Pass 2 approval
  - shipping-complete
  - full product completion
  - official-cloud completion
  - live operational completion
- still excluded:
  - `src/cogs/ora.py` remains blocked-by-Pass2
  - raw `tools/ops/recover_live_web.ps1` remains excluded
