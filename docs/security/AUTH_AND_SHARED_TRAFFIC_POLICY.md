# YonerAI Auth and Shared Traffic Policy Foundation

Status: public contract foundation, not production auth.

This document defines the public-repo boundary for Google OAuth and OpenAI
shared traffic. It is intentionally conservative so weaker agents cannot
accidentally enable production login, token storage, or shared provider traffic.

## Google OAuth CLI Contract

Current public command:

```powershell
yonerai auth status --pretty
yonerai auth google login --dry-run --pretty
```

What it does:

- Reports whether a Google OAuth client id is locally configured.
- Describes an installed-app OAuth flow using PKCE.
- Requires a loopback-only redirect URI such as
  `http://127.0.0.1:8765/oauth/google/callback`.
- Requires a state parameter.
- Limits the planned scopes to `openid email profile`.
- Shows that browser launch, token exchange, and token storage are not
  performed in this public lane.

What it does not do:

- It does not start live OAuth.
- It does not open a browser.
- It does not use an embedded webview.
- It does not print tokens.
- It does not store refresh tokens.
- It does not accept or store provider API keys.
- It does not enable production Google login.

If the OAuth client is missing, the CLI returns a controlled error and still
prints the non-action boundary. That is expected until an owner-approved auth
lane provides official/private credentials and storage policy.

## OpenAI Shared Traffic Policy

Current public command:

```powershell
yonerai privacy status --pretty
```

Default state:

- OpenAI shared traffic is off.
- Runtime shared traffic is not implemented in the public repo.
- A user can record explicit intent in local config, but that does not enable
  traffic.
- No free usage is claimed.
- Owner or organization eligibility is not assumed.

Allowed future shape:

- Only public/safe prompts may be eligible.
- Private prompts, workspace-local file content, local memory records, local
  node payloads, provider keys, and secrets must be excluded.
- The run ledger must record `shared_traffic=false` by default and may record a
  future explicit opt-in flag without storing raw private content.
- Daily quota and rate limit checks must exist before shared traffic can be
  enabled.

Disallowed in this public repo:

- No shared OpenAI traffic by default.
- No private/local file/memory/local node content in shared traffic.
- No provider key storage.
- No telemetry ingestion of prompts or completions.
- No claim that YonerAI provides free OpenAI usage unless the account and
  program eligibility are explicitly verified.

## Release and CI Boundary

The CI quality wall should keep these checks active:

- Google OAuth dry-run only.
- Loopback redirect only.
- No token or client secret output.
- OpenAI shared traffic disabled by default.
- Private content exclusion active.
- Ledger records shared traffic as disabled.
- Release gate blocks missing manifests, unversioned assets, SHA256 mismatch,
  prerelease/stable mismatch, production overclaims, and unresolved
  P0/P1/security blocker markers.
