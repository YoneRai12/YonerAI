# YonerAI Surface / Repo Strategy 2026-05-20

Status: public-safe v7.7 implementation checkpoint. This document is a strategy and boundary ledger, not an implementation plan to land CLI/API/Web/SNS in one branch.

## Decision

Keep YonerAI CLI, API, Web, and SNS source in the public monorepo for now.

The reason is the v7.7 design truth: YonerAI needs one common distribution core and one same-experience contract across official, local, and self-host directions. The product modes should differ through profile, connector, permission, auth, capability manifest, and approval boundaries. They should not diverge into separate codebases before the shared run contract is stable.

This is not a production-readiness claim and not a full product completion claim.

## Why Not Split Now

Splitting the surfaces now would create four risks:

- duplicated contract definitions before the API run envelope is stable
- provider-specific or UI-specific behavior drifting away from provider independence
- public/local/self-host experience labels diverging silently
- old Discord/Web/runtime branches being mistaken for current product truth

Separate repos become useful only after a surface can be packaged without copying core runtime logic or hiding shared contracts.

## API Lane

The API lane is the contract authority.

Surface API 0.1 checkpoint:

- public Core exposes a local in-memory run smoke surface at `POST /api/v1/agent/run`
- run events/results are available at the returned `events_url` and `results_url`
- the surface is not production cloud, not persistent memory, and not final SSE exactness

Next gates:

- SSE event schema
- error schema
- idempotency model
- capability manifest and approval requirements
- signed-envelope and donation-policy compatibility labels

Do not broaden runtime behavior from old dashboard or Discord branches until the public contract documents and tests define the shape.

## CLI Lane

The normal CLI remains public-repo work under `clients/cli` after the Surface API 0.1 run contract is stable.

Surface CLI 0.1 checkpoint:

- `clients/cli` is a temporary local public MVP smoke CLI
- `yonerai health` calls local Core `/health`
- `yonerai message --mode mock "hello"` calls `/v1/public/messages`
- `yonerai run --mode mock "hello"` calls `/api/v1/agent/run`
- remote API origins are rejected by default; loopback Core is required

The CLI should be install-first, test-backed, and narrow:

- local health check
- public message smoke
- local provider selection
- session scaffold inspection
- signed-envelope fixture validation when explicitly requested

It must not become a backdoor for deployment, private runtime inventory, production signing keys, persistent memory, or external provider live generation.

## Native Japanese CLI Lane

The native Japanese CLI is a separate UX lane from the normal CLI.

Reason: Japanese ambiguous commands often need confirmation, explanation, and safer default prompts. It should have separate confirmation UX and docs instead of inheriting terse English CLI behavior blindly.

Next gate:

- command ambiguity policy
- confirmation text fixtures
- refusal / deferral wording
- user-visible safety summary
- parity tests against the API contract

## Web Lane

The Web lane is the product surface, not the contract authority.

Current state:

- `clients/web` is a temporary Web Chat MVP / smoke-demo surface
- old `ora-ui` is retired from active public surface
- final Web product UI is not claimed

Next gates:

- same-experience ledger
- capability manifest display
- safe local/mock provider controls
- dropoff and error UX events
- privacy-preserving feedback affordances

Do not build final Web UI from old broad branches without a fresh v7.7 surface plan.

## SNS / Growth Lane

SNS and growth work belongs in the public repo as docs, examples, FAQ, release notes, and claim guardrails until it becomes a separate campaign/runtime need.

This lane is not a core branch blocker.

Next gates:

- demo plan
- release-note checklist
- public claim guardrails
- FAQ for local/self-host/official directions
- no production or provider-parity overclaim

## Separate Repo Trigger

Create a separate CLI/SDK/Web/SNS repository only when all are true:

- the surface has stable package boundaries
- shared contracts are imported or generated without duplicating core logic
- public/local/self-host capability labels are stable
- release and test discipline can be maintained independently
- moving it does not hide public contract truth or create a private dependency

Until then, keep the source in the public repo and separate lanes by directory, docs, tests, and capability boundaries.

## OpenAI / xAI Repository Lessons To Reuse

Reusable patterns:

- install-first README
- clean root surface
- visible `SECURITY` / `CONTRIBUTING` discipline where applicable
- examples and tests close to the public contract
- release notes and tag discipline
- plan / review / approve workflows for risky changes
- subagents / worktrees as review and validation patterns

Non-goals:

- do not copy provider-specific lock-in
- do not claim provider parity
- do not treat model-provider branding as YonerAI product truth
- do not place production trust material in the public repo

## Current Repo Strategy Summary

| surface | current repo decision | reason | next gate | separate repo trigger |
|---|---|---|---|---|
| API | stay public monorepo | contract authority and public Core tests live here | run/SSE/error/idempotency contract | stable generated SDK boundary |
| CLI | stay public monorepo for future lane | depends on API contract | `clients/cli` or package scaffold after contract stability | package can ship without copying core |
| Native Japanese CLI | stay public monorepo for future lane | confirmation UX and ambiguity rules need same contract | Japanese confirmation fixtures | UX package stabilizes |
| Web | stay public monorepo | temporary Web Chat MVP and capability labels depend on Core | same-experience ledger and capability manifest | final Web surface has stable public package boundary |
| SNS / growth | stay public docs lane | claim discipline and demo plan are public-facing | FAQ, demo plan, release checklist | campaign tooling needs independent lifecycle |
| Discord gateway | do not expand in public lane | private/runtime boundary and `src/cogs/ora.py` residue | extraction plan, owner approval | private runtime repo decision |

## Non-Claims

This strategy does not claim:

- production readiness
- shipping completeness
- official-cloud completion
- hybrid completion
- persistent memory completion
- Google login completion
- Discord gateway completion
- provider ecosystem completion
- final Web UI completion
- `src/cogs/ora.py` resolution
