# Traceability Matrix 0.8

Status:

- planning gate artifact
- docs / tests / code 対応表
- remaining blocker deepening refresh applied
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
| `GET /v1/runs/{run_id}/events` | shared run contract の event stream 入口である | `docs/contracts/external-agent-api.md`, `docs/contracts/sse-run-events.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `V75_INTERNAL_API_ALIGNMENT.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_ends_with_exactly_one_terminal_event` | `core/src/ora_core/api/routes/runs.py` (entry/auth/SSE wrapper; event shape owner unresolved) | partial |
| `GET /v1/runs/{run_id}/events` | unauthenticated run events は reject する | `docs/contracts/external-agent-api.md`, `docs/contracts/sse-run-events.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_unauthenticated_run_events` | `core/src/ora_core/api/routes/runs.py` (401/404 owner gate) | partial |
| `GET /v1/runs/{run_id}/events` | SSE terminal は `final` か `error` のどちらか 1 回だけ | `docs/contracts/sse-run-events.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_ends_with_exactly_one_terminal_event` | `core/src/ora_core/api/routes/runs.py`, `core/src/ora_core/engine/simple_worker.py` (wrapper only; terminal dedupe owner unresolved) | partial |
| `GET /v1/runs/{run_id}/events` | unknown event は safe-ignore する | `docs/contracts/sse-run-events.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_unknown_event_does_not_block_terminal_event` | `core/src/ora_core/api/routes/runs.py` (current wrapper visible; client-side safe-ignore owner remains broad) | partial |
| `GET /v1/runs/{run_id}/events` | `reasoning_summary` は safe summary のみを露出し raw chain-of-thought を契約化しない | `docs/contracts/sse-run-events.md`, `docs/REASONING_SUMMARY_OWNER_REVIEW_0_1.md` | `MISSING TEST` | `core/src/ora_core/api/routes/runs.py` (pass-through serializer only); inspected `core/src/ora_core/engine/simple_worker.py` does not emit `reasoning_summary`; producer / sanitizer owner unresolved | gap |
| `GET /v1/runs/{run_id}/events` | `tool_result_submit` は continuation handoff event である | `docs/contracts/sse-run-events.md`, `docs/contracts/external-agent-api.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_results_accept_continuation_only` | `core/src/ora_core/api/routes/runs.py`, `core/src/ora_core/engine/simple_worker.py` | partial |
| `GET /v1/runs/{run_id}/events` | `meta` は bounded metadata のみを露出し hidden routing internals を含めない | `docs/contracts/sse-run-events.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_meta_does_not_expose_forbidden_probe_fields` | `core/src/ora_core/api/routes/runs.py` (current wrapper visible; server-side filter owner unresolved) | partial |
| `POST /v1/runs/{run_id}/results` | shared run contract の continuation result 入口である | `docs/contracts/external-agent-api.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `V75_INTERNAL_API_ALIGNMENT.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_results_accept_continuation_only` | `core/src/ora_core/api/routes/runs.py` (entry + continuation gate; owner tag broad) | partial |
| `POST /v1/runs/{run_id}/results` | continuation-only。`tool_call_id` なし result は reject | `docs/contracts/external-agent-api.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_results_accept_continuation_only` | `core/src/ora_core/api/routes/runs.py`, `core/src/ora_core/engine/simple_worker.py` | partial |
| `POST /v1/runs/{run_id}/results` | unauthenticated run results は reject する | `docs/contracts/external-agent-api.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_unauthenticated_run_results` | `core/src/ora_core/api/routes/runs.py` (401/404 owner gate) | partial |

## 2. Files Contract

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| run payload | run API は raw bytes を返さず file-ref-only | `docs/contracts/file-download-boundary.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_files_are_refs_only_and_downloadable` | `core/src/ora_core/distribution/files.py` | partial |
| file normalization | local file は run contract を越える前に file reference へ正規化される。exact `fileref:` wire shape は未固定 | `docs/contracts/file-download-boundary.md`, `docs/contracts/storage-boundary.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_files_are_refs_only_and_downloadable` | `core/src/ora_core/distribution/files.py::normalize_tool_result_for_run` | partial |
| file ticket | files contract は `short-lived URL / owner-scope / Cache-Control: no-store / audit` を前提にする | `docs/contracts/file-download-boundary.md`, `docs/contracts/storage-boundary.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_files_are_refs_only_and_downloadable`, `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_unauthenticated_file_ticket` | `core/src/ora_core/api/routes/files.py`, `core/src/ora_core/database/models.py` | partial |
| file ticket | unauthenticated file ticket issuance は reject する | `docs/contracts/file-download-boundary.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `YonerAI Internal Run API v0.1 Draft` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_unauthenticated_file_ticket` | `core/src/ora_core/api/routes/files.py` | partial |
| file ticket | redirect / body return の exact wire behavior は未固定 | `docs/contracts/file-download-boundary.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_files_are_refs_only_and_downloadable` | `core/src/ora_core/api/routes/files.py` (`POST` currently returns JSON `download_url`; `GET` currently returns `FileResponse`, exact contract unresolved) | partial |

## 3. Policy / Capability Constraints

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| capability policy | default deny を維持する | `docs/contracts/tool-capability-and-risk.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_non_deny_default_action` | `core/src/ora_core/distribution/runtime.py`, `config/distribution/distribution_node_capabilities.json` | partial |
| release verification | Distribution Node MVP は fail-closed | `docs/contracts/tool-capability-and-risk.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_release_verification_fails_closed` | `core/src/ora_core/distribution/runtime.py`, `core/src/ora_core/distribution/release.py` | partial |
| excluded capabilities | arbitrary shell / SQL / file write / high-risk control-plane は MVP 非対象 | `docs/contracts/tool-capability-and-risk.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_manifest_explicitly_denies_excluded_capabilities` | `config/distribution/distribution_node_capabilities.json`, `core/src/ora_core/distribution/runtime.py` | partial |
| capability manifest | manifest は declarative allow/deny boundary であり privileged runtime exactness そのものではない | `docs/contracts/tool-capability-and-risk.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_non_deny_default_action`, `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_undeclared_tool_capability` | `config/distribution/distribution_node_capabilities.json` | partial |

