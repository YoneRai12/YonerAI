# Public Security Review Checkpoint

- last_scan_at: 2026-06-19T15:46:43Z
- highest_seen_pr_number: 557
- current_main_head: b745e304
- latest_stable: v0.8.1
- latest_prerelease: v0.22.0-alpha.1
- lane: Public YonerAI security/status gate before realtime sync

## Scan Surfaces

Checked in this checkpoint:

- Open PR list up to #557.
- PR #551 final post-push review/comments/checks before confirming merge state.
- PR #553 review blocker resolution and merged state.
- Issue #549 status coordination comments.
- Issue #552 realtime sync coordination comments.
- Security-adjacent open PRs #556, #555, #554, #543, #542, #541, #540, #539,
- #557 canonical replacement PR, and #521.

## Decisions

| PR / issue | updated_at evidence | classification | review/comment state | CI state | decision |
| --- | --- | --- | --- | --- | --- |
| #551 | 2026-06-19T06:43:08Z | valid-but-already-fixed | No new blocker after final push; merged | all pass on final head | StatusWEB scope closed on main. |
| #553 | merged before this checkpoint | valid-but-already-fixed | `localhost` private-host finding fixed | all pass | Public CLI StatusSnapshot blocker closed. |
| #557 | 2026-06-19T14:06:53Z | valid-now | Gemini readability and Codex P1 comments valid and fixed | pending | Canonical replacement PR; fixed account sanitizer ordering and top-level comment intake. |
| #556 | 2026-06-19T07:23:27Z | valid-now | Gemini test/normalization robustness comment valid | security-static failed on PR branch | Consolidated into current branch with stronger key normalization and redacted test failures. |
| #555 | 2026-06-19T07:04:53Z | valid-now | Gemini server cleanup comment valid | pass but behind | Consolidated into current branch with redirect rejection and explicit server close. |
| #554 | 2026-06-19T06:37:37Z | valid-now | Gemini no-comment review | pass but behind | Consolidated into current security intake branch. |
| #543 | 2026-06-18T04:34:59Z | valid-now | Gemini no-comment review | pass but behind | Consolidated into current security intake branch. |
| #542 | 2026-06-18T04:30:54Z | valid-now | Gemini regex precision comment valid | pass but behind | Consolidated into current security intake branch with stricter regex. |
| #541 | 2026-06-18T04:32:17Z | duplicate | Same local LLM proxy family | not revalidated here | Superseded by #543/current branch. |
| #540 | 2026-06-18T04:33:12Z | duplicate | Same local LLM proxy family | not revalidated here | Superseded by #543/current branch. |
| #539 | 2026-06-18T04:32:37Z | valid-now | Gemini private-IP marker comment valid | pass but behind | Consolidated into current branch with private URL regex. |
| #521 | 2026-06-10T03:26:21Z | valid-but-already-fixed | Gemini minor cleanup only | old pass | Current main already requires validated `account_me.ok`. |
| #549 | latest comments checked | owner-only-blocker | Status/Public comments present | not a CI surface | Do not close until exact final ACK policy is satisfied. |
| #552 | latest comments checked | deferred-with-tracked-issue | Sync contract pending | not a CI surface | Start only after security/status gates are clear. |

## Replacement PR / Tracking

- Current replacement branch: `codex/security-intake-gate-20260619`
- Replacement PR: #557
- Tracking document: `docs/security/SECURITY_PR_INTAKE_2026-06.md`

## Remaining Non-Blocking Debt

- Dependency PRs remain open and tracked by their own PRs.
- UX/theme/language PRs remain open and tracked by their own PRs.
- Managed Cloud / production-adjacent PRs require explicit owner approval.
## 2026-06-20 Follow-up Checkpoint

- last_scan_at: 2026-06-19T15:46:43Z
- current_main_head: b745e304
- branch: codex/fix-post-merge-intake-auth-errors-20260620
- follow-up PR: #558
- classification: valid-now follow-up for merged PR #557 review/CI activity
- review/comment state: merged PR #557 retained a P2 auth-error handling thread; post-merge issue_comment triggered review-intake-required failure.
- CI state: product checks on #557 final head were passing before merge; review-intake-required failed after merge because label mutation was attempted on closed/merged PR activity.
- decision: fix current main with PR #558; add regressions for auth guidance preservation, closed/merged PR intake skip, and fail-closed intake marking that can be cleared by the maintainer-controlled `intake-reviewed` label after classification.
- lane boundary: Public/Status presentation support only; no production deploy, no Web chat, no Firestore listener, no provider consent/control, no quota mutation, no approval control.

## 2026-06-20 PR #558 Bootstrap Follow-up

- last_scan_at: 2026-06-20T02:20:00+09:00
- current_main_head: b745e304
- follow-up PR: #558
- classification: valid-now
- review/comment state: Gemini and Codex both flagged 401/403 sanitizer ordering; current PR branch handles 401/403 before path-specific payload sanitizers. Codex usage-limit comment was non-material.
- CI state: product checks passed; `review-intake-required` failed because the PR updates the same `pull_request_target` workflow that is required before merge.
- decision: keep the gate fail-closed for new review/comment/synchronize activity, handle label-write failures as controlled failures instead of unhandled exceptions, and allow a later maintainer `intake-reviewed` label event to clear the required check.
- replacement PR or tracking issue: #558 remains the canonical current-main fix for this bootstrap/process issue.
