# Status Integration Decision

## Decision

Public YonerAI owns the canonical public status schema and client behavior. Private AWS owns runtime truth. StatusWEB owns rendering.

The accepted public schema is `yonerai.status.v1`.

## Acceptance Rules

1. Public consumers must prefer `schema_version=yonerai.status.v1`.
2. Legacy fields may remain for older consumers, but they are compatibility fields only.
   They are not approved public rendering fields when they contain runtime inventory such as worker hashes,
   queue internals, hostnames, internal paths, or private endpoint detail.
3. A mixed live response may include a canonical v1 projection plus legacy compatibility fields.
   StatusSnapshot v1 schema validation applies to the canonical public projection, not to the full mixed envelope.
4. StatusWEB must render from canonical v1 fields or a `public_status` projection, not from raw legacy
   `status_snapshot` internals.
5. `not_production` is not a health value.
6. Worker availability is derived from cloud heartbeat freshness. Stale heartbeat becomes `offline`.
7. Provider gateway is evaluated separately from worker liveness.
8. Canonical public status payloads must not contain secrets, private endpoints, account details, worker PC identity, AWS ARNs, local paths, provider prompts/outputs, run contents, conversation metadata, or audit detail.
9. Public CLI must not call worker endpoints. It may read account-scoped run status only through public account-auth APIs.
10. Cache headers are allowed only when the payload remains explicitly stale-aware.

## Accepted AWS Compatibility

AWS may keep legacy `contract_version=yonerai.status.feed.v0.2` fields while also serving `schema_version=yonerai.status.v1`.

StatusWEB should render from v1 fields first:

- `overall.health`
- `overall.availability`
- `overall.stage`
- `components[].health`
- `components[].availability`
- `components[].stage`
- `components[].stale`

## Non-Claims

This does not claim production Oracle, production cloud, production Google login, live Discord, provider key custody, or production installer trust.
