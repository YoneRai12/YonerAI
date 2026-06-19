# YonerAI StatusSnapshot v1

StatusSnapshot v1 is the public-safe status shape shared by Public CLI, AWS staging, and StatusWEB.

## Canonical Schema

- Schema file: `docs/contracts/status_snapshot.v1.schema.json`
- Schema version: `yonerai.status.v1`
- Current staging endpoint: `GET https://api-staging.yonerai.com/v1/status`
- Legacy compatibility may remain on the same response, but consumers should prefer `schema_version=yonerai.status.v1`.
- The schema validates the canonical public StatusSnapshot projection, not any mixed legacy transport envelope.
  If a response contains both v1 fields and legacy compatibility fields, public consumers must render only the
  v1 projection or a `public_status` projection and must ignore/drop legacy private runtime fields.

## Required Fields

- `schema_version`
- `snapshot_id`
- `generated_at`
- `stale_after_seconds`
- `overall`
- `components`
- `private_runtime_details_included=false`

`overall` and each component use separate axes:

- `health`: `operational`, `degraded`, `partial_outage`, `major_outage`, `maintenance`, `offline`, `unknown`
- `availability`: `available`, `limited`, `unavailable`
- `stage`: `preview`, `staging`, `production`, `disabled`

`not_production` is not a `health` value. If a backend is not production, it must use `stage=staging` or `stage=preview` plus a clear message.

## Canonical Components

- `api`
- `auth`
- `provider_gateway`
- `official_execution_worker`
- `run_queue`
- `realtime_sync`
- `web`
- `audit`
- `discord`

Unknown future components may be read by the CLI when they are public-safe, but they are not treated as canonical until this document and schema are updated.

## Worker Liveness Rule

Official worker liveness is cloud-derived. Worker self-report is advisory.

If heartbeat freshness exceeds `stale_after_seconds`, the worker component must be:

- `health=offline`
- `availability=unavailable`
- `stale=true`

Provider gateway health is independent from worker liveness. A stale worker must not make provider gateway appear down if provider dispatch remains available and consent-gated.

## Public Safety Boundary

StatusSnapshot v1 must not include:

- account-scoped data
- run contents
- conversation metadata
- provider prompts or outputs
- audit detail
- internal notes
- secret identifiers
- project IDs
- hostnames or IPs
- local paths
- worker PC identity
- AWS ARNs
- emails or account details

Status may include short public messages, component IDs, component health, stage, availability, stale flag, generated time, and cache metadata.

Legacy compatibility fields are not automatically accepted for public rendering. In particular, any legacy
`status_snapshot` field that contains worker identity hashes, queue inventory, hostnames, internal paths,
or other runtime inventory is outside StatusSnapshot v1 and must not be displayed, cached, copied into
StatusWEB, or treated as schema-approved public data.

## Cache Rule

AWS/StatusWEB may use ETag and short public cache headers. `Cache-Control: max-age` must be lower than `stale_after_seconds`. Stale handling remains explicit in the payload.

## CLI Commands

```powershell
yonerai status
yonerai status --json
yonerai status --pretty --lang ja
yonerai status component official_execution_worker --pretty --lang ja
```

The CLI fails closed if a status source contains private endpoints, tokens, local paths, AWS ARNs, account details, or worker identity markers.
