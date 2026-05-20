# YonerAI Release Notes

This page is a public-safe index of current release notes and progress checkpoints.

## v2026.5.20.8 Surface CLI Smoke Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.8-surface-cli-smoke-checkpoint.md`
- Scope: temporary local smoke CLI under `clients/cli` for health, public message, and Surface API run checks against loopback Core.
- Status: public CLI smoke checkpoint, not final CLI, not native Japanese CLI, not production, and not deploy.
- Still open: native Japanese CLI contract, Web capability manifest, Growth/SNS claim guardrails, final packaging/signing, and broader old PR review.

## v2026.5.20.7 Surface API Run Contract Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.7-surface-api-run-contract-checkpoint.md`
- Scope: public Core Surface API 0.1 run contract, in-memory run events/results, and a fresh narrow #142 access-gate fix for current main.
- Status: public API surface checkpoint, not production and not official-cloud completion.
- Still open: CLI smoke client, native Japanese CLI contract, Web capability manifest, Growth/SNS claim guardrails, and broader old security PR review.

## v2026.5.20.6 Hybrid Envelope Policy Semantics Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.6-hybrid-envelope-policy-semantics-checkpoint.md`
- Scope: post-merge hybrid policy semantics fix so memory-candidate and improvement-proposal policy checks cannot be bypassed by spoofing `data_class` or mixing inconsistent semantic fields.
- Status: public policy/correctness checkpoint, not production and not a full hybrid connector.
- Still open: production key lifecycle, durable replay protection, root helper retirement, persistent memory decision, and future `src/cogs/ora.py` extraction.

## v2026.5.20.5 Public Surface and Release Hygiene Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.5-public-surface-release-hygiene-checkpoint.md`
- Scope: public README/checkpoint hygiene, same-day release suffix policy, root surface policy/inventory updates, PR-number presentation policy, and zero-trust practicality matrix.
- Status: public surface checkpoint, not production and not a deploy.
- Still open: older future-dated release metadata correction decision, safe root helper movement lane, provider boundary hardening, local LLM error UX, memory policy, and future `src/cogs/ora.py` extraction.

## v2026.5.20.4 Hybrid Connector Fixture and Memory Policy Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.4-hybrid-connector-fixture-memory-policy-checkpoint.md`
- Scope: synthetic Hybrid Connector Fixture, memory candidate quarantine policy scaffold, public fixture helpers, and capability priority map.
- Status: hybrid fixture checkpoint, not production and not a full hybrid connector.
- Still open: real private connector implementation, production signing/key lifecycle, durable replay protection, approval workflow UI, persistent memory decision, and capability/extension boundary hardening.

## v2026.5.20.3 Hybrid Signed Envelope Donation Policy Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.3-hybrid-signed-envelope-donation-policy-checkpoint.md`
- Scope: public-safe Hybrid Signed Envelope contract, donation quarantine policy, schema helpers, and tests proving signed donated payloads are not trusted automatically.
- Status: hybrid contract checkpoint, not a production release and not a full hybrid connector.
- Still open: private/local signing fixture, production-grade key lifecycle design, durable replay store, owner approval UI contract, persistent memory decision, and official control-plane deployment-free ingress review.

## Historical Future-Dated Labels Requiring Correction

These entries are kept for traceability, but their labels are future-dated relative to the verified 2026-05-20 cleanup date. They should not be used as the current public latest checkpoint.

## v2026.5.22 Web Chat MVP Review-gate Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.22-web-chat-mvp-review-gate-checkpoint.md`
- Scope: clarify `clients/web` as a temporary Web Chat MVP, add mock/local provider controls, improve safe Core API error display, and fix the remaining observed `clients/web` `postcss` advisory locally.
- Status: public temporary Web Chat MVP checkpoint, not a production release.
- Still open: GitHub Dependabot rescan after merge, final Web product UI, Google login, persistent memory, Discord gateway completion, old security PR review, safe branch/worktree cleanup, model listing, local LLM error UX, and future `src/cogs/ora.py` extraction.

Note: this historical markdown note uses a future date relative to the verified 2026-05-20 cleanup date. It should not be treated as the current public latest checkpoint.

## v2026.5.21 ora-ui Retirement and Security Backlog Cleanup Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.21-ora-ui-retirement-security-cleanup-checkpoint.md`
- Scope: retire obsolete `ora-ui`, remove its dependency manifest from the active public surface, and update security/backlog triage.
- Status: public maintenance checkpoint, not a production release.
- Still open: remaining `clients/web` dependency alert until the later web checkpoint reaches main and GitHub rescans, non-`ora-ui` Dependabot PRs, old security PR review, safe branch/worktree cleanup, model listing, local LLM error UX, and future `src/cogs/ora.py` extraction.

Note: this historical markdown note uses a future date relative to the verified 2026-05-20 cleanup date. It should not be treated as the current public latest checkpoint.

## v2026.5.21 Local LLM Provider Compatibility Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.21-local-llm-provider-compatibility-checkpoint.md`
- Scope: provider-neutral local LLM compatibility for Ollama-style `/api/chat` and OpenAI-compatible local `/v1/chat/completions` servers.
- Status: public local provider compatibility checkpoint, not a production release.
- Still open: optional loopback-only model listing endpoint, final Web product UI, Google login, persistent memory, Discord gateway completion, non-loopback/private provider lanes, and future `src/cogs/ora.py` extraction.

Note: the GitHub Release/tag exists, but its label is future-dated relative to the verified 2026-05-20 cleanup date. Do not delete or retag it without explicit owner approval; use a corrected current-date release for latest visibility when safe.

