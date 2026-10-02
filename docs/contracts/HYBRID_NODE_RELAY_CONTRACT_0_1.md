# Hybrid Node/Relay Contract v0.1

This contract defines the public-safe shape that a future Official Hybrid
Private orchestration service can consume from a user-owned Local Node and a
local-dev Relay. It is not a production cloud implementation.

## Public Repository Scope

The public repo may provide:

- Hybrid Wire Local Node fixture status
- Relay local-dev fixture status
- one-time pairing and hash-only token characterization tests
- route preview inputs derived from the Local Node fixture
- doctor/demo output that shows readiness and boundaries
- contract-only official cloud consumption shape

The public repo must not provide:

- production Oracle/control-plane behavior
- Official Managed Cloud runtime
- production signing keys or production trust stores
- release signing service or key rotation operations
- live Discord token usage
- public tunnel startup by default
- message body persistence
- plaintext session token output in status surfaces
- deploy, installer execution, arbitrary shell, or arbitrary file access

## Contract Stub

The public contract stub uses:

```text
schema_version: yonerai-hybrid-node-relay-contract/v0.1
public_repo_scope: contract_and_local_dev_fixture
official_cloud_runtime_implemented: false
production_oracle_used: false
network_required: false
```

It combines:

- `yonerai-hybrid-wire-contract/v0.3`
- `yonerai-relay-status/v0.1`

## CLI Surfaces

```powershell
yonerai node status --pretty
yonerai node pair --dry-run --pretty
yonerai relay status --pretty
yonerai route preview "read selected workspace file" --mode official_hybrid_private --capability workspace_file_access --use-local-node-fixture
yonerai doctor --pretty
yonerai demo --pretty
```

These commands are local and non-mutating. `yonerai relay status` does not start
Relay, start the Node connector, probe the network, start Cloudflare, open a
public tunnel, print pairing codes, print session tokens, or persist message
bodies.

## Future Private/Official Lane

Production Hybrid work belongs in a private or official lane:

- production signing key lifecycle
- production trust store
- official orchestration service
- production Oracle/control-plane implementation
- hosted status ingestion
- durable audit/event storage policy
- deployment and operating runbooks
