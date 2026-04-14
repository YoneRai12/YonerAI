# Distribution Node MVP

This lane is intentionally narrow.

- It does not widen the dirty runtime lane.
- It does not touch `src/cogs/ora.py`.
- It does not add arbitrary shell / arbitrary SQL / arbitrary file write / control-plane execution.
- It keeps the shared internal contract fixed to:
  - `POST /v1/messages`
  - `GET /v1/runs/{run_id}/events`
  - `POST /v1/runs/{run_id}/results`

## Release Verification

The current MVP uses a pinned Ed25519 verification path instead of a larger TUF/Sigstore rollout.
It is real verification, but intentionally small:

- release manifest
- signed metadata
- provenance record
- capability manifest digest binding
- freshness expiry
- rollback check against the last trusted version

When `ORA_DISTRIBUTION_NODE_ENABLE=1`, startup fails closed unless all of these are present and valid:

- `ORA_DISTRIBUTION_CAPABILITY_MANIFEST`
- `ORA_DISTRIBUTION_RELEASE_MANIFEST`
- `ORA_DISTRIBUTION_RELEASE_PROVENANCE`
- `ORA_DISTRIBUTION_RELEASE_SIGNATURE`
- `ORA_DISTRIBUTION_RELEASE_PUBLIC_KEY`
- `ORA_DISTRIBUTION_RELEASE_ARTIFACT`

Trusted version state is stored at:

- `ORA_DISTRIBUTION_RELEASE_STATE`
- default: `data/distribution_node_release_state.json`

## Capability Policy

Capability manifest schema:

- `schema_version = yonerai-distribution-capabilities/v1`
- `profile = distribution_node_mvp`
- `default_action = deny` only
- `capabilities = { "<capability>": true|false }`

Tracked default-safe manifest:

- `config/distribution/distribution_node_capabilities.json`

Dangerous capabilities stay closed unless explicitly declared.
Undeclared tool capabilities are rejected.

## Files Contract

Run events may expose file refs only.
They must not expose raw bytes.

Minimal files API:

- `POST /v1/files/{file_id}/download-url`
- `GET /v1/files/download/{ticket}`

Rules:

- authenticated owner check at ticket issuance when Distribution Node mode is enabled
- short-lived URL
- single-use ticket
- `Cache-Control: no-store`
- audit row for ticket issue and download
- run event streaming and continuation result submission are also owner-scoped when Distribution Node mode is enabled

Schema note:

- the MVP adds file/ticket/audit tables in `core/src/ora_core/database/models.py`
- the current Alembic revision also bootstraps the `tool_calls` prerequisite when upgrading from the older minimal revision chain
- clean init: `python scripts/init_core_db.py`
- existing database: `cd core && alembic upgrade head`
- Alembic now resolves the same root `.env` / `ORA_BOT_DB` target as the runtime session config
- if Alembic CLI is unavailable in a local env, use the repo revision smoke test to validate revision shape, but do not assume `upgrade head` has been execution-verified there
- apply the schema through the repo's DB init/migration flow before enabling the lane on an existing database
- this change does not auto-mutate a live operational database

## Signed Release Creation

Existing archive flow remains:

```powershell
python scripts/create_release.py 2026.4.10
```

Signed metadata can be generated on top of the same archive flow:

```powershell
$env:ORA_DISTRIBUTION_RELEASE_PRIVATE_KEY="<base64-ed25519-private-key>"
python scripts/create_release.py 2026.4.10 --sign-release
```

Artifacts are written under:

- ZIP: repo root
- signed metadata: `artifacts/releases/<version>/`

## Upgrade Path

This MVP is deliberately smaller than a full TUF/Sigstore rollout.
The intended next hardening steps are:

- multiple trusted root keys
- threshold signatures
- explicit root/key rotation metadata
- transparency log or Sigstore-style provenance attestation
- staged metadata roles instead of a single signed envelope
