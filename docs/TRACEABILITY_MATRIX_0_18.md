# Traceability Matrix 0.18

Status:

- post-`v2026.4.28` traceability refresh
- docs / tests / code correspondence table
- supersedes `docs/TRACEABILITY_MATRIX_0_17.md`

## Legend

- `confirmed`: docs evidence and delivered code/test/release evidence agree
- `partial`: evidence exists but unresolved truth remains
- `blocked`: intentionally not landed or not truthful
- `n-a`: not applicable

## 1. Shared Run Contract

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| `POST /v1/messages` | authenticated user identity is authoritative over body `user_identity` | `docs/CURRENT_PHASE_CONTEXT.md`, `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_messages_auth_precedence_uses_authenticated_user_for_run_owner` | `core/src/ora_core/api/routes/messages.py` | confirmed |
| `GET /v1/runs/{run_id}/events` | `meta` exposes bounded metadata only and does not expose hidden routing internals | `docs/contracts/sse-run-events.md`, `docs/CURRENT_PHASE_CONTEXT.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_meta_does_not_expose_forbidden_probe_fields` | `core/src/ora_core/api/routes/runs.py::_build_sse_payload` | confirmed |
| `GET /v1/runs/{run_id}/events` | `reasoning_summary` exposes public-safe summary only and does not contract raw chain-of-thought | `docs/contracts/sse-run-events.md`, `docs/REASONING_SUMMARY_EXACTNESS_ACCEPTANCE_0_1.md`, `docs/CURRENT_PHASE_CONTEXT.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_reasoning_summary_does_not_expose_forbidden_probe_fields`, `tests/test_distribution_node_mvp.py::test_distribution_node_sse_reasoning_summary_does_not_expose_raw_reasoning` | `core/src/ora_core/api/routes/runs.py`, `core/src/ora_core/engine/simple_worker.py` | confirmed |

## 2. Release / Delivery Evidence

| Item | Evidence | Status |
| --- | --- | --- |
| PR #153 merged | `49c18cb9a61ab2cf1b2a9e115c9f030025cbf656` | confirmed |
| PR #154 merged | `bade7d85169a37cc72fdf89b47e9c7825032c5b9` | confirmed |
| public `main` | `bade7d85169a37cc72fdf89b47e9c7825032c5b9` | confirmed |
| PR #153 checkpoint release | `checkpoint-pr153-reasoning-summary-exactness-2026-04-27` | confirmed |
| public progress release | `v2026.4.28` targeting `bade7d85169a37cc72fdf89b47e9c7825032c5b9` | confirmed |
| Stage 6t Pass 2 attempt | stopped safely without landing Pass 2 | confirmed |

## 3. Current Blocking Themes

- active validation blocker:
  - `none known from accepted PR #153/#154 checks`
- confirmed-ready rows:
  - `POST /v1/messages` auth precedence
  - `GET /v1/runs/{run_id}/events` meta exposure
  - `GET /v1/runs/{run_id}/events` reasoning_summary public-core exactness
  - `v2026.4.28` public progress checkpoint release
- still blocked / not claimed:
  - Pass 2 approval, landing, or completion
  - `src/cogs/ora.py` landing or unblocking
  - shipping-complete
  - full product completion
  - official-cloud completion
  - live operational completion
- still excluded:
  - raw `tools/ops/recover_live_web.ps1`
  - Disaster OS lane work
