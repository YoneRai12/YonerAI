# YonerAI Production Graduation Gate

Status: gate definition only. This document does not approve production Google
login, production Oracle/cloud runtime, production account sync, provider-key
storage, or OpenAI shared traffic.

## 1. Purpose

Production acceptance for public CLI account login must not happen by gradually
flipping staging flags. It requires a dedicated future PR with owner approval,
Google verification evidence, threat-model review, and Quality Wall coverage.

## 2. Current Public State

- `yonerai login` is staging-only.
- `yonerai login --no-staging` is rejected.
- The public CLI must not store Google access tokens, Google ID tokens, Google
  auth codes, or refresh tokens.
- The public CLI may store only the approved opaque YonerAI staging session
  claim.
- Local private files, local private memory, and local node content must not
  upload automatically.

## 3. Production Login Graduation Gate

A future production-login PR must include all of the following before
`login --no-staging` can be accepted:

- Google OAuth verification approved for the production domain.
- Separate staging and production client configuration.
- No Google client secret in the public repository.
- No Google access token, ID token, refresh token, auth code, provider key, or
  session secret printed to CLI output, config, logs, ledger, release notes, or
  tests.
- Refresh-token persistence either disabled or moved to an approved secure-store
  design with threat-model review.
- Session expiry, revoke, logout, and re-login UX in Japanese and English.
- Private/local memory, local files, and local-node content excluded from upload
  by default.
- OpenAI shared traffic off by default.
- `agent:run` and `admin:*` disabled by default unless a separate threat-model
  gate approves them.
- Rollback plan and incident response plan.
- Quality Wall tests for token custody, URL validation, session expiry,
  production/staging separation, private-content exclusion, and no local path
  leakage.

Until a future PR satisfies this section, production login remains unavailable.

## 4. Non-Claims

This document is not evidence that production Google login, Official Managed
Cloud, production Oracle, live Discord, passkeys, persistent cloud memory, or a
production installer are complete.
