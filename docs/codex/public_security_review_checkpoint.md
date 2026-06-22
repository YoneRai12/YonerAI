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

## 2026-06-20 Public Auth / Sync Contract Checkpoint

- last_scan_at: 2026-06-20T05:27:22+09:00
- highest_seen_pr_number: 559
- current_main_head: cce5a8d
- branch: codex/native-run-auth-sync-contract-20260620
- lane: Public auth/session contract, provider gateway contract acceptance, realtime sync proposal

Checked in this checkpoint:

- PR #558 state, comments, inline review comments, reviews, and checks.
- Open PR list after #558 merge.
- Issue #552 comments before publishing `[SYNC-PROPOSAL-V1]`.
- Private AWS public-safe impact notices for staging auth/session and provider gateway contract surfaces.
- Live staging safe-smoke status for `/v1/health`, `/v1/status`, `/v1/capabilities`, `/v1/modules`, and unauthenticated `/v1/runs`.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #558 | valid-but-already-fixed | Gemini/Codex 401/403 sanitizer ordering comments were addressed before merge; Codex usage-limit comment non-material | Final required checks passed; merge commit `cce5a8d` | Complete. No required-check disable/restore was needed. |
| #559 | valid-now | New PR created from this branch; no comments or reviews at creation scan | `review-intake-required` initially failed until maintainer classification label was applied; product checks started passing and remaining checks were pending at scan time | Added `intake-reviewed` after classification. Continue to read comments after each push. |
| #559 Gemini/Codex reviews | valid-now | Gemini flagged empty/non-empty opaque session candidate mismatch and placeholder origin schema mismatch; Codex flagged swapped session handler arguments | Added regression tests and fixed all three findings. | Targeted tests now pass with `133 passed`; rerun CI after push. |
| #558 post-merge Codex P2 | valid-now | Codex flagged unnecessary `pull-requests: write` on `pull_request_target` gate | Current branch changes permission to `pull-requests: read`; label writes still use `issues: write` | Fixed in current follow-up branch with workflow test coverage. |
| Staging auth mismatch | valid-now / owner-only-blocker for backend | Browser login can reach linked state, but poll response has `token_returned=false` and no opaque YonerAI CLI session value | Public CLI cannot authenticate `whoami` or Native Run without a backend-issued opaque session | Public now fails closed as `staging_cli_session_unavailable` or `staging_session_rejected`; AWS must issue an opaque YonerAI staging session separate from Google tokens. |
| #552 AWS auth contract proposal | valid-now | AWS proposed top-level `staging_session_token` and matching `session.staging_session_token` as the only CLI-usable opaque YonerAI session value | Public regression tests accept only those fields, reject mismatch/token-like fields, and never print the value | Posted `[PUBLIC-AUTH-ACK]` at https://github.com/YoneRai12/YonerAI/issues/552#issuecomment-4754475408. |
| Provider Gateway #57-#60 notices | valid-now | AWS contract says canonical paths are `/v1/provider-gateway/status`, `/quota`, `/models`; models are allowlist-bound and must not silently fallback | Current branch updates Public CLI to call canonical quota/models and removes status-hint model fallback | `[PR-IMPACT-ACK]` recorded from Public lane. |
| #552 | valid-now / pending ACK | Realtime sync issue was waiting for Public proposal | Posted `[SYNC-PROPOSAL-V1]` at https://github.com/YoneRai12/YonerAI/issues/552#issuecomment-4754454747 | Waiting for `[AWS-SYNC-ACK]` and `[YONERAIWEB-SYNC-ACK]` before `[SYNC-CONTRACT-ACCEPTED]`. |
| #552 AWS sync ACK | valid-but-not-complete | AWS posted `[AWS-SYNC-ACK]` and acknowledged the opaque auth field after Public ACK | AWS says Firestore projection is not live and still waits for public/Web acceptance plus runtime evidence | Public can proceed only after `[YONERAIWEB-SYNC-ACK]`; do not send `[SYNC-CONTRACT-ACCEPTED]` yet. |

Open PR disposition at this checkpoint:

