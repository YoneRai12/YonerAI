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

## 2026-06-22 Firebase Read-Auth / Native Run Continuation Checkpoint

- last_scan_at: 2026-06-23T00:11:16+09:00
- highest_seen_pr_number: 567
- branch: codex/sync-contract-accepted-checkpoint
- local_head: b0d6a24
- latest_stable: v0.8.1
- latest_prerelease: v0.22.0-alpha.1
- lane: Public Native Run and realtime sync client readiness

Checked in this checkpoint:

- Open PR list up to #567.
- PR #567, #566, and #565 review summaries, comments, and check rollups.
- Live staging CLI surfaces for worker status, capabilities, modules, Native Run
  status/events/result, fresh submit/status/events/cancel, and Firebase
  read-auth readiness.
- Issue #552 coordination ledger for Firebase client auth readiness.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #567 | deferred-with-tracked-issue | Gemini commented no actionable review comments | Product checks pass; `review-intake-required` failing closed | Non-security local LLM label test PR. Does not block current sync lane. |
| #566 | deferred-with-tracked-issue / likely replacement candidate | Gemini commented no actionable review comments | Product checks pass; `review-intake-required` failing closed | Security-adjacent staging poll hardening PR remains open; no immediate current-lane P0/P1 observed from review body. |
| #565 | valid-now P2 / superseded-candidate | Gemini suggested case-insensitive local-path matching; Codex review body had no inline finding in fetched summary | `review-intake-required` failed; branch is dirty | Valid sanitizer robustness item, but not a current Native Run or Firebase read-auth P0/P1. Track with security intake rather than blocking sync-client progress. |
| #552 Firebase client-auth notice | valid-now | AWS superseded immediate-revocation wording with closed-alpha short-TTL revocation semantics | Public live smoke accepted `POST /v1/sync/firebase-token` via opaque staging session and did not print or persist token values | Public branch now accepts `short_ttl`, rejects `yonerai_session_ref`, and records `[PUBLIC-FIREBASE-CLIENT-AUTH-ACK]` in issue #552. |
| Existing worker-completed run | valid-but-current-worker-offline | Safe run `run_native_2b860428ee65` returns completed status/result/events through Public CLI | Current worker status is offline/stale; fresh submit queues and can be canceled but does not complete without owner worker heartbeat | Do not recreate v0.22.0-alpha.1. Keep worker status honest. |

Validation for this checkpoint:

- Targeted tests: `74 passed` for Control Spine, realtime sync client, and
  conversation sync policy.
- Broader touched-lane tests before this checkpoint: `230 passed` for auth,
  realtime sync, command display, Native Run, conversation policy, and staging
  sync.
- `ruff`, `compileall`, `git diff --check`, and
  `scripts/ci_quality_scans.py --changed` passed for touched files before the
  local Firebase short-TTL contract commit.

- decision: sanitize public checkpoint language to contract-level evidence and public CLI smoke summaries only; avoid private runtime provenance and live environment internals.

## 2026-06-23 Conversation Policy Display Regression Checkpoint

- last_scan_at: 2026-06-23T00:13:31+09:00
- branch: codex/sync-contract-accepted-checkpoint
- lane: Public Native Run and conversation sync controls

Checked in this checkpoint:

- `sync conversation set ... local_only --pretty --lang ja` display coverage.
- Live staging worker status, existing completed run result, and realtime sync
  listener readiness.

Decision:

- Added a regression test proving the pretty conversation-policy screen exposes
  `local_only`, `execution.official_worker_allowed=false`,
  `memory.inherits_conversation_policy`, `memory.memory_scope=local_private`,
  `memory.cloud_memory_index_allowed=false`, and
  `memory.local_to_cloud_memory_sync=disabled`.
- Live staging still reports the current worker as offline/stale, while existing
  safe run `run_native_2b860428ee65` remains readable as completed through the
  Public CLI.
- Firebase read-auth readiness returns the expected blocker
  `firestore_sync_disabled_until_live_e2e_and_owner_flip`; this is not
  `[PUBLIC-SYNC-CLIENT-READY]`.

Validation:

- Targeted tests: `81 passed` for conversation sync policy, Native Run client,
  realtime sync client, and realtime sync event service.
- `ruff`, `compileall`, `git diff --check`, and
  `scripts/ci_quality_scans.py --changed` passed.

## 2026-06-23 Live Recheck After Firebase Short-TTL Contract

- last_scan_at: 2026-06-23T00:18:05+09:00
- highest_seen_pr_number: 567
- branch: codex/sync-contract-accepted-checkpoint
- local_head: 5f1e1fd
- lane: Public Native Run and conversation sync controls

Checked in this checkpoint:

