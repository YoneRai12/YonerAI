# Alpha2 Security Intake

Date: 2026-05-22

## Summary

This checkpoint records the pre-capability security/runtime PR intake for the
`v0.1.0-alpha.2` release train. It does not create a release or tag, does not
merge stale code, and does not close owner-decision PRs.

Fresh baseline:

- main: `71fb45c122d0c452f9ce0f5c9367823b4b44d534`
- open PR count: 26
- existing prerelease: `v0.1.0-alpha.1`
- `v0.1.0-alpha.2`: not present at intake time

## Classification

| PR | Classification | Evidence | Action |
| --- | --- | --- | --- |
| #25 `router: route_band v1 + model_plan skeleton` | `SUPERSEDED_BY_MAIN` | Dirty PR touching legacy route/model surfaces including `src/cogs/ora.py`; current main has provider planner and execution spine through #312 and #314. | Do not merge. Safe close candidate after owner review or replacement evidence comment. |
| #32 `router: add band1/band2 skeleton and gated agent entry` | `SUPERSEDED_BY_MAIN` | Behind PR adding route policy skeleton; current main has three-mode route preview, model/provider selection, and execution plan preview. | Do not merge. Safe close candidate after owner review or replacement evidence comment. |
| #121 `feat(web): restore managed-cloud mvp surface` | `OWNER_DECISION_REQUIRED` | Draft and dirty; broad managed-cloud/web/auth/storage surface, conflicts with public repo official-cloud contract-only posture. | Do not merge for alpha2 unless owner explicitly opens a managed-cloud lane. |
| #134 `fix(image_gen): prevent double interaction defer in auto image style generation` | `POST_ALPHA_SAFE` | Small stale Discord/image_gen bugfix, not an alpha2 blocker and not current execution-spine runtime. | Reproduce later in Discord/image lane if still relevant. |
| #78 `fix(core): preserve recent image context on follow-up` | `UNKNOWN_DO_NOT_RELEASE` | Dirty multimodal context PR in a stale lane; not a blocker for alpha2 and not safe to merge without current-main reproduction. | Reproduce later on current main if image context work resumes. |
| #81 `feat(core): add self-contained CUA planner MVP` | `OWNER_DECISION_REQUIRED` | Broad CUA/planner surface outside the alpha2 public runtime capability slice. | Do not merge unless owner explicitly opens a CUA lane. |
| #82 `fix(core): enforce structured image overview output` | `POST_ALPHA_SAFE` | Behind multimodal structured-output PR; not release-blocking for alpha2. | Reproduce later with current provider/runtime contracts. |
| #74 `docs: add 3-mode node split migration ledger` | `SUPERSEDED_BY_MAIN` | Three-mode capability surface, route preview, and alpha checkpoints now exist on main. | Do not merge stale docs. Close later if owner agrees. |
| #111 `chore: rename public-facing ORA branding to YonerAI` | `OWNER_DECISION_REQUIRED` | Dirty broad rename conflicts with AGENTS policy that ORA remains legacy/internal runtime namespace until a tested compatibility migration exists. | Do not merge in alpha2. |
| #107/#108 license/IP valuation PRs | `OWNER_DECISION_REQUIRED` | Legal/product policy, outside alpha2 runtime capability scope. | Do not merge without owner/legal decision. |
| Dependabot PRs #6, #7, #18, #34, #143, #145, #146, #147, #148, #150, #151, #152, #156 | `POST_ALPHA_SAFE` | Dependency maintenance PRs are behind and require dependency-lane testing; no confirmed P0/P1 alpha2 blocker in current public runtime gate. | Keep separate dependency lane. |
| #26 Cloudflare DNS/tunnel policy | `OWNER_DECISION_REQUIRED` | Domain/ops/deploy policy outside public alpha2 runtime slice. | Do not merge for alpha2. |
| #79 non-main base multimodal PR | `UNKNOWN_DO_NOT_RELEASE` | Base is not `main`, old carryover branch. | Do not use for release gate. |

## Release Gate Note

No open PR was identified as a confirmed P0/P1 alpha2 release blocker. The
release train can proceed if new capability PRs keep the public/private boundary,
pass CI, and the final release gate re-runs this intake before publishing.

## Non-Actions

- No PRs were merged from stale branches.
- No PRs were closed during this initial intake.
- No release, tag, deploy, live Discord connection, provider live call, or secret
  operation was performed.
