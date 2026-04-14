# Current Phase Context

Status:

- volatile current-phase doc
- truth sync = `MATCH`
- phase sync = `MATCH`
- planning gate = `OPEN`
- execution gate = `CLOSED`
- broader execution = `not justified`
- this file is allowed to change by phase

## Current Anchor / Fixed Anchor

- current anchor = `v7.6`
- fixed anchor = `Internal Run API v0.1`
- planning packet anchor = `docs/PLANNING_PACKET_0_2.md`
- current traceability anchor = `docs/TRACEABILITY_MATRIX_0_16.md`
- current scorecard anchor = `docs/PLANNING_EXIT_SCORECARD_0_12.md`

## Current Lane

- lane = `Distribution Node MVP` only
- current work is final acceptance refresh, readiness judgment, and Pass 2 readiness decision packaging
- current branch is a safe pause point, not completion

## Current Branch Handling

- exact current branch ref = `refs/heads/codex/model-gpt-5-4`
- do not switch branches without explicit approval
- if exact ref is not `codex/model-gpt-5-4` or `refs/heads/codex/model-gpt-5-4`, stop and report before editing
- keep-set branch = `yes`

## Current Gate State

- planning gate = `OPEN`
- execution gate = `CLOSED`
- strict verdict = `still planning-only`
- broader execution = `not justified`
- next move after this docs batch = readiness judgment / Pass 2 decision package
- broader execution gate is still not open
- Pass 2 setup is still out of scope

## Freeze / No-Go

### Freeze

- `src/cogs/ora.py`
- reject 済み事項

### No-Go

- dirty band0 clamp reopen
- route policy widening
- run API に raw bytes を戻すこと
- Oracle-host / control-plane 依存を public relay / public contract に直接混ぜること
- approvals / operator / admin surface を canonical 3 endpoint contract に取り込むこと
- high-risk capability を MVP に再導入すること
- Pass 2 実施
- repo 実移動
- full product completion claim

## Canonical 3 Endpoint Contract

current phase で固定する shared run contract は次のみ。

1. `POST /v1/messages`
2. `GET /v1/runs/{run_id}/events`
3. `POST /v1/runs/{run_id}/results`

固定 truth:

- contract widening はしない
- `POST /v1/messages` は canonical message submission 入口
- `GET /v1/runs/{run_id}/events` は canonical authenticated SSE event stream
- `POST /v1/runs/{run_id}/results` は canonical authenticated continuation result 入口
- continuation-only。`tool_call_id` なし result は reject

## Fixed Shared-Contract Truth

- auth 済み user があれば auth identity が authoritative
- body の `user_identity` は auth identity を上書きしない
- SSE terminal event は `final` または `error` のどちらか 1 回だけ
- run API = file-ref-only
- files boundary = `short-lived URL / owner-scope / Cache-Control: no-store / audit`
- arbitrary shell / arbitrary SQL / arbitrary file write / high-risk control-plane execution は MVP 非対象
- approvals / operator / admin surface は canonical 3 endpoint contract に入れない

## Latest Validation Snapshot

- full post-repair validation snapshot:
  - `python -m compileall src core/src` = pass
  - `pytest tests/test_distribution_node_mvp.py -q` = pass
  - `pytest tests/test_external_agent_api.py -q` = pass
  - `pytest tests/test_distribution_migration_contract.py -q` = pass
  - `pytest tests/test_approvals_api.py -q` = pass

## Current Blocker Summary

- current validation blocker = `none active`
- `POST /v1/messages` auth precedence row is no longer a current blocker
- `GET /v1/runs/{run_id}/events` meta exposure row is no longer a current blocker
- approvals dedicated-handle row is no longer a current blocker
- `GET /v1/runs/{run_id}/events`: `reasoning_summary safe exposure`
  - remains `partial`
  - serializer-boundary sanitization evidence exists in `core/src/ora_core/api/routes/runs.py`
  - durable negative test evidence exists in `tests/test_distribution_node_mvp.py`
  - not confirmed because:
    - producer owner = `UNRESOLVED`
    - payload schema exactness = `UNRESOLVED`

## Current Validation State

- full validation bundle now passes
- active validation blocker = `none`
- latest warnings are non-current-batch blockers unless later evidence proves otherwise
- broader execution remains not justified

## Current Readiness Posture

- readiness judgment package is now supportable
- Pass 2 is not approved
- current Pass 2 decision posture:
  - `not yet, additional bounded work required before decision`

## Non-Gating Open Gaps

- approvals response schema
- approve / deny response redaction exactness
- ambiguous local tables exact class assignment
- final storage decomposition
- relay adapter exact interface
- `public_url_file` lifecycle contractization

## Not Yet Allowed

- source code changes in this docs batch
- tests run in this docs batch
- env changes in this docs batch
- git commands
- branch switch
- stage / commit
- execution broadening
- Pass 2 setup
- `src/web/endpoints.py` edit
- `src/storage.py` edit
- `src/cogs/tools/tool_handler.py` edit
- private runtime exactness や Oracle-host-only internals を public contract に昇格させること
- raw chain-of-thought を SSE で露出すること

## How To Recover After Compression

1. `AGENTS.md` を再読する
2. `docs/CURRENT_PHASE_CONTEXT.md` を再読する
3. latest traceability matrix を再読する
   - current latest = `docs/TRACEABILITY_MATRIX_0_16.md`
4. latest scorecard を再読する
   - current latest = `docs/PLANNING_EXIT_SCORECARD_0_12.md`
5. `docs/FINAL_VALIDATION_SNAPSHOT_0_1.md` を再読する
6. `docs/READINESS_JUDGMENT_0_1.md` と `docs/PASS2_READINESS_DECISION_0_1.md` を再読する
7. 足りない exactness は `GAP` / `UNRESOLVED` として止める
