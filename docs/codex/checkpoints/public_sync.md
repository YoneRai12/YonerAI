# Public Sync Checkpoint

- last_scan_at: 2026-06-25 JST
- current HEAD: `fec9b77`
- branch: `main`
- PR: #578 merged

## Current Goal

Integrate the Firestore cost guard client and emit `[PUBLIC-SYNC-SMOKE-PREPARED]`
after the focused Public PR is merged and live staging proves the sync-off gate.

## Completed Evidence

- Public main and origin/main are `fec9b77` after PR #578 merge.
- Latest stable release observed: `v0.8.1`.
- Latest prerelease observed: `v0.22.0-alpha.1`.
- No `v0.23.0-alpha.1` release exists.
- PR #571, #572, #573, #575, #576, and #577 are merged into current main.
- Issue #552 includes:
  - `[AWS-E2E-SUPPORT-READY]`
  - `[AWS-FIRESTORE-COST-GUARD-READY]`
  - `[AWS-AUTH-POLL-COMPAT-READY]`
  - `[AWS-OFF-MODE-GUARD-READY]`
- Open PR scan:
  - #574 is docs-only and nonblocking for this sync lane.
  - #567 is a display-test PR and nonblocking for this sync lane.
  - dependency, theme, old Web, old license, and old branding PRs are
    nonblocking unless they become current P0/P1/security findings.
- PR #565/#566-equivalent security findings remain covered by current-main
  session-token, Firebase-token, and forbidden-field regression tests.

## Public Implementation State

- Public validates `yonerai.firestore_usage_policy.v1` and fails closed on:
  - initial query limit above 20
  - absolute list limit above 50
  - reconnect cooldown below 30 seconds
  - more than one CLI listener per account
  - non-account-rooted listener requirements
  - offset or collection-group query allowance
  - client writes
  - non-AWS body fetch source
  - projection writes while `sync_mode=off`
- Public treats `sync_mode=off` as a hard stop even if backend sync wiring is
  otherwise present.
- Firebase custom-token exchange now accepts the standard Identity Toolkit
  response where `localId` is absent, deriving the UID from the Firebase ID token
  payload in process memory only and comparing it to the canonical account scope.
- Firebase custom token, Firebase ID token, Firebase refresh token, Google token,
  auth code, provider key, account id, raw body, raw audit, and private path are
  not printed or persisted by the smoke path.

## Live Staging Smoke

- `logout -> login -> whoami`: passed before this checkpoint update.
- Staging opaque YonerAI session: accepted.
- Canonical account binding: present; value not printed.
- `GET /v1/sync/firebase-config`: ready public config observed.
- `POST /v1/sync/firebase-token`: 200.
- Firebase custom-token exchange: passed after Firebase Anonymous auth was
  enabled and Public accepted the no-`localId` Identity Toolkit response shape.
- Firebase ID token: process memory only; not persisted.
- Firebase refresh token: discarded.
- Firestore usage policy: `yonerai.firestore_usage_policy.v1`.
- Cost guard accepted:
  - initial limit 20
  - absolute limit 50
  - reconnect cooldown 30 seconds
  - max CLI listeners per account 1
- Sync remains off as expected:
  - `firestore_sync_enabled=false`
  - `sync_mode=off`
- `yonerai sync listener firestore-poll --json` stops with
  `firestore_sync_disabled_until_live_e2e_and_owner_flip` before Firestore read
  or AWS body fetch.

## Validation

- `python -m pytest tests\test_realtime_sync_client_service.py::test_firebase_custom_token_exchange_accepts_uid_from_id_token_payload -q`
  - result: 1 passed
- `python -m ruff check clients\cli\yonerai_cli\services\realtime_sync_client_service.py tests\test_realtime_sync_client_service.py`
  - result: passed
- Live staging redacted smoke:
  - result: token exchange passed, config ready, usage policy accepted, sync-off
    gate reached
- Live `yonerai sync listener firestore-poll --json`:
  - result: controlled off-mode stop before Firestore read/body fetch

## Exact Blocker

- `[PUBLIC-SYNC-SMOKE-PREPARED]` has not been sent yet after PR #578 merge.
- `[YONERAIWEB-SYNC-SMOKE-PREPARED]` is still missing from issue #552.
- `[OWNER-SYNC-SMOKE-APPROVED]` is still missing from issue #552.
- Staging currently reports `firestore_sync_enabled=false` and
  `sync_mode=off`, so Public must not claim live Web-to-CLI E2E.

## Exact Next Command

After the final issue scan confirms no newer blocker:

```powershell
@'
[PUBLIC-SYNC-SMOKE-PREPARED]

Public main HEAD: fec9b77
Contract: yonerai.realtime_sync.v1
Firebase config contract: yonerai.firebase.public_config.v1
Firebase auth contract: yonerai.firebase.custom_token.v1
Usage policy: yonerai.firestore_usage_policy.v1

Evidence:
- staging opaque YonerAI session accepted
- config ready=true
- Firebase custom-token endpoint 200
- Firebase custom-token exchange passed
- Firebase ID token process-memory only
- Firebase refresh token discarded
- listener mode=one-shot/firestore metadata poll
- initial limit 20, absolute limit 50, reconnect cooldown 30 seconds
- sync remains off: firestore_sync_enabled=false, sync_mode=off
- current blocker=sync off until owner-approved live E2E smoke

Safety:
- no token value, account id, raw body, raw audit, provider key, private path, or
  production claim is included
- no Firestore body fallback
- no AWS body fetch before a validated body-free event

This is not [PUBLIC-SYNC-CLIENT-READY].
'@ | gh issue comment 552 --body-file -
```

## Peer Tags Received/Sent

- received: `[AWS-E2E-SUPPORT-READY]`
- received: `[AWS-FIRESTORE-COST-GUARD-READY]`
- received: `[AWS-AUTH-POLL-COMPAT-READY]`
- received: `[AWS-OFF-MODE-GUARD-READY]`
- sent earlier: `[PUBLIC-SYNC-CLIENT-BLOCKED]`
- not sent yet: `[PUBLIC-SYNC-SMOKE-PREPARED]`
- not sent: `[PUBLIC-SYNC-CLIENT-READY]`
- not sent: `[WEB-TO-CLI-E2E-PASSED]`

## Non-Claims

- No production login, production sync, production cloud, or production deploy
  claim.
- No release or tag was created.
- No token value, account identifier, raw body, private path, provider key, or
  internal runtime detail is recorded here.
- `reference_clawdbot` and `src/cogs/ora.py` were not touched.