- Open Public PR list and issue #552 comments after the latest
  `[FIREBASE-CLIENT-AUTH-READY]` / `[PUBLIC-FIREBASE-CLIENT-AUTH-ACK]`.
- Live staging health/status/capabilities/modules.
- Public CLI `whoami`, realtime sync listener readiness, worker status,
  capability list, and module list against the custom staging origin.

Decision:

- No new Public issue #552 comment was found after
  `[PUBLIC-FIREBASE-CLIENT-AUTH-ACK]`.
- Public CLI still reaches the staging account path with a linked opaque
  YonerAI staging session; no Google token, refresh token, provider key, or
  Firebase custom token value is printed or persisted by the checked reports.
- Firebase read-auth bridge is live and canonical account binding passes, but
  readiness remains false because `firestore_sync_enabled=false`.
- Current worker status remains offline/stale, so a fresh worker-completed
  Native Run E2E is still not proven in this lane.
- Existing open PRs #567, #566, and #565 remain classified as not blocking this
  lane's current P0/P1/security gate; #565 remains a P2 follow-up candidate.
- No release/tag/PR/push was created in this checkpoint.

Current blocker:

- `firestore_sync_disabled_until_live_e2e_and_owner_flip`
- current worker offline/stale for fresh worker-completed Native Run proof

## 2026-06-23 PR #565 Review Fix Checkpoint

- last_scan_at: 2026-06-23T00:24:02+09:00
- highest_seen_pr_number: 567
- branch: codex/sync-contract-accepted-checkpoint
- local_head_before_commit: 8ab29ff
- lane: Public Native Run and conversation sync controls / auth safety follow-up

Checked in this checkpoint:

- Open PR #565 reviews and comments.
- Current auth/session local path sanitizers.
- Live realtime sync readiness and worker status after the sanitizer fix.

Classification:

- PR #565 Gemini review local-path case-insensitive feedback:
  `valid-now` for the legacy staging auth claim sanitizer.
- Existing current branch already covered `staging_auth_bridge` and
  `staging_session_service`; `auth_session_service` still used a case-sensitive
  local-path regex before this checkpoint.

Decision:

- Updated the staging auth claim local-path regex to be case-insensitive.
- Added a regression assertion that a tampered staging auth claim containing an
  uppercase Windows user path is rejected as a local path.
- This is a bounded P2/security-adjacent cleanup and does not change production
  login, production sync, provider traffic, or release state.

Validation:

- `python -m pytest tests\test_auth_privacy_policy.py -q` => `84 passed`.
- Broader auth/sync/native targeted suite => `176 passed`.
- Live realtime sync readiness still reaches Firebase read-auth and remains
  blocked by `firestore_sync_disabled_until_live_e2e_and_owner_flip`.
- Live worker status still reports the official execution worker as offline.

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
| #568 Codex P1 review | valid-now | Temp, var, and workspace absolute paths could still pass as public staging bridge metadata values. | Fixed in the same PR by rejecting common Unix temp/workspace absolute path prefixes and adding regression cases. |
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

## 2026-06-23 Closed-Alpha Firebase Client / Realtime Sync Intake

- last_scan_at: 2026-06-23T05:08:16+09:00
- highest_seen_pr_number: 569
- current_main_head: e7c27d6
- branch: codex/sync-contract-accepted-checkpoint
- lane: Public closed-alpha Firebase client and realtime sync listener

Checked in this checkpoint:

- Open PRs #569, #567, #566, #565, #548, #547, #545, #544, #523, #521,
  stale product PRs, and dependency PRs.
- Recently merged #568 reviews/comments after final push and merge.
- Issue #552 latest AWS/Public/YonerAIWEB Firebase client-auth comments.
- Current branch tests, ruff, compileall, diff check, and changed-file quality
  scan after rebasing onto #568.

Findings and decisions:

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #568 | valid-but-already-fixed | Gemini high/medium and Codex P1 were valid; #568 was merged to main before this checkpoint | Current branch is rebased on merge commit e7c27d6 and preserves quoted token-marker, Windows slash path, and Unix temp/workspace path coverage | Treat as current main truth; no reopen. |
| #566 | valid-now fixed in current branch | Gemini noted no additional comments, but the PR captured a real fail-closed rule for `session.token_returned=true` | Current branch now rejects `token_returned=true` even when an opaque YonerAI session exists; auth/sync regression suite passed | Supersede by this branch rather than merging stale dirty PR. |
| #565 | duplicate / valid-but-already-fixed | Gemini local-path and Codex token-marker findings were valid on the old PR | Covered by #568 plus current branch preserving private endpoint filtering | Close or mark superseded after this branch lands. |
| #569 | deferred-with-tracked-issue | Gemini review lists status-ingestion improvements: atomic promotion, fetch timeout, content-length guard, redundant validation cleanup | Open, blocked, not merged into main; status lane scope, not the active sync listener surface | Track in `docs/tasks/DEFERRED.md`; do not block realtime sync client work. |
| #567 | deferred-with-tracked-issue | No review findings; stale/behind test wording PR | Non-security and not required for closed-alpha sync | Track as CLI UX/test cleanup. |
| #552 | valid-now coordination source | Latest comments confirm short-TTL no-session-ref Firebase client-auth contract; Web ACK is present but live sync is not claimed | Current branch accepts no-session-ref short-TTL contract and keeps sync disabled until owner flip/live E2E | Post `[SYNC-CURRENT-TRUTH-V1]`; no `[PUBLIC-SYNC-CLIENT-READY]` yet. |

