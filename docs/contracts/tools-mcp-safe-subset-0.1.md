# Tools/MCP Safe Subset 0.1

Status: v7.7 public-safe contract. Tools/MCP remains disabled by default and is
not complete.

## Purpose

YonerAI needs a practical tools boundary that can eventually support useful user
workflows without turning the public MVP into an unsafe automation runner. This
contract defines the first public-safe subset gate for tools and MCP.

## Default State

Tools/MCP is disabled by default unless a tool is explicitly declared in a safe
subset and allowed by the public capability boundary.

Unknown tools, undeclared tools, and dynamically discovered MCP tools are denied
in public-safe paths.

## Required Capability Labels

Every future safe tool must declare:

- `capability`
- `surface`
- `tool_kind`
- `read_only`
- `writes_files`
- `uses_network`
- `requires_secret`
- `requires_approval`
- `audit_event`
- `public_safe_output`

Suggested capability labels:

- `tools.safe_read`
- `tools.safe_transform`
- `tools.safe_status`
- `tools.mcp.safe_subset`
- `tools.mcp.disabled_dynamic`

## Always Denied In The Public MVP

The public MVP does not allow:

- shell execution by default
- file system writes by default
- deploy actions
- production database changes
- production signing or trust-store changes
- secret access
- private runtime inventory reads
- live route map exposure
- break-glass detail exposure
- raw chain-of-thought exposure
- raw prompt/completion ingestion as memory
- automatic code mutation
- automatic branch creation
- automatic PR creation
- automatic merge
- automatic deploy

## Safe Subset Candidate Shape

A tool can enter the safe subset only when all of these are true:

- it is explicitly listed in the public capability manifest
- it is deterministic or bounded enough for tests
- it does not require secrets
- it does not expose local paths, usernames, hostnames, private inventory, live
  routes, or raw chain-of-thought
- it either performs no side effects or requires approval before side effects
- it emits a public-safe audit event
- it has tests for allowed and denied inputs
- it has redaction tests for secret-like values and local machine details

## Approval-Gated Actions

Any action that writes, mutates, opens a browser, contacts an external service,
or changes runtime state must require approval before execution. Public MVP
tools should prefer dry-run output first.

Approval must bind:

- tool name
- capability label
- user-visible intent
- proposed inputs after redaction
- expected side effect
- rollback or undo note when relevant
- audit event id

## Audit Event Shape

Safe tool execution should emit a bounded audit event:

```json
{
  "event_type": "tool_capability_decision",
  "tool_name": "example.safe_status",
  "capability": "tools.safe_status",
  "decision": "allowed_or_denied",
  "requires_approval": false,
  "approved": false,
  "redaction_applied": true,
  "memory_persisted": false,
  "reason": "public-safe status read"
}
```

Audit events must not include secrets, local absolute paths, usernames,
hostnames, private runtime inventory, live route maps, raw prompts/completions,
or raw chain-of-thought.

## Allowed Examples

Allowed only after tests and explicit manifest entry:

- status read from already-public Core health metadata
- deterministic payload validation
- redacted schema transformation
- public-safe capability manifest display

## Denied Examples

Denied in this checkpoint:

- arbitrary shell command
- arbitrary SQL command
- file write outside an approved fixture
- deploy command
- production signing key generation
- production trust store update
- MCP tool discovered without explicit allowlist entry
- tool that returns raw local file paths or private runtime inventory
- tool that turns self-evolution proposal output into code mutation

## Relation To Native Japanese CLI

Native Japanese CLI commands can be ambiguous. A Japanese intent must be mapped
to a dry-run and confirmation step before a tool is invoked. Ambiguous Japanese
commands must not auto-select a mutating tool.

The Japanese CLI contract remains separate from the normal CLI because ambiguity
handling and confirmation UX differ.

## Relation To Self-Evolution

Self-evolution remains proposal-only. A self-evolution proposal may suggest a
tool capability, but it must not execute the tool, create a branch, open a PR,
merge, deploy, or mutate code automatically.

## Tests Required Before Runtime Widening

- unknown tool denied
- undeclared MCP tool denied
- shell execution denied
- file write denied
- secret-like output redacted
- local path and hostname output redacted
- approval required for mutating actions
- audit event emitted for allowed and denied decisions
- self-evolution proposal cannot execute a tool
- Japanese ambiguous intent requires dry-run and confirmation

## Not Included

- full MCP implementation
- dynamic MCP execution
- shell execution
- deploy
- production DB behavior
- production signing keys
- production trust stores
- persistent memory
- Google login
- external provider live generation

## Next Gate

Implement a small safe tool decision fixture that evaluates the contract above
without executing tools. Runtime tool execution remains out of scope until that
fixture and review gate pass.
