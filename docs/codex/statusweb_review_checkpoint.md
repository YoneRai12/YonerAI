# StatusWEB review checkpoint

last_scan_at: 2026-06-19T06:28:21Z
highest_seen_pr_number: 553
lane: StatusWEB
scope: status.yonerai.com public status presentation only

## PR #551 - status: StatusSnapshot v1連携を追加

- url: https://github.com/YoneRai12/YonerAI/pull/551
- updated_at: 2026-06-18T23:42:22Z at checkpoint start
- head_before_fix: 1b37fb175adbfd65e1df805c1dbc88d0e4b52ac6
- classification: StatusWEB current-lane PR
- review/comment state:
  - valid-now P1/security: discussion_r3439493207 public feed safety must block private/account/runtime identity keys
  - valid-now P1/security: discussion_r3439493208 healthcheck collector must not copy raw healthcheck URLs/errors into public details
  - valid-now P2: discussion_r3439467470 localized shells must preserve runtime anchors
  - valid-now P2: discussion_r3439467474 null incident_id must be omitted from feeds
  - valid-now P2: discussion_r3439467478 incident back links must fall back to affected route metadata
  - valid-now P2/privacy: discussion_r3439493211 public package manifest must not contain local absolute source_root
  - valid-now P2: discussion_r3439493212 snapshot incident_ref must propagate into source day incident_id when present
  - valid-but-already-fixed: discussion_r3439442977, discussion_r3439442979, discussion_r3439444408, discussion_r3439444413, discussion_r3439444416, discussion_r3439444421, discussion_r3439444423
- CI state: previous head all checks success; branch was BEHIND base before this fix commit
- decision: fix valid-now findings in current StatusWEB branch, validate, push, reread reviews after final push, then merge only if clean
- replacement PR or tracking issue: PR #551 remains canonical StatusWEB PR; issue #549 remains coordination ledger

## PR #553 - fix: StatusSnapshotレビュー指摘を安全側に修正

- url: https://github.com/YoneRai12/YonerAI/pull/553
- updated_at: 2026-06-19T06:26:45Z during checkpoint
- classification: out-of-lane Public CLI/status PR, not StatusWEB implementation
- review/comment state: previous Public CLI P1/security findings from PR #550 are being handled here; latest head still open/BLOCKED during scan because checks/review state were not fully settled
- CI state: most checks success, build-and-test was in progress at checkpoint scan
- decision: owner/Public lane must finish/merge #553 before Public CLI/status release surface; not a StatusWEB #551 code blocker unless files overlap or schema changes
- replacement PR or tracking issue: PR #553 is canonical Public CLI follow-up

## PR #550 - feat: StatusSnapshot v1 public clientを追加

- url: https://github.com/YoneRai12/YonerAI/pull/550
- merged_at: 2026-06-18T23:22:23Z
- classification: merged Public CLI/status PR reviewed for residual comments
- review/comment state:
  - P1/P2/security comments are out-of-lane for StatusWEB and are addressed by PR #553, pending #553 final merge
  - older Gemini comments on explicit :443 and whitespace are valid-but-already-fixed inside #550
- CI state: merged after CI success
- decision: do not edit Public CLI from StatusWEB lane; track #553 as Public owner action
- replacement PR or tracking issue: PR #553

## Issue #549 - StatusSnapshot coordination ledger

- url: https://github.com/YoneRai12/YonerAI/issues/549
- updated_at: 2026-06-19 checkpoint
- classification: active cross-lane coordination issue
- review/comment state:
  - older StatusWEB final ACK and scope-closed comments are stale because later #551 review added valid P1/P2 findings
  - AWS/Public context remains public-safe input for StatusWEB rendering
- CI state: not applicable
- decision: post fresh final evidence after #551 final push, post-push review scan, CI/browser validation, and merge
- replacement PR or tracking issue: PR #551 for StatusWEB; PR #553 for Public CLI follow-up

## Non-overlapping open PRs

- PRs #548, #547, #545, #539, #523, #521, #413, #412, #411, #410, #156, #151, #148 were visible in open PR listing.
- classification: non-overlapping or dependency/older lane PRs for this StatusWEB checkpoint.
- decision: do not repeatedly rescan unchanged PRs unless their files overlap StatusWEB or a P0/P1/security issue affecting current main appears.

