# Cross-repo Same-experience Matrix 2026-05-20

Status: public-safe contract matrix for the Official Cloud Control Plane MVP lane.

This document records how the public Core, private runtime, and official control-plane repositories should preserve the same user-facing YonerAI experience without leaking private or operational detail into the public repository.

It is a contract and planning checkpoint, not an official cloud completion claim.

## Repository State Snapshot

| repository | intended role | current state | editing decision for this lane |
|---|---|---|---|
| `YonerAI` | public distribution core, public Core API, local LLM boundary, public-safe docs and tests | available; public `main` includes `/health`, `POST /v1/public/messages`, local provider compatibility, and temporary `clients/web` smoke-demo surface | public-safe contract docs only |
| `YonerAI-private` | private runtime implementation and private connectors | canonical remote exists; local primary candidate is dirty and not safe to edit in this lane | audit only; no changes |
| `YonerAI-oracle-control-plane` | official cloud/control-plane orchestration, metadata, approval queues, release control | canonical remote exists; clean clone is available for non-production skeleton work | implement only small non-production skeleton if tests stay local and synthetic |

## Matrix

| concern | public core | private runtime | official control-plane | same-experience contract | current status | next action |
|---|---|---|---|---|---|---|
| user identity | no real login; public smoke uses no account | may bind local/private identity | owns future official account reference | all modes must expose stable account/session labels without leaking secrets | public has no identity product | define `AccountRef` stub |
| session | public request may include local conversation id | may keep private session state | records official session metadata | session identifiers must be opaque, scoped, and revocable | public smoke only | define `SessionRef` and no persistence claim |
| conversation | public message endpoint returns reply envelope | may persist private conversation state | records official conversation metadata | message envelope fields must not diverge silently | public has message envelope | align with `MessageEnvelope` sketch |
| message envelope | `POST /v1/public/messages` response includes ok/mode/provider/model/message ids | may enrich privately | official cloud uses compatible run/message envelope | user-facing reply, provider label, approval state, and memory policy must be explicit | implemented for public/local smoke | keep public endpoint as local smoke, not official run API |
| provider selection | mock/offline and loopback local providers only | may route private/local providers | owns official provider orchestration policy | provider choice must be labeled and policy-bound | local provider compatibility exists | add `ProviderIntent` sketch |
| local LLM | loopback-only; no arbitrary remote URL | may execute local/private model calls | must not bypass local privacy boundary | local execution stays user-controlled unless explicit official lane exists | implemented in public Core | keep intact |
| official provider orchestration | not implemented | not public | future control-plane policy only | official orchestration must not require public self-host path to weaken safeguards | planning only | define non-production policy boundary |
| memory | no persistent memory claim | may own private memory | owns official memory policy metadata, not memory completion | memory policy must be shown as none/private/official, never implicit | public says no memory | define `MemoryPolicyRef` |
| self-evolution signal | public synthetic proposal-only fixtures | may hold private/local signals | official queue may accept sanitized/synthetic MVP signals | no raw prompts, completions, chain-of-thought, or private data cross the boundary | public proposal-only exists | define official queue boundary |
| proposal queue | Markdown proposal-only output | may prepare local review data | owns official proposal queue and approval state | proposal score never equals approval | public proposal-only exists | define `ImprovementProposal` |
| approval gate | owner review required | local owner approval remains authoritative | official approval state is explicit and auditable | no automatic mutation, PR, merge, deploy, or bypass | guardrail documented | define `ApprovalDecision` |
| audit event | public docs/tests only | private runtime may audit locally | official control-plane records audit metadata | audit event must avoid secrets and raw private payloads | planning only | define public-safe `AuditEvent` sketch |
| rollback/test evidence | public release notes and tests | private rollback evidence stays private | official proposal requires test and rollback evidence | every change proposal carries test and rollback expectations | planning only | require evidence fields |
| release/checkpoint | public release notes and GitHub Releases | private releases separate | official checkpoints separate | release notes must state non-production and non-completion | current public notes exist | add planning checkpoint |
| UI surface | temporary `clients/web` smoke-demo | private UI may differ | official UI not implemented | labels must not imply final UI or official cloud completion | temporary surface exists | keep as smoke-demo |
| Discord gateway | not complete | private runtime may implement | official policy may coordinate later | Discord completion cannot be implied by cloud skeleton | unresolved | keep out of this MVP |
| security/privacy boundary | public-safe only | private data stays private | control-plane skeleton uses synthetic/local fixtures | no secrets, live routes, DDL, ledger, or break-glass detail in public docs | active guardrail | scan every changed file |

## Contract Rules

- The public Core remains a local/public smoke and self-host foundation.
- Official cloud work must not weaken loopback-only local LLM protections.
- Hybrid private mode must use contracts rather than direct private imports.
- Public docs may describe entity names and message semantics, but must not publish control-plane DDL, live routes, private runtime inventory, operational ledgers, or break-glass details.
- Official self-evolution begins as a proposal queue with explicit approval, not an autonomous mutation pipeline.

## Current Blockers And Unknowns

- The local primary private runtime worktree is dirty and not safe to edit in this lane.
- The public repository must not assume private runtime internals.
- The control-plane repository has deployment and relay material, but the MVP skeleton must remain non-production and local-test-only.

## Next Action

Use the official control-plane repository for a small identity/session/conversation/proposal queue skeleton. Keep public changes to this matrix, the MVP spec, and release/checkpoint wording.
