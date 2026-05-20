# Public GitHub State Reconciliation 2026-05-21

Status: public-safe GitHub state checkpoint for v7.7 repository professionalization.

This document reconciles the current GitHub PR count, recent closure/merge state, and public text-warning state. It does not change runtime behavior and does not claim the security backlog is complete.

## Source Of Truth

Use GitHub API / `gh` as the operational source of truth for PR state.

- `gh pr list --state open --limit 100 --json number --jq length`: `43`
- `gh api "/repos/YoneRai12/YonerAI/pulls?state=open&per_page=100" --jq length`: `43`
- Public HTML check for `https://github.com/YoneRai12/YonerAI/pulls`: rendered `43 Open`
- `origin/main`: `f636c482031021b9d21aeea1cdef1f0252e51ece`
- Latest GitHub Release: `v2026.5.20.6`

If another GitHub surface shows a different count, treat it as a rendered/cache/filter difference until the API and `gh` disagree.

## Recent State Changes

The previous checkpoint reduced open PR count from 39 to 33, then new security/runtime PRs #204 through #213 were opened. The current open count is therefore 43.

Recent merged maintenance PRs:

| PR | result | merge commit | note |
|---|---|---|---|
| #197 | merged | `e72537278d680c3f4d25f962e8caa3d704fad9c2` | Public PR text hygiene and mojibake cleanup. |
| #198 | merged | `06f809ed78fcdd12c2048f0a2bc055f208fc3c95` | PR backlog reconciliation. |
| #199 | merged | `2c61644e1f2352b3b98d6126bbd7ed65af3ec3ff` | Release note style guide. |
| #200 | merged | `5be49fe5a8e5388ae8f232ed38caceb7c1a1d1b9` | Public file index. |
| #201 | merged | `eb6b8e3321ca1465a54876c0c1b4a3cc9bfa2936` | Large-codebase feature inventory. |
| #202 | merged | `9f85b4d9997ae02ffe93a915310a389abbea8e7c` | Dependency PR drain ledger. |
| #203 | merged | `f636c482031021b9d21aeea1cdef1f0252e51ece` | Web dependency PR closure ledger. |

Recent PR closures:

| PR | close result | reason |
|---|---|---|
| #67 | closed unmerged | Superseded by PR #186 / current `require_core_access` tests. |
| #117 | closed unmerged | Current `clients/web/package-lock.json` contains `flatted` `3.4.2`; Dependabot alerts are 0. |
| #119 | closed unmerged | Current `clients/web/package-lock.json` contains `picomatch` `2.3.2` and nested `4.0.4`; Dependabot alerts are 0. |
| #127 | closed unmerged | Current `clients/web/package-lock.json` no longer contains a `node_modules/lodash` package entry; Dependabot alerts are 0. |
| #130 | closed unmerged | Duplicate of still-open #129. |
| #136 | closed unmerged | Duplicate of still-open #135. |
| #142 | closed unmerged | Superseded by PR #186 / current-main access-gate tests. |

## PR #142

PR #142 remains `CLOSED` and unmerged.

Current replacement evidence remains PR #186 plus `tests/test_core_api_access_security.py`. The old PR should not be merged because it would reapply a stale broad files-router dependency model that conflicts with the current ticket-download boundary.

## PR #195

PR #195 remains `MERGED`.

Current PR body scan:

- four-question-mark mojibake sequence: not found
- replacement character: not found
- specified hidden/bidirectional Unicode controls: not found

The body now records that its earlier Japanese sections contained question-mark mojibake and were rewritten as clean UTF-8 English after merge.

## PR #203

PR #203 remains `MERGED`.

Current PR body scan:

- four-question-mark mojibake sequence: not found
- replacement character: not found
- specified hidden/bidirectional Unicode controls: not found

Post-merge Codex review noted a documentation grouping inconsistency between the dependency lane split and the Top 10 list. That inconsistency is handled in the updated open-PR triage ledger by keeping web lockfile PRs #117/#119/#127 closed as superseded and moving future dependency work to fresh lanes.

## Open PR Shape

Current open PRs include:

- new security/runtime PRs #204 through #213;
- older security/runtime PRs #128, #129, #131, #132, #133, #134, #135, and #60;
- remaining dependency PRs #156, #152, #151, #150, #148, #147, #146, #145, #143, #34, #18, #7, and #6;
- broad product/legal/strategy PRs that need owner decisions or fresh v7.7 lanes.

## Non-Claims

This reconciliation does not claim production readiness, shipping completion, official cloud completion, hybrid completion, full security backlog completion, full dependency backlog completion, persistent memory, Google login, Discord gateway completion, Tools/MCP completion, provider ecosystem completion, or `src/cogs/ora.py` resolution.