- #548 dependency PR: deferred dependency lane.
- #547 update language UX: deferred non-security UX.
- #545/#544 theme config duplicates: deferred duplicate UX group.
- #523 docs alpha warning: deferred docs/claim lane.
- #521 validated staging account claim: valid-but-already-fixed on current auth boundary; no merge of stale branch.
- Older dependabot and stale feature PRs: deferred to dependency/owner lanes; no current P0/P1/security blocker observed from the open list.

Current blockers:

- Live `login -> whoami -> run submit -> status/events/result` remains blocked until AWS staging auth bridge issues a CLI-usable opaque YonerAI session claim. Public must not synthesize or infer that credential.
- `[SYNC-CONTRACT-ACCEPTED]` is blocked until YonerAIWEB ACKs the proposal in issue #552 or via a public-safe coordination notice; AWS ACK is recorded.

Validation for this checkpoint:

- Targeted tests: `132 passed` for auth/privacy, control spine, Native Run, PR intake gate workflow, and provider gateway tests.
- `ruff` passed for touched Python paths.
- `compileall` passed for `clients/cli/yonerai_cli` and `tests`.
- `git diff --check` passed with CRLF warnings only.
- `ci_quality_scans.py --changed` passed.
- Live staging smoke confirmed `/v1/health`, `/v1/capabilities`, and `/v1/modules` return 200, provider quota returns 200, and saved legacy session is rejected with controlled repair guidance.

## 2026-06-20 Staging Opaque Session Poll Checkpoint

- last_scan_at: 2026-06-20T06:23:19+09:00
- highest_seen_pr_number: 560
- current_main_head: b5dd674
- branch: codex/staging-opaque-session-poll-fix
- lane: Public staging auth/session contract and Native Run smoke

Checked in this checkpoint:

- PR #560 reviews/comments/checks after final push and squash merge.
- Open PR list after #560 merge.
- Public-safe staging auth contract notice for the opaque CLI session shape.
- Public CLI smoke summaries for auth/session and Native Run account-auth command surfaces, with private runtime details omitted.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #560 | valid-but-already-fixed | Gemini flagged two readability cleanups; both were fixed before merge and inline comments were answered | Product checks passed; review-intake was classified with `intake-reviewed`; squash merge produced `b5dd674` | Complete. |
| Opaque session contract notice | valid-now | Staging auth contract permits only an opaque YonerAI CLI session; no Google token, refresh token, auth code, or provider key is part of the contract | Initial Public sanitizer rejected allowed nested opaque session metadata when `session.token_returned=true` | Current branch allows only `session.staging_session_token` or `session.staging_session_claim` as opaque YonerAI session fields and continues forbidden-token scanning for all other response fields. |
| Public auth command smoke | valid-now | Browser-login CLI flow completed against the public staging contract without printing credential material | Authenticated account status command returned linked state through the public CLI | Auth mismatch root cause is closed on this branch, subject to PR/CI. |
| Native Run account-auth command smoke | deferred-with-existing-release-evidence | Account-auth Native Run command surfaces returned controlled staging responses | Worker-completed regression is a separate smoke and not a realtime-sync contract prerequisite | Public CLI can prove API/session command behavior, but worker health must remain honestly reported. Do not recreate a release for this checkpoint. |
| #552 sync proposal | deferred-with-tracked-issue | AWS ACK is recorded; YonerAIWEB ACK is still missing | Not a CI surface | Do not send `[SYNC-CONTRACT-ACCEPTED]` yet. |

Validation for this checkpoint:

- Targeted tests: `129 passed` for auth/privacy, Control Spine, Native Run, and provider gateway CLI tests.
- `ruff` passed for touched Python paths.
- `compileall` passed for touched Python paths.
- `git diff --check` passed with CRLF warnings only.
- `ci_quality_scans.py --changed` passed.

## 2026-06-20 PR #561 Intake Update