Validation:

- `python -m pytest tests\test_auth_privacy_policy.py tests\test_realtime_sync_client_service.py tests\test_realtime_sync_event_service.py -q` => 145 passed.
- `python -m pytest tests\test_native_run_client.py tests\test_conversation_sync_policy.py tests\test_control_spine_client.py tests\test_cli_command_display_modes.py -q` => 85 passed.
- Combined targeted suite => 230 passed.
- `python -m ruff check ...` => pass.
- `python -m compileall -q clients\cli\yonerai_cli` => pass.
- `git diff --check` => pass.
- `python scripts\ci_quality_scans.py --changed` => pass for 28 files.

Current blocker:

- `[PUBLIC-SYNC-CLIENT-READY]` is not yet true.
- `YONERAI_FIRESTORE_SYNC_ENABLED=false` remains owner-controlled.
- Live Web-to-CLI E2E is not proven in this Public checkpoint.

## 2026-06-23 Firebase Public Config Intake / AWS-E2E-SUPPORT-BLOCKED

- last_scan_at: 2026-06-23T06:25:00+09:00
- highest_seen_pr_number: 569
- current_main_head: e7c27d6
- branch: codex/sync-contract-accepted-checkpoint
- lane: Public closed-alpha Firebase client and realtime sync listener

New cross-lane notice:

- Private AWS reports `/v1/sync/firebase-config` live on staging with
  `config_contract_version=yonerai.firebase.public_config.v1`.
- `YONERAI_FIRESTORE_SYNC_ENABLED=false` remains in force.
- AWS reports `[AWS-E2E-SUPPORT-BLOCKED]` because the staging public Firebase
  client config is not ready yet. This is public client config, not a service
  account key or provider token.
- Fresh PR scan also observed #569's Status lane follow-up review-intake
  comment. Its earlier status-ingestion findings are reported fixed on that PR,
  but #569 remains a separate Status lane PR and is not a realtime sync client
  prerequisite.

Public decision:

- Accept `/v1/sync/firebase-config` as the public Firebase client-config
  endpoint for closed-alpha listener readiness.
- Do not print or persist Firebase public client config values, Firebase custom
  tokens, Google tokens, refresh tokens, provider keys, or account identifiers.
- Treat `ready=false` as `firebase_public_config_not_ready`; do not start the
  Firestore listener or claim `[PUBLIC-SYNC-CLIENT-READY]`.
- Keep environment-provided Firebase client config as an explicit local
  closed-alpha fallback only; the staging API ready flag remains authoritative
  for listener readiness.
- Posted `[PUBLIC-FIREBASE-CONFIG-ACK]` to issue #552:
  https://github.com/YoneRai12/YonerAI/issues/552#issuecomment-4772771412

Live safe smoke:

- `/v1/health` returned 200 with version fields present.
- `/v1/status` returned `yonerai.status.v1`.
- `/v1/sync/firebase-config` returned 200, contract v1, ready false, sync
  disabled; Public smoke printed no config values.
- `yonerai sync listener firebase-config --json` reaches the staging endpoint
  and reports booleans only.
- `yonerai sync listener readiness --json` remains not ready because the saved
  local staging session is rejected by the read-auth endpoint; the output does
  not print account identifiers or token values.

Validation:

- `python -m pytest tests\test_realtime_sync_client_service.py -q` => 38 passed.
- Combined targeted suite
  `tests\test_auth_privacy_policy.py tests\test_realtime_sync_client_service.py
  tests\test_realtime_sync_event_service.py tests\test_native_run_client.py
  tests\test_conversation_sync_policy.py tests\test_control_spine_client.py
  tests\test_cli_command_display_modes.py -q` => 232 passed.
- `python -m ruff check ...` => pass.
- `python -m compileall -q clients\cli\yonerai_cli` => pass.
- `git diff --check` => pass.
- `python scripts\ci_quality_scans.py --changed` => pass for 28 files.

Current blocker:

- `[PUBLIC-SYNC-CLIENT-READY]` is still false.
- Live Web-to-CLI E2E is still blocked by staging session repair/re-login and
  the AWS public Firebase client config readiness blocker.
