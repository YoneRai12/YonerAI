# YonerAI Release Governance

Status: active release policy for the public repository.

## Purpose

YonerAI GitHub Releases must describe user-visible runnable software milestones. They are not the storage location for Codex checkpoints, process ledgers, PR logs, root inventory notes, or internal progress snapshots.

## Release Freeze For Checkpoints

- Do not create a GitHub Release for docs-only, process-only, ledger-only, checkpoint-only, root-inventory-only, or PR-count reconciliation work.
- Do not create a GitHub Release for every PR.
- Do not create date-suffix checkpoint releases such as `vYYYY.M.D.N` unless the owner explicitly overrides this policy for a specific public milestone.
- Do not create a tag just to mark an internal checkpoint.
- Do not delete, retag, or rewrite historical releases. Existing rapid date releases remain historical artifacts.

## Checkpoint Storage

Future internal checkpoints belong in markdown under:

- `docs/changelog/checkpoints/` for chronological implementation and maintenance checkpoints.
- `docs/checkpoints/` only when a short-lived compatibility link is needed.

Existing files under `docs/releases/` remain as historical release/checkpoint archive material. Do not mass-move them in routine goals.

## Next Public Release Shape

The next GitHub Release should be a semantic pre-release for a runnable public milestone, likely:

- `v0.1.0-alpha.1`

Use a date-suffix release only when the owner explicitly requests it and the release is a real runnable user-visible milestone.

## Release Candidate Requirements

A release candidate must include:

- runnable user-visible changes, not only governance or checkpoint text;
- install and run instructions;
- public runnable smoke validation;
- CLI smoke validation when CLI behavior is included;
- Web smoke validation when Web behavior is included;
- known limitations;
- explicit not-included claims;
- traceability to merged PRs and commits;
- no known public-facing secret, local path, username, hostname, or mojibake issue in changed public text.

## Release Body Requirements

A GitHub Release body must include:

1. Summary
2. Runnable changes
3. Install / run instructions
4. Validation
5. Known limitations
6. Not included
7. Traceability

## Non-Claims

A release or checkpoint must not claim production readiness, shipping completion, official cloud completion, Discord restoration, Discord gateway completion, persistent memory completion, Google login completion, final Web UI completion, Tools/MCP completion, full hybrid completion, broad ORA rename completion, `src/cogs/ora.py` resolution, or v7.8 start unless a dedicated approved lane proves it.
