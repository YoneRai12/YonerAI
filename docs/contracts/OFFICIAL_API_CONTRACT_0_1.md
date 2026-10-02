# YonerAI Official API Contract 0.1

This document defines the public contract between YonerAI CLI Local Runtime and a
future official backend for yonerai.com / private YonerAIOracle work.

The public repository contains only contracts, fixtures, schemas, CLI status
surfaces, and conformance tests. It does not contain production AWS credentials,
production Oracle/cloud runtime, production Google login, production sync
storage, or production route inventory.

## Public Repo Status

- Contract and fixture only.
- `yonerai api ...` and `yonerai sync ...` expose local contract reports.
- No official backend request is made by default.
- No production OAuth flow is started.
- No local private conversation upload is performed.
- No provider keys, Google tokens, raw prompts, private files, local memory,
  local node payloads, local absolute paths, or OpenAI shared traffic are present
  in public fixtures.

## Auth Boundary

Official account auth is a future private/official lane. The public repo may
only describe and test the contract.

Required contract:

- installed-app OAuth with PKCE
- state parameter required
- loopback redirect only
- minimal scopes: `openid email profile`
- no embedded webview
- no token printed
- no plaintext refresh token storage
- public client; no client secret in the public repo
- auth states: `unauthenticated`, `dry_run`, `pending`, `linked`, `expired`,
  `revoked`

## Endpoint Contract

All endpoints use JSON request/response bodies. Every production response should
include a request id through either the response body or upstream logging, but
the public fixture does not include production request ids.

Every endpoint must define:

- auth requirement
- request schema
- response schema
- error schema
- rate-limit bucket and headers
- privacy boundary
- public repo support state

| Method | Path | Auth | Rate bucket | Public repo support |
| --- | --- | --- | --- | --- |
| `GET` | `/v1/status` | anonymous allowed | anonymous | fixture only |
| `GET` | `/v1/account/me` | account required | authenticated | fixture only |
| `GET` | `/v1/rate-limit` | account or device | authenticated | fixture only |
| `GET` | `/v1/conversations` | account required | user_quota | fixture only |
| `POST` | `/v1/sync/preview` | account required | cloud_contract | fixture only |
| `POST` | `/v1/sync/approve` | account required | cloud_contract | fixture only |
| `POST` | `/v1/oracle/runs` | account required | oracle_queue | fixture only |
| `GET` | `/v1/oracle/runs/{run_id}` | account required | oracle_queue | fixture only |
| `POST` | `/v1/evolve/proposals` | account required | user_quota | fixture only |
| `GET` | `/v1/evolve/proposals` | account required | user_quota | fixture only |

`GET /v1/status` is further specified by
`docs/contracts/STATUS_API_CONTRACT_0_1.md` so that YonerAI CLI,
status.yonerai.com, and the future private/AWS backend consume the same
public-safe status component/feed shape.

Schema files live under:

- `docs/contracts/schemas/official-api-contract-0.1.schema.json`
- `docs/contracts/schemas/official-api-0.1/*.schema.json`

Fixture file:

- `docs/contracts/fixtures/official-api-contract-0.1.fixture.json`

## Error Contract

Errors must use:

```json
{
  "ok": false,
  "error": {
    "code": "quota_exceeded",
    "message": "Quota exceeded.",
    "retry_after": 60,
    "request_id": "optional-request-id"
  }
}
```

`retry_after` is a required key on every error object so CLI/TUI consumers can
handle quota responses uniformly. It must contain a retry delay for quota
exceeded responses and may be `null` for non-quota errors.

## Rate-Limit Headers

Official backend responses should expose these headers where applicable:

- `Retry-After`
- `X-YonerAI-RateLimit-Limit`
- `X-YonerAI-RateLimit-Remaining`
- `X-YonerAI-RateLimit-Reset`
- `X-YonerAI-RateLimit-Bucket`

Required buckets:

- `anonymous`
- `authenticated`
- `user_quota`
- `device_quota`
- `provider_quota`
- `cloud_contract`
- `oracle_queue`
- `abuse`

If cloud quota is exceeded, the CLI should explain the reason and fall back to
local mock or loopback provider behavior when safe. It must not claim free
OpenAI usage or shared traffic eligibility.

## Sync Boundary

Objects named by this contract:

- `CloudConversationRef`
- `LocalConversationRef`
- `SyncEnvelope`
- `SyncDirection`
- `SyncDecision`
- `SyncAudit`

Rules:

- `cloud_to_local` is allowed only after account link and user-selected cloud
  conversation.
- `local_to_cloud` is disabled by default.
- `local_to_cloud` requires explicit approval plus an audit reason.
- `local_private`, `local_only`, and `secret_like` content cannot sync.
- private file content, local memory, local node payloads, raw prompts, provider
  keys, and local absolute paths are excluded by default.
- every sync decision has an audit reason.
- public fixtures cannot carry raw private content.

## Oracle Run Boundary

`POST /v1/oracle/runs` is a contract for official/private implementation only.
The public repo may generate a request envelope shape and validate privacy
classification, but it must not run production Oracle, upload private payloads,
or expose control-plane internals.

Private file content and local node payloads must not be sent to
`cloud_contract_candidate` or official Oracle fixtures. Public tasks may use
hashes or low-resolution summaries only when explicitly allowed by policy.

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

## CLI Surfaces

Users can inspect the public contract with:

```powershell
yonerai api status --pretty --lang ja
yonerai api contract --json
yonerai api rate-limit --pretty --lang ja
yonerai sync status --pretty --lang ja
yonerai sync preview --direction cloud-to-local --json
yonerai sync approve --dry-run --direction local-to-cloud --json
yonerai sync api-contract --json
yonerai sync rate-limit --json
```

Interactive aliases:

- `/API`
- `/公式`
- `/sync`
- `/同期`
- `/privacy`
- `/プライバシー`

These commands do not upload local content, contact an official backend, perform
production OAuth, or call production Oracle.

## Non-Claims

Do not claim:

- production Official Managed Cloud is runnable from this public repo
- production AWS backend is included here
- production Oracle is implemented here
- production Google login is complete
- local private conversations sync up automatically
- persistent memory/cloud memory is complete
- OpenAI shared traffic is enabled
- npm, winget, or production installer is ready
- live Discord is restored
