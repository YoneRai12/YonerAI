# Public GitHub State Reconciliation 2026-05-21

Status: refreshed public-safe GitHub state checkpoint after dirty-worktree preservation and clean `origin/main` continuation.

This document reconciles the current GitHub PR count, release state, root state, and the mismatch between older ledgers, public pages, and the current `gh` source of truth. It does not change runtime behavior and does not claim the security backlog is complete.

## Source Of Truth

Use GitHub API / `gh` as the operational source of truth for PR and Release state.

| item | verified value |
|---|---|
| `origin/main` | `2e72ab680faa94f1542315c07355065f50f0fe18` |
| clean reconciliation branch | `codex/clean-state-reconcile-and-continue` |
| `gh` open PR count | `34` |
| latest GitHub Release from `gh repo view` | `v2026.5.21.2` |
| latest GitHub Release title | `YonerAI Final Public Presentation Checkpoint` |
| latest GitHub Release target | `2e72ab680faa94f1542315c07355065f50f0fe18` |
| latest GitHub Release published time | `2026-05-20T19:33:53Z` |

If another public GitHub surface shows `34`, `36`, or `37` open pull requests, use the `gh` count above for this checkpoint. The observed divergence is a rendered/filter/cache difference unless the GitHub API and `gh` disagree.

## Prior Report Check

The prior Codex report that claimed PRs #219 through #228 were merged and that `v2026.5.21.2` exists was correct after fetch/prune and `gh` verification.

| item | result |
|---|---|
| PR #228 exists | yes |
| PR #228 state | `MERGED` |
| PR #228 merge commit | `2e72ab680faa94f1542315c07355065f50f0fe18` |
| PR #228 branch | `codex/release-alignment-final-checkpoint` |
| `v2026.5.21.2` exists | yes |
| `v2026.5.21.2` is latest in `gh release list` | yes |
| `v2026.5.20.6` still exists | yes; not latest |

## Recent Mainline State

Recent merged maintenance PRs now verified on current `origin/main`:

| PR | branch | merge commit | result |
|---:|---|---|---|
| #219 | `codex/current-pr-branch-reality-ledger` | `7f747a481150e46ae86ec1b9303c2d90f303ed40` | merged |
| #220 | `codex/file-pr-traceability-matrix` | `2694503a463d52d6a2c12df72f10d394ab3de2da` | merged |
| #221 | `codex/large-codebase-integration-retirement-map` | `146d2b5948e05775786a14d5345e192e7ce5e8f2` | merged |
| #222 | `codex/security-runtime-deep-pass-1` | `d977ab45af3957e2a7fb8a2483de975ef1c753e5` | merged |
| #223 | `codex/dependency-pr-lane-drain` | `a4cbbdd828a3196e30fc25728a399cefc8b506d7` | merged |
| #224 | `codex/root-surface-physical-cleanup-pass` | `6fe30e16cca6542b85c5ae67bd5e39486f9afb92` | merged |
| #225 | `codex/release-alignment-current-checkpoint` | `fcc34426b69c4c48c52b223bc9c7e4106c66cd14` | merged |
| #226 | `codex/v7-7-evidence-v7-8-readiness` | `6f2d7ce94aed3ffb7df4a7f1f4de2c3e79dc4567` | merged |
| #227 | `codex/public-repo-presentation-pass` | `c0abb5cbbd4ee1642917fd68717af8c6f5917a3a` | merged |
| #228 | `codex/release-alignment-final-checkpoint` | `2e72ab680faa94f1542315c07355065f50f0fe18` | merged |

## Root State

`remove_legacy.ps1` is not present in the `origin/main` root tree. It is present at `tools/maintenance/remove_legacy.ps1`.

Root entries still include:

- `config.yaml`
- `main.py`
- `start.sh`
- `start_all.bat`
- `start_vllm.bat`
- `start_windows.bat`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `reference_clawdbot`

If a public GitHub page shows `remove_legacy.ps1` at root, that page is stale or not showing current `main`. The current `origin/main` tree and GitHub-backed `gh` verification show it is out of root.

## Open PR Shape

Current open PRs include:

- security/runtime PRs #205, #128, #129, #131, #132, #133, #134, #135, and #60;
- remaining dependency PRs #156, #152, #151, #150, #148, #147, #146, #145, #143, #34, #18, #7, and #6;
- broad product/legal/strategy PRs #25, #26, #32, #74, #78, #79, #81, #82, #107, #108, #111, and #121.

PRs #206 and #207 are no longer open in the refreshed `gh` list. They were part of the prior backlog spike and should not be counted as current open PR debt.

## Dirty Worktree Relation

The earlier local dirty branch `codex/gpt5.5` was not public truth. Its changes were preserved locally and were not adopted into this clean continuation. See `DIRTY_WORKTREE_PRESERVATION_2026_05_21.md`.

## Commands Recorded

- `git fetch --all --prune`
- `git rev-parse origin/main`
- `git log --oneline -n 60`
- `git ls-tree --name-only origin/main`
- `gh repo view --json nameWithOwner,url,defaultBranchRef,latestRelease`
- `gh pr list --state open --limit 100 --json number,title,author,createdAt,updatedAt,isDraft,baseRefName,headRefName,mergeStateStatus,reviewDecision,labels,url`
- `gh pr list --state closed --limit 150 --json number,title,mergedAt,closedAt,headRefName,baseRefName,url`
- `gh pr view 222 --json number,state,title,mergedAt,mergeCommit,headRefName,baseRefName,url`
- `gh pr view 228 --json number,state,title,mergedAt,mergeCommit,headRefName,baseRefName,url`
- `gh release list --limit 80`
- `gh release view v2026.5.21.2`
- `gh release view v2026.5.20.6`

## Non-Claims

This reconciliation does not claim production readiness, shipping completion, official cloud completion, hybrid completion, full security backlog completion, full dependency backlog completion, persistent memory, Google login, Discord gateway completion, Tools/MCP completion, provider ecosystem completion, or `src/cogs/ora.py` resolution.
