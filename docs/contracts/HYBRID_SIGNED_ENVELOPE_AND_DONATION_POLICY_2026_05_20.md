# Hybrid Signed Envelope and Donation Policy 2026-05-20

Status: public-safe contract and test fixture boundary.

This document defines the first YonerAI hybrid ingress contract. It is not a full hybrid connector, not persistent memory, not an official cloud completion claim, and not a production security release.

## 1. Purpose

Hybrid private mode needs a way for public/local/private runtimes to hand results to the official control plane without letting the control plane trust donated data blindly.

The Hybrid Signed Envelope proves origin and integrity for a payload. The Donation Policy decides whether the payload is rejected, quarantined, or sent to approval review.

## 2. Threat Model

The MVP policy is designed against:

- forged node identity
- replayed result envelopes
- stale or not-yet-valid envelopes
- wrong audience
- compromised or revoked node keys
- secret-like values in payloads
- memory poisoning
- self-evolution poisoning
- overbroad capability claims
- object-level or field-level authorization bypass
- signature-valid but policy-invalid donations

## 3. Envelope Schema

Required fields:

- `envelope_type`
- `issuer_node_id`
- `subject_user_id` or `account_ref`
- `audience`
- `session_id`
- `conversation_id`
- `capability`
- `data_class`
- `purpose`
- `issued_at`
- `expires_at`
- `nonce`
- `payload_hash`
- `payload`
- `signature.algorithm`
- `signature.key_id`
- `signature.signature`

The public schema helper computes `payload_hash` as a canonical JSON `sha256:<hex>` digest.

## 4. Trust Registry

The MVP trust registry is in-memory and fixture based. It maps a node issuer to:

- key id
- allowed capabilities
- revoked state

Unknown and revoked issuers are rejected. Matching a known key id is not enough if the envelope claims an unapproved capability.

## 5. Signature Verification

The public repo defines a verifier interface and test verifier only. It does not publish production signing keys, a production key registry, a deployment trust store, or a private runtime inventory.

Signature verification is one input to policy. A valid signature never means the payload is trusted.

## 6. Replay Protection

Replay protection is nonce plus expiry based.

The MVP nonce store is in-memory and rejects reuse for the tuple:

- issuer node id
- audience
- nonce

This is sufficient for local tests and contract validation only. It is not a production replay store.

## 7. Donation Policy

Donation means any payload contributed from local/private/self-host runtime into the official cloud/control-plane lane.

Examples:

- local LLM result
- conversation continuation metadata
- memory candidate
- tool result
- self-evolution signal
- improvement proposal

The MVP policy checks:

- required envelope fields
- audience
- expiry window
- nonce replay
- issuer trust
- revoked state
- key id
- signature verifier result
- allowed capability
- data class
- purpose
- payload hash
- field-level denylist
- secret-like content markers

Valid donated payloads are quarantined and require approval. Invalid payloads are rejected.

## 8. Memory Candidate Quarantine

A signed memory candidate is still only a candidate.

The MVP requires quarantine and owner/control-plane approval before any future memory lane may use it. This contract does not implement persistent memory, cross-device history, Google login, or official identity.

## 9. Self-evolution Signal / Proposal Queue

Self-evolution donations may only enter a proposal queue or quarantine state. They must not:

- mutate code
- create branches
- open PRs
- merge PRs
- create releases
- deploy
- bypass approval

Future official proposals must include evidence, suggested tests, rollback notes, privacy risk, hype debt, provider independence score, and same-experience score.

## 10. Approval Requirement

Approval is separate from validation.

Validation answers: "is this envelope structurally valid and signed by an allowed issuer?"

Approval answers: "may the official system act on this data?"

The MVP never treats validation as approval.

## 11. Field-level Authorization

Payload keys and text are scanned for forbidden private markers, including raw prompts, raw completions, chain-of-thought, API keys, access tokens, private keys, local paths, and private machine path markers.

The public policy is intentionally conservative. If the field is ambiguous, it should be rejected or quarantined for owner review rather than trusted.

## 12. What Public Repo Implements

The public repo implements:

- envelope dataclasses
- canonical payload hash helper
- structural validation
- in-memory trust registry fixture
- in-memory nonce store fixture
- verifier protocol
- static test verifier
- donation policy tests that prove signed payloads are not trusted automatically

## 13. What Official Control-plane Implements

The control-plane MVP may implement:

- non-production envelope verifier skeleton
- in-memory trust registry
- in-memory nonce store
- donation quarantine records
- audit events
- self-evolution donation queue boundary

It must not require production DBs, deployment, live traffic, provider secrets, or real private data.

## 14. What Private Runtime Implements Later

Private/local runtime may later implement:

- node key management
- envelope signing
- local result donation
- private memory candidate preparation
- local approval UX

Those details are not in the public repo and must cross repos only through this contract.

## 15. Not Included

- production hybrid connector
- persistent memory
- official cloud completion
- Google login
- cross-device session sync
- external provider live calls
- production trust registry
- production replay store
- production signing key distribution
- automatic self-evolution mutation
- deployment

## 16. Tests Required

The minimum test set must cover:

- valid signed donation is quarantined, not trusted
- signature-valid memory candidate still requires approval
- wrong audience rejection
- expiry rejection
- payload hash mismatch rejection
- replay rejection
- unknown issuer rejection
- revoked issuer rejection
- capability rejection
- invalid signature rejection
- secret-like payload rejection
- self-evolution donation quarantine without mutation

## 17. Next Lane

The next safe lane is a private/local signing fixture plus a control-plane review UI contract, still without persistent memory, Google login, full hybrid connector, or deployment.
