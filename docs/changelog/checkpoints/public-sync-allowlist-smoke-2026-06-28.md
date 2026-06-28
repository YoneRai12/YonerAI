# Public Sync Allowlist Smoke Checkpoint - 2026-06-28

This governed checkpoint holds the detailed Public sync owner-allowlist smoke notes moved from `docs/codex/checkpoints/public_sync.md` after PR #584 review intake.

## 2026-06-28 Public Sync Hold Checkpoint

### Current HEAD / Branch / PR

- Public worktree: `<LOCAL_PUBLIC_WORKTREE>`
- Branch: `main`
- Public `main` / `origin/main`: `125e00f` (`fix: Web依存のDependabot警告を解消する (#583)`)
- Current PR: none for this local follow-up. No push or release was performed in this checkpoint.

### Review / PR Intake

- Open PRs were scanned.
- Current valid security/P0/P1 blocker on Public main: none found.
- #581 was already closed as superseded by #582 on current main.
- #521 was already closed as superseded by current auth-session validation.
- #544 was already closed as duplicate of #545.
- #545 remains the canonical P2/UX theme parser follow-up; it is not a sync/security blocker.
- #574/#567/#547/#523 remain nonblocking docs/test/UX items for this sync lane.
- Dependency and old nonlane PRs remain deferred and were not pulled into this sync lane.

### Issue #552 Standalone Tags

- present: `[AWS-FIRESTORE-COST-GUARD-READY]`
- present: `[AWS-FIREBASE-AUTH-EXCHANGE-READY]`
- present: `[AWS-WEB-AUTH-BRIDGE-READY]`
- present: `[PUBLIC-SYNC-SMOKE-PREPARED]`
- present: `[YONERAIWEB-SYNC-SMOKE-PREPARED]`
- missing: `[OWNER-SYNC-SMOKE-APPROVED]`
- missing: `[AWS-OWNER-SYNC-SMOKE-READY]`
- missing: `[PUBLIC-SYNC-CLIENT-READY]`
- missing: `[WEB-TO-CLI-E2E-PASSED]`

### Completed Evidence

- Targeted sync tests passed:
  - `python -m pytest tests\test_realtime_sync_client_service.py tests\test_realtime_sync_event_service.py -q`
  - result: 70 passed
- `ruff` passed for the touched realtime sync service/test.
- `compileall` passed for the touched realtime sync service/test.
- `git diff --check` passed.
- `python scripts\ci_quality_scans.py --changed` passed.
- Live staging Firebase config check through the CLI passed after accepting the current AWS usage-policy shape:
  - config ready: true
  - usage policy: `yonerai.firestore_usage_policy.v1`
  - initial limit: 20
  - absolute limit: 50
  - reconnect cooldown: 30 seconds
  - max CLI listeners: 1
  - offset forbidden: true
  - collection-group query allowed: false
  - body fetch source: `aws_only`
  - Firestore body fallback: false
  - sync enabled: false
  - sync mode: off

### Local Follow-Up Fix

- Public CLI now accepts the current AWS `usage_policy.kill_switch` object shape when `tripped=false`.
- `usage_policy.kill_switch.tripped=true` still fails closed.
- Unknown kill-switch object fields are rejected as private fields.
- Regression tests cover boolean and object kill-switch behavior.
- This fix is local only at this checkpoint. It is not pushed, PR'd, or merged.

### Exact Blocker

- `[AWS-OWNER-SYNC-SMOKE-READY]` is not present, so Public must not start the owner-only Web-to-CLI smoke.
- Current local saved staging session is not bearer-capable; `yonerai sync listener once` stops at controlled `staging_session_required`.
- A fresh interactive `yonerai login` will be required before Public can receive the owner-only synthetic event.
- Staging remains `sync_enabled=false` / `sync_mode=off`.

### Exact Next Command

If the owner authorizes publishing this Public follow-up:

