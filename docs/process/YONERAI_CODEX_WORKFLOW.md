# YonerAI Codex Workflow

This workflow is the durable entrypoint for future YonerAI Codex goals. It follows Codex guidance for long-running goals: one durable objective, a verifiable stopping condition, first-read context, validation artifacts, checkpoint progress, and explicit stop conditions.

Official Codex references:

- <https://developers.openai.com/codex/use-cases/>
- <https://developers.openai.com/codex/guides/agents-md>

## 1. Fresh Verification

Start every delivery run by checking current state instead of trusting prior reports.

Minimum:

- `git status --short --branch`
- `git fetch --all --prune`
- `git rev-parse origin/main`
- recent `git log --oneline`
- relevant open PRs with `gh pr list`
- latest releases with `gh release list`
- relevant lane docs and contracts

If fetch fails only for a stale local backup remote, record it and continue when GitHub remotes are verified. If GitHub state cannot be verified, stop.

## 2. Scope Selection

Choose one primary lane and one independent fallback lane. Do not mix unrelated lanes in one PR.

Good scope examples:

- one security/runtime patch with tests
- one Discord contract acceptance increment
- one API/CLI/Web smoke improvement
- one `src/cogs/ora.py` characterization or extraction step
- one release checkpoint after implementation PRs merge

Avoid loose backlog sweeps with no single stopping condition.

## 3. Branch Rules

- Branch from clean `origin/main` or verified `public/main`.
- Do not continue implementation from preserved dirty branches.
- Preserve/stash dirty state before switching, without adopting dirty runtime changes.
- Do not adopt dirty `src/cogs/ora.py` content.
- Use `codex/<short-lane-name>` unless the user requests another branch name.

## 4. Lane Types

Standard lanes:

- security/runtime patch
- API smoke improvement
- CLI smoke improvement
- native Japanese CLI contract or parser work
- Web smoke improvement
- Discord hybrid contract
- `src/cogs/ora.py` extraction
- three-mode acceptance harness
- dependency lane drain
- root professionalization
- release checkpoint
- docs/process governance

## 5. Implementation Preference

Prefer code/tests first where safe. Use docs-only work when it:

- records necessary governance
- unblocks implementation or review
- explains a blocked security/private/runtime boundary
- aligns a release/checkpoint after implementation PRs

For stale PRs, inspect old intent, reproduce on current main, create a fresh narrow patch, then close the old PR only with replacement evidence.

For refactors, add characterization tests before moving code.

## 6. Review Loop

For every PR:

1. Create the PR with scope, validation, non-claims, and boundary confirmations.
2. Read GitHub, Gemini, Codex, and human comments.
3. Classify comments: P0, P1, P2, P3, outdated, duplicate, false-positive.
4. Fix P0/P1/security/correctness before merge.
5. Fix small low-risk P2 when practical.
6. Rerun validation after fixes.
7. Merge only when checks pass and no material review remains.

Priority definitions:

- P0: critical security/correctness issue; must block merge.
- P1: merge-blocking bug, boundary violation, or missing required validation.
- P2: maintainability or clarity issue; fix when low risk or document why deferred.
- P3: style or optional polish; fix only when cheap and clearly useful.

A quota warning from an automated reviewer is not a material review comment, but record it.

## 7. Stop Conditions

Stop the current lane when:

- dirty state cannot be safely preserved
- GitHub state cannot be verified
- the action needs a forbidden private/live/production boundary
- the same test category fails twice
- unresolved P0/P1/security/correctness review remains
- owner approval is required and not already given

If blocked, switch only to an independent lane that does not depend on the blocked work.

## 8. Final Report

Final reports are Japanese and exact. Include:

- starting and final main HEAD
- PRs created, merged, and closed
- files changed
- validation commands and results
- secret/local-path and mojibake/hidden-Unicode scans
- runtime boundary confirmation
- `src/cogs/ora.py` and `reference_clawdbot` status
- what can now be claimed
- what must not be claimed
- next recommended goal
