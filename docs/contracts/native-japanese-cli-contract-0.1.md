# Native Japanese CLI Contract 0.1

Status: v7.7 public-safe contract scaffold. Not an implementation.

## Purpose

The native Japanese CLI is a separate surface from the normal `yonerai` CLI
because Japanese user commands often carry omitted subjects, softer intent,
context-dependent urgency, and ambiguous action scope. This contract defines how
that surface must interpret, confirm, and refuse commands before any
implementation can safely execute actions.

This is not a final CLI product, not Google login, not persistent memory, not a
deployment tool, and not production readiness.

## Position In v7.7

- API remains the contract authority.
- Normal CLI remains the command authority for explicit commands.
- Native Japanese CLI is the ambiguity and confirmation UX authority.
- Web remains the product surface.
- SNS/growth remains distribution and claim discipline.

The Japanese CLI must call public API contracts. It must not duplicate Core
reasoning logic or directly import private/control-plane internals.

## Intent-To-Command Mapping

Every Japanese input is first mapped to one of these states:

| state | meaning | allowed next step |
|---|---|---|
| `explicit_safe_read` | User asks for a local status/read-only check. | Execute only if capability is allowlisted. |
| `explicit_safe_message` | User asks to send a mock/offline/local message through Core. | Execute through API after showing target and mode. |
| `ambiguous_action` | Subject, target, or consequence is unclear. | Explain ambiguity and ask for confirmation. |
| `destructive_or_external` | Could delete, deploy, publish, spend money, contact others, or expose data. | Dry-run only; approval required before any future implementation. |
| `forbidden_public_surface` | Requires private internals, production secrets, raw chain-of-thought, live routes, deploy, or uncontrolled external provider calls. | Refuse or defer with a safe explanation. |

## Ambiguity Handling

The CLI must not guess when the command is ambiguous.

Required ambiguity checks:

- target: what repo, API origin, file, PR, or surface is affected?
- mode: mock/offline/local/official/private?
- consequence: read-only, write, publish, deploy, delete, or contact?
- approval: is owner approval required?
- evidence: what API/test/doc result proves the action is safe?

If any required field is missing, the CLI returns a confirmation prompt instead
of executing.

## Explain-Before-Action Requirement

Before any non-read action, the Japanese CLI must show:

- interpreted intent
- target surface
- API endpoint or command it would call
- whether it is read-only or state-changing
- required approval state
- dry-run availability
- rollback or no-rollback note

## Dry-Run Requirement

Dangerous or externally visible actions must first produce a dry-run packet:

```yaml
dry_run:
  interpreted_intent: "<Japanese user intent summary>"
  target_surface: "public-core | clients/cli | clients/web | docs | unknown"
  proposed_api_call: "<method path or none>"
  state_change: true
  approval_required: true
  execution_allowed_now: false
  reason: "<why this is blocked or needs approval>"
```

## Approval Binding

Approval is scoped to the exact dry-run packet. If target, command, branch,
release, provider, or data class changes, approval is invalid and the CLI must
ask again.

Approval must never imply:

- deploy permission
- production signing
- production trust-store changes
- persistent memory
- Google login
- external provider live generation
- private/control-plane data access

## Capability Allowlist 0.1

Allowed in a future implementation:

- `yonerai health`
- `yonerai message --mode mock "..."`
- `yonerai run --mode mock "..."`
- read-only contract/doc lookup
- dry-run explanation for future actions

Not allowed in 0.1:

- shell command execution
- deploy commands
- branch deletion
- release/tag mutation
- production signing or trust-store changes
- private runtime inventory access
- persistent memory writes
- Google login
- Discord gateway actions
- uncontrolled external provider calls

## Audit Event Shape

Future implementations must emit public-safe audit metadata for every interpreted
Japanese command:

```yaml
audit_event:
  event_type: "native_japanese_cli_interpretation"
  contract_version: "native-japanese-cli-contract-0.1"
  input_language: "ja"
  interpreted_state: "explicit_safe_read | explicit_safe_message | ambiguous_action | destructive_or_external | forbidden_public_surface"
  target_surface: "<public-safe label>"
  capability: "<allowlisted capability or none>"
  approval_required: true
  dry_run: true
  executed: false
  memory_persisted: false
```

The audit event must not include raw chain-of-thought, secret values, private
runtime inventory, live route maps, or local machine paths.

## Examples

### Allowed Read

Input:

```text
状態を見せて
```

Interpretation:

```yaml
state: explicit_safe_read
command: yonerai health
approval_required: false
```

### Allowed Mock Message

Input:

```text
モックでこんにちはって送って
```

Interpretation:

```yaml
state: explicit_safe_message
command: yonerai message --mode mock "こんにちは"
approval_required: false
```

### Ambiguous Command

Input:

```text
これ直して
```

Required response:

```text
対象と変更範囲が不明です。どのファイル、PR、または機能を直すか指定してください。実行前に dry-run を表示します。
```

### Rejected Public Surface

Input:

```text
本番の秘密鍵を作ってデプロイして
```

Required response:

```text
この public CLI lane では production signing、trust store、deploy は扱いません。owner-approved production/control-plane lane が必要です。
```

## Tests Required Before Implementation

- Japanese safe read maps to health dry-run/execution.
- Japanese mock message maps to `yonerai message --mode mock`.
- Ambiguous command requests clarification and does not execute.
- Destructive/external command returns dry-run only.
- Forbidden production/private/control-plane command is refused.
- Audit event excludes raw chain-of-thought, secrets, local paths, and private inventory.

## Non-Claims

This contract does not claim:

- native Japanese CLI implementation complete
- final CLI product
- production readiness
- Google login
- persistent memory
- deploy support
- Discord gateway completion
- provider ecosystem completion

## Next Gate

Add parser fixtures and dry-run tests in a later branch before implementing any
Japanese command execution.
