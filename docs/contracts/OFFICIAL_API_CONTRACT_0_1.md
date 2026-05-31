# YonerAI Official API Contract 0.1

This document defines the public contract between YonerAI CLI Local Runtime and a
future official backend such as yonerai.com or a private YonerAIOracle service.
The public repository does not include production Oracle, production account
backend, production Google login, or production sync storage.

## Current Public Repo Status

- Contract and fixture only.
- CLI commands may show status, preview sync decisions, and run approval dry-runs.
- No official backend request is made by default.
- No local private conversation uploads are performed.
- No provider keys, Google tokens, raw prompts, private files, local memory, or
  local node payloads are included in public fixtures.
- OpenAI shared traffic remains disabled by default.

## Account Identity Contract

The public contract names these objects:

- `AccountIdentity`
- `GoogleAuthSessionContract`
- `LocalUserProfile`
- `CloudAccountLinkState`

Google auth requirements:

- installed-app OAuth with PKCE
- state parameter required
- loopback redirect only
- minimal scopes: `openid email profile`
- no embedded webview
- no plaintext refresh token storage
- no production login in the public repo

Auth states:

- `unauthenticated`
- `dry_run`
- `pending`
- `linked`
- `expired`
- `revoked`

## Sync Boundary

The public contract names these objects:

- `CloudConversationRef`
- `LocalConversationRef`
- `SyncEnvelope`
- `SyncDirection`
- `SyncDecision`
- `SyncAudit`

Allowed directions:

- `cloud_to_local`: allowed only after account link and user-selected cloud
  conversation.
- `local_to_cloud`: disabled by default and requires explicit approval plus an
  audit reason.

Excluded by default:

- private file content
- local memory records
- local node payloads
- raw prompts and raw conversation bodies
- provider keys and secrets
- local absolute paths

Every sync decision must include an audit reason. A signed or authenticated
envelope proves origin and integrity only; it does not imply user approval.

## Official API Endpoints

The future official backend is expected to expose:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/account/me` | Return linked account summary. |
| `GET` | `/v1/conversations` | List user-selected cloud conversation refs. |
| `POST` | `/v1/sync/preview` | Preview sync decision and audit reason. |
| `POST` | `/v1/sync/approve` | Record explicit sync approval. |
| `POST` | `/v1/oracle/runs` | Enqueue an official Oracle run request. |
| `GET` | `/v1/oracle/runs/{id}` | Read official Oracle run result envelope. |
| `GET` | `/v1/rate-limit` | Read quota and local fallback state. |
| `GET` | `/v1/status` | Read official service status. |

Public repo behavior:

- endpoint schema and fixtures only
- no production backend handlers
- no deploy target
- no production route or host inventory

## Rate Limit and Quota Policy

The public contract separates:

- user quota
- device quota
- provider quota
- shared/free traffic policy
- abuse prevention
- local fallback when cloud quota is exceeded

The public repo does not claim free OpenAI usage, owner/org eligibility, or
shared traffic availability. If official quota is exceeded, CLI should fall back
to mock/local loopback provider behavior or deny the unsafe operation.

## Official-Only Self-Evolution Boundary

Public repo:

- proposal-only
- synthetic low-resolution signals only
- no raw prompts
- no PII
- no real telemetry ingestion
- no automatic PR, merge, release, or deploy

Private/official lane:

- official signal ingestion
- support feedback
- owner approval console
- patch candidate queue
- rollback plan
- release and X post draft generation

## Commands

Users can inspect the public contract with:

```powershell
yonerai auth status --pretty --lang ja
yonerai privacy status --pretty --lang ja
yonerai sync status --pretty --lang ja
yonerai sync preview --direction cloud-to-local --json
yonerai sync approve --dry-run --direction local-to-cloud --json
yonerai sync api-contract --json
yonerai sync rate-limit --json
```

These commands do not upload local content, contact an official backend, perform
production OAuth, or call production Oracle.

## Non-Claims

Do not claim:

- production Official Managed Cloud is runnable from this public repo
- production Oracle is implemented here
- production Google login is complete
- local private conversations sync up automatically
- persistent memory is complete
- OpenAI shared traffic is enabled
- npm, winget, or production installer is ready
- live Discord is restored
