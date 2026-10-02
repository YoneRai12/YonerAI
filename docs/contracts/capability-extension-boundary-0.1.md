# Capability / Extension Boundary 0.1

Status: v7.7 public-safe boundary checkpoint. Not a tools/MCP completion claim.

## Purpose

YonerAI now has multiple public-facing lanes: Core API, CLI, native Japanese CLI
contract, Web smoke surface, growth/SNS docs, hybrid connector fixture,
self-evolution proposal-only, and local LLM boundary. This contract defines the
public capability boundary that keeps those lanes explicit and deny-by-default
before broader extensions or tools are enabled.

## Boundary Rule

The public repo treats unknown capabilities as unavailable. A capability must be
declared before a public surface can describe it as available.

Capability declaration does not mean production readiness. It only records the
current public-safe status:

- `available`: runnable in the public MVP without credentials or production
  dependencies.
- `proposal_only`: public-safe proposal queue behavior only.
- `quarantine_only`: accepted only into quarantine/policy review, not trusted or
  persisted.
- `contract_only`: documented boundary only; no executable public path.
- `docs_only`: public documentation or claim guardrail, not runtime behavior.
- `disabled`: not available in the public MVP.

## Current Public Capabilities

The code-level public manifest is in `core/src/ora_core/public_capabilities.py`.

Available public-safe lanes:

- `api.health`
- `api.public_messages.mock_offline`
- `api.agent_run.mock_offline`
- `cli.health`
- `cli.message_mock`
- `cli.run_mock`
- `web.temporary_chat_smoke`
- `web.safe_error_display`
- `local_llm.loopback_ollama`
- `local_llm.loopback_openai_compatible`

Policy-gated public-safe lanes:

- `self_evolution.proposal_only`
- `memory.candidate_quarantine`
- `hybrid.connector_fixture`

Contract/docs-only lanes:

- `native_japanese_cli.contract`
- `growth_sns.claim_guardrails`
- `tools.mcp.safe_subset`

Disabled lanes:

- `tools.mcp.dynamic_execution`
- `tools.shell`
- `memory.persistent`
- `private_runtime.inventory`
- `control_plane.official_cloud_runtime`
- `discord.gateway_complete`
- `web.final_ui`

## Tools/MCP Boundary

Tools/MCP remains contract-only or disabled by default in this checkpoint.

The public repo does not enable:

- arbitrary shell execution
- arbitrary file writes
- deploy actions
- secret access
- private runtime inventory reads
- live route map exposure
- raw chain-of-thought exposure
- automatic code mutation, PR creation, merge, or deploy

The next Tools/MCP lane must define an explicit safe subset before runtime
execution is widened.

## Same-Experience Constraint

API, CLI, Web, local LLM, hybrid fixture, and future Japanese CLI surfaces must
use consistent capability labels. A feature must not silently appear as enabled
in one surface while being unavailable, private-only, or control-plane-only in
another.

## Tests

`tests/test_public_capability_boundary.py` verifies:

- unknown capability is denied by default
- private/control-plane capabilities are not enabled public capabilities
- Tools/MCP is contract-only or disabled by default
- memory persistence remains disabled
- self-evolution remains proposal-only
- public API / CLI / Web / local LLM smoke capabilities are explicitly listed

## Not Included

- full MCP implementation
- dynamic tool execution
- shell execution
- production deployment
- production signing or trust stores
- persistent memory
- Google login
- Discord gateway completion
- final Web UI
- external provider live generation

## Next Gate

Define the Tools/MCP safe subset contract. It must keep tools disabled by
default unless a public-safe allowlist, approval model, audit event shape, and
secret/local-path redaction tests are in place.
