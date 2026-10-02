# Release Date Hygiene Policy

Status: historical policy, superseded for future work by `docs/process/YONERAI_RELEASE_GOVERNANCE.md`. This policy does not delete, retag, or rewrite any existing release.

## Superseded Direction

The date-suffix checkpoint release practice is frozen for future routine Codex work. GitHub Releases are now reserved for runnable user-visible public milestones. Internal checkpoints should be written under `docs/changelog/checkpoints/`, not published as GitHub Releases.

## Purpose

YonerAI checkpoint labels should be useful to users reading the public GitHub surface. A release name must not imply that the repository is ahead of the verified calendar date, production-ready, or complete.

## Date Source

Before creating any future runnable release candidate:

- verify the local date and UTC date;
- use the owner-intended current date when the owner explicitly states it;
- treat future-dated labels as a release hygiene issue, not as the current public truth;
- record any drift in the PR or release note.

For the historical cleanup lane that created this file, the verified date was 2026-05-20.

## Version Format

Do not use this historical date-suffix policy for new internal checkpoints. The next public GitHub Release should use semantic pre-release versioning such as `v0.1.0-alpha.1`, unless the owner explicitly overrides it for a runnable milestone.

## GitHub Releases

GitHub Releases should not be created for internal checkpoints, docs-only/process-only updates, ledgers, root inventory, or PR-count reconciliation. A markdown checkpoint note alone is enough for internal progress.

Release titles must be product-facing:

- use checkpoint capability names;
- do not lead with PR numbers;
- include PR numbers only in a late `Traceability` section when useful.

## Existing Future-Dated Labels

If a future-dated tag or GitHub Release already exists:

- do not delete it;
- do not retag it;
- do not rewrite history;
- create a corrected current-date release only when the target commit is verified and no tag conflict exists;
- avoid treating the future-dated release as the public latest checkpoint in README-first-screen surfaces.

## Non-Claims

Release hygiene does not claim:

- production readiness;
- shipping completeness;
- official cloud completion;
- live operations completion;
- full product completion;
- hybrid completion;
- persistent memory completion;
- Google login completion;
- Discord gateway completion;
- provider ecosystem completion.
