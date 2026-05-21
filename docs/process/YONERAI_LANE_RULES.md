# YonerAI Lane Rules

Each lane must stay narrow, current-main based, and verifiable.

## Security / Runtime

- Allowed: reproduce current-main issue, fresh narrow patch, regression tests, close old PR with evidence.
- Forbidden: blind stale PR merge, broad dependency churn, private/live secrets, `src/cogs/ora.py` edits unless lane-approved.
- Required tests: targeted regression, relevant smoke, `ruff`/`compileall` for Python.
- Owner decision: required for live/private runtime or irreversible behavior.
- Can claim: specific issue fixed.
- Must not claim: all security backlog resolved.

## API

- Allowed: public-safe contract endpoints, loopback/local smoke, deterministic errors.
- Forbidden: exposing private routes, production DB behavior, raw traces, live provider generation by default.
- Required tests: API route tests and public smoke.
- Can claim: endpoint/contract behavior covered.
- Must not claim: official cloud complete.

## CLI

- Allowed: local smoke commands and stable public capability names.
- Forbidden: hidden shell escalation, private runtime inventory, remote host defaults.
- Required tests: CLI invocation/mocking and public smoke.
- Can claim: command path works for covered mode.
- Must not claim: final CLI complete.

## Native Japanese CLI

- Allowed: parser, confirmation UX, dry-run, public-safe explanations.
- Forbidden: silent destructive actions, ambiguous execution, private/live operations.
- Required tests: ambiguity, confirmation, dry-run, deny behavior.
- Owner decision: required for destructive or live operations.
- Can claim: contract/parser behavior.
- Must not claim: full native CLI complete.

## Web

- Allowed: temporary public-safe smoke UI, safe error display, capability manifest display.
- Forbidden: Google login completion, final UI claim, private route leak, raw stack/private errors.
- Required tests: API/Web smoke and frontend checks when UI changes.
- Can claim: temporary smoke surface behavior.
- Must not claim: final Web product UI.

## Discord

- Allowed: synthetic contract tests, private-gateway boundary docs, no-token fixtures.
- Forbidden: live Discord, real tokens, restoring chat without owner-approved live lane, making public PythonBot the production responder.
- Required tests: duplicate responder denial, final once-only, same-message edit, reply-chain, files/download contract.
- Owner decision: required for live/private gateway implementation.
- Can claim: synthetic contract coverage.
- Must not claim: Discord restored or gateway complete.

## Hybrid / Self-Host Signed Contract

- Allowed: signed envelope schema, quarantine policy, replay/nonce tests, capability manifest.
- Forbidden: production signing keys, production trust store, treating signed payload as trusted automatically.
- Required tests: signature semantics, quarantine, approval requirement, replay behavior.
- Can claim: public-safe contract semantics.
- Must not claim: full hybrid complete.

## Memory / Quarantine

- Allowed: candidate quarantine, proposal-only flows, non-persistent metadata tests.
- Forbidden: persistent memory completion, raw prompt/completion log ingestion, private memory inventory.
- Required tests: no persistence by default, approval gate, redaction.
- Owner decision: required for persistent memory.
- Can claim: quarantine behavior.
- Must not claim: persistent memory complete.

## Tools / MCP

- Allowed: safe subset contract, explicit allowlist, deny-by-default tests.
- Forbidden: unrestricted shell/tool execution, dynamic MCP execution without explicit safe subset.
- Required tests: denied unknown tools, safe subset names, audit/approval behavior.
- Can claim: safe subset contract coverage.
- Must not claim: Tools/MCP complete.

## Dependency Updates

- Allowed: lane-split updates with changelog/security evidence and tests.
- Forbidden: broad blind dependency merges, memory/vector/provider churn without tests.
- Required tests: package-specific checks and touched-lane smoke.
- Owner decision: required for risky major upgrades.
- Can claim: specific dependency lane resolved.
- Must not claim: all dependency backlog resolved.

## Root Professionalization

- Allowed: validated `git mv`, reference updates, docs index updates.
- Forbidden: mass-touching for GitHub last-commit display, deleting uncertain files, touching `reference_clawdbot`.
- Required tests: reference scan, smoke, diff check.
- Owner decision: required for active entrypoint/config moves.
- Can claim: specific root item classified/moved.
- Must not claim: root fully solved.

## ORA / YonerAI Naming

- Allowed: public wording that says YonerAI while acknowledging ORA legacy/internal namespace.
- Forbidden: broad ORA symbol rename without compatibility plan and tests.
- Required tests: import/compatibility tests for code rename.
- Owner decision: required for runtime namespace migration.
- Can claim: specific public-facing wording cleanup.
- Must not claim: broad ORA rename complete.

## Release Notes

- Allowed: changelog checkpoint after meaningful merged implementation/test work, and GitHub Release only for a runnable public milestone.
- Forbidden: GitHub Release for docs-only/process-only/checkpoint-only work, future dates, delete/retag, release for every tiny PR, production claims.
- Required validation: changelog/release note scan, public runnable smoke for release candidates, `gh release list/view` only when inspecting existing releases.
- Can claim: checkpoint recorded or release candidate prepared, depending on the lane.
- Must not claim: product completion unless explicitly proven.
