# Planning Exit Scorecard 0.5

Status:

- planning gate artifact
- strict scoring only
- basis:
  - `docs/PLANNING_PACKET_0_2.md`
  - `docs/TRACEABILITY_MATRIX_0_9.md`
  - `docs/TEST_GAP_REGISTER_0_4.md`
  - `docs/EXECUTION_GATE_CANDIDATE_0_1.md`
  - `docs/TRACK_A_MICRO_EXECUTION_SCOPE_0_1.md`
  - `docs/NON_GATING_GAPS_REGISTER_0_1.md`

## Scorecard

| Planning-exit criterion | Status | Basis |
| --- | --- | --- |
| `docs/V76_TRUTH_SYNC_PACKET_JP.md` と planning packet に矛盾がない | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| shared run contract 3 endpoint が docs 上で一意に読める | `satisfied` | `docs/PLANNING_PACKET_0_2.md`, `docs/contracts/external-agent-api.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| auth precedence / SSE terminal rule / file-ref-only / files boundary が docs 上で一意に読める | `satisfied` | `docs/contracts/external-agent-api.md`, `docs/contracts/sse-run-events.md`, `docs/contracts/file-download-boundary.md`, `docs/CURRENT_PHASE_CONTEXT.md` |
| docs / tests / code の traceability が十分に埋まっている | `blocked` | `docs/TRACEABILITY_MATRIX_0_9.md` に strict `gap` が残る。exact blocker row: `GET /v1/runs/{run_id}/events`: `reasoning_summary` safe exposure。補助根拠: `docs/REASONING_SUMMARY_OWNER_REVIEW_0_1.md`, `docs/EXECUTION_GATE_CANDIDATE_0_1.md` |
| code 着手条件 / 停止条件 / readiness judgment 条件が memo 化されている | `satisfied` | `docs/TRACK_A_MICRO_EXECUTION_SCOPE_0_1.md` が candidate scope / stop conditions を狭く定義している |
| freeze / no-go list に例外がない | `satisfied` | `docs/CURRENT_PHASE_CONTEXT.md` |
| execution reservation が reservation としてのみ保持されている | `satisfied` | `docs/EXECUTION_GATE_CANDIDATE_0_1.md`, `docs/TRACK_A_MICRO_EXECUTION_SCOPE_0_1.md` |
| durable contract docs が planning artifact から参照可能 | `satisfied` | `docs/TRACEABILITY_MATRIX_0_9.md` が contract docs と review docs を docs evidence に接続している |

## Strict Verdict

`still planning-only`

## Distance Moved Since 0.4

- row status の upgrade は行っていない
- ただし remaining work は `must-close-before-execution` / `closable-during-execution` / `non-gating partials` に分解された
- `reasoning_summary` blocker は inspected `core/src/ora_core` で emit / write site が見つからない点まで sharpen した
- future Track A の dormant file set と stop conditions は docs 上で固定した

## Why The Verdict Still Does Not Move

- strict `gap` row が canonical `GET /v1/runs/{run_id}/events` に残っている
- `TEST_GAP_REGISTER_0_4.md` 上では `reasoning_summary` row は `execution-gate-blocked` だが、
  それは「docs-only では閉じない」という意味であり、
  直ちに narrow execution entry が ready だという意味ではない
- current docs-only packet では `reasoning_summary` の exact code-side owner を single-file scope まで固定できていない
- したがって、Track A micro-scope は dormant candidate までで止まり、gate opening までは正当化されない
- approvals / storage / relay の open gaps は non-gating だが、今回 verdict を動かす材料にもなっていない

## Execution Gate Candidate Note

- execution gate candidate decision も `still planning-only`
- Track A micro-scope は plausible だが、未 authorization
- next batch で narrow execution を再評価するには、
  `reasoning_summary` safe exposure の exact code-side owner を single-file scope で示す必要がある

## Exact Remaining Blockers

- `docs/TRACEABILITY_MATRIX_0_9.md`
  - `GET /v1/runs/{run_id}/events`: `reasoning_summary` safe exposure
- `docs/REASONING_SUMMARY_OWNER_REVIEW_0_1.md`
  - `UNRESOLVED`: `reasoning_summary` producer owner
  - `UNRESOLVED`: server-side sanitizer / validator owner
  - `GAP`: durable negative test injection path without source change
- `docs/NON_GATING_GAPS_REGISTER_0_1.md`
  - approvals response schema
  - approve / deny response redaction exactness
  - ambiguous local tables exact class assignment
  - final storage decomposition
  - relay adapter exact interface
  - `public_url_file` lifecycle contractization

## Bottom Line

- planning exit はまだ未達
- narrow execution gate もこの batch では開かない
- current strict state は `still planning-only`