- No release/tag was created.

## 2026-06-23 PR #570 Clean Replacement Checkpoint

- last_scan_at: 2026-06-23T06:35:00+09:00
- highest_seen_pr_number: 570
- current_main_head: 59786e8
- original PR: #570
- replacement branch: `codex/firebase-sync-config-clean-20260623`
- lane: Public closed-alpha Firebase client and realtime sync listener

Checked in this checkpoint:

- PR #570 reviews, comments, status check rollup, commits, and changed files.
- Current open PR list after `origin/main` advanced to `59786e8`.
- Current AWS staging `/v1/sync/firebase-config` public-safe readiness fields.
- #565/#566 security findings against current main and the replacement branch.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #570 | duplicate / valid-but-replaced | Gemini review was valid: `auth_policy.py` needed a type check before `dict(staging_claim)`, and English sync blocker rows were incomplete. The PR also carried 32 commits / 30 files including Native Run and Control Spine history outside the Firebase sync scope. | Product checks were mostly green, but `review-intake-required` failed and the branch was behind current main. | Do not merge #570. Create a clean replacement from current `origin/main`, keep only realtime sync/auth-session/Control Spine account-id compatibility needed by the sync contract, and port the valid review fixes. |
| #565 | valid-but-covered | Token/private metadata and local path findings were valid on older branches. | Current main includes #568 coverage, and this replacement preserves forbidden scalar, private endpoint, local path, and nested token-field regression tests. | Supersede stale #565 rather than merging its dirty branch. |
| #566 | valid-but-covered | `session.token_returned=true` must fail closed even when an opaque session-like field is present. | Replacement branch preserves the `staging_bridge_token_return_forbidden` behavior and tests that no Google/provider/session token value is printed or persisted. | Supersede stale #566 rather than merging its dirty branch. |
| AWS firebase-config readiness | valid-now blocker | AWS staging reports `config_contract_version=yonerai.firebase.public_config.v1`, `ready=false`; no token/config value is printed. | Public CLI treats `ready=false` as `firebase_public_config_not_ready` and does not start the listener. | Do not claim `[PUBLIC-SYNC-CLIENT-READY]`; no release before live Web-to-CLI E2E. |

Validation:

- `python -m pytest tests\test_auth_privacy_policy.py tests\test_realtime_sync_client_service.py tests\test_realtime_sync_event_service.py -q` => `148 passed`.
- Broader targeted suite for auth, realtime sync, Control Spine, Native Run, conversation sync, and command display => `226 passed`.
- `python -m ruff check ...` on touched Python paths => pass.
- `python -m compileall -q ...` on touched Python paths => pass.
- `git diff --cached --check` => pass.
- `python scripts\ci_quality_scans.py --changed` => pass.
- `python scripts\ci_quality_scans.py --all` still reports existing baseline warnings outside this branch; do not treat that as a new changed-file finding.

Current blocker:

- `[PUBLIC-SYNC-CLIENT-READY]` is still false because staging Firebase public config is not ready and live Web-to-CLI E2E has not run.

## 2026-06-23 PR #571 Post-Push Review Intake

- last_scan_at: 2026-06-23T15:30:00+09:00
- highest_seen_pr_number: 571
- current_main_head: 59786e8
- active PR: #571
- lane: Public closed-alpha Firebase client and realtime sync listener

Checked in this checkpoint:

- PR #571 review submissions, inline review comments, PR comments, status check rollup, and changed files after the latest push.
- PR #570 closure state as superseded by #571.
- Open PR list for overlap with the realtime sync client lane.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #571 Gemini CRLF review | valid-now | AWS body text sanitizer allowed `\n` and `\t` but rejected normal Windows `\r\n` line endings. | Fixed by allowing `\r` alongside `\n` and `\t`; added `test_listener_accepts_windows_crlf_in_aws_body`. | Keep the fix in #571 before merge. |
| #571 Codex Firestore cursor review | valid-now | Firestore REST polling did not send the saved cursor, so a full first page could starve newer events. | Fixed by loading the saved account cursor before the Firestore read and passing it as `pageToken`; added `test_firestore_poll_resumes_after_saved_cursor`. | Keep the fix in #571 before merge. |
| #570 | duplicate / replaced | Closed with replacement evidence. | #571 is current-main based and contains only the relevant realtime sync/auth-session/account-id compatibility scope. | Do not merge #570. |
| #565 / #566 | valid-but-covered | Findings remain valid historically but are covered by current-main + #571 tests. | #571 preserves token/private metadata/local path rejection and `token_returned=true` fail-closed behavior. | Keep #571 as canonical; stale PR branches remain superseded. |

Validation after CRLF fix:

