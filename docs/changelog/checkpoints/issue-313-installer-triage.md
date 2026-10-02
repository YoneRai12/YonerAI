# Issue #313 installer bootstrap triage

Date: 2026-05-22

Issue: https://github.com/YoneRai12/YonerAI/issues/313

## Decision

Keep Issue #313 open as the installer bootstrap tracking issue.

The manifest-first definition is partly complete, but the issue still contains
implementation work that is not represented as finished elsewhere. Closing it
now would make the remaining installer/bootstrap work harder to audit.

## Completed or effectively completed

- Manifest schema: completed in PR #307 via `releases/manifest.schema.json`.
- Manifest example: completed in PR #307 via `releases/manifest.example.json`.
- Manifest verification: completed in PR #309 via local-only
  `yonerai manifest verify`.
- Doctor diagnostics: completed in PR #309 and improved in PR #311 via
  `yonerai doctor`.
- Release artifact naming policy: documented in PR #307 via
  `docs/tasks/installer-distribution.md`.
- Dry-run Windows install planning: completed in PR #320 via
  `yonerai install plan-windows` and
  `scripts/install/plan_windows_install.ps1`.

## Partially complete

- PowerShell installer policy: policy and dry-run planning exist, but a real
  installer skeleton, rollback behavior, and production signature verification
  are not implemented.
- Unified `yonerai install` flow: the dry-run Windows planner exists, but
  install/update command coverage is still incomplete.
- Install docs: alpha dry-run docs exist, but production-safe install,
  rollback, uninstall, and public install-page docs remain incomplete.

## Remaining work

- Implement a safe PowerShell installer skeleton without remote execution.
- Implement production signed manifest verification against an explicit trust
  source.
- Add `yonerai install` and `yonerai update` dry-run planning commands that
  consume the same manifest.
- Validate release artifact asset naming and manifest-to-asset consistency in
  tests/release checks.
- Write safe install, rollback, and uninstall documentation for the future
  `yonerai.com/install` path.
- Keep npm, winget, production signing keys, production trust stores, and
  network-executing installers out of scope until those gates are proven.

## Follow-up issue policy

Issue #313 should remain open until the remaining implementation items are
either completed or split into linked child issues. If child issues are created,
this issue may be closed as "definition complete" only after those links are
recorded in the issue thread.

## Boundary confirmation

This triage does not add installer execution, remote download, PATH mutation,
package installation, production signing material, production trust stores,
Oracle control-plane behavior, live Discord, telemetry ingestion, or provider
API key handling.
