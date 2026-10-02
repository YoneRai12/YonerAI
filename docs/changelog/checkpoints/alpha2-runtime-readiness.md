# Alpha2 Runtime Readiness Checkpoint

Date: 2026-05-22

## Summary

YonerAI now has a public-safe runtime experience foundation after `v0.1.0-alpha.1`.
This checkpoint does not create a release or tag. It records whether the new runtime surface is ready to consider as a future `v0.1.0-alpha.2` candidate after owner review.

## Implemented

- Provider adapter contracts for request, response, status, capabilities, and safe errors.
- Deterministic mock provider for default tests and demos.
- OpenAI-compatible provider contract with redacted env presence and request payload construction.
- Provider registry that lists configured and unconfigured providers without live calls.
- Task classification for public summarization, research-like work, coding, private local files, PC operations, dangerous operations, long-running tasks, and unsupported live/private requests.
- Model/provider selection policy based on task risk, mode, provider availability, and local-node requirements.
- Execution-plan preview that combines classification, route preview, provider/model selection, approval gates, disabled reasons, and side-effect boundaries.
- CLI `yonerai plan` and `yonerai ask --dry-run`.
- Public demo `provider_planner` section.

## Large-Codebase Connections

- `src/cogs/mcp_policy.py` is connected as a preview-only safety check in execution plans. It does not execute MCP tools.
- `core/src/ora_core/brain/process.py` managed download guard behavior is connected as a preview-only safety check. It does not download or write files.

## Security And Boundary

- No live provider call is made by default.
- No provider key is required for tests, demo, plan, or ask dry-run.
- Provider key presence is reported only as `present_redacted`.
- `yonerai ask` requires `--dry-run`; live execution remains blocked.
- Official Managed Cloud remains external and contract-only in the public repo.
- Live Discord, Oracle, persistent memory, Google login, production DB behavior, deploy, telemetry ingestion, production signing keys, and production trust stores are not included.

## PR Debt Notes

- PR #25 and PR #32 are now stronger superseded candidates because current-main runtime planning covers provider/model selection, route preview, and approval-gated planning without touching `src/cogs/ora.py`.
- PR #121 remains an owner/product decision because it is a broad draft managed-cloud web/runtime lane and conflicts with the public repo contract-only cloud boundary.
- PR #78, #79, #82, #134, and dependency PRs should remain in their own lanes.

## Tests

Targeted tests cover:

- provider adapter success/unavailable/error redaction
- OpenAI-compatible payload construction without live call
- task classification
- provider/model selection
- execution-plan preview
- CLI `plan` and `ask --dry-run`
- public demo provider/planner section

## Not Included

- No GitHub Release or tag.
- No live OpenAI, Anthropic, Gemini, Discord, or Oracle connection.
- No network-executing installer.
- No npm publishing or winget implementation.
- No persistent memory.
- No production trust material.
- No `src/cogs/ora.py` fix or broad ORA rename.

## Readiness Judgment

The runtime experience is a reasonable candidate for a future `v0.1.0-alpha.2` release gate after broader validation and owner approval. Do not publish automatically from this checkpoint.
