# YonerAI Branch Hygiene Ledger 2026-05-19

Status: maintenance checkpoint
Scope: public repository branch and PR sprawl review
Runtime behavior changed: no
Branches deleted in this checkpoint: none

This ledger is public-safe. It records branch names, hashes, PR status, and cleanup classes, but it intentionally omits local machine paths and private operational details.

## Summary

| item | count | note |
|---|---:|---|
| local branches before this docs branch | 111 | counted before creating this maintenance branch |
| local branches after this docs branch | 112 | one new docs-only branch was created for this ledger and refactor plan |
| remote-tracking refs after prune | 197 | `public` and `origin` tracking refs were pruned; one unavailable local backup remote was not used for decisions |
| live `public` remote heads | 85 | verified from `public` remote |
| GitHub PRs inspected | 168 | 52 open, 68 merged, 48 closed |
| branches deleted | 0 | no branch satisfied all deletion criteria after worktree and PR checks |

## Deletion Policy Used

A branch can be deleted only when all of these are true:

- it is not `main`
- it is not protected
- it is not `codex/gpt5.5`
- it is not the current working branch
- it has no open PR
- if it had a PR, the PR is merged or closed and no unique commits are needed
- its tip is contained in `public/main`, or the exact PR merge proves the content landed
- it is not an open Dependabot branch
- it is not PR #169 while PR #169 is open
- it is not used by an active worktree
- the exact ref, hash, reason, and rollback command are recorded

Because active worktrees and open PRs are still present, this checkpoint does not delete branches.

## RED Keep

| branch | tip | reason | action |
|---|---|---|---|
| `main` | `2ede476c` | protected/default branch | keep |
| `codex/gpt5.5` | `2bc2ae78` | original dirty quarantine branch | keep; read-only only |
| `codex/self-evolution-proposal-only-mvp` | `682dcaab` | PR #169 is open/draft and has unresolved review comments | keep |
| `codex/model-gpt-5-4` | `2bc2ae78` | fixed-anchor/legacy model branch; shares quarantine-era commit | keep |
| `release/2026.4.11-clean` | `1a10de62` | release branch; owner review required | keep |

## Open PR Branches

All open PR heads are RED for deletion. They must not be deleted until their PRs are merged or closed and a later pass proves no needed commits remain.

