# YonerAIOracle Self-Evolution System Handoff

This is a sanitized public-repo handoff for a future private YonerAIOracle lane.
It is not production backend code and does not contain private routes, secrets,
tokens, production hostnames, production inventory, or control-plane internals.

## Public Repo Boundary

The public repository may expose only:

- contract schemas
- fixture envelopes
- proposal-only self-evolution reports
- synthetic low-resolution signals
- CLI/TUI status surfaces
- conformance tests

The public repository must not ingest:

- raw user prompts
- raw conversation bodies
- private file contents
- local memory records
- local node payloads
- provider keys
- OAuth tokens
- real user telemetry
- support transcripts with PII

The public repository must not perform:

- automatic PR creation from private signals
- automatic merge
- automatic release
- deployment
- production Oracle execution

## Private YonerAIOracle Future Lane

The private official lane may implement:

- official signal ingestion
- support feedback normalization
- owner approval console
- patch candidate queue
- risk scoring
- rollback plan generation
- release note draft generation
- X post draft generation
- rate-limit-aware proposal prioritization

Owner approval remains mandatory before:

- opening a patch PR
- merging a patch
- releasing
- deploying
- changing production rate limits
- enabling shared traffic
- syncing local private content to cloud

## Suggested Private Modules

These names are non-binding placeholders for private implementation planning:

- `official_api.auth`
- `official_api.rate_limit`
- `official_api.account`
- `official_api.conversation_sync`
- `official_api.oracle_runs`
- `self_evolution.signal_ingestion`
- `self_evolution.proposal_queue`
- `self_evolution.owner_review`
- `self_evolution.rollback`

## Public/Private Sync Rules

- Cloud conversation to local sync is allowed only after linked account and
  user-selected cloud conversation.
- Local private conversation to cloud is disabled by default.
- Local to cloud sync requires explicit user approval and an audit reason.
- Private file content, local memory, local node payload, secrets, provider keys,
  and local absolute paths are excluded by default.
- A sync approval is not equivalent to tool execution approval.
- A signed envelope is not a trust grant.

## Private Implementation Checklist

1. Add auth middleware stub with PKCE/state/loopback assumptions.
2. Add account summary endpoint stub.
3. Add conversation list endpoint stub using refs only.
4. Add sync preview endpoint that returns `SyncDecision`.
5. Add sync approval endpoint that records audit reason.
6. Add rate-limit middleware stub with user/device/provider quota categories.
7. Add Oracle run request/result envelope queue stub.
8. Add proposal queue backend stub for official-only self-evolution.
9. Add owner approval console stub.
10. Add rollback and release/X draft queue stubs.

## Non-Claims

Do not claim from this handoff alone:

- production Oracle complete
- production Official Managed Cloud complete
- production Google login complete
- live Discord restored
- OpenAI shared traffic enabled
- persistent memory complete
- production installer/npm/winget ready
- automatic self-evolution complete
