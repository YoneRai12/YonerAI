# Public Sync Checkpoint

- last_scan_at: 2026-06-25 JST
- current HEAD: `1c218503f8cf60d347728303294f860957c279b9`
- branch: `main`
- PR: none for the current local follow-up patch

## Current Goal

Revalidate the closed-alpha Firebase client-auth path after the owner refreshed
the interactive staging browser login, then keep Public at the expected
sync-off smoke-prepared boundary. Do not claim client-ready or live Web-to-CLI
E2E while staging sync remains off.

## Fresh Truth

- Public `main` and `origin/main` both point at `1c218503f8cf60d347728303294f860957c279b9`.
- Latest merged Public PR inspected: #579.
- Open PR scan:
  - #574 is docs-only AI assistant guidance; its process-path review is
    nonblocking for this sync lane.
  - #567 is a display-test PR; nonblocking for this sync lane.
  - older dependency/theme/docs/Web/license PRs are deferred or stale and do
    not represent a current P0/P1/security blocker for the sync lane.
- Issue #552 includes `[AWS-FIREBASE-AUTH-EXCHANGE-READY]` after the owner
  completed the interactive Public CLI browser login.
- Issue #552 still shows sync disabled/off and does not contain
  `[PUBLIC-SYNC-CLIENT-READY]` or `[WEB-TO-CLI-E2E-PASSED]`.

## Local Public Fix In Progress

- `yonerai login` now uses the normal owner flow by default:
  bridge login, browser open, and wait-for-linked are enabled for the short
  command without requiring expert flags.
- `yonerai login --json` remains machine-oriented and does not implicitly open
  the browser.
- `build_realtime_sync_listener_readiness_report(...)` now performs the
  Firebase custom-token exchange readiness check and reports only boolean
  safety outcomes.
- The reported AWS/Public review blocker
  `NameError: linked_account_id is not defined` is fixed locally and covered by
  tests.
- Early canonical-account rejection still avoids backend calls and preserves the
  existing safe report shape.

## Live Staging Evidence

- Earlier `yonerai sync listener readiness --json` against staging returned after
  the owner refreshed the interactive login:
  - `ok=true`
  - `ready=false`
  - `auth_state=linked`
  - opaque staging session available
  - Firebase public config ready
  - Firebase custom-token endpoint 200
  - Firebase custom-token exchange attempted and passed
  - Firebase ID token received but not printed or persisted
  - Firebase refresh token discarded and not persisted
  - usage policy accepted: `yonerai.firestore_usage_policy.v1`
  - initial query limit 20
  - absolute query limit 50
  - reconnect cooldown 30 seconds
  - max CLI listeners per account 1
  - `firestore_sync_enabled=false`
  - blocker: `firestore_sync_disabled_until_live_e2e_and_owner_flip`
- `yonerai sync listener firestore-poll --json` stops at:
  - `firestore_sync_disabled_until_live_e2e_and_owner_flip`
  - `sync_mode=off`
  - `projection_write_allowed=false`
  - no Firestore body fallback
  - no AWS body fetch before a validated body-free event
- Latest local recheck after the browser-control attempt shows the API bearer
  session is no longer available locally:
  - readiness stops at `opaque_staging_session_required`
  - `whoami` stops at the controlled staging-auth-required boundary
  - next required action remains the normal interactive `yonerai login` flow

## Validation

- `python -m pytest tests\test_realtime_sync_client_service.py tests\test_realtime_sync_event_service.py tests\test_official_sync_cli.py tests\test_auth_privacy_policy.py -q`
  - result: 170 passed
- `python -m ruff check clients\cli\yonerai_cli\services\realtime_sync_client_service.py clients\cli\yonerai_cli\commands\sync.py clients\cli\yonerai_cli\commands\auth.py tests\test_realtime_sync_client_service.py tests\test_auth_privacy_policy.py`
  - result: passed
- `python -m compileall -q clients\cli\yonerai_cli tests`
  - result: passed
- `git diff --check`
  - result: passed
- `python scripts\ci_quality_scans.py --changed`
  - result: passed

## Exact Blocker

- The current local fix is not yet in a PR or merged to Public main.
- The currently installed local session is not bearer-capable; a fresh
  interactive staging login is required before any further live auth smoke.
- `[YONERAIWEB-SYNC-SMOKE-PREPARED]` is still missing from issue #552.
- `[OWNER-SYNC-SMOKE-APPROVED]` is still missing from issue #552.
- Staging remains `firestore_sync_enabled=false` and `sync_mode=off`, so Public
  must not claim live Web-to-CLI E2E.

## Exact Next Command

If the owner wants this local follow-up persisted to Public main, create a
focused branch/PR for:

```powershell
git switch -c codex/public-sync-auth-readiness-followup
git add clients/cli/yonerai_cli/commands/auth.py clients/cli/yonerai_cli/commands/sync.py clients/cli/yonerai_cli/services/realtime_sync_client_service.py tests/test_auth_privacy_policy.py tests/test_realtime_sync_client_service.py docs/codex/checkpoints/public_sync.md
git commit -m "fix: Public同期ログインとFirebase準備確認を補強"
```

## Peer Tags Received/Sent

- received: `[AWS-FIRESTORE-COST-GUARD-READY]`
- received: `[AWS-AUTH-POLL-COMPAT-READY]`
- received: `[AWS-OFF-MODE-GUARD-READY]`
- received: `[AWS-FIREBASE-AUTH-EXCHANGE-READY]`
- received: `[PUBLIC-REVIEW-BLOCKER]`
- sent: `[REVIEW-BLOCKER-RESOLVED]` for the local follow-up fix; the fix is not
  merged to Public main yet
