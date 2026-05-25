# Hybrid to Oracle Implementation Plan

Status: active public-repo implementation plan

Owner lane: public YonerAI contract and local-dev fixture. Private YonerAIOracle must implement the official control-plane runtime later.

## Purpose

This plan turns the current Hybrid local-dev fixture into an Oracle-ready contract and conformance surface. The public repo must prove local-dev behavior, schema boundaries, and routing decisions without implementing production Oracle, official cloud runtime, production trust stores, live Discord, deployment, arbitrary shell, or arbitrary file access.

## Non-goals

- No production Oracle runtime.
- No official managed cloud runtime in this public repo.
- No production signing key or production trust store.
- No live Discord token or gateway connection.
- No public tunnel, deployment, or remote execution.
- No provider key requirement in tests or default CLI paths.
- No arbitrary shell, arbitrary file read, or uncontrolled tool execution.
- No claim that Hybrid, Oracle, Discord, installer, persistent memory, or cloud runtime is complete.

## Current Public Baseline

- `core/src/ora_core/hybrid/transport.py` has an in-memory local-dev relay transport with loopback-only reporting, hash-only token state, body hash reporting, heartbeat timeout, session expiry, revocation, and controlled errors.
- `core/src/ora_core/hybrid/local_node_enrollment.py` has test enrollment, pairing-code hashing, one-time pairing challenge consumption, session token hash storage, heartbeat state, revoke, expiry, and capability decisions.
- `core/src/ora_core/hybrid/local_node_action_envelope.py` has signed local node action envelope verification with session/manifest binding, args hash, expiry, nonce replay protection, and approval-required output.
- `core/src/ora_core/hybrid/node_posture.py` reduces exposed capabilities based on verified, limited, recovery, quarantined, and revoked posture states.
- `core/src/ora_core/hybrid/extension_manifest.py` denies duplicate, unknown, and overbroad extension capability declarations and keeps extension execution disabled.
- `core/src/ora_core/route_preview.py` exposes local-first, cloud-contract-only, and `cloud_contract_candidate` route preview fields, including privacy class, route strategy, approval state, cloud escape reason, audit requirements, and explicit no-private-content-to-cloud flags.
- `core/src/ora_core/hybrid/wire_contract.py` defines public-safe `OfficialOrchestrationStubRequest` and `OfficialOrchestrationStubResponse` schemas for private YonerAIOracle conformance without public-repo execution.
- `yonerai doctor`, `yonerai status`, `yonerai node status`, `yonerai node pair --dry-run`, and `yonerai route preview` expose public-safe fixture status.

## Milestone 1: Hybrid Relay/Node Local-Dev Runtime

Objective: make the local-dev relay/node behavior close enough to process behavior for conformance tests while staying in-memory and loopback-only.

Acceptance criteria:

- Relay status reports loopback-only binding and redacts non-loopback bind hosts.
- Pairing is one-time and produces no plaintext pairing code in public output.
- Session token is stored and reported as hash-only.
- Request and response bodies are never persisted or returned raw; only body size and hash are exposed.
- Heartbeat stale, revoked node/session, expired session, capability mismatch, key mismatch, body-too-large, and handler error all return controlled public-safe errors.
- Audit event shape exists for proxy request attempts and results.
- Replay protection is represented for action envelopes and conformance output.

Validation:

- `python -m pytest tests/test_hybrid_transport.py tests/test_local_node_enrollment_pairing.py tests/test_local_node_signed_action_envelope.py -q`
- `python -m pytest tests/test_hybrid_relay_node_e2e.py -q`
- `python -m ruff check core/src/ora_core/hybrid tests/test_hybrid_transport.py`
- `python -m compileall -q core/src/ora_core/hybrid`

Blockers:

- Production process supervision, sockets, public tunnel, service registration, and production trust material remain private/official work.

Private YonerAIOracle handoff:

- Consume the public `LocalNodeHello`, heartbeat, session ref, capability manifest, action envelope, proxy result, and audit event shapes.
- Replace in-memory transport with a private loopback relay process only after production trust and deployment approval exist outside this repo.

## Milestone 2: Extension Capability Boundary

Objective: define how local extensions declare safe capabilities without granting execution by default.

Acceptance criteria:

