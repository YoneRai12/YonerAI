# AGENTS.md - YonerAI Codex Baseline

## Product Identity

- Public product name: YonerAI.
- ORA remains a legacy/internal runtime namespace until compatibility migration is explicitly planned and tested.
- Public repo role: contract-first distribution core. Private runtime and Oracle/control-plane work stay behind contracts.

## Non-Negotiable Invariants

- Preserve public/private/control-plane separation.
- Never expose secrets, private runtime truth, live routes, raw production inventory, break-glass detail, raw chain-of-thought, or control-plane internals.
- Preserve provider independence and the same experience across Full Private Self-Host, Official Hybrid Private, and Official Managed Cloud.
- Dangerous capabilities are deny-by-default.
- A signed envelope proves origin/integrity only; it does not imply trust or approval.
- Do not claim production-ready, shipping-complete, official-cloud complete, Discord restored, persistent memory complete, Google login complete, final Web UI complete, Tools/MCP complete, full hybrid complete, `src/cogs/ora.py` solved, broad ORA rename complete, or v7.8 started without explicit evidence and approval.

## Work Style

- Work implementation-first under guardrails: prefer code, tests, fixtures, and acceptance harnesses when safe.
- Docs-only PRs are allowed when they unblock implementation, release, review, governance, or a blocked boundary decision.
- Prefer fresh current-main patches over merging stale PRs.
- Never broad-refactor without characterization tests.
- Keep PRs lane-scoped; do not mix unrelated lanes in one PR.
- Do not push, create PRs, merge, tag, create releases, deploy, migrate, or broaden scope unless the current user goal explicitly authorizes that action.

## Required First Reads

Before scoped work, read:

- `docs/process/YONERAI_CODEX_WORKFLOW.md`
- `docs/process/YONERAI_GOAL_TEMPLATE.md`
- `docs/process/YONERAI_LANE_RULES.md`
- relevant lane docs under `docs/contracts/`, `docs/architecture/`, `docs/design/`, `docs/roadmap/`, or `docs/maintenance/`

## Validation Baseline

Run the smallest relevant set, usually including:

- `git diff --check`
- targeted tests for touched behavior
- public smoke tests when runtime/API/CLI/Web behavior changes
- `ruff` and `compileall` for touched Python paths
- secret and local-path scan on changed files
- mojibake and hidden-Unicode scan on changed public text

## Special Boundaries

- `reference_clawdbot`: do not initialize, repair, remove, replace, stage, or edit.
- `src/cogs/ora.py`: not permanently forbidden, but implementation edits require characterization tests and behavior-preserving extraction scope.
- Live Discord, real tokens, deploys, production signing keys, production trust stores, persistent memory, Google login, and production DB behavior require an explicit owner-approved private/live lane.
- Do not broad-rename ORA symbols without a compatibility plan and tests.

## Reporting

Final reports must be Japanese and include exact PRs, commits, tests, scans, runtime-boundary status, `src/cogs/ora.py` status, `reference_clawdbot` status, non-claims, blockers, and the next recommended goal.
