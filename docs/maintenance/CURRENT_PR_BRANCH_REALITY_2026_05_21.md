# Current PR and Branch Reality 2026-05-21

Status: public-safe maintenance ledger from fresh GitHub and `origin/main` verification.

This ledger records the current pull-request and branch reality for the v7.7 public repository workstream. It is not a product release note and it does not merge, close, delete, or retag anything by itself.

## Source of Truth

The GitHub CLI API result is the source of truth for open pull requests in this checkpoint:

- Command: `gh pr list --state open --limit 100 --json number,title,author,createdAt,updatedAt,isDraft,baseRefName,headRefName,mergeStateStatus,reviewDecision,labels,url`
- Verified open PR count: `36`
- Verified `origin/main`: `e64299142bb68a731245b03678e8531dc18b36a9`
- Latest GitHub Release observed: `v2026.5.20.6`
- Latest markdown checkpoint linked from README: `docs/releases/v2026.5.20.14-tools-mcp-safe-subset-contract-checkpoint.md`

Public GitHub web pages can temporarily show different counts because they render different filters, stale page state, or recently closed/merged branches. This ledger uses `gh` output because it queries the repository API directly at verification time.

## Recent Mainline State

Recent merged PRs on the verified mainline include:

| PR | branch | result |
|---:|---|---|
| #214 | `codex/public-github-state-reconciliation` | Merged; reconciled public GitHub state. |
| #215 | `codex/public-text-unicode-cleanup-pass` | Merged; hardened public text hygiene. |
| #216 | `codex/security-runtime-pr-validation-pass` | Merged; landed the current-main security/runtime replacement patch set. |
| #217 | `codex/security-runtime-pr-validation-ledger` | Merged; recorded security/runtime replacement decisions. |
| #218 | `codex/root-surface-professionalization-pass-2` | Merged; moved validated root helper surface. |

PRs #204, #208, #209, #210, #211, #212, and #213 are closed unmerged as superseded or duplicate after PR #216. The open PR count is therefore expected to be lower than the temporary backlog spike recorded before that close pass.

## Current Open PR Groups

| group | PRs | current action |
|---|---|---|
| Current security/runtime review | #205, #206, #207 | Keep open for fresh current-main security review. Do not close until replacement evidence is explicit. |
| Older security/runtime review | #128, #129, #131, #132, #133, #134, #135, #60 | Keep open unless a fresh patch, reproduction result, or supersession proof is recorded. |
| Dependency lane | #6, #7, #18, #34, #143, #145, #146, #147, #148, #150, #151, #152, #156 | Keep open for lane-specific dependency validation. Do not merge blindly. |
| Product / planning / boundary lanes | #25, #26, #32, #74, #78, #79, #81, #82, #107, #108, #111, #121 | Needs owner or lane-specific review before action. |

No new post-#218 merged PRs were observed during this verification pass. Open PR count drift from earlier handoffs is explained by the prior security/runtime backlog spike and subsequent close pass, not by a broken ledger.

## Branch Reality

Open Codex-created branches remain active for the PRs listed above. They should not be deleted from this checkpoint. Branch cleanup requires a separate owner-approved branch hygiene pass.

The previous `codex/root-surface-professionalization-pass-2` branch is already merged and no longer needed for active work. The current maintenance work proceeds from `origin/main` on a separate branch.

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

GitHub Releases still show `v2026.5.20.6` as the latest release. The README points at markdown checkpoint `v2026.5.20.14`.

This is a release-presentation mismatch, not a runtime change. The release-alignment lane should decide whether to create or update a current checkpoint release. This ledger does not delete, retag, or edit releases.

## Current Risk Notes

- PR #205 is documentation/security-disclosure related and remains dirty; it needs review before any close or replacement.
- PRs #206 and #207 are security/runtime patches around local LLM access and loopback behavior; they remain open and must not be closed without reproduction or replacement evidence.
- Older Discord or private-adjacent PRs that require `src/cogs/ora.py` changes remain out of scope for automatic patching in this public repository checkpoint.
- Dependency PRs have no open Dependabot alert evidence from the prior dependency drain, but they still need lane-specific validation before closure or merge.

## Non-Claims

This checkpoint does not claim production readiness, shipping completeness, official-cloud completion, live-ops completion, hybrid completion, persistent memory completion, Google login, Discord gateway completion, provider ecosystem completion, final Web UI completion, Tools/MCP completion, all security backlog resolution, all dependency backlog resolution, Pass 2 landing, or `src/cogs/ora.py` resolution.
