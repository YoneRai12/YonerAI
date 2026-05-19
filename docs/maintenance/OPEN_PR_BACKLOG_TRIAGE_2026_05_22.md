# Open PR Backlog Triage 2026-05-22

Status: public-safe backlog gate for the temporary Web Chat MVP review-gate checkpoint.

This report is a triage snapshot. It does not close, merge, or delete any PR.

## Summary

- Open PRs observed before this branch: 40
- Dependabot PRs: 16
- Non-Dependabot PRs: 24
- Draft PRs observed: 2
- Retired `ora-ui` PRs still open: 0
- Active owner feature PRs safe to build on for this lane: 0

## Gate Decision

The temporary Web Chat MVP should be built from current `public/main`, not from an open backlog branch.

No open PR is used as a base for this lane. The old `ora-ui` Dependabot PRs observed in the previous cleanup have already been closed unmerged, and no currently open PR is clearly tied to an active `ora-ui` manifest.

## Backlog Classes

| class | examples | decision |
|---|---|---|
| GitHub Actions Dependabot PRs | #6, #7, #34, #156 | Review in a dependency-maintenance lane; do not batch-merge here. |
| Python dependency PRs | #18, #143, #145, #146, #147, #148, #150, #151, #152 | Review with targeted tests and migration risk checks; do not batch-merge here. |
| `clients/web` dependency PRs | #117, #119, #127 | Re-evaluate after the `postcss` fix reaches main; do not merge blindly. |
| Old security Codex branches | #60, #67, #128, #129, #130, #131, #132, #133, #134, #135, #136, #142 | Re-evaluate against current main and recreate clean fixes if still valid. |
| Route / architecture / planning branches | #25, #32, #74 | Owner review or dedicated architecture lane. |
| Web / cloud / product or multimodal branches | #26, #78, #79, #81, #82, #121 | Outside this temporary Web Chat MVP scope; do not use as base. |
| Owner-only legal / IP branches | #107, #108 | Owner decision required. |
| Likely superseded public branding cleanup | #111 | Do not merge without current-main re-review. |

## Not Touched

- No PRs were merged.
- No PRs were closed.
- No branches were deleted.
- No stale branches were rebased.
- No `src/cogs/ora.py` or `reference_clawdbot` PR was touched.

## Recommendation

Proceed with the temporary Web Chat MVP as a fresh mainline branch.

After this checkpoint, handle the backlog in this order:

1. confirm GitHub closes the remaining `clients/web` `postcss` alert after merge and rescan
2. review `clients/web` Dependabot PRs against the updated lockfile
3. review GitHub Actions Dependabot PRs
4. review Python dependency PRs with targeted tests
5. re-evaluate old security Codex PRs against current main only if still relevant

