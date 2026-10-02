# Current PR and Branch Reality 2026-05-21

Status: refreshed public-safe maintenance ledger from clean `origin/main` verification after dirty-worktree preservation.

This ledger records the current pull-request and branch reality for the v7.7 public repository workstream. It is not a product release note and it does not merge, close, delete, or retag anything by itself.

## Source of Truth

The GitHub CLI API result is the source of truth for open pull requests in this checkpoint:

- Command: `gh pr list --state open --limit 100 --json number,title,author,createdAt,updatedAt,isDraft,baseRefName,headRefName,mergeStateStatus,reviewDecision,labels,url`
- Verified open PR count: `34`
- Verified `origin/main`: `2e72ab680faa94f1542315c07355065f50f0fe18`
- Latest GitHub Release observed: `v2026.5.21.2`
- Latest markdown checkpoint linked from README: `docs/releases/v2026.5.21.2-final-public-presentation-checkpoint.md`

Public GitHub web pages can temporarily show different counts because they render different filters, stale page state, or recently closed/merged branches. This ledger uses `gh` output because it queries the repository API directly at verification time.

## Recent Mainline State

Recent merged PRs on the verified mainline include:

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

PRs #206 and #207 are not open in the refreshed list. Current open-count drift from older handoffs is explained by the prior security/runtime backlog spike, subsequent close pass, and stale public page rendering, not by owner-created PR drift in this run.

## Current Open PR Groups

| group | PRs | current action |
|---|---|---|
| Current security/runtime review | #205 | Keep open for fresh current-main security review. Do not close until replacement evidence is explicit. |
| Older security/runtime review | #128, #129, #131, #132, #133, #134, #135, #60 | Keep open unless a fresh patch, reproduction result, or supersession proof is recorded. |
| Dependency lane | #6, #7, #18, #34, #143, #145, #146, #147, #148, #150, #151, #152, #156 | Keep open for lane-specific dependency validation. Do not merge blindly. |
| Product / planning / boundary lanes | #25, #26, #32, #74, #78, #79, #81, #82, #107, #108, #111, #121 | Needs owner or lane-specific review before action. |

## Branch Reality

Open Codex-created branches remain active for the PRs listed above. They should not be deleted from this checkpoint. Branch cleanup requires a separate owner-approved branch hygiene pass.

The dirty local branch `codex/gpt5.5` was preserved and is not used as a delivery source. The clean continuation branch is `codex/clean-state-reconcile-and-continue`, based on current `origin/main`.

## Root Surface Reality

The verified root tree still includes:

- `config.yaml`
- `main.py`
- `start.sh`
- `start_all.bat`
- `start_vllm.bat`
- `start_windows.bat`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `reference_clawdbot`

The root tree no longer includes `remove_legacy.ps1`; it is present as `tools/maintenance/remove_legacy.ps1` and remains a `DO_NOT_RUN` / retire candidate because it can alter runtime code if executed.

## Release Reality

GitHub Releases show `v2026.5.21.2` as the latest release. The README points at markdown checkpoint `docs/releases/v2026.5.21.2-final-public-presentation-checkpoint.md`.

`v2026.5.20.6` still exists as a historical checkpoint. It is not the latest release in the refreshed `gh release list` output.

## Current Risk Notes

- PR #205 is documentation/security-disclosure related and remains open; it needs review before any close or replacement.
- Older Discord or private-adjacent PRs that require `src/cogs/ora.py` changes remain out of scope for automatic patching in this public repository checkpoint.
- Dependency PRs have no current evidence here that they can be safely closed or merged; they still need lane-specific validation.
- The dirty `src/cogs/ora.py` changes from `codex/gpt5.5` were preserved only and not adopted.

## Non-Claims

This checkpoint does not claim production readiness, shipping completeness, official-cloud completion, live-ops completion, hybrid completion, persistent memory completion, Google login, Discord gateway completion, provider ecosystem completion, final Web UI completion, Tools/MCP completion, all security backlog resolution, all dependency backlog resolution, Pass 2 landing, or `src/cogs/ora.py` resolution.
