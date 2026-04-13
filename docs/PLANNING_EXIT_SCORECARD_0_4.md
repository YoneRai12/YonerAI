# Planning Exit Scorecard 0.4

Status:

- planning gate artifact
- strict scoring only
- basis:
  - `docs/PLANNING_PACKET_0_2.md`
  - `docs/EXECUTION_GATE_MEMO_0_2.md`
  - `docs/TRACEABILITY_MATRIX_0_8.md`
  - `docs/TEST_GAP_REGISTER_0_4.md`
  - `docs/CODE_EVIDENCE_REVIEW_0_3.md`

## Scorecard

| Planning-exit criterion | Status | Basis |
| --- | --- | --- |
| `docs/V76_TRUTH_SYNC_PACKET_JP.md` と planning packet に矛盾がない | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| shared run contract 3 endpoint が docs 上で一意に読める | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/contracts/external-agent-api.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| auth precedence / SSE terminal rule / file-ref-only / files boundary が docs 上で一意に読める | `satisfied` | `docs/contracts/external-agent-api.md`, `docs/contracts/sse-run-events.md`, `docs/contracts/file-download-boundary.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| docs / tests / code の traceability が十分に埋まっている | `blocked` | `docs/TRACEABILITY_MATRIX_0_8.md` に `gap` が残る。exact blocker row: `GET /v1/runs/{run_id}/events`: `reasoning_summary` safe exposure。補助根拠: `docs/REASONING_SUMMARY_OWNER_REVIEW_0_1.md`, `docs/TEST_GAP_REGISTER_0_4.md`, `docs/CODE_EVIDENCE_REVIEW_0_3.md` |
| code 着手条件 / 停止条件 / readiness judgment 条件が memo 化されている | `satisfied` | `docs/EXECUTION_GATE_MEMO_0_2.md` |
| freeze / no-go list に例外がない | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| execution reservation が reservation としてのみ保持されている | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/EXECUTION_GATE_MEMO_0_2.md` |
| durable contract docs が planning artifact から参照可能 | `satisfied` | `docs/TRACEABILITY_MATRIX_0_8.md` が contract docs と review docs を docs evidence に接続している |

## Strict Verdict

`still planning-only`

## Distance Moved Since 0.3

- strict `gap` row の本数は変わらない
- ただし `reasoning_summary` blocker は `runs.py` が pass-through serializer である点まで sharpen した
- approvals blocker は `list/detail minimum envelope` と `approve / deny redaction exactness` に分解して読めるようになった
- storage blocker は ambiguous local tables の exact list が `users`, `user_identities`, `conversations` に狭まった
- relay blocker は broad ambiguity ではなく boundary / ownership gap として狭まった

## Why The Verdict Still Does Not Move

- strict `gap` row がまだ 1 本残っている
- その 1 本は `reasoning_summary` safe exposure で、producer / sanitizer owner と durable test injection path が閉じていない
- さらに approvals response schema exactness、ambiguous local tables exact class assignment、relay adapter exact interface などの `GAP` / `UNRESOLVED` が残っている
- `docs/EXECUTION_GATE_MEMO_0_2.md` の前提上、execution gate は別判定でしか開かない

## Exact Remaining Blockers

- `docs/TRACEABILITY_MATRIX_0_8.md`
  - `GET /v1/runs/{run_id}/events`: `reasoning_summary` safe exposure
- `docs/APPROVALS_RESPONSE_SHAPE_REVIEW_0_1.md`
  - `GAP`: approvals response schema
  - `GAP`: approve / deny response redaction exactness
- `docs/STORAGE_TABLE_CLASS_ASSIGNMENT_0_1.md`
  - `GAP`: ambiguous local tables exact class assignment
  - `UNRESOLVED`: final storage decomposition
- `docs/RELAY_INTERFACE_REVIEW_0_1.md`
  - `UNRESOLVED`: relay adapter exact interface
  - `UNRESOLVED`: `public_url_file` lifecycle contractization
- `docs/REASONING_SUMMARY_OWNER_REVIEW_0_1.md`
  - `UNRESOLVED`: `reasoning_summary` producer owner
  - `UNRESOLVED`: server-side sanitizer / validator owner

## Bottom Line

- planning exit は 0.3 より少しだけ sharper
- ただし strict verdict は変わらない
- current state は `still planning-only`
