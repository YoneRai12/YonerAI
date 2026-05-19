# Open PR Backlog Triage 2026-05-21

Status: public-safe backlog gate for the Local LLM Conversation MVP.

This report is a triage snapshot. It does not close, merge, or delete any PR.

## Summary

- Open PRs observed: 49
- Dependabot/security-like PRs: 25
- Non-Dependabot PRs: 24
- Active owner feature PRs safe to build on for this lane: 0

## Gate Decision

The Local LLM Conversation MVP should be built from current `public/main`, not from an open backlog branch.

No open PR is used as a base for this lane. `ora-ui` Dependabot PRs and old Web/cloud PRs remain outside this Core API checkpoint.

## Backlog Classes

| class | examples | decision |
|---|---|---|
| Dependabot/security clean candidates | #143, #146, #147, #148, #150, #151, #152, #157, #158, #159 | Review in dependency-security lanes; do not batch-merge here. |
| Dependabot/security blocked or stale | #6, #7, #77, #117, #118, #119, #120, #122, #125, #127, #141, #145, #156 | Rebase/recreate or inspect failures before any merge decision. |
| Old security Codex branches | #60, #67, #128, #129, #130, #131, #132, #133, #134, #135, #136, #142 | Re-evaluate against current main and recreate clean fixes if still valid. |
| Broad Web/cloud/product PRs | #25, #26, #32, #78, #79, #81, #121 | Do not use for Local LLM MVP; several are dirty, stacked, or outside scope. |
| Owner-only/legal/IP PRs | #107, #108 | Owner decision required. |
| Superseded public presentation work | #111 | Likely superseded by later public cleanup; do not merge without re-review. |

## Not Touched

- No PRs were merged.
- No PRs were closed.
- No branches were deleted.
- No stale branches were rebased.
- No `src/cogs/ora.py` or `reference_clawdbot` PR was touched.

## Recommendation

Proceed with the Local LLM Conversation MVP as a fresh mainline branch.

After this checkpoint, handle the backlog in this order:

1. dedicated `ora-ui` retire-or-remediate decision
2. GitHub Actions Dependabot PRs that are behind or failing
3. Python dependency PRs with major version risk
4. old security Codex PRs recreated against current main only if still relevant
