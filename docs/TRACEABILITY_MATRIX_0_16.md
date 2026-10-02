# Traceability Matrix 0.16

Status:

- planning gate artifact
- docs / tests / code 対応表
- final validation snapshot refresh applied
- self-citation は使用しない

## Legend

- `confirmed`: authoritative docs evidence があり、tests / code evidence が一致している
- `partial`: docs / tests / code evidence はあるが、未解決点が残る
- `gap`: authoritative docs / tests / code のいずれかが欠けている
- `n-a`: 性質上不要

## 1. Shared Run Contract

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| `POST /v1/messages` | auth 済み user があれば body の `user_identity` より auth identity を優先する | `docs/contracts/external-agent-api.md`, `docs/CURRENT_PHASE_CONTEXT.md`, `docs/BOUNDED_REPAIR_ACCEPTANCE_0_1.md`, `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_messages_auth_precedence_uses_authenticated_user_for_run_owner` | `core/src/ora_core/api/routes/messages.py` preserves route-side precedence; accepted repair outcome showed prior failure was a test fixture rollback artifact | confirmed |
| `GET /v1/runs/{run_id}/events` | `meta` は bounded metadata のみを露出し hidden routing internals を含めない | `docs/contracts/sse-run-events.md`, `docs/BOUNDED_REPAIR_ACCEPTANCE_0_1.md`, `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_meta_does_not_expose_forbidden_probe_fields` | `core/src/ora_core/api/routes/runs.py::_build_sse_payload` applies serializer-boundary sanitization to `meta` without fixing a new exact allowlist truth | confirmed |
| `GET /v1/runs/{run_id}/events` | `reasoning_summary` は safe summary のみを露出し raw chain-of-thought を契約化しない | `docs/contracts/sse-run-events.md`, `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md`, `docs/READINESS_JUDGMENT_0_1.md`, `docs/CURRENT_PHASE_CONTEXT.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_reasoning_summary_does_not_expose_forbidden_probe_fields` | `core/src/ora_core/api/routes/runs.py::_sanitize_reasoning_summary_data`, `core/src/ora_core/api/routes/runs.py::_build_sse_payload` | partial |

## 2. Full Validation Snapshot

| Bundle item | Docs evidence | Tests / command evidence | Code evidence | Status |
| --- | --- | --- | --- | --- |
| `python -m compileall src core/src` | `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md`, `docs/VALIDATION_BUNDLE_OUTCOME_0_2.md` | compileall result = pass | `src`, `core/src` import tree compiles in current env | confirmed |
| `tests/test_distribution_node_mvp.py -q` | `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md`, `docs/VALIDATION_BUNDLE_OUTCOME_0_2.md` | `16 passed, 50 warnings` | target suite remains green after accepted repairs | confirmed |
| `tests/test_external_agent_api.py -q` | `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md`, `docs/VALIDATION_BUNDLE_OUTCOME_0_2.md` | `1 passed, 8 warnings` | external-agent API token gate remains green in current env | confirmed |
| `tests/test_distribution_migration_contract.py -q` | `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md`, `docs/VALIDATION_BUNDLE_OUTCOME_0_2.md` | `1 passed` | migration contract target remains green in current env | confirmed |
| `tests/test_approvals_api.py -q` | `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md`, `docs/VALIDATION_BUNDLE_OUTCOME_0_2.md` | `3 passed, 24 warnings` | approvals suite is green after the bounded test-only repair | confirmed |

## 3. Approvals Surface

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| approvals surface | dedicated approval handle operates on a seedable/readable `approval_requests` row through detail / deny / detail-after flow | `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md`, `docs/VALIDATION_BUNDLE_OUTCOME_0_2.md`, `docs/APPROVALS_FAILURE_REVIEW_0_1.md`, `docs/APPROVALS_REPAIR_CANDIDATE_0_1.md` | `tests/test_approvals_api.py::test_approvals_surface_uses_dedicated_approval_handle` now passes | `src/web/endpoints.py` approvals routes read / decide rows; `src/storage.py::Store.init()` creates table + migration columns; `src/web/app.py` startup calls `await store.init()`; source edit was not required because the repaired issue was test startup order | confirmed |

## 4. Current Blocking Themes

- active validation blocker:
  - `none`
- confirmed-ready rows:
  - `POST /v1/messages` auth precedence
  - `GET /v1/runs/{run_id}/events` meta exposure
  - approvals dedicated-handle row
- residual partial:
  - `GET /v1/runs/{run_id}/events` reasoning_summary safe exposure
- unresolved exactness behind the residual partial:
  - producer owner
  - exact payload schema
- broader execution remains not justified
