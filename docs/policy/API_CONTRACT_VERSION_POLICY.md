# YonerAI API Contract Version Policy

Status: public policy for staging/public CLI contract compatibility.

This policy pins the v0.14 Official API contract family as the public compatibility
baseline for the CLI Control Spine dogfood lane. It does not enable production
Google login, production Oracle/cloud runtime, provider-key storage, OpenAI
shared traffic, or automatic private-content upload.

## 1. Contract Baseline

- Public CLI baseline: `yonerai-official-api-contract/v0.14`.
- Staging health endpoint: `GET /v1/health`.
- Health response fields used by the CLI:
  - `api_version`
  - `min_cli_version`
  - optional `contract_version`
- The CLI may warn on version skew, but it must not print private runtime
  inventory, internal hostnames, tokens, local paths, or stack traces.

## 2. Compatibility Window

- A staging backend should support at least the latest public prerelease contract
  and the latest stable CLI contract unless a security advisory says otherwise.
- Backward-incompatible response changes require a new `api_version` and a
  `min_cli_version` bump in `/v1/health`.
- The CLI warning path is:
  - show current CLI version
  - show backend `api_version`
  - show backend `min_cli_version`
  - suggest `yonerai update check`
  - never auto-update or silently disable local-only features

## 3. Production Login Graduation Gate

Production Google login is not an incremental toggle in the public CLI.

Before `yonerai login --no-staging` or production login can be accepted, a
separate PR must provide a Graduation Gate packet with:

- Google OAuth verification approved for the production domain.
- Separate staging and production client configuration.
- No Google client secret in the public repo.
- No Google access token, refresh token, ID token, auth code, or session secret
  printed to CLI output, config, logs, ledger, release notes, or tests.
- Refresh-token persistence either disabled or moved to an approved secure store
  design with threat-model review.
- Private/local memory, local files, and local-node data excluded from upload by
  default.
- A rollback path and account/session revocation path.
- Quality Wall tests proving token custody, URL validation, session expiry, and
  production/staging separation.

Until that packet lands, public CLI production login remains rejected.

## 4. Dangerous Scope Freeze

These scopes are not issued by default in dogfood:

- `agent:run`
- `admin:*`

Any use of those scopes requires a separate threat-model gate and explicit owner
approval. If a staging backend accidentally advertises them as default-enabled,
the public CLI must display them as disabled and `requires_threat_model`.

## 5. Deprecation Rule

- Deprecation notices are advisory unless a separate security policy marks a
  version as unsafe.
- Critical backend policies may block only live/cloud/provider-sensitive
  features. Basic local mock chat and local-only diagnostics must remain usable.
- The public CLI must prefer clear Japanese guidance for Japanese language mode,
  with no raw stack trace.

