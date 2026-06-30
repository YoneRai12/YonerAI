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

## Lane Ownership

- CLI visual, terminal theme, IME, and display polish are the Claude lane.
- Control Spine client behavior, auth/session/sync command contracts, release gates, manifests, and GitHub Releases are the Codex lane.
- Design book updates, design deltas, and broad audit narratives are the Claude doc lane unless the current owner prompt assigns them elsewhere.
- GPT-5.5 is the manager lane for cross-lane decisions, final claim boundaries, and ownership conflicts.
- Files owned by another lane must not be modified without an explicit handoff tag in the current task, PR body, or review thread.
- Review ping-pong is limited to one response round per disputed point. If a conflict remains after that, escalate to the manager lane instead of repeatedly editing the same files.
- All lanes must read `CURRENT_TRUTH.md`, `AGENTS.md`, and `docs/process/YONERAI_CODEX_WORKFLOW.md` before making public release, API, CLI, or production-readiness claims.

## Cross-Lane Contract Pre-Verification

Before any live integration window, owner-only smoke, E2E, or cross-lane runtime test, every lane MUST verify the contract at every interface it shares with another lane by using cross-thread Codex messages and the canonical coordination issue.

Do not discover contract mismatches by opening a live window.

A contract means the exact public-safe shape of the interface, including:

- request JSON shape
- response JSON shape
- required fields
- forbidden fields
- auth credential type at that hop
- status codes
- error shape
- Firestore security rule shape
- Firestore query shape
- body fetch shape
- status snapshot shape
- event schema
- retry/idempotency/cursor semantics

The producing lane MUST publish its exact public-safe contract before live execution.

The consuming lane MUST reply with an explicit ACK or mismatch report before live execution.

Examples:

- AWS publishes the body endpoint response shape.
- Public CLI ACKs that its sanitizer accepts that exact shape.
- AWS publishes the Firestore rule shape.
- Public CLI publishes its Firestore query shape.
- AWS and Public verify rule/query compatibility before any sync window.
- YonerAIWEB publishes that live `/jp/chat` serves the sync runtime and not a stale MVP-only runtime.
- StatusWEB publishes that it consumes only public-safe StatusSnapshot/feed fields.

Cross-thread messages are mandatory for cross-lane runtime work. They are not optional status updates.

The canonical coordination ledger is issue #552 unless a newer manager-approved ledger is specified.

Live smoke MUST NOT begin unless all required producer/consumer ACKs exist as fresh standalone tags or explicit ACK comments in the ledger.

Forbidden:

- implementing against guessed peer behavior
- widening security rules to make a client query pass
- accepting stale tags from old failed windows
- treating "missing" text as a present tag
- using old window evidence after rollback
- consuming owner approval to discover a static contract mismatch
- adding helper scripts/runbooks/templates while the direct blocker is an unverified cross-lane contract

Firestore-specific rule learned from the 2026-06 Firestore read 400 incident:

Firestore Security Rules are not filters. A client query is rejected unless the query itself carries the same constraints that the rules require.

Therefore, before any Firestore live read smoke:

- AWS must publish the deployed rule shape.
- Public/YonerAIWEB must publish their query shape.
- The rule and query must be compared before opening a sync window.
- If they mismatch, fix the client query to match the strict rule.
- Do not broaden the rule unless manager explicitly approves a security tradeoff.
- Broad `sync_events` list relaxation is forbidden for closed-alpha sync.

Owner approval is expensive and bounded. It must never be consumed to discover a mismatch that static cross-lane contract comparison could have caught.

## Cross-Lane Contract Matrix

Before opening any live integration window, owner smoke, E2E, or cross-lane runtime test, every producing and consuming lane must complete a public-safe contract matrix on issue #552.

A live smoke window must never be used to discover a contract mismatch that could have been caught by comparing public-safe contracts.

For every interface, record:

- producer lane
- consumer lane
- endpoint/path
- request JSON shape
- response JSON shape
- required fields
- forbidden fields
- auth credential type
- status codes
- error shape
- Firestore rule shape if applicable
- client query shape if applicable
- ACK tag from producer
- ACK tag from consumer
- AWS verification tag if AWS owns the rule or endpoint

Interfaces include at minimum:

1. AWS body endpoint -> Public CLI body fetch
2. AWS body endpoint -> YonerAIWEB body fetch
3. AWS Firestore rules -> Public CLI Firestore query
4. AWS Firestore rules -> YonerAIWEB onSnapshot query
5. YonerAIWEB Web sender -> AWS Web receiver endpoint
6. AWS firebase-config -> Public CLI / YonerAIWEB Firebase init
7. AWS firebase-token -> Public CLI / YonerAIWEB Firebase sign-in
8. AWS status snapshot -> StatusWEB feed adapter

## Firestore Consumers

Firestore security rules are not filters.

Every Firestore consumer must make a query that already satisfies the same constraints required by the rules.

This applies to:

- Public CLI one-shot receiver
- YonerAIWEB onSnapshot listener
- any future Local UI listener
- any future mobile/client listener

Before owner-only sync smoke:

- AWS must publish the deployed safe Firestore rule shape.
- Public must ACK its CLI query shape.
- YonerAIWEB must ACK its Web/onSnapshot query shape.
- AWS must verify both consumer query shapes against deployed rules.
- The live window must not open until both consumer queries are verified.

Never fix a Firestore rule-vs-query failure by broadening rules unless the rule itself is proven wrong. Prefer fixing the query to match the strict safe rule.

## Web Send Contract

The Web sender path is also a cross-lane contract.

Before owner-only sync smoke:

- YonerAIWEB must publish the exact live Web sender endpoint and request shape.
- AWS must confirm the matching endpoint exists in the currently deployed staging API.
- AWS must confirm the response shape includes the body commit acknowledgement fields the Web runtime expects.
- YonerAIWEB must ACK the response shape.
- The smoke window must not open until Web sender and AWS receiver match.

A Web-side send helper alone is not sufficient. The producer/consumer pair must match.

## Auth Session Persistence Contract

A staging login is not considered ready merely because a client saved a local claim or `whoami` appears successful.

For any owner-only sync smoke, login readiness means all of the following are true:

- the client can authenticate to staging
- the server-side canonical staging session store contains an active row for the same authenticated owner
- `whoami` and owner allowlist construction read from the same canonical session source
- expired or stale rows are rejected
- a completed login writes exactly one active canonical session row
- no token, account identifier, raw body, private path, provider key, or secret is logged

If `whoami` succeeds but the owner allowlist builder cannot find an active canonical session row, this is a session persistence contract failure. Do not ask the client to repeatedly re-login. Fix the persistence path or the source mismatch.

Routine session refresh may be autonomous during staging preflight. Opening a sync window remains owner-gated.

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
