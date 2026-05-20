# Security Policy

YonerAI is a public v7.7 implementation and research repository. It is not a production service, not an official-cloud-complete runtime, and not a full product release.

## Reporting Security Issues

Please do not open public issues or pull requests that include secrets, private runtime inventory, live routes, hostnames, usernames, local absolute paths, break-glass details, control-plane internals, raw prompt/completion logs, or raw chain-of-thought.

Use the repository owner's preferred private reporting channel when available. If a private channel is not available, open a minimal public issue that describes the affected public-safe component and impact without exploit secrets or environment-specific details.

## Public-Safe Scope

Security work in this public repository should stay within public-safe contracts and tests unless the owner explicitly approves a broader lane.

Allowed public-safe areas include:

- public Core API contracts and tests;
- local loopback-only provider boundaries;
- CLI/Web smoke surfaces;
- capability manifests and deny-by-default policy;
- release, dependency, PR, and repository hygiene docs;
- regression tests that do not require secrets or private infrastructure.

Out of scope for public PRs without explicit owner approval:

- production deployment or rollback behavior;
- production signing keys or trust stores;
- persistent private memory;
- Google login or private auth implementation;
- official Discord gateway completion;
- unrestricted tools/MCP runtime execution;
- raw prompt/completion ingestion;
- private/control-plane routes, host facts, or operational inventories.

## Fixed Boundaries

- Do not touch `src/cogs/ora.py` implementation unless a dedicated owner-approved lane says so.
- Do not initialize, repair, remove, replace, or stage `reference_clawdbot`.
- Do not rewrite git history or force-push.
- Do not delete or retag existing releases.
- Do not add deploy, production signing, production trust store, persistent memory, Google login, production DB behavior, external provider live generation, real telemetry collection, or unrestricted shell/tool execution in a security cleanup PR.

## Validation Expectations

Security or hardening PRs should include:

- focused regression tests for the affected behavior;
- `git diff --check`;
- targeted lint/compile/build checks for touched code;
- changed-file secret scan;
- changed-file local absolute path / username / hostname scan;
- mojibake and hidden Unicode scan for public docs;
- explicit confirmation that `src/cogs/ora.py` and `reference_clawdbot` were not changed, unless the PR is explicitly scoped and approved for those boundaries.

## Non-Claims

Security cleanup in this repository does not mean all security backlog is resolved. Each PR should state what was fixed, what was not included, what remains open, and which older PRs or issues are superseded only when replacement evidence is strong.
