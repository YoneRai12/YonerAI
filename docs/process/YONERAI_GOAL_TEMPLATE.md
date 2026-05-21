# YonerAI Goal Template

Use this file to replace huge repeated prompts with short `/goal` prompts that reference repository workflow docs.

## A. Implementation Goal Template

```text
/goal Complete <one durable objective> for YonerAI v7.7.
Read first: AGENTS.md and docs/process/YONERAI_CODEX_WORKFLOW.md.
Lane: <security/runtime | API | CLI | Web | Discord contract | ora extraction | release | process>.
Verify current main, latest release, open PRs, and relevant lane docs before editing.
Forbidden: secrets, live Discord, deploy, production signing/trust stores, persistent memory, Google login, production DB, reference_clawdbot, broad ORA rename, v7.8 claims.
Validation: use docs/process/YONERAI_VALIDATION_MATRIX.md for touched paths.
Stop when: <verifiable end state>, validation passes, PR merges, or a stop condition in docs/process/YONERAI_STOP_CONDITIONS.md is hit.
Final report: Japanese, exact PRs/commits/tests/scans/non-claims/blockers/next goal.
```

## B. Security / Runtime Patch Template

```text
Objective: reproduce and patch <issue/old PR> on current main.
Steps:
1. Inspect old PR title/body/diff/reviews.
2. Verify affected path exists on current main.
3. Reproduce safely or prove superseded.
4. Create a fresh narrow current-main patch.
5. Add regression tests.
6. Run targeted validation and public smoke where relevant.
7. Close old PR only with replacement evidence.
Do not merge stale PRs blindly.
```

## C. `src/cogs/ora.py` Extraction Template

```text
Objective: make one behavior-preserving ORA extraction step.
Rules:
- characterization tests first
- one pure helper or one clearly bounded seam only
- no broad rename
- no live Discord/provider/memory changes
- no private runtime truth
- no reference_clawdbot changes
Stop if import side effects, BOM/encoding, or private-runtime coupling make behavior preservation unclear.
```

## D. Discord Hybrid Contract Template

```text
Objective: advance Discord restoration through synthetic contracts only.
Rules:
- no live Discord token
- no live connection
- private gateway is canonical production responder
- public PythonBot / ORA residue must not become simultaneous responder
- test duplicate responder denial
- test terminal final once-only
- test same-message edit flow
- test controlled error shape
- test files/download contract without arbitrary external URL download
- record synthetic vs live evidence gap
```

## E. Release Checkpoint Template

```text
Objective: publish a release checkpoint after meaningful implementation/test PRs.
Rules:
- use current verified date
- same-day suffix: vYYYY.M.D, vYYYY.M.D.1, vYYYY.M.D.2, ...
- no future dates
- no delete/retag
- product-facing title
- body sections: Summary, Implemented, Security and boundary, Tests, Not included, Still open, Traceability
- state clearly: not production, not full product, not Discord restored, not src/cogs/ora.py solved, not v7.8
```
