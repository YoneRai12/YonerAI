# Staging Google Login E2E Evidence

Date: 2026-06-06

Status: public-safe evidence for staging only

Backend origin: `https://api-staging.yonerai.com`

## Summary

The private YonerAIOracle staging backend completed the Google OAuth browser
flow and the public YonerAI CLI bridge reached linked state through the staging
origin. This evidence is safe to publish because it does not include a Google
client secret, Google access token, refresh token, authorization code, raw
request id, private path, or unredacted account email.

This is not production Google login. Production login, production AWS/Oracle
runtime, account sync, local private upload, OpenAI shared traffic, live
Discord, and production signing/trust remain out of scope.

## Command

```powershell
$env:YONERAI_STAGING_AUTH_ORIGIN = "https://api-staging.yonerai.com"
yonerai auth google login --staging --bridge --open-browser --wait-linked --pretty --lang ja
```

## E2E State Transition

| Step | Observed staging result | Public-safe boundary |
| --- | --- | --- |
| Status check | `GET /v1/status` returned `200` with staging `not_production` status. | No production claim. |
| Rate-limit check | `GET /v1/rate-limit` returned `200` with YonerAI rate-limit headers. | Contract visibility only. |
| Unauthenticated account check | `GET /v1/account/me` without staging session returned controlled `401`. | No anonymous profile leak. |
| CLI bridge start | `POST /auth/cli/start` returned a one-time browser start URL and poll path. | No token or auth code returned to CLI. |
| Browser login | Google staging browser login completed and callback UI rendered completion. | Browser-side OAuth only; public CLI did not receive Google tokens. |
| CLI bridge poll | `GET /auth/cli/poll/{request_id}` reached linked state. | Request id omitted from this public evidence. |
| Account profile | `GET /v1/account/me` with the staging session claim returned authenticated `200` and minimal profile. | Email is redacted; no Google token returned or stored. |

## Verified Security Boundary

- Google client secret in public repo: no
- Google access token returned to public CLI: no
- Google ID token returned to public CLI: no
- Google refresh token returned to public CLI: no
- Authorization code printed by public CLI: no
- Refresh token persistence: disabled
- Staging session token printed: no
- Staging session token stored: no
- Redacted YonerAI staging account claim storage: yes
- Production Google login enabled: no
- Account sync enabled: no
- Local private memory or file upload: no
- OpenAI shared traffic enabled: no
- Production Oracle/cloud runtime: no

## Public CLI Evidence

The public CLI stores only a redacted YonerAI staging account claim when the
linked state is validated through `GET /v1/account/me`. The stored claim is a
local display/status claim, not a Google credential and not a staging session
secret.

The staging bridge now also fails closed if the backend accidentally returns
token-like parameters in bridge paths, including URL query strings and URL
fragments.

## Limitations

- This is an alpha prerelease evidence slice.
- The staging backend is private and owner-operated.
- Production Google login is not enabled.
- Production passkeys/account runtime is not included.
- Production cloud sync is not included.
- The public CLI does not upload local private memory, local files, or local
  node content.
- `src/cogs/ora.py` remains a legacy boundary.
- `reference_clawdbot` is not touched.