- `python -m pytest tests\test_realtime_sync_client_service.py -q` => `41 passed`.
- Broader targeted suite for auth, realtime sync, Control Spine, Native Run, conversation sync, and command display => `228 passed`.
- `python -m ruff check clients\cli\yonerai_cli\services\realtime_sync_client_service.py tests\test_realtime_sync_client_service.py` => pass.
- `python -m compileall -q clients\cli\yonerai_cli\services\realtime_sync_client_service.py tests\test_realtime_sync_client_service.py` => pass.
- `git diff --check` => pass.
- `python scripts\ci_quality_scans.py --changed` => pass.

Current blocker:

- `[PUBLIC-SYNC-CLIENT-READY]` remains false until AWS firebase-config is ready and live Web-to-CLI E2E is proven.
- No release/tag is allowed from this checkpoint.

## 2026-06-23 PR #571 Post-Merge Review Follow-Up

- last_scan_at: 2026-06-23T15:50:26+09:00
- highest_seen_pr_number: 571
- current_main_head: a4752e4
- follow-up branch: `codex/post-571-review-fixes`
- lane: Public closed-alpha Firebase client and realtime sync listener

Checked in this checkpoint:

- PR #570 inline review comments and closure state.
- PR #571 inline review comments after merge.
- #565/#566 closure comments and current-main coverage.
- Current open PR list for overlap with the realtime sync/auth lane.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #570 English sync blocker display | valid-but-already-fixed | Gemini correctly noted that English readiness summaries covered fewer blockers than Japanese. | Current main has English rows for canonical account, Firebase config, token contract, sync-disabled, owner permission, staging login/session/origin, and unreachable blockers in `commands/sync.py`. | No #570 merge. Keep #571/current-main implementation. |
| #570 `auth_policy.py` Mapping check | valid-but-already-fixed | Gemini correctly noted `dict(staging_claim)` needed a Mapping guard. | Current main uses `dict(staging_claim) if isinstance(staging_claim, Mapping) else {}`. | No further action. |
| #571 P1 non-opaque account IDs | valid-now | Codex review found `account_id` could preserve raw identifiers such as emails or Google subject-like values while claiming raw identifiers were not stored. | Follow-up fix accepts only `acct_...` opaque IDs as canonical account IDs; other safe text is hashed into `staging-account-<hash>`. Regression: `test_staging_auth_claim_hashes_non_opaque_account_id_values`. | Fix before any further sync/client-ready claim. |
| #571 P2 interactive sync action callback | valid-now | Codex review found normal packaged interactive callbacks did not wire `sync_action`, making `/sync event validate ...` unreachable outside tests. | Follow-up fix wires `sync_action` through `_interactive_callbacks`. Regression: `test_interactive_callbacks_wire_sync_action`. | Fix in same follow-up because scope is small and directly tied to #571. |
| #565 / #566 | valid-but-covered | Stale PRs remain superseded; findings are current-main covered. | Current main and this follow-up retain metadata/token/local-path rejection and `token_returned=true` fail-closed tests. | Do not merge old dirty branches. |

Validation so far:

- `python -m pytest tests/test_auth_privacy_policy.py::test_staging_auth_claim_hashes_non_opaque_account_id_values tests/test_auth_privacy_policy.py::test_staging_auth_claim_storage_redacts_and_rejects_secret_material tests/test_auth_privacy_policy.py::test_staging_session_preserves_canonical_account_id_for_realtime_sync tests/test_control_spine_client.py::test_interactive_callbacks_wire_sync_action tests/test_realtime_sync_event_service.py::test_interactive_sync_event_validate_uses_same_safe_boundary -q` => `5 passed`.
- `python -m pytest tests/test_auth_privacy_policy.py tests/test_control_spine_client.py tests/test_realtime_sync_client_service.py tests/test_realtime_sync_event_service.py -q` => `185 passed`.
- `python -m pytest tests/test_cli_runtime_shell_v020.py tests/test_auth_privacy_policy.py -q` => `100 passed`.
- `python -m pytest tests/test_cli_interactive_v030.py tests/test_cli_command_display_modes.py tests/test_cli_output_formatting.py -q -k "not install_like_entry_point_starts_yonerai"` => `94 passed, 1 deselected`.
- `python -m pytest tests/test_ci_quality_scans.py tests/test_core_api_access_security.py tests/test_cloudflare_auth_security.py tests/test_web_auth_loopback_security.py tests/test_redaction_security.py tests/test_agent_trace_security.py tests/test_mcp_runtime_deny_policy.py tests/test_mcp_client_fail_open.py tests/test_tools_mcp_safe_subset_contract.py tests/test_policy_engine.py tests/test_workspace_file_capability.py tests/test_cli_output_formatting.py -q` => `69 passed`.
- `python -m pytest tests/test_verify_version.py tests/test_release_workflow_prerelease.py tests/test_release_gate.py tests/test_current_truth_anchor.py tests/test_quality_wall_workflow.py -q` => `45 passed`.
- Historical local run of `python -m pytest tests/test_realtime_sync_client_service.py tests/test_realtime_sync_event_service.py -q` was recorded in this older checkpoint, but it is not current merge-gate evidence; use the latest GitHub Quality Wall for current gate status.
- `python -m ruff check clients/cli/yonerai_cli/cli.py clients/cli/yonerai_cli/services/auth_session_service.py tests/test_auth_privacy_policy.py tests/test_control_spine_client.py` => pass.
- `python -m compileall -q clients/cli/yonerai_cli core/src/ora_core scripts` => pass.
- `git diff --check` => pass.
- `python scripts/ci_quality_scans.py --changed` => pass.
- `python -m pytest -q` is not a Quality Wall command and failed during collection on local optional dependencies (`discord`, `PIL`) and an existing non-lane import issue; use GitHub Quality Wall as the release/merge gate for this follow-up.