| PR | branch | tip | draft | merge state | class |
|---:|---|---|---|---|---|
| #169 | `codex/self-evolution-proposal-only-mvp` | `682dcaab` | yes | clean | RED_KEEP |
| #160 | `dependabot/npm_and_yarn/clients/web/next-16.2.6` | `17bab928` | no | behind | RED_KEEP |
| #159 | `dependabot/npm_and_yarn/ora-ui/next-16.2.6` | `d3a7dd84` | no | behind | RED_KEEP |
| #158 | `dependabot/npm_and_yarn/ora-ui/babel/plugin-transform-modules-systemjs-7.29.4` | `969aa8cb` | no | behind | RED_KEEP |
| #157 | `dependabot/npm_and_yarn/ora-ui/fast-uri-3.1.2` | `66164084` | no | behind | RED_KEEP |
| #156 | `dependabot/github_actions/softprops/action-gh-release-3` | `99a90283` | no | behind | RED_KEEP |
| #152 | `dependabot/pip/numpy-gte-2.4.4-and-lt-3.0` | `2918c4bc` | no | behind | RED_KEEP |
| #151 | `dependabot/pip/discord-py-gte-2.7.1-and-lt-3.0` | `ebf27a35` | no | behind | RED_KEEP |
| #150 | `dependabot/pip/transformers-gte-5.6.2` | `2d09871f` | no | behind | RED_KEEP |
| #149 | `dependabot/pip/pillow-gte-12.2.0-and-lt-13.0` | `0587965a` | no | behind | RED_KEEP |
| #148 | `dependabot/pip/pytesseract-gte-0.3.13-and-lt-1.0` | `36a9fbbe` | no | behind | RED_KEEP |
| #147 | `dependabot/pip/soundfile-gte-0.13.1` | `8b73e077` | no | behind | RED_KEEP |
| #146 | `dependabot/pip/aiohttp-gte-3.13.5-and-lt-4.0` | `34a408bf` | no | behind | RED_KEEP |
| #145 | `dependabot/pip/pynacl-gte-1.6.2-and-lt-2.0` | `1a7a1b49` | no | behind | RED_KEEP |
| #143 | `dependabot/pip/chromadb-1.5.8` | `7be56ec5` | no | behind | RED_KEEP |
| #142 | `codex/fix-core-api-access-vulnerability` | `9325c3d2` | no | behind | RED_KEEP |
| #141 | `dependabot/npm_and_yarn/ora-ui/lodash-4.18.1` | `f6a2a413` | no | behind | RED_KEEP |
| #136 | `codex/fix-unredacted-log-forwarding-issue-xxune2` | `93544ee7` | no | behind | RED_KEEP |
| #135 | `codex/fix-unredacted-log-forwarding-issue` | `15bdc137` | no | behind | RED_KEEP |
| #134 | `codex/fix-double-defer-in-auto-style-generation` | `0f513456` | no | behind | RED_KEEP |
| #133 | `codex/fix-ssrf-risk...embed-image-processing` | `d3ecd266` | no | behind | RED_KEEP |
| #132 | `codex/fix-unbounded-image-upload-vulnerability` | `bf02656b` | no | behind | RED_KEEP |
| #131 | `codex/propose-fix-for-/listen-command-vulnerability` | `f4c1a489` | no | behind | RED_KEEP |
| #130 | `codex/fix-authorization-bypass-in-/say-command-wsvf7m` | `88f70739` | no | behind | RED_KEEP |
| #129 | `codex/fix-authorization-bypass-in-/say-command` | `f7c421dc` | no | behind | RED_KEEP |
| #128 | `codex/fix-path-traversal-vulnerability-in-api` | `6db84f0a` | no | behind | RED_KEEP |
| #127 | `dependabot/npm_and_yarn/clients/web/lodash-4.18.1` | `46d9530b` | no | behind | RED_KEEP |
| #125 | `dependabot/npm_and_yarn/ora-ui/electron-40.8.5` | `ee7a4223` | no | behind | RED_KEEP |
| #122 | `dependabot/npm_and_yarn/ora-ui/lodash-es-4.18.1` | `1b98b71d` | no | behind | RED_KEEP |
| #121 | `codex/managed-cloud-mvp-phase1` | `db85c0db` | yes | dirty | RED_KEEP |
| #120 | `dependabot/npm_and_yarn/ora-ui/multi-57404e07ab` | `bbfc7819` | no | behind | RED_KEEP |
| #119 | `dependabot/npm_and_yarn/clients/web/multi-bf05dc1ecf` | `fffdcbdb` | no | behind | RED_KEEP |
| #118 | `dependabot/npm_and_yarn/ora-ui/multi-bf05dc1ecf` | `b1af5529` | no | behind | RED_KEEP |
| #117 | `dependabot/npm_and_yarn/clients/web/flatted-3.4.2` | `a985611b` | no | behind | RED_KEEP |
| #111 | `codex/public-ora-branding-cleanup` | `19456188` | no | dirty | RED_KEEP |
| #108 | `codex/evaluate-intellectual-property-value-wmiu77` | `5263f375` | no | dirty | RED_KEEP |
| #107 | `codex/evaluate-intellectual-property-value` | `7a417885` | yes | dirty | RED_KEEP |
| #82 | `codex/public-generic-image-structured-output` | `10c4e09a` | no | behind | RED_KEEP |
| #81 | `feat/cua-sidecar-adoption` | `f76be287` | no | dirty | RED_KEEP |
| #79 | `codex/public-image-explanation-broad-summary` | `ed4118c6` | no | clean | RED_KEEP |
| #78 | `codex/public-multimodal-followup-carryover` | `9229dfc1` | no | dirty | RED_KEEP |
| #77 | `dependabot/npm_and_yarn/ora-ui/multi-ca49cfd856` | `b5c28bb2` | no | behind | RED_KEEP |
| #74 | `codex/node-3mode-planning-ledger` | `e99fa9c7` | no | behind | RED_KEEP |
| #67 | `codex/propose-fix-for-unauthenticated-api` | `eef297ea` | no | dirty | RED_KEEP |
| #60 | `codex/fix-ssrf-vulnerability-in-image_crop_upscale` | `89a28561` | no | dirty | RED_KEEP |
| #34 | `dependabot/github_actions/stefanzweifel/git-auto-commit-action-7` | `b6a4229c` | no | behind | RED_KEEP |
| #32 | `feat/router-band1-band2-skeleton` | `108fd965` | no | behind | RED_KEEP |
| #26 | `feat/domain-cloudflare-plan` | `afb5e1d9` | no | behind | RED_KEEP |
| #25 | `feat/route-band-v1` | `538d5ff6` | no | dirty | RED_KEEP |
| #18 | `dependabot/pip/pycountry-gte-22.3-and-lt-27.0` | `c6a60638` | no | behind | RED_KEEP |
| #7 | `dependabot/github_actions/actions/setup-python-6` | `f374d9a3` | no | behind | RED_KEEP |
| #6 | `dependabot/github_actions/actions/checkout-6` | `ca914170` | no | behind | RED_KEEP |

