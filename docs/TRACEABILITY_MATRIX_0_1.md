# Traceability Matrix 0.1

Status:

- planning gate artifact
- docs / tests / code 対応表
- `UNCONFIRMED` は不足ではなく、まだ planning gate で固定していない項目

## 1. Shared Run Contract

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| `POST /v1/messages` | shared run contract の message submission 入口である | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `V75_INTERNAL_API_ALIGNMENT.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_idempotency_replay_returns_same_run_id` | `core/src/ora_core/api/routes/messages.py` | partial |
| `POST /v1/messages` | idempotency replay は same `run_id` を返す | `docs/TRACEABILITY_MATRIX_0_1.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_idempotency_replay_returns_same_run_id` | `core/src/ora_core/api/routes/messages.py`, `core/src/ora_core/database/repo.py` | partial |
| `GET /v1/runs/{run_id}/events` | shared run contract の event stream 入口である | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `V75_INTERNAL_API_ALIGNMENT.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_ends_with_exactly_one_terminal_event` | `core/src/ora_core/api/routes/runs.py` `UNCONFIRMED` | partial |
| `GET /v1/runs/{run_id}/events` | terminal event は 1 回だけ終端に出る | `UNCONFIRMED` | `tests/test_distribution_node_mvp.py::test_distribution_node_sse_ends_with_exactly_one_terminal_event` | `core/src/ora_core/engine/simple_worker.py`, `core/src/ora_core/api/routes/runs.py` `UNCONFIRMED` | UNCONFIRMED |
| `POST /v1/runs/{run_id}/results` | shared run contract の continuation result 入口である | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md`, `V75_INTERNAL_API_ALIGNMENT.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_results_accept_continuation_only` | `core/src/ora_core/api/routes/runs.py` `UNCONFIRMED` | partial |
| `POST /v1/runs/{run_id}/results` | continuation-only。`tool_call_id` なし result は reject | `UNCONFIRMED` | `tests/test_distribution_node_mvp.py::test_distribution_node_results_accept_continuation_only` | `core/src/ora_core/api/routes/runs.py`, `core/src/ora_core/engine/simple_worker.py` `UNCONFIRMED` | UNCONFIRMED |

## 2. External Alias Surface

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/agent/run` | external alias は path と response URL を維持する | `ENDPOINTS_ROUTE_MATRIX.md` | `tests/test_external_agent_api.py::test_external_agent_run_requires_token` | `src/web/endpoints.py` | partial |
| `/api/v1/agent/*` | external alias は legacy queue surface であり canonical core contract そのものではない | `ENDPOINTS_ROUTE_MATRIX.md` | `UNCONFIRMED` | `src/web/endpoints.py` | UNCONFIRMED |

## 3. Files Contract

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| run payload | run API は raw bytes を返さず file-ref-only | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `UNCONFIRMED` | `core/src/ora_core/distribution/files.py` | partial |
| file normalization | tool result の local file は `fileref:` に正規化される | `docs/DISTRIBUTION_NODE_MVP.md` | `UNCONFIRMED` | `core/src/ora_core/distribution/files.py::normalize_tool_result_for_run` | UNCONFIRMED |
| file ticket | download ticket は authenticated owner check 前提 | `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_unauthenticated_file_ticket` | `core/src/ora_core/api/routes/files.py` `UNCONFIRMED` | partial |
| file ticket | short-lived URL / single-use / `Cache-Control: no-store` / audit | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `UNCONFIRMED` | `core/src/ora_core/api/routes/files.py`, `core/src/ora_core/database/models.py` `UNCONFIRMED` | UNCONFIRMED |

## 4. Policy / Capability Constraints

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| capability policy | default deny を維持する | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_non_deny_default_action` | `core/src/ora_core/distribution/runtime.py`, `core/src/ora_core/distribution/capabilities.py` `UNCONFIRMED` | partial |
| release verification | Distribution Node MVP は fail-closed | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `tests/test_distribution_node_mvp.py::test_distribution_node_release_verification_fails_closed` | `core/src/ora_core/distribution/runtime.py`, `core/src/ora_core/distribution/release.py` | partial |
| excluded capabilities | arbitrary shell / SQL / file write / high-risk control-plane は MVP 非対象 | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `docs/DISTRIBUTION_NODE_MVP.md` | `UNCONFIRMED` | `config/distribution/distribution_node_capabilities.json`, policy enforcement path `UNCONFIRMED` | UNCONFIRMED |

## 5. Boundary Constraints

| Scope | Rule | Docs evidence | Tests evidence | Code evidence | Status |
| --- | --- | --- | --- | --- | --- |
| safe pause | `src/cogs/ora.py` は freeze | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `B3_SCOPE_AND_VALIDATION.md` | `UNCONFIRMED` | `src/cogs/ora.py` | partial |
| reject | dirty band0 clamp は reopen しない | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `FINAL_DECISION_SUMMARY.md` | `UNCONFIRMED` | `core/src/ora_core/brain/process.py` | partial |
| public/private boundary | Oracle host 依存を public relay / public contract に直接混ぜない | `docs/V76_TRUTH_SYNC_PACKET_JP.md`, `CONTRACT_GAPS.md`, `REPO_TARGET_TREES.md` | `UNCONFIRMED` | `src/relay/main.py`, `src/relay/expose_cloudflare.py`, `src/utils/temp_downloads.py` | UNCONFIRMED |

## 6. Planned Durable Docs

以下は planning gate 中に作成してよい durable docs であり、traceability の欠落を埋める候補。

- `docs/contracts/external-agent-api.md`
- `docs/contracts/sse-run-events.md`
- `docs/contracts/tool-capability-and-risk.md`
- `docs/contracts/storage-boundary.md`
- `docs/contracts/relay-exposure-boundary.md`
- `docs/contracts/file-download-boundary.md`

これらは implementation note ではなく、final 成果物へ吸収可能な正本候補として扱う。