Current blocker:

- AWS firebase-config is still not client-ready; no `[PUBLIC-SYNC-CLIENT-READY]` claim and no release/tag from this follow-up.

## 2026-06-23 PR #572 Post-Merge Review Follow-Up

- last_scan_at: 2026-06-23T16:05:28+09:00
- highest_seen_pr_number: 572
- current_main_head: a9da7ec
- follow-up branch: `codex/post-572-review-fix`
- lane: Public closed-alpha Firebase client and realtime sync listener

Checked in this checkpoint:

- PR #572 review submissions, inline comments, and conversation comments after merge.
- Current open PR list for overlap with the realtime sync/auth lane.
- Current-main implementation of staging account claim sanitization and realtime sync account binding.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #572 P2 placeholder account id | valid-now | Codex review found that a rejected non-opaque `account_id` such as `google-oauth2\|...` could stop fallback evaluation and persist `linked-staging-account` as a dummy linked account. | Follow-up fix tries safe account-ref candidates in order and treats `linked-staging-account` as requiring a fresh canonical account id before realtime sync readiness. Regression tests cover rejected upstream account ids and placeholder rejection before backend calls. | Fix in a narrow follow-up PR before any client-ready or sync E2E claim. |
| #573 Gemini/Codex space-separated placeholder reviews | valid-but-already-fixed | Gemini correctly noted that `linked staging account` is also a placeholder. Codex separately noted placeholder-only claims must not be hashed into concrete-looking `staging-account-<hash>` references. | Follow-up update treats both `linked-staging-account` and `linked staging account` as placeholders in auth claim sanitization and realtime sync readiness. Regression tests cover both spellings and the placeholder-only display-label case. | Keep in #573 before merge and rerun intake/Quality Wall. |
| AWS firebase-config readiness notice | valid-but-not-client-ready | Private AWS reported `/v1/sync/firebase-config ready=true`, but explicitly requested `[PUBLIC-SYNC-CLIENT-READY]` only after Public CLI listener and authenticated AWS body-fetch evidence. | This branch does not implement the listener path or live Web-to-CLI E2E. | Record the blocker update, but do not claim client-ready and do not release. |

Validation:

- `python -m pytest tests/test_auth_privacy_policy.py::test_staging_auth_claim_does_not_collapse_rejected_account_id_to_placeholder tests/test_auth_privacy_policy.py::test_staging_auth_claim_hashes_non_opaque_account_id_values tests/test_realtime_sync_client_service.py::test_listener_readiness_rejects_placeholder_account_id_before_backend_call tests/test_realtime_sync_client_service.py::test_listener_readiness_rejects_legacy_public_ref_before_backend_call -q` => `4 passed`.
- `python -m pytest tests/test_auth_privacy_policy.py tests/test_control_spine_client.py tests/test_realtime_sync_client_service.py tests/test_realtime_sync_event_service.py -q` => `187 passed`.
- `python -m pytest tests/test_cli_runtime_shell_v020.py tests/test_auth_privacy_policy.py -q` => `101 passed`.
- `python -m pytest tests/test_cli_interactive_v030.py tests/test_cli_command_display_modes.py tests/test_cli_output_formatting.py -q -k "not install_like_entry_point_starts_yonerai"` => `94 passed, 1 deselected`.
- `python -m pytest tests/test_ci_quality_scans.py tests/test_core_api_access_security.py tests/test_cloudflare_auth_security.py tests/test_web_auth_loopback_security.py tests/test_redaction_security.py tests/test_agent_trace_security.py tests/test_mcp_runtime_deny_policy.py tests/test_mcp_client_fail_open.py tests/test_tools_mcp_safe_subset_contract.py tests/test_policy_engine.py tests/test_workspace_file_capability.py tests/test_cli_output_formatting.py -q` => `69 passed`.
- `python -m pytest tests/test_verify_version.py tests/test_release_workflow_prerelease.py tests/test_release_gate.py tests/test_current_truth_anchor.py tests/test_quality_wall_workflow.py -q` => `45 passed`.
- `python -m ruff check clients/cli/yonerai_cli/services/auth_session_service.py clients/cli/yonerai_cli/services/realtime_sync_client_service.py tests/test_auth_privacy_policy.py tests/test_realtime_sync_client_service.py` => pass.
- `python -m compileall -q clients/cli/yonerai_cli core/src/ora_core scripts` => pass.
- `git diff --check` => pass.
- `python scripts/ci_quality_scans.py --changed` => pass.

