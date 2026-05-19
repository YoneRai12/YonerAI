# Open PR Backlog Triage 2026-05-21

Status: public-safe backlog gate for the Local LLM Conversation MVP and provider-compatibility follow-up.

This report is a triage snapshot. It does not close, merge, or delete any PR.

## Summary

- Open PRs observed after PR #175 merge: 49
- Dependabot/security-like PRs: 25
- Non-Dependabot PRs: 24
- Active owner feature PRs safe to build on for this lane: 0
- Obvious retired-`ora-ui` Dependabot close candidates after this cleanup reaches `main`: 9

## Gate Decision

The Local LLM Conversation MVP should be built from current `public/main`, not from an open backlog branch.

No open PR is used as a base for this lane. `ora-ui` Dependabot PRs and old Web/cloud PRs remain outside this Core API checkpoint.

Recheck for the provider compatibility lane kept the same decision: build from current `public/main`, do not merge backlog PRs in bulk, and do not use old UI branches as the product foundation.

## Backlog Classes

| class | examples | decision |
|---|---|---|
| Retired `ora-ui` Dependabot close candidates | #77, #118, #120, #122, #125, #141, #157, #158, #159 | Close after the `ora-ui` retirement cleanup reaches `main`; their target manifest is removed. |
| Dependabot/security clean candidates | #143, #146, #147, #148, #150, #151, #152 | Review in dependency-security lanes; do not batch-merge here. |
| Dependabot/security blocked or stale | #6, #7, #117, #119, #127, #145, #156 | Rebase/recreate or inspect failures before any merge decision. |
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

1. close obsolete `ora-ui` Dependabot PRs after this cleanup reaches `main`
2. GitHub Actions Dependabot PRs that are behind or failing
3. Python dependency PRs with major version risk
4. old security Codex PRs recreated against current main only if still relevant
