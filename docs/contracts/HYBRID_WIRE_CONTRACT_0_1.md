# Hybrid Wire Contract v0.1

Hybrid Wire Contract v0.1 defines the public-safe shape exchanged between
YonerAI official orchestration and a user-owned Local Node. It is a contract and
dev-fixture surface only. It does not implement production Oracle, Official
Managed Cloud runtime, production signing keys, production trust stores, live
Discord, deployment, arbitrary shell access, or arbitrary file access.

## Scope

Public repo scope:

- define stable wire payload names and fields
- expose a loopback/dev-fixture Local Node status
- expose a dry-run pairing preview
- let route preview consume safe Local Node fixture state
- test that no raw prompt, secret, provider key, or local path enters wire
  payloads

Private/official scope:

- production signing keys
- production trust store
- key rotation
- official orchestration service
- production Oracle/control-plane implementation
- live Local Node transport and deployment

## Wire Schemas

All payloads use `schema_version: yonerai-hybrid-wire-contract/v0.1` at report
level and include a `schema_name` when the payload is an individual wire object.

- `LocalNodeHello`: Local Node identity, mode, loopback-only flag, and
  non-production/public-trust boundary.
- `LocalNodeHeartbeat`: synthetic health heartbeat for the dev fixture.
- `LocalNodeCapabilityManifest`: Local Node capability list and trust flags.
- `LocalNodeSessionRef`: public-safe session reference. It is not a bearer token.
- `LocalNodeRunEnvelope`: run request summary for Local Node work. It does not
  include raw prompts, provider keys, or local paths.
- `LocalNodeRunResult`: result summary from Local Node work. It does not include
  raw results or local paths.
- `LocalNodeError`: public-safe error code/message. It excludes raw exception
  detail.
- `OfficialOrchestrationStubRequest`: dry-run request shape for future official
  orchestration. It explicitly reports that official cloud runtime and
  production Oracle are not implemented here.

## Capability Manifest

The v0.1 dev fixture declares:

| Capability | Enabled | Approval | Route capability | Notes |
| --- | --- | --- | --- | --- |
| `local_model` | yes | required | `local_tools` | Loopback-only local model execution contract. |
| `workspace_file_access` | yes | required | `private_files` | Explicit selected workspace file only. |
| `mock_search` | yes | not required | `local_tools` | Mock fixture only; no live web search by default. |
| `tool_boundary` | yes | required | `local_tools` | Boundary planning only; no arbitrary shell. |
| `ledger` | yes | not required | `local_tools` | Redacted local run ledger reference. |
| `dangerous_operation` | no | required | `dangerous_operations` | Disabled in public repo. |

## Trust And Session Rules

The public evaluator returns one of these states:

- `missing_node`: no Local Node fixture is present.
- `unverified_node`: node or session uses unsupported public trust material or
  lacks test verification.
- `verified_test_node`: non-production test node is verified for preview.
- `expired_session`: session is missing or not active.
- `revoked_session`: session was revoked.
- `capability_not_declared`: requested capability is absent from manifest.
- `approval_required`: requested capability is disabled or requires owner
  approval.

`execute_allowed` is always `false` in this public contract. A verified test node
can make route preview more specific, but it does not authorize execution.

## CLI Surface

```powershell
yonerai node status --json
yonerai node pair --dry-run --json
yonerai route preview "read selected workspace file" --mode official_hybrid_private --capability workspace_file_access --use-local-node-fixture
```

These commands are local and non-mutating. They do not call live providers,
official cloud, Oracle, Discord, deployment systems, network installers, or
arbitrary shell/file surfaces.

## Conformance

Conformance is covered by:

- `tests/test_hybrid_wire_contract.py`
- `tests/test_three_mode_route_preview.py`
- `tests/test_surface_cli_smoke.py`

The tests verify Local Node fixture shape, official stub shape, unknown
capability denial, dangerous operation approval requirements, route preview node
state consumption, and public-safe wire payload redaction.