Current blocker:

- `[PUBLIC-SYNC-CLIENT-READY]` remains false until Public CLI listener + authenticated AWS body fetch are implemented and live Web-to-CLI E2E is proven.
- No release/tag is allowed from this follow-up.

## 2026-06-25 PR #580 Security Review Intake

- last_scan_at: 2026-06-25T20:51:55+09:00
- highest_seen_pr_number: 580
- current_main_head: 1c21850
- active_branch: `codex/public-sync-auth-readiness-followup`
- active_PR: #580
- lane: Public closed-alpha login/readiness safety follow-up

Checked in this checkpoint:

- Open PR list through #580.
- PR #580 review submissions, conversation comments, check rollup, and changed files after the initial push.
- `review-intake-required` run logs for PR #580.
- Issue #552 latest update timestamp and the Private AWS shared-traffic-default-off impact notice.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #580 Gemini review: non-TTY login hang | valid-now | Gemini correctly noted that making short `yonerai login` always wait/open browser can hang CI or non-interactive processes. | Fixed by restoring TTY gating for implicit browser-open and wait behavior while keeping interactive `yonerai login` as the owner flow. Regression tests cover interactive and non-TTY defaults. | Keep fix in #580 and rerun Quality Wall. |
| #580 Gemini review: misleading endpoint flags | valid-now | Gemini correctly noted readiness could mark Firebase token endpoint as checked/live when canonical account validation failed before any backend call. | Fixed by leaving endpoint checked/status fields unset when `_linked_account_id` fails before network I/O. Regression tests cover legacy and placeholder account IDs. | Keep fix in #580 and rerun Quality Wall. |
| #580 Gemini review: duplicate Firebase token request | valid-now | Gemini correctly noted readiness minted Firebase read-auth twice: once for readiness summary and again for token exchange. | Fixed by requesting the Firebase custom token once in readiness and reusing the sanitized payload for the Firebase sign-in exchange. Regression test asserts the token endpoint is called once. | Keep fix in #580 and rerun Quality Wall. |
| #580 `review-intake-required` | valid-now process gate | Gate failed by design after synchronize/review activity and requires maintainer intake classification. | This checkpoint records classification before applying `intake-reviewed`. Product checks were already green before the follow-up push. | After final review scan and validation, add `intake-reviewed` for the current head. |
| AWS `[AWS-SHARED-TRAFFIC-STATUS-DEFAULT-OFF]` notice | valid-but-already-compatible | Private AWS says shared traffic fields are consistently off and provider_gateway remains the availability surface. | Public CLI already treats shared traffic as off/default-disabled and does not enable production/provider traffic from status. | Record ACK on issue #552; no Public code change required from this notice. |
| #574 / #567 / #548 / #547 / #545 / #544 and older open PRs | deferred-with-tracked-issue / duplicate / stale | Open PR list was refreshed; no current P0/P1/security blocker overlapping #580 was found. | Older PRs remain behind/dirty or separate dependency/UX/docs lanes. | Keep tracked in `docs/tasks/DEFERRED.md`; do not starve the sync/auth security lane. |

Validation in progress:

- Targeted review regression subset => `10 passed`.
- Broader auth/realtime sync validation, ruff, compileall, diff check, and changed-file quality scan still required before final push.

Current blocker:

- #580 cannot be merged until the follow-up push, post-push review reread, `intake-reviewed` label, and required CI pass.
- `[PUBLIC-SYNC-CLIENT-READY]` remains false; live Web-to-CLI E2E is not proven and sync remains off.

## 2026-06-28 Post-#585 Public Review/Security Intake

- last_scan_at: 2026-06-28T14:21:09+09:00
- highest_seen_pr_number: 586
- current_main_head: 8c6b068
- lane: Public realtime sync / PR security intake

Checked in this checkpoint:

- Current `main`/`origin/main` after PR #584 and #585.
- All currently open PRs through #586 and older dependency/doc/UX PRs.
- Open PR review submissions, conversation comments, and keyword hits for
  P0/P1/security/token/secret/blocker-style findings.
