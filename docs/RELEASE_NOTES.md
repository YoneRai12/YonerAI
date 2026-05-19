# YonerAI Release Notes

This page is a public-safe index of current release notes and progress checkpoints.

## v2026.5.21 Local LLM Provider Compatibility Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.21-local-llm-provider-compatibility-checkpoint.md`
- Scope: provider-neutral local LLM compatibility for Ollama-style `/api/chat` and OpenAI-compatible local `/v1/chat/completions` servers.
- Status: public local provider compatibility checkpoint, not a production release.
- Still open: optional loopback-only model listing endpoint, final Web product UI, Google login, persistent memory, Discord gateway completion, `ora-ui` dependency remediation, non-loopback/private provider lanes, and future `src/cogs/ora.py` extraction.

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
