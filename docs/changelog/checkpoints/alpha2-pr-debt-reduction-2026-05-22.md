# Alpha2 PR Debt Reduction - 2026-05-22

This checkpoint records the PR debt pass after the alpha2 capability implementation
slice. It is intentionally narrow: close only PRs that are superseded by current
`main`, and leave dependency, legal, branding, managed-cloud, and unresolved
runtime PRs open for their own review lanes.

## Closed as superseded

| PR | Reason |
| --- | --- |
| #25 `router: route_band v1 + model_plan skeleton` | Superseded by the current provider planner, execution spine, model/provider selection, and CLI/demo runtime surfaced through #312 and #315-#321. The stale PR also touches legacy chat and `src/cogs/ora.py`, so it should not be merged into alpha2. |
| #32 `router: add band1/band2 skeleton and gated agent entry` | Superseded by current route preview, task classification, model/provider selection, execution plan preview, and execution spine work on `main`. |
| #74 `docs: add 3-mode node split migration ledger` | Superseded by current three-mode route, boundary, status, provider/runtime, and alpha2 demo contracts on `main`. The stale migration ledger should not be merged as current truth. |

## Left open intentionally

| PR group | Decision |
| --- | --- |
| Dependabot updates (#6, #7, #18, #34, #143, #145-#148, #150-#152, #156) | Not alpha2 runtime debt. They remain behind and should be handled by a dependency update lane with compatibility tests. |
| #121 managed-cloud MVP | Owner decision required. Public alpha2 keeps Official Managed Cloud contract-only and external. |
| #111 ORA branding rename | Owner decision required. Alpha2 does not broad-rename ORA symbols/modules/env vars. |
| #107/#108 license/IP valuation | Owner/legal decision required. Not part of alpha2 runtime capability. |
| #78/#79 multimodal carryover | Unknown/stale runtime branches. They require current-main reproduction before merge or close. |
| #81 CUA sidecar adoption guide | Owner decision required. Outside the alpha2 capability slice. |
| #82/#134 image-related fixes | Post-alpha or separate image/runtime validation lane. Not closed without current-main reproduction. |
| #26 domain Cloudflare plan | Owner/ops decision required. Alpha2 does not deploy or change official domain operations. |

## Release-gate effect

- Open PR count before this pass: 26.
- Open PR count after closing the superseded PRs: 23.
- No release tag or GitHub Release was created by this PR debt pass.
- No code, runtime behavior, provider behavior, installer behavior, or public
  boundary changed in this checkpoint.