- sent earlier: `[PUBLIC-SYNC-SMOKE-PREPARED]`
- not sent: `[PUBLIC-SYNC-CLIENT-READY]`
- not sent: `[WEB-TO-CLI-E2E-PASSED]`

## Non-Claims

- No production login, production sync, production cloud, or production deploy
  claim.
- No release or tag was created.
- No token value, account identifier, raw body, private path, provider key, or
  internal runtime detail is recorded here.
- `reference_clawdbot` and `src/cogs/ora.py` were not touched.

## 2026-06-28 Public Sync Allowlist Smoke Pointer

- Detailed checkpoint log moved to `docs/changelog/checkpoints/public-sync-allowlist-smoke-2026-06-28.md`.
- Current PR: #584 (`codex/public-sync-allowlist-smoke-compat`).
- Current blocker: issue #552 latest effective state is `[AWS-PUBLIC-ALLOWLIST-BLOCKER]`; `[PUBLIC-SYNC-CLIENT-READY]` and `[WEB-TO-CLI-E2E-PASSED]` are not emitted.
- Next required action after merge: post `[PUBLIC-ALLOWLIST-SMOKE-MODE-READY]` to issue #552 with public-safe CI/review evidence, then wait for fresh owner approval and fresh `[AWS-OWNER-SYNC-SMOKE-READY]`.
- Non-claims: no production deploy/login/sync, no release/tag, no token/account/body/private path/provider key.

## 2026-06-28 Public Sync Ready Gate Follow-up

- Current branch: `codex/public-sync-ready-gates-allowlist`.
- Base HEAD: `98365e6` (`fix: owner allowlist同期smokeモードを受け入れる (#584)`).
- Review source: merged PR #584 follow-up Codex P1 review.
- Valid finding:
  - `sync_enabled=true`, `sync_mode=allowlist`, and `ready=false` must not let
    the CLI proceed to Firebase token exchange, Firestore reads, or AWS body
    fetch.
  - The listener must treat `ready=false` as a hard stop even in owner-only
    allowlist smoke mode.
- Fix in progress:
  - `firestore_sync_enabled` now requires Firebase public config `ready=true`.
  - Added config-report and listener-poll regression tests for
    allowlist/`ready=false`.
- Local evidence:
  - `python -m pytest tests\test_realtime_sync_client_service.py tests\test_realtime_sync_event_service.py -q`
  - result: 73 passed
- Exact blocker:
  - This follow-up is not merged to Public main yet.
  - Do not post `[PUBLIC-ALLOWLIST-SMOKE-MODE-READY]` until the follow-up PR is
    reviewed, CI-green, and merged.
- Next command:

```powershell
python -m ruff check clients\cli\yonerai_cli\services\realtime_sync_client_service.py tests\test_realtime_sync_client_service.py
```

- Peer tags:
  - received: `[AWS-PUBLIC-ALLOWLIST-BLOCKER]`
  - not sent: `[PUBLIC-ALLOWLIST-SMOKE-MODE-READY]`
  - not sent: `[PUBLIC-SYNC-CLIENT-READY]`
- Non-claims: no release/tag, no production sync/login/deploy, no token/account
  identifier/raw body/private path/provider key.

## 2026-06-28 Public Sync AWS Body Shape Follow-up

- Current branch: `codex/public-sync-aws-body-shape`.
- Base HEAD: `5f2ae44a31d37770e34bf984b302ee60f1876d0b`.
- Trigger: owner-only staging smoke reached Public CLI Firestore body-free event
  receive and authenticated AWS body fetch, then stopped at
  `sync_aws_body_private_fields`.
- Current blocker:
  - AWS rolled back the owner-only smoke window.
  - Public must merge the AWS body response shape compatibility fix before a
    fresh owner approval/window.
- Fix in progress:
  - Public now accepts the live AWS top-level body metadata shape with
    `body_text` while keeping Firestore body/private credential/path flags
    fail-closed.
  - `body_text` requires `body_authority=aws` and
    `contract_version=yonerai.message_body.v1`.
  - `account_id` in the body response is checked against the validated
    SyncEvent account binding and is not printed.
  - Unknown body fields still fail closed.
- Local evidence:
  - `python -m pytest tests\test_realtime_sync_client_service.py tests\test_realtime_sync_event_service.py tests\test_official_sync_cli.py -q`
  - result: 88 passed
  - `python -m ruff check clients\cli\yonerai_cli\services\realtime_sync_client_service.py tests\test_realtime_sync_client_service.py`
  - result: passed
  - `python -m compileall -q clients\cli\yonerai_cli\services\realtime_sync_client_service.py tests\test_realtime_sync_client_service.py`
  - result: passed
  - `git diff --check`
  - result: passed with existing line-ending normalization warnings only
- Peer tags:
  - received: `[AWS-OWNER-SYNC-SMOKE-READY]`
  - received: `[OWNER-SYNC-SMOKE-APPROVED]`
  - received: `[AWS-OWNER-SYNC-SMOKE-BLOCKED]`
  - not sent: `[PUBLIC-SYNC-CLIENT-READY]`
  - not sent: `[WEB-TO-CLI-E2E-PASSED]`
- Non-claims: no release/tag, no production sync/login/deploy, no token/account
  identifier/raw body/private path/provider key recorded here.
