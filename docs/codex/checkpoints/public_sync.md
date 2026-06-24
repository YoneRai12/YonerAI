# Public Sync Checkpoint

- last_scan_at: 2026-06-25 JST
- current HEAD: `b25b5c3`
- branch: `main`
- PR: #575 merged; #576 merged

## Current Goal

Integrate the Firestore cost guard client and emit `[PUBLIC-SYNC-SMOKE-PREPARED]`
only after the focused PR is merged and live staging reaches the expected
sync-off gate.

## Completed Evidence

- Public main and origin/main are `c6fbadd` after PR #575 merge.
- Latest stable release observed: `v0.8.1`.
- Latest prerelease observed: `v0.22.0-alpha.1`.
- PR #571, #572, and #573 are merged into current main.
- PR #565 and #566 security findings are superseded by current-main fixes and
  regression tests.
- Issue #552 includes:
  - `[AWS-E2E-SUPPORT-READY]`
  - `[AWS-FIRESTORE-COST-GUARD-READY]`
  - `[AWS-AUTH-POLL-COMPAT-READY]`
  - `[AWS-OFF-MODE-GUARD-READY]`
- Open PR scan:
  - #574 is docs-only and currently failing review-intake, nonblocking for this
    sync lane.
  - #567 is a display-test PR, nonblocking for this sync lane.
  - dependency and old unrelated PRs remain classified as nonblocking unless
    they become current P0/P1/security issues.
- Public local implementation now validates `yonerai.firestore_usage_policy.v1`
  and fails closed on:
  - initial query limit above 20
  - absolute list limit above 50
  - reconnect cooldown below 30 seconds
  - more than one CLI listener per account
  - non-account-rooted listener requirements
  - offset or collection-group query allowance
  - client writes
  - non-AWS body fetch source
  - projection writes while `sync_mode=off`
- Public local implementation treats `sync_mode=off` as a hard stop even if a
  backend sync wiring flag is present.
- PR #575 Gemini review on state overwrite was valid-now and fixed locally:
  Firestore poll now reloads the state file before recording
  `last_firestore_poll_at`, preserving cursor/idempotency written by event
  processing.
- PR #575 Gemini cleanup on unused usage-policy parameter was valid-now and
  fixed locally.
- PR #575 merged as `c6fbadd`.
- Live staging smoke after #575 found a Public-side blocker: `login` saved a
  non-canonical hashed account reference when `/v1/account/me` returned
  canonical `account_id` at the top level plus a nested display `account`
  object. `whoami` repaired the claim, but sync readiness should not require
  a separate whoami repair step.
- The follow-up branch preserves the top-level canonical account id while still
  rejecting token-like/private fields.
- PR #576 Gemini/Codex review on nested non-canonical `account.account_id` was
  valid-now. The helper now always prioritizes the top-level canonical
  `account_id`; the regression fixture includes a legacy nested account id.
- PR #576 normal CI and Quality Wall checks passed on `4fae1b5`; review-intake
  still needs the final post-push classification label.
- PR #576 merged as `b25b5c3`.
- Live staging sync smoke after #576:
  - logout/login/whoami: passed without printing account identifiers
  - Firebase public config: `firebase_public_config_ready=true`
  - Firebase custom-token endpoint: 200
  - Firestore usage policy: `yonerai.firestore_usage_policy.v1`
  - limits accepted: initial 20, absolute 50, reconnect cooldown 30 seconds,
    max CLI listeners 1
  - Firestore sync gate: `firestore_sync_enabled=false`, `sync_mode=off`
  - Firestore read/body fetch: not performed
  - Firebase custom token exchange: blocked by Identity Toolkit
    `CONFIGURATION_NOT_FOUND`

## Validation

- `python -m pytest tests\test_realtime_sync_client_service.py -q`
  - result: 46 passed
- `python -m pytest tests\test_realtime_sync_client_service.py tests\test_realtime_sync_event_service.py tests\test_official_sync_cli.py tests\test_conversation_sync_policy.py tests\test_native_run_client.py tests\test_control_spine_client.py -q`
  - result: 129 passed
- `python -m ruff check clients\cli\yonerai_cli\services\realtime_sync_client_service.py clients\cli\yonerai_cli\commands\sync.py tests\test_realtime_sync_client_service.py tests\test_official_sync_cli.py`
  - result: passed
- `python -m compileall -q clients\cli\yonerai_cli tests`
  - result: passed
- `git diff --check`
  - result: passed
- `python scripts\ci_quality_scans.py --changed`
  - result: passed
- changed/untracked secret and local-path scan
  - result: no live secret, account identifier, private path, raw body, or token value found
- `python -m pytest tests\test_auth_privacy_policy.py::test_staging_login_preserves_top_level_account_id_from_account_me tests\test_auth_privacy_policy.py::test_staging_login_token_custody_scans_filesystem_config_and_ledger tests\test_realtime_sync_client_service.py -q`
  - result: 48 passed
- `python -m ruff check clients\cli\yonerai_cli\staging_auth_bridge.py tests\test_auth_privacy_policy.py`
  - result: passed

## Exact Blocker

- `[PUBLIC-SYNC-SMOKE-PREPARED]` has not been sent yet.
- `[PUBLIC-SYNC-SMOKE-PREPARED]` is blocked because Firebase custom-token
  exchange returns `CONFIGURATION_NOT_FOUND`.
- Staging currently reports `firestore_sync_enabled=false` and
  `sync_mode=off`, so Public must not attach a live listener or claim
  Web-to-CLI E2E.

## Exact Next Command

```powershell
@'
[PUBLIC-SYNC-SMOKE-BLOCKED]

Public sync smoke is blocked at Firebase custom-token exchange:
- firebase config ready: true
- custom-token endpoint: 200
- usage policy: yonerai.firestore_usage_policy.v1
- Firestore sync: off
- Identity Toolkit exchange: 400 CONFIGURATION_NOT_FOUND

Private AWS/GCP must align the staging Firebase Auth / Identity Toolkit
configuration before Public can emit [PUBLIC-SYNC-SMOKE-PREPARED].
'@ | gh issue comment 552 --body-file -
```

After AWS reports the exchange blocker fixed, rerun live staging sync-off smoke
from current main and send `[PUBLIC-SYNC-SMOKE-PREPARED]` only if token exchange
passes without printing or persisting credentials.

## Peer Tags Received/Sent

- received: `[AWS-E2E-SUPPORT-READY]`
- received: `[AWS-FIRESTORE-COST-GUARD-READY]`
- received: `[AWS-AUTH-POLL-COMPAT-READY]`
- received: `[AWS-OFF-MODE-GUARD-READY]`
- sent earlier: `[PUBLIC-SYNC-CLIENT-BLOCKED]`
- not sent: `[PUBLIC-SYNC-SMOKE-PREPARED]`
- not sent: `[PUBLIC-SYNC-CLIENT-READY]`
- not sent: `[WEB-TO-CLI-E2E-PASSED]`

## Non-Claims

- No production login, production sync, production cloud, or production deploy
  claim.
- No release or tag was created.
- No token value, account identifier, raw body, private path, provider key, or
  internal runtime detail is recorded here.
- `reference_clawdbot` and `src/cogs/ora.py` were not touched.