- Extension manifest includes typed inputs, typed outputs, risk tags, owner scope, audit requirements, and declared capability scope.
- Safe fixture capabilities remain review-only and `can_execute` stays false.
- Unknown, duplicate, overbroad, dangerous, private-file, PC operation, live Discord, deployment, and official control-plane capabilities fail closed.
- Node posture reduces exposed capabilities when manifest verification fails, policy drift appears, manifest drift appears, suspicious behavior appears, or session is revoked.
- Public output includes no secrets, local absolute paths, raw prompts, or control-plane internals.

Validation:

- `python -m pytest tests/test_hybrid_extension_manifest.py tests/test_hybrid_node_posture.py -q`
- `python -m pytest tests/test_hybrid_wire_contract.py -q`
- `python -m ruff check core/src/ora_core/hybrid/extension_manifest.py core/src/ora_core/hybrid/node_posture.py`
- `python -m compileall -q core/src/ora_core/hybrid/extension_manifest.py core/src/ora_core/hybrid/node_posture.py`

Blockers:

- Real extension execution, extension marketplace, production review workflow, and private extension signing are not public-repo work.

Private YonerAIOracle handoff:

- Implement private extension review, signing, revocation, and execution only after this public manifest boundary is stable.

## Milestone 3: Local-First and Cloud-Escape Routing

Objective: route private/local work to Local Node contract previews, and route only public or hard reasoning work to cloud-contract candidates.

Acceptance criteria:

- Route preview classifies task difficulty and privacy class.
- Public docs and hard reasoning can become `cloud_contract_candidate` only when no private content is included.
- Private files, local memory, local tools, and PC operations stay local node or deny.
- Dangerous operations require approval and remain non-executing.
- Cloud escape preserves approval state, audit requirement, args hash requirement, disabled reason, and non-claims.
- Public route output confirms no private file content, provider key, raw prompt body, or local absolute path is sent to cloud.

Validation:

- `python -m pytest tests/test_three_mode_route_preview.py tests/test_surface_cli_smoke.py -q`
- `python -m pytest tests/test_hybrid_wire_contract.py -q`
- `python -m ruff check core/src/ora_core/route_preview.py clients/cli/yonerai_cli/cli.py`
- `python -m compileall -q core/src/ora_core/route_preview.py clients/cli/yonerai_cli/cli.py`

Blockers:

- Official cloud execution and private control-plane selection logic must stay outside the public repo.

Private YonerAIOracle handoff:

- Implement the cloud contract candidate consumer with approval/audit/args_hash preservation and strict private-data exclusion.

## Milestone 4: Oracle Contract Stub

Objective: define the official orchestration request/response contract that private YonerAIOracle must implement.

Acceptance criteria:

- Public schemas cover status, heartbeat, capability manifest, session ref, route decision, audit event, orchestration request, orchestration response, controlled error, and disabled reason.
- Contract fixtures prove production Oracle is not used.
- Contract fixtures prove official cloud runtime is not implemented in this repo.
- Contract fixtures require no network, provider key, Discord token, production database, production signing key, or production trust store.
- Conformance report groups local-dev, extension, routing, and Oracle stub checks.

Validation:

- `python -m pytest tests/test_hybrid_wire_contract.py tests/test_hybrid_node_relay_contract.py tests/test_relay_local_dev_status.py -q`
- `python -m pytest tests/test_yonerai_demo_contract.py tests/test_public_demo_script.py -q`
- `python -m ruff check core/src/ora_core/hybrid scripts/dev/public_demo.py`
- `python -m compileall -q core/src/ora_core/hybrid scripts/dev/public_demo.py`

Blockers:

- Production status service, Oracle control-plane runtime, production signing, release signing, and private deployment are private/official lanes.

Private YonerAIOracle handoff:

- Consume the stub request/response schemas and publish a private implementation conformance matrix without copying private routes, secrets, or runtime inventory into this public repo.

## Milestone 5: CLI, Demo, and Doctor

Objective: make the public CLI explain what is a fixture, what is local-dev only, and what private Oracle must implement next.

Acceptance criteria:

- `yonerai doctor --json` shows provider setup, Hybrid Wire conformance, relay status, node relay contract, and no live network by default.
- `yonerai status --source fixture --json` shows official status contract fixture and non-claims.
- `yonerai node status --json` shows relay/node/session/posture state without plaintext tokens or raw body.
- `yonerai node pair --dry-run --json` shows one-time pairing plan, hash-only token behavior, and no network/install/deploy.
- `yonerai route preview <task> --use-local-node-fixture --json` shows local, hybrid, cloud contract, or deny strategy with approval/audit/args_hash status.
- `yonerai demo --json` summarizes the Hybrid/Oracle contract without claiming production Oracle or official cloud runtime.

