# Planning Exit Scorecard 0.2

Status:

- planning gate artifact
- strict scoring only
- basis:
  - `docs/PLANNING_PACKET_0_2.md`
  - `docs/EXECUTION_GATE_MEMO_0_2.md`
  - `docs/TRACEABILITY_MATRIX_0_6.md`
  - `docs/TEST_GAP_REGISTER_0_2.md`
  - `docs/CODE_EVIDENCE_REVIEW_0_2.md`

## Scorecard

| Planning-exit criterion | Status | Basis |
| --- | --- | --- |
| `docs/V76_TRUTH_SYNC_PACKET_JP.md` と planning packet に矛盾がない | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| shared run contract 3 endpoint が docs 上で一意に読める | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/contracts/external-agent-api.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| auth precedence / SSE terminal rule / file-ref-only / files boundary が docs 上で一意に読める | `satisfied` | `docs/contracts/external-agent-api.md`, `docs/contracts/sse-run-events.md`, `docs/contracts/file-download-boundary.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| docs / tests / code の traceability が十分に埋まっている | `blocked` | `docs/TRACEABILITY_MATRIX_0_6.md` に `gap` が残る。exact blocker row: `unknown event safe-ignore`, ``reasoning_summary` safe exposure`, ``meta` bounded exposure`。補助根拠: `docs/SSE_EXPOSURE_PREDICATES_0_1.md`, `docs/TEST_GAP_REGISTER_0_2.md` |
| code 着手条件 / 停止条件 / readiness judgment 条件が memo 化されている | `satisfied` | `docs/EXECUTION_GATE_MEMO_0_2.md` |
| freeze / no-go list に例外がない | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| execution reservation が reservation としてのみ保持されている | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/EXECUTION_GATE_MEMO_0_2.md` |
| durable contract docs が planning artifact から参照可能 | `satisfied` | `docs/TRACEABILITY_MATRIX_0_6.md` が contract docs を docs evidence に接続している |

## Strict Verdict

`still planning-only`

## Distance Moved Since 0.1

- strict blocker row `approvals / operator / admin surface stays outside canonical 3 endpoint contract` は `gap -> partial`
- strict blocker row `storage boundary separation` は `gap -> partial`
- approvals token requirement owner と list/detail redaction owner が read-only mapping で具体化した
- SSE 3 blocker は negative predicate が sharpen したが、status は `gap` のまま

## Why The Verdict Still Does Not Move

- planning exit を止めている `gap` がまだ 3 本残っている
- 3 本とも SSE exposure 系で、dedicated test も server-side enforcement owner も閉じていない
- `docs/EXECUTION_GATE_MEMO_0_2.md` の前提上、execution gate は別判定でしか開かない

## Exact Remaining Blockers

- `docs/TRACEABILITY_MATRIX_0_6.md`
  - `GET /v1/runs/{run_id}/events`: unknown event safe-ignore
  - `GET /v1/runs/{run_id}/events`: `reasoning_summary` safe exposure
  - `GET /v1/runs/{run_id}/events`: `meta` bounded exposure
- `docs/contracts/approvals-surface-boundary.md`
  - `GAP`: approvals response schema
  - `GAP`: approve / deny response redaction exactness
- `docs/contracts/storage-boundary.md`
  - `GAP`: ambiguous local tables durable class assignment
  - `UNRESOLVED`: final storage decomposition
- `docs/CODE_EVIDENCE_REVIEW_0_2.md`
  - `UNRESOLVED`: SSE enforcement owner
  - `UNRESOLVED`: relay adapter exact interface/dependency reading

## Bottom Line

- planning exit は 0.1 より近い
- ただし strict verdict は変わらない
- current state は `still planning-only`
