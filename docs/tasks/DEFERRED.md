# Deferred Public YonerAI Work

This file tracks non-blocking P2/P3, dependency, and UX work that must not block
current security gates or realtime sync sequencing. It is public-safe and should
not include secrets, private runtime details, internal hostnames, or local paths.

## 2026-06 Security Intake Deferrals

| Item | Classification | Why deferred | Next owner/action |
| --- | --- | --- | --- |
| #548 `js-yaml` dependency update | deferred-with-tracked-issue | Dependency update, not a current P0/P1/security finding in the public CLI lane. | Dependency lane rebase and CI. |
| #547 update parent language option | deferred-with-tracked-issue | UX/correctness, not security-blocking for realtime sync. | CLI UX lane rebase and focused tests. |
| #545 / #544 theme configuration | duplicate / deferred | Overlapping theme-setting PRs; not a current security blocker. | Choose one canonical theme PR later, likely #545 or a fresh main patch. |
| #523 README alpha warning | deferred-with-tracked-issue | Docs warning, not required for current security gate. | Docs/release lane can refresh from current truth. |
| Older dependency PRs (#413, #412, #411, #410, #156, #151, #148, #147, #146, #145, #34, #18, #7, #6) | deferred-with-tracked-issue | Dependabot/dependency maintenance and stale bases; separate compatibility risk. | Dependency lane batches by ecosystem and runs Quality Wall. |
| Legacy/stale product PRs (#134, #121, #111, #108, #107, #81, #79, #26) | stale or owner-only-blocker | Old base branches or production-adjacent scope that needs owner approval. | Close, supersede, or re-open as fresh scoped PRs only with explicit lane approval. |

## Blocking Boundary

These deferred items do not permit bypassing current P0/P1/security review gates.
If any deferred item is later found to affect the active release or sync surface
as a P0/P1/security issue, it must be promoted out of this file and fixed before
that phase continues.
