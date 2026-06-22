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

## 2026-06-23 Realtime Sync Lane Intake

| Item | Classification | Why deferred | Next owner/action |
| --- | --- | --- | --- |
| #569 status feed live ingestion | deferred-with-tracked-issue / separate lane | Status lane PR remains open and outside the realtime sync listener surface. Follow-up review-intake comment says atomic write, timeout, content-length, URL validation, stale fallback, and status projection findings were addressed, but it still needs its own lane CI/merge decision. | Status lane owns final review/CI/merge; do not claim Status closure from this sync PR. |
| #565 staging session metadata sanitizer | duplicate / valid-but-already-fixed | The valid token-marker and local-path findings were superseded by #568 on current main. This branch also preserves private endpoint filtering. | Close or mark superseded by #568 and the current sync branch's regression tests. |
| #566 staging poll token_returned handling | valid-now fixed in current branch | The open PR captured a real auth safety rule: `session.token_returned=true` must fail closed even when an opaque YonerAI session exists. Current sync branch implements this and adds regression coverage. | Supersede #566 after this branch lands, or close it with the current-main evidence. |
| #567 Japanese local LLM label test | deferred-with-tracked-issue | Non-security test wording update, behind main, and not required for closed-alpha Firebase sync client work. | CLI UX/test lane can rebase later. |
| AWS staging public Firebase config readiness | owner/private-lane blocker | `/v1/sync/firebase-config` is live but reports `ready=false`; Public accepts the endpoint and blocks the listener safely. This is not a Public code blocker after this branch, but live Web-to-CLI E2E cannot proceed until AWS config is ready and the owner keeps sync disabled until E2E. | Private AWS config owner prepares public Firebase client config, then Public reruns listener readiness and live E2E. |