- last_scan_at: 2026-06-20T06:31:00+09:00
- highest_seen_pr_number: 561
- current_main_head: b5dd674
- branch: codex/staging-opaque-session-poll-fix
- PR: #561

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #561 Codex usage-limit comment | stale / non-actionable | The only initial PR comment is a Codex usage-limit notice, not a code finding | `review-intake-required` failed closed until classification | Applied `intake-reviewed` after classification; continue to read new review/comments after each push and before merge. |
| #561 implementation | valid-now | No inline review thread at creation scan | Local tests and scans passed; GitHub product checks pending | Keep PR scoped to accepting only AWS-issued opaque YonerAI staging session fields while preserving forbidden token scans. |
## 2026-06-20 PR #559 Merged Review Follow-up

- last_scan_at: 2026-06-20T09:49:13+09:00
- current_main_head: 741a885f
- branch: codex/fix-intake-gate-least-privilege-20260620
- classification: valid-now merged PR review follow-up
- review/comment state: PR #559 retained unresolved merged review threads; three were already fixed on current main, and one P2 manual poll linked-without-CLI-session failure remained valid.
- CI state: local targeted validation runs on this branch before PR creation.
- decision: fail manual --poll-request-id responses that report linked browser state without an opaque YonerAI CLI session, even when wait_linked is false; resolve already-fixed PR #559/#560 threads with evidence.
- lane boundary: Public auth/session safety follow-up only; no production deploy, no Web chat, no Firestore listener, no provider consent/control, no quota mutation, no approval control.

## 2026-06-20 Staging Poll Verifier Impact Checkpoint

- last_scan_at: 2026-06-20T10:42:00+09:00
- highest_seen_pr_number: 562
- current_main_head: 170e949
- branch: codex/staging-poll-url-verifier-fix
- lane: Public staging auth poll-verifier security contract

Checked in this checkpoint:

- PR #562 state, comments, inline review comments, checks, and merge result before starting this bounded follow-up.
- Public-safe auth contract notice requiring Public CLI to use the returned `poll_url` exactly because poll authorization is now bound to a CLI-only verifier.
- Current `staging_auth_bridge.py` behavior, which reconstructed the poll URL from `request_id` before this patch.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #562 | valid-now / completed | No inline review comments; Gemini comment was quota-only and non-actionable | Required checks passed; squash merged as `170e949` | Completed bounded P2 auth safety follow-up before this patch. |
| Poll verifier contract notice | valid-now security contract change | Poll authorization now requires exact `poll_url` use; browser URL must not carry the verifier | Local regression tests added and pass; Public CLI smoke confirmed the verifier is consumed internally and not printed | Current branch patches Public CLI to use returned `poll_url` internally, sanitize it from public reports, and reject wrong origin, sensitive query params, browser verifier leakage, or unexpected poll query fields. |
| Native Run worker completion | deferred-with-existing-release-evidence | Manager correction says v0.22.0-alpha.1 already exists and Windows worker completion is a parallel regression smoke, not a prerequisite for realtime_sync.v1 | Current Public CLI account-auth command smoke returned controlled staging responses; worker health remains a separate runtime signal | Do not recreate release or block sync acceptance on worker completion; keep worker status honest. |

## 2026-06-20 PR #563 Intake Update

- last_scan_at: 2026-06-20T10:49:00+09:00
- highest_seen_pr_number: 563
- current_main_head: 170e949
- branch: codex/staging-poll-url-verifier-fix
- PR: #563

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #563 Gemini quota comment | stale / non-actionable | The only initial PR comment is a Gemini quota warning, not a code or security finding | `review-intake-required` failed closed until classification; product checks pending | Apply `intake-reviewed` after classification and reread comments/checks after CI and before merge. |
| #563 implementation | valid-now | No inline review thread at creation scan | Local auth/control-spine/native-run/provider tests passed; Public CLI smoke confirmed exact `poll_url` use without verifier/token printing | Keep PR scoped to poll-verifier contract patch. |

## 2026-06-20 PR #563 Post-Merge Review Follow-up