## Current blocker disposition

- current StatusWEB P0/P1/security: valid-now findings on #551 are being fixed in this checkpoint.
- out-of-lane Public CLI P1/security: PR #553 must be handled by Public lane/owner before Public CLI/status release surface; recorded here but not edited from StatusWEB.
- owner-only blocker: production deploy remains not approved and is not attempted.

## Validation evidence - 2026-06-19T06:31:33Z

- fixture snapshot validation: PASS
- fixture snapshot pipeline: PASS
- generated feed validation: PASS
- generated public feed safety: PASS
- public feed sync route: PASS
- public package build: PASS
- healthcheck collector: PASS
- healthcheck bridge: PASS
- browser acceptance desktop/mobile/reduced-motion/keyboard/no-color-only: PASS
- touch probe: PASS
- live AWS canonical public_status snapshot consumed: PASS
- live snapshot_id: sts_03cbe305aaa845cb6f15
- live provider_gateway: operational/available
- live official_execution_worker: offline/unavailable/stale=true
- live realtime_sync: degraded/limited/preview
- negative safety account_id/worker_identity: PASS, rejected
- negative safety file-url/internal-hostname: PASS, rejected
- generated feed/package secret/local-path/mojibake scan: PASS
- git diff --check for StatusWEB/doc checkpoint paths: PASS

## Phase checkpoint

[PHASE-CHECKPOINT]
- phase: review-fix-validation-before-push
- quota: no explicit quota value exposed in this environment
- decision: P1/security StatusWEB findings are fixed locally; proceed to commit/push and post-push reread.

## Post-push review intake - 2026-06-19T06:38:06Z

- PR #551 push head before additional review fixes: 3bf1df35cdc5ebe73dcdbcd71c15b3c6baa97266
- GitHub CI on that head: all required checks PASS
- Newly discovered active review threads after final push:
  - discussion_r3440679735 P2: incident detail panel must add is-visible before append
  - discussion_r3440679736 P2: adapter must honor per-day days[].color overrides
- classification: valid-now P2, current StatusWEB lane
- decision: fix in mock-status-adapter.js, add targeted browser probe evidence, push again, reread comments again.

## Additional validation evidence - 2026-06-19T06:38:06Z

- status-feed.scenarios.example.json validation: PASS
- browser acceptance on live generated feed snapshot_id sts_03cbe305aaa845cb6f15: PASS
- touch probe on live generated feed: PASS
- targeted Playwright incident/color probe: PASS
  - #incident/inc-1 rendered #incidentDetailPanel.is-visible
  - incident panel computed opacity: 1
  - day color override #123456 reached bar CSS/background color
- git diff --check for mock-status-adapter.js: PASS

[PHASE-CHECKPOINT]
- phase: post-push-review-fix-before-second-push
- quota: no explicit quota value exposed in this environment
- decision: commit/push the two valid P2 fixes, then reread review/CI before merge.

## PR #556 - fix: block camelCase status feed secret keys

- url: https://github.com/YoneRai12/YonerAI/pull/556
- updated_at: 2026-06-19T07:08:19Z during checkpoint
- classification: StatusWEB current-lane public feed safety PR
- review/comment state:
  - valid-now security: discussion_r3440920624 key normalization must collapse repeated underscores, hyphens, and spaces before sensitive-key matching
  - valid-now P2/privacy-test: discussion_r3440920616 temp feed test must clean up temporary files and include redacted stdout/stderr if rejection unexpectedly passes
  - non-material: Codex usage-limit PR comment has no code action
- CI state: security-static failed on test literal wording before this fix; other checks were passing
- decision: fix current PR, run targeted safety tests and security scan locally, push, then reread PR reviews/comments/checks before any final report
- replacement PR or tracking issue: PR #556 remains canonical StatusWEB safety follow-up

[PHASE-CHECKPOINT]
- phase: pr-556-review-fix-before-validation
- quota: no explicit quota value exposed in this environment
- decision: valid StatusWEB safety findings are fixed locally in isolated worktree; proceed to validation.
