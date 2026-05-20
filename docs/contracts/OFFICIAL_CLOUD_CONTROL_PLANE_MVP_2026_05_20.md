# Official Cloud Control Plane MVP 2026-05-20

Status: public-safe MVP contract and implementation addendum.

This document defines the first Official Cloud Control Plane MVP lane for YonerAI. It does not claim official cloud completion, production readiness, deployment, Google login completion, memory completion, or live operations completion.

## 1. Purpose

The Official Cloud Control Plane MVP establishes a non-production boundary for official-side metadata and approval workflows while preserving the same-experience contract with the public Core and local/self-host runtimes.

It should make these facts explicit:

- public Core remains usable as a credential-free local/self-host smoke and local LLM path
- official cloud can later own account/session/conversation metadata and governance policy
- hybrid private mode can bridge official governance and local/private execution through contracts
- official self-evolution begins as proposal review, not autonomous code mutation

## 2. Non-production Boundary

The MVP may define schemas, local in-memory services, tests, and synthetic fixtures.

It must not require:

- deployment
- production traffic
- real Google login
- billing
- real provider secrets
- production databases
- private runtime inventory
- live route maps
- raw user telemetry
- raw prompts, raw completions, or raw chain-of-thought
- automatic code mutation, branch creation, PR creation, merge, release, or deploy

## 3. Same-experience Contract

The same-experience contract is that user-facing semantics stay consistent even when implementations differ.

The contract includes:

- account/session/project identifiers are opaque references
- message envelopes expose mode/provider/model/approval/memory policy clearly
- provider selection is policy-bound and labeled
- memory policy is explicit and never implied
- self-evolution proposals require approval
- evidence, test requirements, rollback notes, and audit events are part of the proposal lifecycle

The public `POST /v1/public/messages` endpoint remains the public/local smoke endpoint. It is not the official cloud run API.

## 4. Minimal Entities

Public docs may use schema sketches only. Exact persistence and operational schemas belong in the control-plane repository and must remain non-public.

- `AccountRef`: opaque account reference, display label, capability tier.
- `ProjectRef`: workspace/project reference scoped to an account.
- `SessionRef`: active user session metadata and expiration semantics.
- `ConversationRef`: conversation metadata and memory policy reference.
- `MessageEnvelope`: public-compatible message/run envelope fields.
- `ProviderIntent`: requested provider class, mode, model, and policy labels.
- `MemoryPolicyRef`: none/local/private/official policy label and retention stance.
- `SignalEvent`: sanitized product-intelligence signal.
- `ImprovementProposal`: owner-reviewable proposal with evidence, tests, rollback, privacy risk, hype debt, provider independence, and same-experience score.
- `ApprovalDecision`: explicit approve/reject/defer decision by an authorized owner/reviewer.
- `AuditEvent`: public-safe event metadata for action, state transition, and evidence reference.

## 5. Minimal APIs / Events

The implementation MVP may expose service functions or local-only endpoints if a framework already exists.

Required MVP operations:

- health/status
- create/list session metadata
- append conversation metadata or message envelope
- record synthetic `SignalEvent`
- create/list `ImprovementProposal`
- approve/reject/defer proposal
- append/list `AuditEvent`

If the control-plane repository has no clear API framework, do not invent production endpoints. Implement service functions and tests first.

## 6. Self-evolution Proposal Queue

Official self-evolution is separate from public proposal-only fixtures.

The MVP proposal queue may use synthetic or sanitized local fixtures only. A proposal must include:

- evidence summary
- affected capability
- suggested tests
- rollback note
- privacy risk
- hype debt
- provider independence score
- same-experience score
- approval state

No score is approval. No proposal mutates code or infrastructure.

## 7. Approval Model

Approval state is explicit:

- `owner_review_required`
- `approved`
- `rejected`
- `deferred`

Approval decisions must produce audit events. The MVP must not bypass approval through automation.

## 8. What Remains Public / Local / Private

| lane | owns | must not expose |
|---|---|---|
| public Core | credential-free smoke, mock/offline message, loopback local LLM, temporary Web smoke-demo, public proposal-only fixtures | private runtime inventory, live routes, control-plane internals |
| private runtime | local/private execution, private memory and connector details | secrets into public docs, direct public imports |
| official control-plane | official metadata, governance, proposal queues, approval state, release/audit metadata | production secrets, live route maps, operational ledger in public docs |
| hybrid private | bridge contract between official governance and local execution | implicit provider, memory, or approval behavior |

## 9. Not Included

- claim that official cloud is complete
- production readiness
- deployment
- real Google login
- billing
- persistent memory completion
- Discord gateway completion
- external provider live calls from the public Core
- arbitrary remote local-provider URLs
- real telemetry ingestion
- raw prompt/completion/chain-of-thought ingestion
- automatic self-evolution mutation
- automatic branch/PR/merge/deploy
- `src/cogs/ora.py` refactor or rename

## 10. Tests Required

Control-plane skeleton tests should prove:

- entity references can be created without secrets
- session/conversation/message envelope metadata follows the same-experience contract
- synthetic signal events can create proposals
- forbidden raw/private signal fields are rejected
- proposal approval/rejection records audit events
- proposal queue does not expose mutation/deploy behavior
- no production database or deploy command is required

Public repo checks should prove:

- docs are syntactically clean
- no secrets or local machine paths are introduced
- `src/cogs/ora.py` and `reference_clawdbot` are untouched

## 11. Next Implementation Lane

After the skeleton lands, the next safe lane is one of:

1. local-only official control-plane model listing / provider policy metadata
2. proposal queue evidence schema hardening
3. hybrid private result-envelope contract
4. memory policy reference scaffold without memory completion claim
5. owner approval UI contract, not implementation
