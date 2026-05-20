# Hybrid Connector Fixture 2026-05-20

Status: public-safe fixture contract. This is not production hybrid connectivity.

## 1. Purpose

The Hybrid Connector Fixture proves a minimal synthetic path from a local/private node shaped payload to official control-plane ingress semantics:

`synthetic_local_node_fixture -> signed envelope -> public schema validation -> official control-plane verifier -> donation policy -> quarantine / queue / audit`

The fixture exists to test the boundary before real private connector work. It must not ingest real private data.

## 2. Fixture Path

The public repo creates deterministic test-only envelopes in `core/src/ora_core/hybrid/connector_fixture.py`.

Fixture envelope types:

- `memory_candidate`
- `self_evolution_signal`
- `improvement_proposal`

The official control-plane repo consumes the same JSON shape through its non-production ingress skeleton.

## 3. Public Side Schema

The public schema is still `hybrid-signed-envelope-0.1`.

The signed envelope includes:

- issuer and key metadata
- subject/account reference
- audience
- session and conversation identifiers
- capability, data class, and purpose
- issue/expiry timestamps
- nonce
- payload hash
- payload
- signature metadata

The public fixture also exposes mapping round-trip helpers so a fixture can be serialized without importing private or control-plane internals.

## 4. Private / Local Node Fixture

The fixture represents a local/private node without using private runtime code.

It uses:

- fixture-only node id
- fixture-only key id
- fixture-only static signature
- synthetic payloads
- no raw prompts
- no raw completions
- no chain-of-thought
- no local file paths
- no private runtime inventory

Production signing, key lifecycle, and node enrollment remain out of scope.

## 5. Control-Plane Ingress

The official control-plane ingress skeleton verifies:

- contract shape
- issuer trust fixture
- signature fixture
- audience
- expiry
- nonce replay
- payload hash
- capability allowlist
- data class and purpose
- forbidden payload markers

Valid signed payloads are quarantined or queued. They are not trusted by default.

## 6. Donation Policy

Donation policy is fail-closed for the fixture:

- invalid signature: reject
- unknown or revoked issuer: reject
- wrong audience: reject
- expired envelope: reject
- replayed nonce: reject
- payload hash mismatch: reject
- forbidden content marker: reject
- valid signed payload: quarantine, `trusted=false`, approval required

## 7. Memory Candidate Quarantine

Memory candidates use explicit scaffold states:

- `observed`
- `quarantined`
- `rejected`
- `approved_for_memory`
- `expired`

Current fixture behavior:

- default status is `quarantined`
- `memory_persisted=false`
- approval is required before any memory persistence
- secret-like content is rejected
- raw chain-of-thought is rejected
- raw prompts/completions are rejected
- private runtime inventory is rejected
- live route maps are rejected

This is not persistent memory.

## 8. Self-Evolution Signal Queue

Self-evolution donations stay in signal/proposal review only.

The fixture does not:

- mutate code
- create branches
- open PRs
- merge PRs
- deploy
- bypass owner approval

Improvement proposals must carry test, rollback, privacy risk, hype debt, provider independence, and same-experience evidence fields.

## 9. Approval / Audit

Control-plane ingress records quarantine and rejection audit events in the non-production in-memory store.

Audit events are fixture evidence only. They are not an operational ledger.

## 10. What Is Not Included

- real private connector
- production cryptography
- production key registry
- production DB
- deploy
- Google login
- persistent memory
- cross-device sync
- official cloud completion
- full hybrid connector

## 11. Tests

Required fixture tests:

- memory candidate envelope hashes and quarantines
- self-evolution signal queues without mutation
- improvement proposal requires safety fields
- replay nonce rejects
- wrong audience rejects
- expired envelope rejects
- payload hash mismatch rejects
- invalid signature rejects
- secret-like memory payload rejects