## Same-Day 2026-05-20 Checkpoint History

## v2026.5.20.2 Conversation Session Scaffold Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.2-conversation-session-scaffold-checkpoint.md`
- Scope: public Core API conversation session metadata, feature inventory, and releaseability map.
- Status: public conversation session scaffold checkpoint, not a production release and not persistent memory.
- Still open: memory policy scaffold, identity/login, cross-device history, official cloud runtime, stale dashboard/login route isolation, and future `src/cogs/ora.py` extraction.

## v2026.5.20.1 Official Cloud Control Plane MVP Planning Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.1-official-cloud-control-plane-mvp-planning-checkpoint.md`
- Scope: cross-repo same-experience matrix, Official Cloud Control Plane MVP contract, and official self-evolution proposal queue boundary.
- Status: public-safe planning checkpoint, not a production release and not a claim that official cloud is complete.
- Still open: control-plane skeleton PR review, private runtime clean-baseline decision, hybrid private result-envelope contract, memory policy scaffold, owner approval UI contract, and deployment-free official control-plane tests.

## v2026.5.20 Local LLM Conversation MVP Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20-local-llm-conversation-mvp-checkpoint.md`
- GitHub Release: `v2026.5.20` normal visible checkpoint
- Scope: loopback-only local LLM adapter, `POST /v1/public/messages` local mode, Dependabot triage refresh, and open PR backlog gate.
- Status: public Local LLM conversation MVP checkpoint, not a production release.
- Still open: final Web product UI, Google login, persistent memory, Discord gateway completion, `ora-ui` dependency remediation, non-loopback/private provider lanes, and future `src/cogs/ora.py` extraction.

## v2026.5.20 Web UI Mock-chat Security Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20-web-ui-mock-chat-security-checkpoint.md`
- Scope: Dependabot triage, public message API follow-up hardening, `clients/web` dependency cleanup, and a local mock/offline Web UI surface.
- Status: public Web UI mock-chat checkpoint, not a production release.
- Still open: live provider generation, Google login, persistent memory, Discord gateway completion, `ora-ui` dependency remediation, and future `src/cogs/ora.py` extraction.

## v2026.5.20 Public Core Message MVP Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20-public-core-message-mvp-checkpoint.md`
- Scope: credential-free local Core API mock/offline message contract plus refactor Step 0.1 static analyzer hardening.
- Status: public core message MVP checkpoint, not a production release.
- Still open: Web UI chat, provider adapter boundary, memory persistence, Google login, Discord gateway completion, web search, official cloud, and future `src/cogs/ora.py` extraction.

## v2026.5.19 `ora.py` Import Map Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.19-ora-py-import-map-checkpoint.md`
- Scope: static import map tooling and facade contract tests for `src/cogs/ora.py`.
- Status: refactor Step 0 checkpoint, not a production release.
- Still open: implementation extraction, rename, runtime split, private/control-plane ownership, and behavior-preservation tests for later PRs.

## v2026.5.19 Self-Evolution Proposal-only Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.19-self-evolution-proposal-only-checkpoint.md`
- Scope: synthetic fixture signal normalization, proposal scoring, owner-reviewable Markdown proposal packets, and approval-gate tests.
- Status: public-safe proposal-only MVP checkpoint, not a production release.
- Still open: real telemetry remains out of scope, SNS scraping remains out of scope, and execution lanes require owner approval.

## v2026.5.19 Branch Hygiene and Refactor Readiness Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.19-branch-hygiene-refactor-readiness-checkpoint.md`
- Scope: branch / PR / worktree hygiene inventory plus `src/cogs/ora.py` decomposition planning.
- Status: maintenance checkpoint, not a production release.
- Still open: PR #169 review fixes, dedicated worktree cleanup, dedicated remote branch deletion, dependency-security triage, and future `src/cogs/ora.py` implementation.

## v2026.5.19 Public Runnable MVP Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.19-public-runnable-mvp-checkpoint.md`
- GitHub Release: `v2026.5.19` prerelease checkpoint
- Scope: PR #163 boundary-plan closure plus a credential-free local Core API smoke path for fresh public checkouts.
- Status: public runnable MVP checkpoint, not a production release.
- Still open: broader runtime hardcoded path cleanup, deployment/control-plane docs, optional history remediation decision, dependency-security lane, and future `src/cogs/ora.py` implementation.

## v2026.5.18 Public Progress Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.18-public-progress-checkpoint.md`
- Scope: v7.7 source-of-truth alignment, public GitHub hygiene cleanup, self-evolution product intelligence specification, and PR #165 public README/root-surface/release-note cleanup.
- Status: public progress checkpoint, not a production release.
- Still open: PR #163 boundary plan, runtime/tooling hardcoded path cleanup, optional history remediation decision, and dependency-security lane.

## v2026.4.28 Public Progress Checkpoint

- Public checkpoint note: `docs/releases/v2026.4.28-public-progress-checkpoint.md`
- Scope: post-PR #153 / #154 / #155 public progress record and reasoning-summary exactness guardrails for delivered public-core scope.
- Status: public progress checkpoint, not a production release.
- Still open: Pass 2 remains stopped / not landed, and `src/cogs/ora.py` remains unresolved boundary residue.

## Older Date-Version Notes

Older release note files remain under `docs/releases/` for historical reference.

They are not production-readiness claims, and they should not be read as current private runtime, live operations, or control-plane truth.

Current status and boundary truth should be checked against:

- `docs/CURRENT_PHASE_CONTEXT.md`
- `docs/TRACEABILITY_MATRIX_0_19.md`
- `docs/releases/v2026.5.19-public-runnable-mvp-checkpoint.md`
