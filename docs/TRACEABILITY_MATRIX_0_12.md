# Traceability Matrix 0.12

Status:

- planning gate artifact
- docs / tests / code 対応表
- post-code refresh applied
- self-citation は使用しない

## Legend

- `confirmed`: authoritative docs evidence があり、tests / code evidence が一致しているか、または `n-a`
- `partial`: authoritative docs evidence はあるが、tests または code の裏付けがまだ弱い
- `gap`: authoritative docs / tests / code のいずれかが欠けている
- `n-a`: その欄は性質上不要

## 1. Shared Run Contract

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| `POST /v1/messages` | shared run contract の message submission 入口である | `docs/contracts/external-agent-api.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `V75_INTERNAL_API_ALIGNMENT.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_idempotency_replay_returns_same_run_id` | `core/src/ora_core/api/routes/messages.py` | partial |
| `POST /v1/messages` | auth 済み user があれば body の `user_identity` より auth identity を優先する | `docs/contracts/external-agent-api.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_messages_auth_precedence_uses_authenticated_user_for_run_owner` | `core/src/ora_core/api/routes/messages.py` | partial |
| `POST /v1/messages` | idempotency replay は same `run_id` を返す | `docs/contracts/external-agent-api.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_idempotency_replay_returns_same_run_id` | `core/src/ora_core/api/routes/messages.py`, `core/src/ora_core/database/repo.py` | partial |
| `GET /v1/runs/{run_id}/events` | shared run contract の event stream 入口である | `docs/contracts/external-agent-api.md`, `docs/contracts/sse-run-events.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `V75_INTERNAL_API_ALIGNMENT.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_ends_with_exactly_one_terminal_event` | `core/src/ora_core/api/routes/runs.py` | partial |
| `GET /v1/runs/{run_id}/events` | unauthenticated run events は reject する | `docs/contracts/external-agent-api.md`, `docs/contracts/sse-run-events.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_unauthenticated_run_events` | `core/src/ora_core/api/routes/runs.py` | partial |
| `GET /v1/runs/{run_id}/events` | SSE terminal は `final` か `error` のどちらか 1 回だけ | `docs/contracts/sse-run-events.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_ends_with_exactly_one_terminal_event` | `core/src/ora_core/api/routes/runs.py`, `core/src/ora_core/engine/simple_worker.py` | partial |
| `GET /v1/runs/{run_id}/events` | unknown event は safe-ignore する | `docs/contracts/sse-run-events.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_unknown_event_does_not_block_terminal_event` | `core/src/ora_core/api/routes/runs.py` | partial |
| `GET /v1/runs/{run_id}/events` | `reasoning_summary` は safe summary のみを露出し raw chain-of-thought を契約化しない | `docs/contracts/sse-run-events.md`, `docs/CODE_BATCH_ACCEPTANCE_0_1.md`, `docs/VALIDATION_ENV_BLOCKER_0_1.md`, `docs/REASONING_SUMMARY_SINGLE_FILE_CLOSURE_0_1.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_reasoning_summary_does_not_expose_forbidden_probe_fields` | `core/src/ora_core/api/routes/runs.py::_sanitize_reasoning_summary_data`, `core/src/ora_core/api/routes/runs.py::_build_sse_payload` | partial |
| `GET /v1/runs/{run_id}/events` | `tool_result_submit` は continuation handoff event である | `docs/contracts/sse-run-events.md`, `docs/contracts/external-agent-api.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_results_accept_continuation_only` | `core/src/ora_core/api/routes/runs.py`, `core/src/ora_core/engine/simple_worker.py` | partial |
| `GET /v1/runs/{run_id}/events` | `meta` は bounded metadata のみを露出し hidden routing internals を含めない | `docs/contracts/sse-run-events.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_meta_does_not_expose_forbidden_probe_fields` | `core/src/ora_core/api/routes/runs.py` | partial |
| `POST /v1/runs/{run_id}/results` | shared run contract の continuation result 入口である | `docs/contracts/external-agent-api.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `V75_INTERNAL_API_ALIGNMENT.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_results_accept_continuation_only` | `core/src/ora_core/api/routes/runs.py` | partial |
| `POST /v1/runs/{run_id}/results` | continuation-only。`tool_call_id` なし result は reject | `docs/contracts/external-agent-api.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_results_accept_continuation_only` | `core/src/ora_core/api/routes/runs.py`, `core/src/ora_core/engine/simple_worker.py` | partial |
| `POST /v1/runs/{run_id}/results` | unauthenticated run results は reject する | `docs/contracts/external-agent-api.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_unauthenticated_run_results` | `core/src/ora_core/api/routes/runs.py` | partial |

## 2. Files Contract

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| run payload | run API は raw bytes を返さず file-ref-only | `docs/contracts/file-download-boundary.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_files_are_refs_only_and_downloadable` | `core/src/ora_core/distribution/files.py` | partial |
| file normalization | local file は run contract を越える前に file reference へ正規化される。exact `fileref:` wire shape は未固定 | `docs/contracts/file-download-boundary.md`, `docs/contracts/storage-boundary.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_files_are_refs_only_and_downloadable` | `core/src/ora_core/distribution/files.py::normalize_tool_result_for_run` | partial |
| file ticket | files contract は `short-lived URL / owner-scope / Cache-Control: no-store / audit` を前提にする | `docs/contracts/file-download-boundary.md`, `docs/contracts/storage-boundary.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_files_are_refs_only_and_downloadable`, `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_unauthenticated_file_ticket` | `core/src/ora_core/api/routes/files.py`, `core/src/ora_core/database/models.py` | partial |
| file ticket | unauthenticated file ticket issuance は reject する | `docs/contracts/file-download-boundary.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_unauthenticated_file_ticket` | `core/src/ora_core/api/routes/files.py` | partial |
| file ticket | redirect / body return の exact wire behavior は未固定 | `docs/contracts/file-download-boundary.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_files_are_refs_only_and_downloadable` | `core/src/ora_core/api/routes/files.py` | partial |

## 3. Policy / Capability Constraints

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| capability policy | default deny を維持する | `docs/contracts/tool-capability-and-risk.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_non_deny_default_action` | `core/src/ora_core/distribution/runtime.py`, `config/distribution/distribution_node_capabilities.json` | partial |
| release verification | Distribution Node MVP は fail-closed | `docs/contracts/tool-capability-and-risk.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_release_verification_fails_closed` | `core/src/ora_core/distribution/runtime.py`, `core/src/ora_core/distribution/release.py` | partial |
| excluded capabilities | arbitrary shell / SQL / file write / high-risk control-plane は MVP 非対象 | `docs/contracts/tool-capability-and-risk.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_manifest_explicitly_denies_excluded_capabilities` | `config/distribution/distribution_node_capabilities.json`, `core/src/ora_core/distribution/runtime.py` | partial |
| capability manifest | manifest は declarative allow/deny boundary であり privileged runtime exactness そのものではない | `docs/contracts/tool-capability-and-risk.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_non_deny_default_action`, `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_undeclared_tool_capability` | `config/distribution/distribution_node_capabilities.json` | partial |

## 4. Remaining Blocking Themes

- current blocker movement
  - `GET /v1/runs/{run_id}/events`: `reasoning_summary safe exposure`
  - `gap -> partial`
- not confirmed because:
  - producer owner = `UNRESOLVED`
  - exact payload schema = `UNRESOLVED`
  - `pytest tests/test_distribution_node_mvp.py -q` is blocked by environment dependency
- current validation blocker
  - `ModuleNotFoundError: sqlalchemy`
- non-gating open gaps
  - approvals response schema exactness
  - approve / deny response redaction exactness
  - ambiguous local tables exact class assignment
  - final storage decomposition
  - relay adapter exact interface
  - `public_url_file` lifecycle contractization
