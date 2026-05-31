# Official Self-Evolution Boundary

Status: public contract for the v0.8 alpha boundary.

YonerAI self-evolution in the public repository is proposal-only. It may turn
synthetic, low-resolution, public-safe fixture signals into owner-reviewable
proposal records. It must not ingest production telemetry, raw prompts, raw
completions, support inbox content, account data, local memory, local file
content, Discord messages, provider secrets, or private runtime inventory.

## Public Repository May Include

- Synthetic signal fixtures under `tests/fixtures/self_evolution/`.
- Local proposal scoring and queue reports.
- Approval states such as `proposed`, `approved`, `rejected`, and
  `needs_owner`.
- CLI commands that display or simulate proposals:
  - `yonerai evolve status`
  - `yonerai evolve simulate --fixture ...`
  - `yonerai evolve proposals list/show`
- TUI screens:
  - `/自己進化`
  - `/evolve`
- Draft fields for owner review:
  - test plan
  - rollback plan
  - release-note draft
  - social-post draft

## Public Repository Must Not Include

- Production signal ingestion.
- Raw prompt or completion collection.
- Support inbox ingestion.
- Stable user tracking.
- Account or billing data ingestion.
- Private runtime inventory.
- Automatic code mutation.
- Automatic branch, issue, PR, merge, tag, release, or deploy actions.
- Production Oracle mutation or control-plane internals.
- No production Oracle execution, routing, or release mutation in the public
  repository.
- No production Google login, production auth, or account linking in the
  public self-evolution path.

## Required Public Non-Actions

Every public self-evolution report must preserve these non-actions:

- no code mutation
- no GitHub write
- no PR creation
- no merge
- no tag or release creation
- no deployment
- no production configuration mutation
- no raw prompt persistence
- no provider key storage

## Public Input Guard

Public proposal-loop summaries are treated as unsafe when they contain local
machine paths, live URLs, secret-shaped values, raw prompt/completion markers,
stable account/user identifiers, email-shaped values, chain-of-thought markers,
or private runtime inventory markers. Those summaries must be redacted and
converted into owner-review guardrail proposals before any public output is
returned.

This guard is still not telemetry ingestion. It is a public-safe simulator
boundary for synthetic or local fixture input only.

## Approval Console Contract

The production YonerAIOracle approval console is private/official and is not
implemented by this public repository. Any future private console must keep
approval separate from scoring and validation.

Minimum public-safe contract:

- allowed states: `owner_review_required`, `approved`, `rejected`, `deferred`
- required evidence: evidence summary, affected capability, test plan, rollback
  plan, privacy risk, hype debt, provider-independence score, same-experience
  score
- approval cannot create a branch, PR, merge, release, deploy, or mutate code by
  itself
- every state transition must emit an audit event that excludes secrets, raw
  prompts, raw completions, chain-of-thought, local paths, and private runtime
  inventory
- private implementation may hand a public-safe proposal summary back to this
  repository only after redaction and owner-approved publication

## Private/Official Lane Responsibilities

The real official self-evolution system belongs outside this public repo. It
must be implemented in an owner-approved private/official lane and must define:

- signal ingestion contracts
- product intelligence aggregation
- support feedback handling
- owner approval workflow
- patch candidate generation
- test and rollback plans
- release note and social post drafts
- audit and retention policy
- emergency stop and rollback behavior

## Claim Boundary

Allowed wording:

- "YonerAI public repo includes a proposal-only self-evolution queue."
- "Public self-evolution uses synthetic fixtures and owner-reviewable proposal
  records."
- "Production self-evolution remains private/official."

Forbidden wording:

- "Self-evolution is complete."
- "YonerAI automatically fixes itself in production."
- "Production support feedback is ingested in the public repo."
- "YonerAI can automatically open PRs, merge, deploy, or release itself."
