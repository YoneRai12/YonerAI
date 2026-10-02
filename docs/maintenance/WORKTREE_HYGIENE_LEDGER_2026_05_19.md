# YonerAI Worktree Hygiene Ledger 2026-05-19

Status: maintenance checkpoint
Scope: public-safe worktree inventory summary
Runtime behavior changed: no
Worktrees deleted in this checkpoint: none

This public ledger intentionally omits local filesystem paths. Detailed local paths belong only in local Codex ledgers that are not committed.

## Summary

| class | count | action |
|---|---:|---|
| RED quarantine | 1 | do not touch |
| open PR worktrees | 4 | preserve until PRs are resolved |
| dirty worktrees | 7+ | inspect before cleanup |
| prunable missing metadata entries | 10 | cleanup candidate only in a dedicated Git metadata cleanup batch |
| clean merged/review worktrees | many | candidates after owner review and local handoff preservation |

## RED

| label | branch | head | reason | action |
|---|---|---|---|---|
| original quarantine | `codex/gpt5.5` | `2bc2ae78` | dirty quarantine branch with preserved owner state | do not clean, reset, stash, switch, merge, delete, or reuse as delivery source |

## Preserve Because PR Is Open

| branch | head | PR | state | action |
|---|---|---:|---|---|
| `codex/self-evolution-proposal-only-mvp` | `682dcaab` | #169 | open/draft | preserve; fix review comments before merge |
| `codex/managed-cloud-mvp-phase1` | `db85c0db` | #121 | open/draft | preserve |
| `codex/public-ora-branding-cleanup` | `19456188` | #111 | open | preserve |
| `feat/router-band1-band2-skeleton` | `108fd965` | #32 | open | preserve |

## Cleanup Candidates, Not Executed

| group | examples | reason cleanup was deferred |
|---|---|---|
| clean merged worktrees | PR #161, #162, #163, #164, #165, #166, #167, #168 lanes | must preserve local handoff/ledger state first; branch deletion also requires worktree removal |
| clean old review worktrees | review and security PR worktrees | branch purpose and owner intent need review |
| prunable missing metadata | detached temporary verification entries | safe only in a dedicated `git worktree prune` batch after owner approval |
| release and delivery lineage worktrees | public release / delivery candidates | release-history intent needs owner review |
| backup worktrees | backup and restore-stash branches | backup retention policy needed |

## Recommended Cleanup Sequence

1. Keep the original quarantine branch untouched.
2. Keep all open PR worktrees.
3. Export or preserve any local-only `.codex` state from cleanup worktrees.
4. Run a dedicated worktree cleanup batch that removes only clean, merged, owner-approved worktrees.
5. Run `git worktree prune` only after verifying the prunable entries point to missing directories.
6. Delete local branches with normal `git branch -d` only after their worktrees are removed.
7. Do not delete remote branches in the same batch as local worktree cleanup.

## Non-Claims

This ledger does not claim the repository is fully clean. It records a safe cleanup plan and explains why destructive cleanup was deferred.
