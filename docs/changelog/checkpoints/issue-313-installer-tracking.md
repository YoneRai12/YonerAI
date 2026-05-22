# Issue #313 installer tracking checkpoint

Date: 2026-05-22

## Decision

Issue #313 remains open as the parent tracking issue for the manifest-first
installer bootstrap system.

The issue is no longer treated as a loose definition note. Completed work is
listed with PR references, and remaining implementation/docs work is split into
child issues so the parent can track progress without hiding unfinished
installer blockers.

## Completed or substantially completed

- Manifest schema: PR #307, `releases/manifest.schema.json`.
- Manifest example: PR #307, `releases/manifest.example.json`.
- Local manifest verification: PR #309, `yonerai manifest verify`.
- Doctor diagnostics: PR #309 and PR #311, `yonerai doctor`.
- Installer distribution foundation doc: PR #307,
  `docs/tasks/installer-distribution.md`.
- Windows dry-run planning foundation: PR #320,
  `yonerai install plan-windows`.
- Release artifact naming validation foundation: PR #326.

## Remaining child issues

- #328 `feat: implement signed manifest verification`.
- #329 `feat: add yonerai install/update dry-run commands`.
- #330 `feat: add PowerShell dry-run installer skeleton`.
- #331 `docs: define safe install and uninstall flow`.
- #332 `feat: validate release artifact hashes and naming`.
- #333 `docs: define installer signing and key rotation lifecycle`.
- #334 `docs: prepare install.yonerai.com onboarding page`.

## Parent issue handling

Issue #313 should stay open until the remaining child issues are complete or
the owner explicitly approves closing it as a completed parent index.

The parent body/comment should state:

- #313 is the canonical installer/bootstrap parent tracker.
- Alpha2 includes local manifest verification, doctor diagnostics, artifact
  naming validation foundation, and Windows dry-run planning only.
- No production installer, signed production manifest verification, npm/winget
  distribution, or install page is complete.

## Boundary confirmation

This checkpoint does not add a network installer, `irm ... | iex`, remote
download, remote execution, PATH mutation, package installation, production
signing key, production trust store, deploy, Oracle connection, live Discord
connection, Google login, production DB behavior, telemetry ingestion, or
private runtime detail.

`reference_clawdbot` is not touched. `src/cogs/ora.py` remains unresolved and
is not part of this installer tracking checkpoint.
