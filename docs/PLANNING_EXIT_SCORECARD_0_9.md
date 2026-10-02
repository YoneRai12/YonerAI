# Planning Exit Scorecard 0.9

Status:

- planning gate artifact
- strict scoring only
- validation fallout refresh applied
- basis:
  - `docs/VALIDATION_OUTCOME_0_1.md`
  - `docs/AUTH_PRECEDENCE_FAILURE_REVIEW_0_1.md`
  - `docs/META_EXPOSURE_FAILURE_REVIEW_0_1.md`
  - `docs/BOUNDED_REPAIR_CANDIDATE_0_1.md`
  - `docs/TRACEABILITY_MATRIX_0_13.md`
  - `docs/CURRENT_PHASE_CONTEXT.md`

## Scorecard

| Planning-exit criterion | Status | Basis |
| --- | --- | --- |
| `docs/V76_TRUTH_SYNC_PACKET_JP.md` と planning packet に矛盾がない | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| shared run contract 3 endpoint が docs 上で一意に読める | `satisfied` | `docs/contracts/external-agent-api.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| auth precedence / SSE terminal rule / file-ref-only / files boundary が docs 上で一意に読める | `satisfied` | `docs/contracts/external-agent-api.md`, `docs/contracts/sse-run-events.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| docs / tests / code の traceability が十分に埋まっている | `blocked` | `docs/TRACEABILITY_MATRIX_0_13.md` で concrete failing rows が残る。auth precedence と meta exposure は validation 実行まで到達したが未修復。`reasoning_summary safe exposure` も `partial` のまま |
| code 着手条件 / 停止条件 / readiness judgment 条件が memo 化されている | `satisfied` | `docs/BOUNDED_REPAIR_CANDIDATE_0_1.md` |
| freeze / no-go list に例外がない | `satisfied` | `docs/CURRENT_PHASE_CONTEXT.md` |
| execution reservation が reservation としてのみ保持されている | `satisfied` | `docs/CURRENT_PHASE_CONTEXT.md`, `docs/BOUNDED_REPAIR_CANDIDATE_0_1.md` |
| durable contract docs が planning artifact から参照可能 | `satisfied` | `docs/TRACEABILITY_MATRIX_0_13.md` |

## Strict Verdict

`still planning-only`

## Latest Re-Score

- narrow validation is no longer env-only blocked
- accepted target pytest now returns `2 failed, 14 passed`
- current active blockers are concrete behavioral failures, not dependency import failure

## Next Move Decision

`bounded repair candidate justified`

## Why

- the two current failures map plausibly to narrow owner files:
  - auth precedence -> `core/src/ora_core/api/routes/messages.py`
  - meta exposure -> `core/src/ora_core/api/routes/runs.py`
- the smallest plausible repair scope stays within 3 files including tests
- broader execution is still not justified because:
  - current work is not yet repaired
  - `reasoning_summary safe exposure` remains only `partial`
  - no code work is auto-authorized by this scorecard

## Bottom Line

- strict verdict remains `still planning-only`
- next move is a bounded repair candidate, not broader execution
- any code repair still requires explicit approval