Validation:

- `python -m pytest tests/test_surface_cli_smoke.py tests/test_yonerai_demo_contract.py tests/test_public_demo_script.py -q`
- `python -m ruff check clients/cli/yonerai_cli/cli.py scripts/dev/public_demo.py`
- `python -m compileall -q clients/cli/yonerai_cli/cli.py scripts/dev/public_demo.py`

Blockers:

- Production deployment, live Discord, provider-key live calls, production Oracle, and official managed cloud runtime remain explicitly out of scope.

Private YonerAIOracle handoff:

- Use CLI fixture fields as public conformance expectations for the private runtime.

## Private YonerAIOracle Consumer Handoff Matrix

The private/official Oracle lane must consume these public-safe contracts without copying
production secrets, private routes, private runtime inventory, raw prompts, or local file
content into this public repo.

| Consumer responsibility | Public contract source | Public proof | Private implementation expectation |
| --- | --- | --- | --- |
| Status | `build_local_node_status_report()` / `yonerai node status --json` | loopback-only, non-production, no network, no plaintext token | Replace fixture status with private relay/node status while preserving public-safe fields. |
| Heartbeat | `LocalNodeHeartbeat` | lease id, lease expiry, audit cursor, no message body persistence | Verify heartbeat freshness, expiry, revoke state, and audit cursor continuity. |
| Capability manifest | `LocalNodeCapabilityManifest` and extension manifest decisions | typed capabilities, disabled dangerous operation, no production trust material | Enforce private signed capability review and revocation without widening public capabilities. |
| Session ref | `LocalNodeSessionRef` | hash-only token, bearer token excluded, lease-bound session | Store only hash/reference material in public-facing reports; never expose bearer tokens. |
| Route decision | `preview_route()` / `yonerai route preview` | `local`, `hybrid`, `cloud_contract_candidate`, or `deny` with privacy class | Consume route decisions and preserve local/private work on the Local Node boundary. |
| Audit event | Hybrid transport audit and wire conformance fields | audit required, args hash required, cloud escape preserves approval/audit/args hash | Persist private audit events in the private lane without message body or secret leakage. |
| Orchestration request | `OfficialOrchestrationStubRequest` | dry-run, approval required, audit required, args hash required, no raw prompt/provider key | Implement private request ingestion and policy evaluation outside this public repo. |
| Orchestration response | `OfficialOrchestrationStubResponse` | contract stub only, public execution unavailable, disabled reason, controlled error schema | Return private runtime status/results through controlled public-safe envelopes only. |
| Controlled error | `LocalNodeError` | public safe, raw exception excluded, local paths and credentials redacted | Map private failures to stable public-safe error codes and summaries. |

## Required Cross-Cutting Checks

Run the smallest relevant subset per PR, plus:

- `git diff --check`
- secret scan on changed files
- local absolute path scan on changed files
- mojibake and hidden-Unicode scan on changed public text
- `gh pr view <PR> --json reviews,comments,statusCheckRollup`
- `gh api repos/YoneRai12/YonerAI/pulls/<PR>/comments --paginate`

## Open Implementation Items

1. Completed in public implementation: add typed input/output, risk tag, owner scope, and audit fields to extension manifests.
2. Completed in public implementation: add audit event shape to local-dev transport proxy attempts and results.
3. Completed in public implementation: add explicit `cloud_contract_candidate` route strategy for hard public reasoning tasks while keeping private content local/denied.
4. Completed in public implementation: add Oracle request/response stub fields for route, approval, audit, args hash, disabled reason, controlled error schema, and no-runtime/no-network boundaries.
5. Completed in public implementation: update CLI/demo/doctor output to show the new contract fields without production claims. `yonerai route preview`, `yonerai node pair`, `yonerai demo`, and doctor Hybrid Wire rows expose `cloud_contract_candidate` / `OfficialOrchestrationStubResponse` status while keeping production execution disabled.

## MAIN-CODEX-HANDOFF

Next safe implementation lane:

1. Add deeper conformance checks that compare route preview output to the Oracle request/response stub field-by-field.
2. Keep `can_execute` false and deny unknown, overbroad, dangerous, private-file, PC operation, live Discord, deployment, and official-control-plane capabilities.
3. Do not implement production Oracle, production signing/trust, public tunnel, or official cloud runtime in this repo.