## Local Branches That Are Merged But Not Deleted

These local branches were identified as merged into `public/main`, but deletion was deferred because the branch is currently associated with a worktree, is part of a release/traceability lineage, or needs an owner-review cleanup batch.

| branch | tip | associated PR | ancestor of `public/main` | class | proposed action |
|---|---|---:|---|---|---|
| `codex/gpt5.5-a-v77-source-of-truth` | `ff59dbde` | #161 | yes | YELLOW_KEEP_REVIEW | remove only after its worktree is reviewed and removed |
| `codex/gpt5.5-b-self-evolution-spec-stacked` | `bae9baa2` | #162 | yes | YELLOW_KEEP_REVIEW | remove only after its worktree is reviewed and removed |
| `codex/public-github-hygiene-20260518` | `127eef53` | #164 | yes | YELLOW_KEEP_REVIEW | remove only after local ledger is preserved |
| `public-delivery/stage2b-candidate` | `43e82a83` | #140 | yes | YELLOW_KEEP_REVIEW | owner review before deleting delivery lineage |
| `public-release/post-pr153-traceability-refresh` | `4988c7a1` | #154 | yes | YELLOW_KEEP_REVIEW | owner review before deleting release lineage |
| `public-release/post-v2026-4-28-state-freeze` | `f5943ccc` | #155 | yes | YELLOW_KEEP_REVIEW | owner review before deleting release lineage |
| `public-release/reasoning-summary-closure-r2` | `422226c9` | #144 | yes | YELLOW_KEEP_REVIEW | owner review before deleting release lineage |
| `public-release/reasoning-summary-exactness-r3` | `e35f8543` | #153 | yes | YELLOW_KEEP_REVIEW | owner review before deleting release lineage |

Rollback command shape if a later approved cleanup deletes one of these local branches:

```bash
git branch <branch> <tip>
```

## Closed PR Aliases Deferred

Local aliases `pr83` through `pr104` map to closed PR heads. Their tips are not ancestors of `public/main`, so they are not GREEN under the current rules. They should be reviewed as a separate "closed PR alias cleanup" batch.

Rollback command shape if a later approved cleanup deletes one of these local aliases:

```bash
git branch <branch> <tip>
```

## Remote Deletion Decision

No remote branch was deleted.

Live `public` still has open PR heads and several closed or merged PR heads whose tips are not ancestors of `public/main`, likely due to squash merges or abandoned PRs. They need a separate remote deletion batch that checks each PR, branch tip, and owner intent immediately before deletion.

Rollback command shape if a later approved cleanup deletes a remote branch:

```bash
git push public <tip>:refs/heads/<branch>
```

## Next Safe Cleanup Lane

1. Resolve PR #169 review comments before considering that branch for merge or cleanup.
2. For worktree cleanup, first preserve any local-only `.codex` handoff or owner notes.
3. Remove clean worktrees only in a dedicated cleanup batch.
4. Delete local merged branches only after their worktrees are removed.
5. Defer remote branch deletion until open PR, closed PR, squash merge, and owner-intent checks are repeated.
