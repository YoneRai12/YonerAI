# Planning Exit Scorecard 0.3

Status:

- planning gate artifact
- strict scoring only
- basis:
  - `docs/PLANNING_PACKET_0_2.md`
  - `docs/EXECUTION_GATE_MEMO_0_2.md`
  - `docs/TRACEABILITY_MATRIX_0_7.md`
  - `docs/TEST_GAP_REGISTER_0_3.md`
  - `docs/CODE_EVIDENCE_REVIEW_0_2.md`

## Scorecard

| Planning-exit criterion | Status | Basis |
| --- | --- | --- |
| `docs/V76_TRUTH_SYNC_PACKET_JP.md` と planning packet に矛盾がない | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| shared run contract 3 endpoint が docs 上で一意に読める | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/contracts/external-agent-api.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| auth precedence / SSE terminal rule / file-ref-only / files boundary が docs 上で一意に読める | `satisfied` | `docs/contracts/external-agent-api.md`, `docs/contracts/sse-run-events.md`, `docs/contracts/file-download-boundary.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| docs / tests / code の traceability が十分に埋まっている | `blocked` | `docs/TRACEABILITY_MATRIX_0_7.md` に `gap` が残る。exact blocker row: `GET /v1/runs/{run_id}/events`: `reasoning_summary` safe exposure。補助根拠: `docs/TEST_GAP_REGISTER_0_3.md`, `docs/CODE_EVIDENCE_REVIEW_0_2.md` |
| code 着手条件 / 停止条件 / readiness judgment 条件が memo 化されている | `satisfied` | `docs/EXECUTION_GATE_MEMO_0_2.md` |
| freeze / no-go list に例外がない | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| execution reservation が reservation としてのみ保持されている | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/EXECUTION_GATE_MEMO_0_2.md` |
| durable contract docs が planning artifact から参照可能 | `satisfied` | `docs/TRACEABILITY_MATRIX_0_7.md` が contract docs を docs evidence に接続している |

## Strict Verdict

`still planning-only`

## Distance Moved Since 0.2

- strict blocker row `unknown event safe-ignore` は `gap -> partial`
- strict blocker row `meta bounded exposure` は `gap -> partial`
- `auth precedence` は durable test evidence を得たが status は `partial` 維持
- `excluded capability classes` は durable test evidence を得たが status は `partial` 維持
- `approvals / operator / admin surface stays outside canonical 3 endpoint contract` は durable test evidence を得たが status は `partial` 維持

## Why The Verdict Still Does Not Move

- planning exit を止めている `gap` がまだ 1 本残っている
- その 1 本は `reasoning_summary` safe exposure で、dedicated test も server-side enforcement owner も閉じていない
- さらに approvals response exactness / storage decomposition / relay interface の `GAP` / `UNRESOLVED` が残っている
- `docs/EXECUTION_GATE_MEMO_0_2.md` の前提上、execution gate は別判定でしか開かない

## Exact Remaining Blockers

- `docs/TRACEABILITY_MATRIX_0_7.md`
  - `GET /v1/runs/{run_id}/events`: `reasoning_summary` safe exposure
- `docs/contracts/approvals-surface-boundary.md`
  - `GAP`: approvals response schema
  - `GAP`: approve / deny response redaction exactness
- `docs/contracts/storage-boundary.md`
  - `GAP`: ambiguous local tables durable class assignment
  - `UNRESOLVED`: final storage decomposition
- `docs/CODE_EVIDENCE_REVIEW_0_2.md`
  - `UNRESOLVED`: reasoning_summary / SSE enforcement owner
  - `UNRESOLVED`: relay adapter exact interface/dependency reading

## Bottom Line

- planning exit は 0.2 より近い
- ただし strict verdict は変わらない
- current state は `still planning-only`