```powershell
git switch -c codex/public-sync-kill-switch-policy-compat
git add clients/cli/yonerai_cli/services/realtime_sync_client_service.py tests/test_realtime_sync_client_service.py docs/codex/checkpoints/public_sync.md
git commit -m "fix: Firestore同期ポリシーのkill switch互換性を補強"
```

If `[AWS-OWNER-SYNC-SMOKE-READY]` appears first, refresh login and then run:

```powershell
$env:YONERAI_STAGING_AUTH_ORIGIN="https://api-staging.yonerai.com"
$env:YONERAI_OFFICIAL_API_STAGING_ORIGIN="https://api-staging.yonerai.com"
yonerai logout
yonerai login
yonerai sync listener once --pretty --lang ja
```

### Peer Tags Received / Sent

- received: `[AWS-FIRESTORE-COST-GUARD-READY]`
- received: `[AWS-FIREBASE-AUTH-EXCHANGE-READY]`
- received: `[AWS-WEB-AUTH-BRIDGE-READY]`
- received: `[YONERAIWEB-SYNC-SMOKE-PREPARED]`
- sent earlier: `[PUBLIC-SYNC-SMOKE-PREPARED]`
- not sent: `[PUBLIC-SYNC-CLIENT-READY]`
- not sent: `[WEB-TO-CLI-E2E-PASSED]`

### Non-Claims

- No production login, production sync, production cloud, or production deploy claim.
- No owner-only smoke was started.
- No release or tag was created.
- No token value, account identifier, raw body, private path, provider key, or internal runtime detail is recorded here.
- `reference_clawdbot` and `src/cogs/ora.py` were not touched.

## 2026-06-28 AWS Owner Smoke Blocked Update

### Fresh Issue #552 Gate

- present: `[AWS-OWNER-SYNC-SMOKE-BLOCKED]`
- missing: `[OWNER-SYNC-SMOKE-APPROVED]` as a current standalone tag
- missing: `[AWS-OWNER-SYNC-SMOKE-READY]`
- missing: `[PUBLIC-SYNC-CLIENT-READY]`
- missing: `[WEB-TO-CLI-E2E-PASSED]`

### Decision

- Public CLI did not start `yonerai sync listener once`.
- Public CLI did not consume a synthetic SyncEvent.
- Public CLI did not emit `[PUBLIC-SYNC-CLIENT-READY]`.

### Blocker

- AWS attempted the owner-only smoke after owner approval, but the Firestore usage guard failed closed because live usage freshness was not explicitly fresh.
- AWS rollback is complete per the public-safe notice: sync remains off, projection remains disabled, and temporary owner admission was removed.
- AWS fixed the guard-state parameters in private PR #141, but a new owner approval is required before another time-boxed owner-only smoke attempt.

### Next Command

Wait for fresh issue #552 tags:

```text
[OWNER-SYNC-SMOKE-APPROVED]
[AWS-OWNER-SYNC-SMOKE-READY]
```

Only after those tags appear, refresh the Public staging login and run:

```powershell
$env:YONERAI_STAGING_AUTH_ORIGIN="https://api-staging.yonerai.com"
$env:YONERAI_OFFICIAL_API_STAGING_ORIGIN="https://api-staging.yonerai.com"
yonerai logout
yonerai login
yonerai sync listener once --pretty --lang ja
```

### Non-Claims

- No production deploy, production login, general sync, external alpha, release, tag, token value, account identifier, raw body, private path, provider key, or internal runtime detail.

## 2026-06-28 Public Allowlist Mode Blocker Follow-Up

### Fresh Issue #552 Gate

- present: `[AWS-PUBLIC-ALLOWLIST-BLOCKER]`
- latest effective owner-smoke state: blocked.
- missing: `[PUBLIC-SYNC-CLIENT-READY]`
- missing: `[WEB-TO-CLI-E2E-PASSED]`

### Blocker

- AWS briefly enabled the staging owner-only smoke mode and rolled back.
- AWS-side body commit -> body-free Firestore projection -> authenticated AWS body fetch succeeded.
- Full Web-to-CLI E2E did not complete because Public CLI rejected `sync_mode=allowlist`.

