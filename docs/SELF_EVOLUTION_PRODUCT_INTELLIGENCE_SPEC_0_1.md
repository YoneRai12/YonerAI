# Self-Evolution Product Intelligence Spec 0.1

Status:

- B lane docs/spec only
- no runtime implementation
- no telemetry collection code
- no external scraping implementation
- no SNS automation implementation
- no unapproved code mutation
- no production-readiness claim

## Purpose

YonerAI self-evolution is product intelligence, not automatic code mutation.

The loop exists to observe safe signals, convert them into reviewed product proposals, score them against user value and risk, and only then feed approved implementation work into a separate execution lane.

This spec keeps self-evolution separate from API, CLI, native Japanese CLI, Web, SNS, and `src/cogs/ora.py` boundary work.

## Non-Goals

- claim shipping-complete, production-ready, official-cloud complete, live-ops complete, or full product complete
- collect raw conversation text, raw prompts, raw completions, raw chain-of-thought, secrets, credentials, or file contents
- implement telemetry ingestion
- implement external market or SNS scraping
- implement automatic PR creation, patch application, deployment, or release
- bypass owner approval, tests, privacy review, or rollback evidence
- merge private runtime or control-plane exactness into public artifacts

## Product Intelligence Loop

| stage | purpose | allowed input | output | gate |
|---|---|---|---|---|
| observe | capture safe product signals | anonymized feature usage, complaint category, drop-off bucket, failure class, aggregate demand signal | normalized signal event | privacy contract |
| aggregate | reduce individual identifiability | cohort counts, time buckets, coarse categories | aggregate metric | small-cohort threshold |
| interpret | turn metrics into user problems | trend deltas, repeated complaint classes, feature request clusters | problem statement | human review |
| candidate | define possible improvement | problem statement, affected surface, expected value | candidate proposal | scope boundary review |
| score | compare value, cost, risk, alignment | candidate proposal and evidence | scored backlog item | scoring rubric |
| specify | write implementation-ready spec | accepted candidate | docs/spec, tests expected, rollback plan | owner approval |
| approve | authorize code work | spec package | execution ticket / branch instruction | explicit approval |
| implement | separate code lane | approved ticket only | patch / tests | normal code review |
| evaluate | verify outcomes | tests, release metrics, rollback checks | adoption / regression report | release gate |
| release | ship bounded change | verified patch | release or checkpoint | release approval |
| market | explain safe public value | approved public-safe claims | launch/digest copy | claim review |
| learn | feed results back | aggregate results only | updated scoring priors | privacy review |

## Signal Model

| signal family | examples | raw text allowed | default lane |
|---|---|---:|---|
| feature usage | feature opened, command used, setting toggled | no | product intelligence |
| complaint / failure | complaint category, failure class, repeated timeout bucket | no | product intelligence |
| drop-off | onboarding abandoned, flow cancelled, repeated retry bucket | no | product intelligence |
| tool execution | tool category success/failure, latency bucket, approval-required class | no | product intelligence |
| release feedback | adoption bucket, regression category, rollback reason | no | release intelligence |
| extension signal | extension category, install count bucket, error class | no | ecosystem intelligence |
| external demand | public issue category, competitor feature category, search/social aggregate | no | proposal input only |
| SNS signal | aggregate public interest, campaign source bucket, CTA click bucket | no | distribution lane |

External demand, competitor, and SNS signals are proposal inputs only.
They do not authorize implementation, release, messaging claims, or private data access.

## Data Boundaries

- L0 anonymous basic improvement signal may be considered default-safe only when it contains no personal identifier, account ID, IP, device fingerprint, exact timestamp, raw text, or file content.
- L1 detailed anonymous analysis requires explicit opt-in and must preserve small-cohort protections.
- L2 personal personalization requires explicit opt-in and must remain separate from aggregate official improvement.
- L3 personal Feature Lab requires explicit opt-in and per-feature confirmation.
- Developer telemetry is opt-in and must not become user tracking by default.

Forbidden fields:

- raw conversation text
- raw prompt
- raw completion
- raw chain-of-thought
- email, phone, address, account ID, Discord user ID, IP address, device fingerprint
- exact timestamp when coarse bucket is enough
- file contents
- secrets, tokens, keys, credentials

## Scoring Rubric

| dimension | scoring intent | positive weight | penalty |
|---|---|---:|---:|
| user value | solves repeated real user pain | high | low if speculative |
| same experience | improves contract consistency across surfaces | high | high if surface-specific drift increases |
| provider independence | reduces provider lock-in or keeps provider-neutral contract | high | high if hard-codes one provider into product truth |
| privacy safety | minimizes data and preserves consent | high | blocking if raw/private data is required |
| implementation cost | bounded and testable | medium | high if cross-lane or broad runtime work |
| support load | reduces operator/user confusion | medium | medium if it increases hidden complexity |
| evidence quality | supported by aggregate signal and clear reproduction | high | high if based on hype only |
| hype debt | avoids overclaiming capability | n-a | high if marketing outruns evidence |
| rollback readiness | has measurable rollback or disable path | medium | high if irreversible |

Candidates with privacy blocking issues, unapproved private data access, raw chain-of-thought exposure, or unbounded runtime mutation must be rejected before implementation.

## Approval Gate

No candidate may become code work until an owner-approved spec exists.

Required approval packet:

- problem statement
- evidence summary using safe aggregates
- target lane: API, CLI, native Japanese CLI, Web, SNS, self-evolution, private runtime, or control-plane
- expected user benefit
- privacy and consent impact
- tests / validation plan
- rollback plan
- public-claim wording if any
- explicit non-goals

Approval must be explicit.
Silence, aggregate score, or model confidence is not approval.

## Evidence And Rollback Requirements

Before release or checkpoint, an approved implementation lane must provide:

- tests relevant to the changed lane
- negative tests for privacy and forbidden fields when data is involved
- no secret-bearing diff
- no private internals imported into public artifacts
- rollback or disable path
- public wording review that avoids forbidden completion claims

## Lane Boundaries

- API lane: contract authority and endpoint semantics.
- CLI lane: command authority.
- Native Japanese CLI lane: ambiguity confirmation, explanation responsibility, and Japanese UX expectations.
- Web lane: product surface and user-facing flows.
- SNS lane: distribution and public signal intake only; not a core blocker.
- Self-evolution lane: product intelligence and proposal generation only until approved.
- Private runtime lane: official app, Discord gateway, official yonerai.com runtime, operator/admin surfaces.
- Control-plane lane: Oracle host deploy/rollback/supervision/cloudflared/hooks/evaluator scaffolding.

## Open Questions

- exact small-cohort threshold for each signal family
- L0 opt-out UI placement
- L1 retention period
- how to separate local-only personalization from account-synced personalization
- exact candidate score thresholds
- how market/SNS signals are de-duplicated without tracking users
- what part of scoring belongs in public contracts versus private official analytics
