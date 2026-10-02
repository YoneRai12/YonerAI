# Dirty Worktree Preservation 2026-05-21

Status: local preservation ledger for the dirty `codex/gpt5.5` worktree before clean v7.7 continuation.

This document records what was preserved before continuing from clean `origin/main`. It does not adopt, validate, or reject the preserved changes as product work.

## Why This Exists

The previous run stopped because the worktree was dirty before any new work began, including a dirty `src/cogs/ora.py`. The follow-up instruction was to preserve that state safely, then continue from a clean branch based on the real public `origin/main`.

## Dirty Starting Point

| item | observed value |
|---|---|
| dirty branch | `codex/gpt5.5` |
| dirty HEAD | `2bc2ae7892598a1a9e40d67cf22b1344bb68a00d` |
| tracked modified paths in stash | `16` |
| tracked deleted paths in stash | `91` |
| untracked paths captured | `280` |
| `src/cogs/ora.py` dirty before preservation | yes |
| audio cache deletion paths | present under `src/data/cache/audio_notify/` |
| self-evolution untracked code/tests | present |

## Preservation Actions

| preservation item | result |
|---|---|
| local backup branch pointer | `codex/preserve-dirty-gpt55-20260521-053331` |
| backup branch target | `2bc2ae7892598a1a9e40d67cf22b1344bb68a00d` |
| tracked patch | `<TEMP_DIR>/yonerai_dirty_tracked_20260521-053331.patch` |
| tracked binary patch | `<TEMP_DIR>/yonerai_dirty_tracked_binary_20260521-053331.patch` |
| untracked file list | `<TEMP_DIR>/yonerai_dirty_untracked_files_20260521-053331.txt` |
| inventory report | `<TEMP_DIR>/yonerai_dirty_inventory_20260521-053310.txt` |
| dirty-state stash | `stash@{1}` at preservation time |
| dirty-state stash commit | `4a035f92e13870d031cf670532829b24f39034f9` |
| stash message | `preserve dirty codex/gpt5.5 before clean v7.7 continuation 20260521-053331` |

After switching to the clean branch, four residual untracked entries were still present in the working tree. They were preserved separately instead of deleted.

| residual preservation item | result |
|---|---|
| residual untracked list | `<TEMP_DIR>/yonerai_clean_branch_residual_untracked_20260521-053419.txt` |
| residual stash | `stash@{0}` at preservation time |
| residual stash commit | `a2d9cac0b969eada8fc1ddc090f7f7d4b2f07d54` |
| residual stash message | `preserve residual untracked files after clean origin/main switch 20260521-053419` |

## Classification

| path family | classification | handling |
|---|---|---|
| `src/cogs/ora.py` | `FORBIDDEN_BOUNDARY` / `DO_NOT_ADOPT` | Preserved only. Not adopted into clean continuation. |
| `.env` / `.env.*` style paths | `SECRET_RISK` / `NEVER_STAGE` | Do not stage or publish. |
| `src/data/cache/audio_notify/*.mp3` deletions | `CACHE_OR_GENERATED` / `UNKNOWN` | Preserved only. Do not delete or restore without owner decision. |
| untracked `src/self_evolution/*` | `RUNTIME_CODE_CANDIDATE` / `UNKNOWN` | Preserved only. Needs separate lane. |
| untracked `tests/test_self_evolution_*` | `RUNTIME_CODE_CANDIDATE` / `UNKNOWN` | Preserved only. Needs separate lane. |
| broad docs deletions and rewrites | `PRIOR_CODEX_CANDIDATE` / `UNKNOWN` | Preserved only. Not adopted automatically. |
| `reference_clawdbot` | `DO_NOT_TOUCH` | No initialization, repair, removal, replacement, or staging. |

## Clean Continuation Branch

| item | value |
|---|---|
| clean branch | `codex/clean-state-reconcile-and-continue` |
| branch base | `origin/main` |
| clean base commit | `2e72ab680faa94f1542315c07355065f50f0fe18` |
| clean branch status after preservation | clean |
| `src/cogs/ora.py` diff on clean branch | none |
| `reference_clawdbot` status on clean branch | untouched |

## Commands Recorded

- `git status --short --branch`
- `git branch --show-current`
- `git rev-parse HEAD`
- `git log --oneline -n 20`
- `git diff --stat`
- `git diff --name-status`
- `git ls-files --others --exclude-standard`
- `git diff -- src/cogs/ora.py`
- `git branch codex/preserve-dirty-gpt55-20260521-053331`
- `git diff`
- `git diff --binary`
- `git stash push -u`
- `git fetch --all --prune`
- `git switch -c codex/clean-state-reconcile-and-continue origin/main`

## Non-Claims

This preservation does not claim the dirty changes are correct, safe, owned by the user, ready to merge, or part of v7.7. It also does not claim production readiness, Discord restoration, persistent memory, Google login, official-cloud completion, full product completion, or `src/cogs/ora.py` resolution.