### Local Public Fix

- Public CLI now treats `sync_mode=allowlist` as a valid staging owner-smoke mode.
- `sync_mode=off` remains the prepared-smoke stop condition.
- `allowlist` mode can proceed to account-scoped body-free SyncEvent listening and authenticated AWS body fetch.
- The client does not infer owner admission; it still relies on AWS/Firebase auth, Firestore rules, and controlled backend errors.
- Regression coverage:
  - Firebase config accepts owner allowlist mode.
  - Firestore metadata poll can proceed in allowlist mode.
  - no offset, account-rooted query, max initial limit, cursor/idempotency, and AWS-only body fetch behavior remain covered.

### Validation

- `python -m pytest tests\test_realtime_sync_client_service.py tests\test_realtime_sync_event_service.py -q`
  - result: 71 passed
- `python -m ruff check clients\cli\yonerai_cli\services\realtime_sync_client_service.py tests\test_realtime_sync_client_service.py`
  - result: passed
- `git diff --check`
  - result: passed with CRLF warnings only
- `python -m compileall -q clients\cli\yonerai_cli\services\realtime_sync_client_service.py tests\test_realtime_sync_client_service.py`
  - result: passed
- `python scripts\ci_quality_scans.py --changed`
  - result: passed
- Live `yonerai sync listener firebase-config --json` after AWS rollback:
  - endpoint: live 200
  - result: controlled fail closed
  - error code: `firestore_usage_policy_kill_switch_active`
  - Firestore body read: not performed
  - AWS body fetch: not performed
  - token/account/body/private path printed: false

### Publishing State

- This fix is local only at this checkpoint.
- No push, PR, merge, tag, release, production deploy, production login, general sync, token value, account identifier, raw body, private path, provider key, or internal runtime detail.

### Exact Next Command

If the owner authorizes publishing this Public follow-up:

```powershell
git switch -c codex/public-sync-allowlist-smoke-compat
git add clients/cli/yonerai_cli/services/realtime_sync_client_service.py tests/test_realtime_sync_client_service.py docs/codex/checkpoints/public_sync.md
git commit -m "fix: Firestore同期のowner allowlist smokeモードに対応"
```

## 2026-06-28 Owner Smoke Ready Superseded By Blocked

### Fresh Issue #552 Gate

- `[AWS-OWNER-SYNC-SMOKE-BLOCKED]` appeared at `2026-06-27T20:08:51Z`.
- `[AWS-OWNER-SYNC-SMOKE-READY]` appeared at `2026-06-27T21:50:54Z`.
- `[AWS-OWNER-SYNC-SMOKE-BLOCKED]` appeared again at `2026-06-27T21:58:45Z`.
- Latest effective owner-smoke state: blocked, not ready.
- `[PUBLIC-SYNC-CLIENT-READY]`: missing.
- `[WEB-TO-CLI-E2E-PASSED]`: missing.

### Decision

- Public CLI did not run `yonerai sync listener once`.
- Public CLI did not read Firestore.
- Public CLI did not fetch any AWS message body.
- Public CLI did not emit `[PUBLIC-SYNC-CLIENT-READY]`.

### Exact Blocker

- The latest AWS lane notice supersedes the earlier ready tag.
- AWS must post a fresh standalone `[AWS-OWNER-SYNC-SMOKE-READY]` after a new owner approval and successful time-boxed enablement.

### Exact Next Command

After a fresh, latest-effective `[AWS-OWNER-SYNC-SMOKE-READY]` appears:

```powershell
$env:YONERAI_STAGING_AUTH_ORIGIN="https://api-staging.yonerai.com"
$env:YONERAI_OFFICIAL_API_STAGING_ORIGIN="https://api-staging.yonerai.com"
yonerai logout
yonerai login
yonerai sync listener once --pretty --lang ja
```

### Non-Claims

- No production deploy, production login, general sync, external alpha, release, tag, token value, account identifier, raw body, private path, provider key, or internal runtime detail.

