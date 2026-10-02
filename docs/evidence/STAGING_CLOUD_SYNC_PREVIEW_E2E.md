# Staging Cloud Conversation Sync Preview E2E

Date: 2026-06-06
Status: public-safe staging E2E evidence
Backend: `https://api-staging.yonerai.com`

This evidence confirms the public YonerAI CLI can use the private staging
backend contract after staging Google login, without receiving or printing
Google tokens.

## Commands Verified

```powershell
$env:YONERAI_STAGING_AUTH_ORIGIN = "https://api-staging.yonerai.com"
yonerai auth google login --staging --bridge --open-browser --wait-linked --pretty --lang ja
yonerai auth session status --pretty --lang ja
yonerai sync status --pretty --lang ja
yonerai sync conversations --pretty --lang ja
yonerai sync conversation show <cloud_conversation_id> --pretty --lang ja
yonerai sync preview --direction cloud-to-local --audit-reason public_cli_live_e2e --pretty --lang ja
yonerai sync preview --direction local-to-cloud --audit-reason public_cli_live_e2e --pretty --lang ja
```

## Verified Results

- staging bridge start succeeded against `api-staging.yonerai.com`
- browser login linked the one-time CLI bridge request
- CLI received an opaque YonerAI staging session claim
- the session was stored through Windows DPAPI for the local test profile
- `auth session status` reported linked state without printing the session value
- `sync status` read staging status and rate-limit endpoints
- `sync conversations` returned a metadata-only cloud conversation reference
- `sync conversation show` returned only redacted metadata/summary fields
- `sync preview --direction cloud-to-local` returned an allowed preview decision
- `sync preview --direction local-to-cloud` stayed approval-required and did not call the backend

## Safety Observed

- Google access token printed: no
- Google ID token printed: no
- Google refresh token printed or stored: no
- Google auth code printed or stored: no
- provider key printed or stored: no
- raw cloud conversation body printed: no
- private/local file content uploaded: no
- local memory uploaded: no
- local node payload uploaded: no
- OpenAI shared traffic enabled: no
- production Google login enabled: no
- production Oracle/cloud runtime enabled: no

## Public Output Shape

The CLI keeps only public-safe metadata in reports:

- `auth_state`
- redacted linked-account state
- session availability and storage backend
- `session_hash`
- rate-limit header presence
- cloud conversation id/title/count/privacy class
- sync decision state and audit reason
- explicit non-actions

The CLI does not include the opaque staging session value in JSON or pretty
output.

## Limitations

- This is staging-only.
- The public repo does not implement production AWS/Oracle runtime.
- Cloud-to-local is preview only in this alpha.
- Local-to-cloud remains disabled by default and requires explicit approval.
- Production account/passkey/auth is not included.
- Production installer signing/trust store is not included.