- last_scan_at: 2026-06-20T10:56:00+09:00
- current_main_head: 73fa7b5
- branch: codex/sanitize-pr563-runtime-provenance
- classification: valid-now P1 merged PR review follow-up
- review/comment state: Codex review on merged PR #563 flagged private-runtime provenance and live-state wording in the public checkpoint.
- CI state: local `git diff --check` and `python scripts\ci_quality_scans.py --changed` passed before opening PR #564; PR #564 CI is tracked separately below.
- decision: sanitize public checkpoint language to contract-level evidence and public CLI smoke summaries only; avoid private runtime provenance and live environment internals.

## 2026-06-20 PR #564 Intake Update

- last_scan_at: 2026-06-20T11:18:00+09:00
- highest_seen_pr_number: 564
- current_main_head: 73fa7b5
- branch: codex/sanitize-pr563-runtime-provenance
- PR: #564

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #564 Gemini quota comment | stale / non-actionable | The only initial PR comment is a Gemini quota warning, not a code or security finding | `review-intake-required` failed closed until classification; product checks pending | Apply `intake-reviewed` after classification and reread comments/checks after CI and before merge. |
| #564 implementation | valid-now | Codex P2 review on the initial PR commit correctly noted the post-merge follow-up entry still said pending validation | Local `git diff --check` and `ci_quality_scans.py --changed` passed; checkpoint now records completed local validation explicitly | Keep PR scoped to sanitizing merged PR #563 public checkpoint wording and recording completed validation evidence. |

## 2026-06-23 Live Status Ingestion Gate / PR #565 Security Intake

- last_scan_at: 2026-06-22T19:35:00Z
- highest_seen_pr_number: 567
- current_main_head: 698ad1e9

### PR #568 final-push review intake

| Source | Classification | Finding | Decision |
| --- | --- | --- | --- |
| #568 Gemini high review | valid-now | Quoted token-like scalar keys, such as JSON-shaped metadata values, were not covered by the first regex. | Fixed in the same PR by accepting optional quote characters around the forbidden public key and adding quoted regression cases. |
| #568 Gemini medium review | valid-now | Windows absolute paths written with forward slashes were not covered by the first local-path value regex. | Fixed in the same PR by accepting either slash form after the drive letter and adding a regression case. |
- branch: codex/status-live-ingestion-20260623
- lane: Public security gate before StatusWEB live ingestion

Checked in this checkpoint:

- Current dirty workspace was not adopted; an isolated worktree was created from `origin/main`.
- Open PRs #567, #566, #565, #548, #547, #545, #544, #523, #521, dependency PRs, and stale owner/deploy lanes.
- PR review submissions, inline review threads, PR comments, issue comments, and CI rollups available from GitHub API.
- status.yonerai.com live host and current same-origin status static assets.
- Live AWS staging `/v1/status` schema/cache headers and public projection boundary.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #565 | valid-now P1/security | Codex P1 says underscored token metadata markers can pass in session metadata values; Gemini medium says local-path scalar scan should be case-insensitive | Reproduced on current main: `session.type` / `session.token_field` values containing token-like markers were accepted and returned in public report metadata | Fix current main before StatusWEB live ingestion by rejecting token-like public scalar values and adding regression coverage. |
| #567 | deferred-with-tracked-issue | Gemini no-comment review; review-intake-required failing until classification | Non-status CLI test PR; not a P0/P1/security blocker for this lane | Do not merge or reimplement here. |
| #566 | deferred-with-tracked-issue | Gemini no-comment security review; review-intake-required failing until classification | Auth/security-adjacent but not the current live-ingestion blocker after main validation | Do not merge stale branch blindly; preserve any still-valid finding only after current-main reproduction. |
| #548 and dependency PRs | deferred-with-tracked-issue | Dependabot lanes | Some stale/failed checks on old branches | Track separately; dependency work must not starve StatusWEB live ingestion. |
| #545/#544 | deferred-with-tracked-issue / duplicate UX | Theme alias review comments remain open | UX/correctness, not current P0/P1/security | Track separately; not blocking this lane. |
| #552 | valid-now coordination source | Public/AWS/YonerAIWEB status and sync notices checked | Current issue state says sync/firestore remains staging/disabled or short-TTL-gated; no production claim | Status page may render staging/preview truth only, with no account/token/internal detail. |
