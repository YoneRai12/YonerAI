# Alpha2 Execution Spine Readiness Checkpoint

Date: 2026-05-22

## Summary

YonerAI now has a public-safe execution spine on top of the provider/planner
preview surface. This checkpoint records readiness for a future
`v0.1.0-alpha.2` discussion only. It does not create a GitHub Release or tag.

## Implemented

- Redacted run ledger with `run_id`, execution events, route/provider decisions,
  status, disabled reason, and result/error summaries.
- Default mock provider execution through the `ProviderAdapter` path.
- CLI `yonerai ask` actual mock execution with structured JSON output and
  human-readable pretty output.
- CLI `yonerai runs list` and `yonerai runs show` for an opt-in redacted JSONL
  local ledger.
- OpenAI-compatible provider live execution path gated by both `--live` and
  `YONERAI_OPENAI_COMPATIBLE_LIVE=1`.
- Local LLM provider registry integration using the existing loopback-only local
  LLM config and transport path.
- Web-search and tool boundary adapters modeled as disabled/mock/plan-only
  surfaces with no live network or shell execution by default.
- Public demo `execution_spine` section showing mock execution, run status,
  local provider availability, and disabled search/tool boundaries.

## Large-Codebase Connections

- `src/cogs/mcp_policy.py` remains connected through the execution-plan safety
  checks and tool boundary deny behavior. It does not execute MCP tools.
- `core/src/ora_core/brain/process.py` managed download guard remains connected
  through plan safety checks. It does not download or execute artifacts.
- `src/utils/redaction.py` is used by the run ledger when available so run
  summaries avoid secrets and local path leakage.

## Runtime Boundary

- Default execution uses the deterministic mock provider.
- Default CI and smoke tests do not require provider keys.
- OpenAI-compatible execution is unavailable unless explicitly selected with
  `--live` and enabled with env configuration.
- Local LLM execution is loopback-only and unavailable unless explicitly enabled.
- Dangerous operations remain approval-gated and preview-only.
- Search, shell, arbitrary local file reads, deploy, live Discord, Oracle,
  persistent memory, production DB behavior, telemetry ingestion, npm publishing,
  winget, production signing keys, and production trust stores are not included.

## PR Debt Notes

- PR #25 and PR #32 remain superseded candidates after the provider/planner and
  execution spine landed on current main.
- PR #121 remains an owner/product decision because it is broader than the
  public repo execution spine and touches managed-cloud/runtime posture.
- No PR was closed from this checkpoint without owner review.

## Validation

Targeted validation should include:

- run ledger create/append/complete/fail/redaction tests
- mock `yonerai ask` execution tests
- dangerous task blocked tests
- OpenAI-compatible no-key/no-live/skip-live tests
- local LLM loopback/non-loopback tests
- search/tool boundary deny tests
- public demo JSON and pretty output tests
- CLI run history tests
- `ruff`, `compileall`, `git diff --check`
- secret/local path and mojibake/hidden Unicode scans

## Readiness Judgment

This is release-candidate material for a future `v0.1.0-alpha.2` owner gate if
the validation matrix and CI remain clean. Do not publish automatically from this
checkpoint.
