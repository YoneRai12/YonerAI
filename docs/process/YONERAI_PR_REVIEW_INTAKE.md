# YonerAI PR Review Intake

This process is a required gate before new Public YonerAI product work. It is
designed to prevent valid security, privacy, CI, and review findings from being
lost after PRs are opened, updated, reviewed, or merged.

## Required Checkpoints

Run a review intake checkpoint:

- at task start
- at every phase boundary
- after every push
- before every merge
- immediately before final reporting

Each checkpoint must inspect:

- newly opened or updated PRs since the previous checkpoint
- review submissions
- inline review threads
- PR conversation comments
- linked issue comments
- failed checks and CI annotations
- relevant comments on recently merged PRs

## Ledger

For Public YonerAI work, update:

- `docs/codex/public_security_review_checkpoint.md`
- `docs/security/SECURITY_PR_INTAKE_2026-06.md` when security/privacy/release
  findings are involved
- `docs/tasks/DEFERRED.md` for non-blocking P2/P3, dependency, or UX debt

The checkpoint must record PR number, update time, classification, review or
comment state, CI state, decision, and replacement PR or tracking issue.

## Classification

Use one of these labels for every new or updated finding:

- `valid-now`
- `valid-but-already-fixed`
- `stale`
- `duplicate`
- `false-positive`
- `deferred-with-tracked-issue`
- `owner-only-blocker`

`valid-now` findings require a current-main fix, a regression test, and relevant
validation before the next product phase.

## Severity Gate

No next product phase may begin with unresolved current P0/P1/security findings.
No release may ship with an unresolved finding that affects that release surface.
P2/P3, dependency, and UX items may be deferred only when they are tracked and do
not affect the active security or release surface.

## Automation

The `YonerAI PR Intake Gate` workflow marks PRs with `needs-intake` when new PR,
review, or comment activity arrives. Maintainers may add `intake-reviewed` only
after the checkpoint is updated and findings are classified.
