# Hybrid Wire Contract v0.3

Hybrid Wire Contract v0.3 extends the public-safe Local Node fixture with
status, lease, audit, and hash-only session fields. It remains a contract and
dev-fixture surface only. It does not implement production Oracle, Official
Managed Cloud runtime, production signing keys, production trust stores, live
Discord, deployment, arbitrary shell access, arbitrary file access, or network
installer behavior.

## Compatibility

Reports use:

```text
schema_version: yonerai-hybrid-wire-contract/v0.3
compatible_versions:
  - yonerai-hybrid-wire-contract/v0.1
  - yonerai-hybrid-wire-contract/v0.2
  - yonerai-hybrid-wire-contract/v0.3
```

v0.3 is additive over the public fixture shape. Consumers should continue to
treat all public repo decisions as preview-only because `execute_allowed` remains
`false`.

## Added Fields

Local Node status now reports:

- lease identity and expiry metadata
- hash-only session token representation
- message body persistence set to `false`
- audit event schema `hybrid-wire-audit/v0.3`

Wire object additions:

- `LocalNodeHello`: `status`, `lease_required`, `audit_log_required`
- `LocalNodeHeartbeat`: `status`, `lease_id`, `lease_expires_at`,
  `audit_cursor`, `message_body_persisted`
- `LocalNodeCapabilityManifest`: `manifest_status`, `lease_policy`,
  `audit_event_schema`, `message_body_persistence`
- `LocalNodeSessionRef`: `lease_id`, `lease_expires_at`, `token_hash`,
  `token_hash_algorithm`, `bearer_token_hash_only`,
  `message_body_persisted`
- `LocalNodeRunEnvelope`: `created_at`, `lease_id`, `audit_event_id`,
  `audit_summary`, `message_body_persisted`
- `LocalNodeRunResult`: `completed_at`, `audit_event_id`,
  `message_body_persisted`
- `LocalNodeError`: `status`, `audit_event_id`

## Trust Hardening

The public evaluator denies preview trust when:

- the manifest is missing or unverified
- the session reference is missing, expired, revoked, or unverified
- the session reference does not bind to the evaluated manifest and node
- duplicate capability names are present
- the requested capability is not declared
- the requested capability requires owner approval

The evaluator never allows execution in the public contract. Verified fixture
state only improves route preview.

## Public-Safe Boundary

The conformance checks reject wire payloads that include raw prompts, provider
keys, bearer tokens, secret-like values, local paths, or cyclic structures that
would otherwise break recursive validation. Session token material is represented
as a test hash only; plaintext tokens are not emitted.

## CLI Surface

```powershell
yonerai node status --json
yonerai node status --pretty
yonerai node pair --dry-run --json
yonerai node pair --dry-run --pretty
yonerai route preview "read selected workspace file" --mode official_hybrid_private --capability workspace_file_access --use-local-node-fixture
yonerai demo --json
```

These commands are local and non-mutating. They do not start a relay, open a
public tunnel, call live providers, connect to Official Managed Cloud, connect to
Oracle, connect to Discord, deploy, install packages, mutate PATH, or execute
remote scripts.

## Conformance

Conformance is covered by:

- `tests/test_hybrid_wire_contract.py`
- `tests/test_three_mode_route_preview.py`
- `tests/test_surface_cli_smoke.py`
- `tests/test_public_demo_script.py`