## 4. External Alias / Admin Surfaces

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/agent/run` | external alias は path と response URLs を維持する | `docs/contracts/external-agent-api.md`, `ENDPOINTS_ROUTE_MATRIX.md` | `tests/test_external_agent_api.py::test_external_agent_run_requires_token` | `src/web/endpoints.py` | partial |
| `/api/v1/agent/*` | external alias は legacy queue surface であり canonical core contract そのものではない | `docs/contracts/external-agent-api.md`, `ENDPOINTS_ROUTE_MATRIX.md` | `MISSING TEST` | `src/web/endpoints.py` | partial |
| approvals surface | approvals endpoints は token を要求する | `docs/contracts/approvals-surface-boundary.md` | `tests/test_approvals_api.py::test_approvals_endpoints_require_token` | `src/web/endpoints.py::require_web_api`, `src/web/endpoints.py::require_admin`, approvals route family | partial |
| approvals surface | approval detail は `expected_code` を露出しない | `docs/contracts/approvals-surface-boundary.md`, `docs/APPROVALS_RESPONSE_SHAPE_REVIEW_0_1.md` | `tests/test_approvals_api.py::test_expected_code_is_not_exposed` | `src/web/endpoints.py::api_list_approvals`, `src/web/endpoints.py::api_get_approval`; raw persistence side `src/storage.py::get_approval_requests_rows`, `src/storage.py::get_approval_request` | partial |
| approvals surface | list/detail の minimum observable response envelope は `ok` + `data` に留まる | `docs/APPROVALS_RESPONSE_SHAPE_REVIEW_0_1.md`, `docs/contracts/approvals-surface-boundary.md` | `tests/test_approvals_api.py::test_expected_code_is_not_exposed` | `src/web/endpoints.py::api_list_approvals`, `src/web/endpoints.py::api_get_approval` | partial |
| approvals surface | approvals / operator / admin surface は canonical 3 endpoint contract の外側に残す | `docs/contracts/approvals-surface-boundary.md`, `docs/contracts/external-agent-api.md` | `tests/test_approvals_api.py::test_approvals_surface_uses_dedicated_approval_handle` | `src/web/endpoints.py` approvals route family (`/approvals*`, `/audit/approvals`) is separate from canonical `/v1/*` run contract surfaces | partial |

## 5. Migration / Schema Constraints

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| migration revision | migration revision は `tool_calls` と distribution file tables を含む | `docs/contracts/storage-boundary.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_migration_contract.py::test_distribution_revision_includes_tool_calls_and_file_tables` | `core/alembic/versions/9d2e4c3c0f31_add_distribution_file_tables.py`, `core/src/ora_core/database/models.py` | partial |
| storage boundary | shared contract state は private runtime state / operator-admin state と同一視しない | `docs/contracts/storage-boundary.md`, `docs/STORAGE_TABLE_CLASS_ASSIGNMENT_0_1.md` | `MISSING TEST` | `core/src/ora_core/database/models.py` shared-facing minimum (`tool_calls`, `distribution_file*`) vs `src/storage.py` local mixed state (`approval_requests`, `tool_audit`, `dashboard_tokens`, `web_sessions`, `scheduled_tasks`, `public_chat_feedback`) | partial |

## 6. Relay / Boundary Rules

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| safe pause | `src/cogs/ora.py` は freeze 対象 | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/PLANNING_PACKET_0_2.md` | `n-a` | `n-a` | confirmed |
| reject rule | dirty band0 clamp は reopen しない | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `FINAL_DECISION_SUMMARY.md` | `n-a` | `n-a` | confirmed |
| relay boundary | Oracle host 依存を public relay / public contract に直接混ぜない | `docs/contracts/relay-exposure-boundary.md`, `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `CONTRACT_GAPS.md`, `REPO_TARGET_TREES.md` | `n-a` | `src/relay/main.py`, `src/relay/expose_cloudflare.py`, `src/utils/temp_downloads.py` | partial |
| relay boundary | public relay contract は Oracle-host-only internals を required dependency にしない | `docs/contracts/relay-exposure-boundary.md`, `docs/RELAY_INTERFACE_REVIEW_0_1.md`, `CONTRACT_GAPS.md` | `n-a` | `src/relay/main.py` (import-time adapter coupling visible); `src/relay/expose_cloudflare.py` current observed adapter surface is `start_quick_tunnel` / `wait_for_public_url` / `write_public_url_file`; `src/utils/temp_downloads.py` is separate expose ownership | partial |
| boundary rule | public artifacts は private internals を直接 import しない | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/PLANNING_PACKET_0_2.md` | `n-a` | `n-a` | confirmed |
| boundary rule | cross-repo interaction は contract 経由だけ | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/PLANNING_PACKET_0_2.md` | `n-a` | `n-a` | confirmed |

## 7. Remaining Blocking Themes

- `GET /v1/runs/{run_id}/events`: `reasoning_summary` safe exposure
- approvals response schema exactness
  - list/detail minimum envelope は観測できる
  - approve / deny response redaction exactness は未解決
- ambiguous local tables durable class assignment
  - `users`
  - `user_identities`
  - `conversations`
- risk / approval runtime exactness
- storage decomposition exactness
- relay adapter exact interface
