# Dependency PR Drain 2026-05-21

Status: public-safe dependency PR reconciliation checkpoint after the large-codebase inventory pass.

This document records the current open dependency PR state and explains why no dependency PR was closed in this pass. It is a maintenance ledger, not a dependency remediation claim.

## Verification Snapshot

- Source of truth: GitHub CLI open PR list and Dependabot alert API.
- Open PR count before this dependency pass: 36.
- Open PR count after web-lockfile superseded closures: 33.
- Open Dependabot alerts observed: 0.
- Open dependency PRs observed: 16.
- Close result: 3 dependency PRs closed as superseded: #117, #119, #127.

## Drain Decision

Most dependency PRs did not meet the safe-close bar.

Current GitHub alerts are clean. After a second web-lockfile check, #117, #119, and #127 were safe to close because current `main` already contains the relevant `flatted` and `picomatch` lockfile versions, no longer contains the target `lodash` package entry, and GitHub reports 0 open Dependabot alerts.

The remaining dependency PRs still represent version-update work that may be valid after rebase and targeted validation. None of those remaining PRs was proven to be superseded by a newer open PR or by a current-main manifest change. Closing them would reduce visible PR count while losing useful dependency-lane tracking.

The next safe action is to split the backlog into focused refresh lanes:

- GitHub Actions workflow lane.
- Python runtime dependency lane.
- Discord / crypto boundary lane.
- Media / OCR / audio lane.
- Web lockfile lane.
- Optional memory dependency lane.

## Dependency PR Classification

| PR | dependency / surface | current merge state | classification | close-safe | evidence / risk | next action |
|---|---|---|---|---|---|---|
| #156 | `softprops/action-gh-release` 1 -> 3 / release workflow | BEHIND | KEEP_WORKFLOW_REFRESH | No | Workflow action update may still be valid; no replacement PR was proven. | Rebase in a workflow lane and validate release dry-run semantics without creating a release. |
| #152 | `numpy` range to `>=2.4.6,<3.0` / Python runtime | BEHIND | KEEP_HIGH_RISK_PYTHON_REFRESH | No | Major numeric dependency range can affect media and optional providers. | Refresh separately with focused Python and media tests. |
| #151 | `discord-py` to `>=2.7.1,<3.0` / Discord boundary | BEHIND | KEEP_DISCORD_BOUNDARY_REFRESH | No | Discord runtime remains a separate boundary; not safe to batch-close or merge. | Evaluate with Discord/private-runtime boundary review. |
| #150 | `transformers` to `>=5.8.1` / provider-model stack | BEHIND | KEEP_PROVIDER_MODEL_REFRESH | No | Large provider/model dependency jump; current public lane does not validate this stack. | Keep for provider compatibility lane. |
| #148 | `pytesseract` to `>=0.3.13,<1.0` / OCR | BEHIND | KEEP_MEDIA_OCR_REFRESH | No | Media/OCR tooling may still need the update; not superseded. | Refresh with OCR/media smoke tests. |
| #147 | `soundfile` to `>=0.13.1` / audio | BEHIND | KEEP_MEDIA_AUDIO_REFRESH | No | Audio dependency may affect media surfaces not covered by public Core smoke. | Refresh with audio-focused tests. |
| #146 | `aiohttp` to `>=3.13.5,<4.0` / network stack | BEHIND | KEEP_NETWORK_STACK_REFRESH | No | Network dependency touches API/provider surfaces; no replacement proven. | Refresh with Core API and provider tests. |
| #145 | `pynacl` to `>=1.6.2,<2.0` / crypto and Discord | BEHIND | KEEP_CRYPTO_DISCORD_REFRESH | No | Prior check history includes a failing build; crypto/runtime impact needs review. | Keep for Discord/crypto boundary lane. |
| #143 | `chromadb` to `1.5.9` / optional memory | BEHIND | KEEP_MEMORY_LANE_REFRESH | No | Persistent memory is not complete; optional memory dependency should not advance without memory policy. | Keep for future memory-policy dependency lane. |
| #127 | `lodash` in `clients/web` | CLOSED | CLOSE_SUPERSEDED | Yes | Current `clients/web/package-lock.json` no longer contains a `node_modules/lodash` package entry; Dependabot alerts are 0. | Closed with evidence comment. Recreate only if `lodash` reappears. |
| #119 | `picomatch` in `clients/web` | CLOSED | CLOSE_SUPERSEDED | Yes | Current `clients/web/package-lock.json` contains `picomatch` 2.3.2 and nested `picomatch` 4.0.4; Dependabot alerts are 0. | Closed with evidence comment. |
| #117 | `flatted` in `clients/web` | CLOSED | CLOSE_SUPERSEDED | Yes | Current `clients/web/package-lock.json` contains `flatted` 3.4.2; Dependabot alerts are 0. | Closed with evidence comment. |
| #34 | `stefanzweifel/git-auto-commit-action` 5 -> 7 / workflow automation | BEHIND | KEEP_WORKFLOW_REFRESH | No | Action behavior can affect automation; no current replacement proven. | Rebase and validate workflow behavior in an Actions lane. |
| #18 | `pycountry` range to `<27.0` / Python runtime | BEHIND | KEEP_LOW_RISK_REFRESH | No | Looks low-risk but still a manifest change; not superseded. | Refresh with standard Python tests. |
| #7 | `actions/setup-python` 4 -> 6 / CI workflow | BEHIND | KEEP_WORKFLOW_REFRESH | No | Prior check history includes a failing build; no replacement proven. | Rebase with Actions lane and validate CI. |
| #6 | `actions/checkout` 4 -> 6 / CI workflow | BEHIND | KEEP_WORKFLOW_REFRESH | No | Prior check history includes workflow failures; no replacement proven. | Rebase with Actions lane and validate CI. |

## Why Only Three Were Closed

- #117, #119, and #127 were closed because current `main` already resolves or removes their specific web lockfile target and there are no open Dependabot alerts.
- No other open dependency PR is a duplicate of a newer open dependency PR.
- No other current-main manifest change was confirmed to make the PR obsolete.
- Some remaining dependency PRs have stale or failing check history, but stale checks are not enough to prove the update should be discarded.
- Closing the remaining PRs would hide dependency refresh work rather than resolving it.

## Safe Next Lanes

1. Refresh GitHub Actions dependency PRs together: #156, #34, #7, #6.
2. Keep the active web lockfile lane clear; #117, #119, and #127 are closed as superseded.
3. Refresh network/runtime dependency PRs separately: #146, #152, #18.
4. Keep Discord and crypto updates separate: #151, #145.
5. Keep model/media dependencies separate: #150, #148, #147.
6. Keep optional memory dependency update #143 blocked behind memory-policy scope.

## Non-Claims

This pass does not claim that dependencies are fully up to date, that all historical dependency risk is resolved, that the project is production-ready, or that Discord, memory, provider ecosystem, tools/MCP, official cloud, or private runtime lanes are complete.
