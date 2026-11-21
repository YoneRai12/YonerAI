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
- Do not create GitHub Releases or tags for internal checkpoints, docs-only/process-only PRs, ledgers, root inventory, or PR-count reconciliation. Use `docs/changelog/checkpoints/` for checkpoint logs.
- Squash merge subjects should use `type: concise summary (#PR)`, with the PR number at the end. Do not rewrite old history or mass-touch files to change GitHub root "Last commit message" display.

## Required First Reads

Before scoped work, read:

- `docs/process/YONERAI_CODEX_WORKFLOW.md`
- `docs/process/YONERAI_GOAL_TEMPLATE.md`
- `docs/process/YONERAI_LANE_RULES.md`
- `docs/process/YONERAI_PR_REVIEW_INTAKE.md`
- `docs/process/YONERAI_RELEASE_GOVERNANCE.md` for release or checkpoint work
- `docs/process/YONERAI_CROSS_LANE_CONTRACTS.md` for cross-lane runtime, sync, or live smoke
- relevant lane docs under `docs/contracts/`, `docs/architecture/`, `docs/design/`, `docs/roadmap/`, or `docs/maintenance/`

## Validation Baseline

Run the smallest relevant set, usually including: `git diff --check`; targeted tests; public smoke when runtime/API/CLI/Web behavior changes; `ruff` and `compileall` for touched Python paths; secret and local-path scan on changed files; mojibake and hidden-Unicode scan on changed public text.

## Special Boundaries

- `reference_clawdbot`: do not initialize, repair, remove, replace, stage, or edit.
- `src/cogs/ora.py`: not permanently forbidden, but implementation edits require characterization tests and behavior-preserving extraction scope.
- Live Discord, real tokens, deploys, production signing keys, production trust stores, persistent memory, Google login, and production DB behavior require an explicit owner-approved private/live lane.
- Do not broad-rename ORA symbols without a compatibility plan and tests.

## Lane Ownership

- CLI visual, terminal theme, IME, and display polish are the Claude lane.
- Control Spine client behavior, auth/session/sync command contracts, release gates, manifests, and GitHub Releases are the Codex lane.
- Design book updates, design deltas, and broad audit narratives are the Claude doc lane unless the current owner prompt assigns them elsewhere.
- GPT-5.5 is the manager lane for cross-lane decisions, final claim boundaries, and ownership conflicts.
- Files owned by another lane must not be modified without an explicit handoff tag in the current task, PR body, or review thread.
- Review ping-pong is limited to one response round per disputed point. If a conflict remains after that, escalate to the manager lane instead of repeatedly editing the same files.
- All lanes must read `CURRENT_TRUTH.md`, `AGENTS.md`, and `docs/process/YONERAI_CODEX_WORKFLOW.md` before making public release, API, CLI, or production-readiness claims.

## Cross-Lane Contracts (summary)

Before any live integration window, owner-only smoke, E2E, or cross-lane runtime test: verify every shared interface statically (public-safe request/response, auth, errors, Firestore rule/query when applicable). Producers publish; consumers ACK or report mismatch on issue #552 unless a manager-approved ledger replaces it. Live smoke MUST NOT start without fresh ledger ACKs. Do not guess peer behavior, widen rules for client queries, or burn owner approval on mismatches static comparison could catch. Matrix, Firestore, Web send, and session persistence detail: `docs/process/YONERAI_CROSS_LANE_CONTRACTS.md`.

## Review Criteria

When the goal authorizes PRs: include scope, validation, non-claims, and boundary confirmations; classify review as P0/P1/P2/P3, outdated, duplicate, or false-positive; fix P0/P1/security/correctness before merge; rerun validation after fixes; merge only when checks pass and no material review remains. Use `docs/process/YONERAI_PR_REVIEW_INTAKE.md` for intake checkpoints and `docs/process/REQUIRED_CHECKS.md` for branch protection.

## No CI-Burning Polish While Blocked

When blocked on owner approval, cross-lane gate, or owner-only smoke window, do not create PRs for:

- helper scripts
- evidence templates
- runbooks
- checkpoint-only updates
- ACTIVE.md-only updates
- review-checkpoint-only updates
- readiness wrappers
- UI polish
- docs-only restatements

Every PR burns GitHub Actions minutes, Codex rate window, review time, and owner attention.

Allowed work while blocked:

1. run the smoke when the gate opens
2. fix a current P0/P1/security issue
3. fix the minimal blocker directly preventing the smoke
4. report blocked and wait

A checkpoint may be updated locally without opening a PR while blocked. Batch such docs into one later PR only after E2E passes or the blocker is genuinely resolved.

No production claim.
No broad scope expansion.
No UI polish during sync launch unless explicitly requested by owner.

## Reporting

Final reports must be Japanese and include exact PRs, commits, tests, scans, runtime-boundary status, `src/cogs/ora.py` status, `reference_clawdbot` status, non-claims, blockers, and the next recommended goal.