- Issue #552 latest coordination tags after
  `[PUBLIC-ALLOWLIST-SMOKE-MODE-READY]`.

| PR / issue / notice | classification | review/comment state | CI / evidence state | decision |
| --- | --- | --- | --- | --- |
| #584 post-merge Codex P1 `ready=false` allowlist gate | valid-now, fixed | Codex correctly noted that `sync_enabled=true` and `sync_mode=allowlist` must not let Public CLI proceed if Firebase public config `ready=false`. | PR #585 is merged to main. `firestore_sync_enabled` now requires `ready=true`; regression tests cover config report and listener/poll stop before Firebase token exchange, Firestore reads, or AWS body fetch. | Closed by #585. |
| #585 `review-intake-required` | valid-but-already-fixed process gate | Gemini review had no additional comments. PR intake comment was posted and `intake-reviewed` label was applied. | Latest intake gate passed before merge; Quality Wall/core checks passed. | Merged as `8c6b068`. |
| #586 checkpoint review intake | valid-now, fixed in PR | Gemini medium path portability comment was fixed with forward slashes. Codex P1 evidence-integrity comments were treated as gate-integrity findings. The checkpoint no longer relies on local targeted pytest output as the merge gate; current GitHub CI/Quality Wall remains the required authority for this docs-only PR. Codex P2 requested #586 itself be recorded in this checkpoint; this row and the updated `highest_seen_pr_number` address it. | Connector reviews reported inconsistent temporary-SHA failures for the targeted pytest command, so this checkpoint does not record that command as cleared by local output. Latest GitHub CI/Quality Wall plus `review-intake-required` must pass before merge. | Keep PR scoped to checkpoint/docs only; merge only after latest review-intake and CI pass. |
| #574 CLAUDE.md security keyword hit | deferred-with-tracked-issue / nonblocking docs | Review comment is about missing `docs/process/` path prefixes in a docs-only assistant guide. The keyword hit is from security-boundary wording, not a current vulnerability. | PR is behind and outside realtime sync/security lane. | Track as docs cleanup; not P0/P1/security. |
| #545 theme config keyword hit | deferred-with-tracked-issue / nonblocking UX | Existing intake comment classifies it as P2/UX: use `theme_from_input` for aliases. | PR is behind and outside realtime sync/security lane. | Keep deferred; not sync/security blocking. |
| #567 / #547 / #523 / #413-#410 / #156 / #151-#145 / #134 / #121 / #111 / #108 / #107 / #81 / #79 / #34 / #26 / #18 / #7 / #6 | stale / dependency / docs / UX / separate lane | Cross-PR review scan found no current P0/P1/security finding affecting Public main or the sync receiver lane. Many are behind or dirty. | No evidence that these unblock or block current Web-to-CLI sync owner smoke. | Do not merge during sync lane; keep deferred unless a fresh security finding appears. |
| issue #552 `[PUBLIC-ALLOWLIST-SMOKE-MODE-READY]` | valid current coordination state | Public posted main evidence after #584/#585. Latest effective state still lacks a fresh post-fix `[AWS-OWNER-SYNC-SMOKE-READY]`. | Staging remains no-release/no-production-claim from Public side. | Wait for fresh AWS owner smoke ready before running `yonerai sync listener once`. |

Validation:

- Targeted #585 validation:
  - Codex connector reviews reported inconsistent failures for `python -m pytest tests/test_realtime_sync_client_service.py tests/test_realtime_sync_event_service.py -q` on temporary SHAs.
  - To avoid overstating evidence, this checkpoint does not treat local output from that command as the merge gate.
  - Current GitHub CI/Quality Wall and `review-intake-required` are the required gate evidence for #586.
  - Latest GitHub CI/Quality Wall and `review-intake-required` must pass before merge.
  - `python -m ruff check clients/cli/yonerai_cli/services/realtime_sync_client_service.py tests/test_realtime_sync_client_service.py` => passed.
  - `python -m compileall -q clients/cli/yonerai_cli/services/realtime_sync_client_service.py tests/test_realtime_sync_client_service.py` => passed.
  - `git diff --check` => passed.
  - `python scripts/ci_quality_scans.py --changed` => passed.
- GitHub PR #585:
  - core/Quality Wall checks passed.
  - latest `review-intake-required` passed after intake.

Current blocker:

- No current Public P0/P1/security finding is known after #585.
- A fresh post-fix `[AWS-OWNER-SYNC-SMOKE-READY]` is still required before the
  Public CLI receiver smoke can run.
- `[PUBLIC-SYNC-CLIENT-READY]` and `[WEB-TO-CLI-E2E-PASSED]` are not emitted.
- No release/tag is allowed from this checkpoint.
