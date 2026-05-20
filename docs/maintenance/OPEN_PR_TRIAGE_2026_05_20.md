# Open PR Triage 2026-05-20

Status: public-safe maintenance checkpoint from live GitHub state. This ledger classifies all open PRs observed during this run. It does not merge any PR and does not close any PR by itself.

## Verification Snapshot

- `origin/main`: `7acb471f5292905247a392856a7e3c3f7135fd3a`
- Latest GitHub Release: `v2026.5.20.6`
- Open PR count before this checkpoint: 40
- Open PR count after this checkpoint: 40
- Root verification: `debug_state.py`, `video_utils.py`, and `run_dashboard_backend.py` are no longer root files; `config.yaml`, `remove_legacy.ps1`, `start.sh`, `start_all.bat`, `start_vllm.bat`, `start_windows.bat`, compose files, and `main.py` remain in root.
- Close decision: no PR met all safe-close rules during this 60-minute checkpoint.

## Classification Rules Used

| class | meaning |
|---|---|
| `KEEP_SECURITY_REVIEW` | Security-sensitive PR. Do not close or merge without a fresh threat review and current-main rework. |
| `KEEP_CORRECTNESS_REVIEW` | Potential correctness/product value. Needs refresh and focused tests. |
| `KEEP_DEPENDENCY_UPDATE` | Dependency/update PR. Needs dependency lane review and CI/security context. |
| `CLOSE_SUPERSEDED` | Clearly replaced by landed work and safe to close with evidence. None reached that bar in this run. |
| `CLOSE_DUPLICATE` | Clearly duplicate and safe to close. Security/legal duplicates were not closed because impact is uncertain. |
| `CLOSE_STALE_UNSAFE` | Clearly stale and unsafe to merge. None closed without deeper owner review. |
| `REPLACE_WITH_V7_7_LANE` | Old branch may contain ideas, but should be replaced by a fresh v7.7 lane rather than merged. |
| `NEEDS_OWNER_DECISION` | Product/legal/repo-boundary judgment needed. |
| `UNKNOWN_DO_NOT_TOUCH` | Not enough evidence to act safely. Avoided where possible. |

## Open PR Ledger

| PR | title | source / branch | age | state | merge status | class | v7.7 lane alignment | recommendation | evidence | risk / next step |
|---|---|---|---:|---|---|---|---|---|---|---|
| #156 | build(deps): bump softprops/action-gh-release from 1 to 3 | dependabot / `dependabot/github_actions/softprops/action-gh-release-3` | 19d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | release hygiene | Keep for dependency lane | `.github/workflows/release.yml`, 1-line action bump | Rebase and validate release workflow before merge. |
| #152 | build(deps): update numpy requirement | dependabot / `dependabot/pip/numpy-gte-2.4.4-and-lt-3.0` | 23d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | core/runtime dependency | Keep for dependency lane | `requirements.txt`, major numpy range jump | High compatibility risk; run full numeric/media tests first. |
| #151 | build(deps): update discord-py requirement | dependabot / `dependabot/pip/discord-py-gte-2.7.1-and-lt-3.0` | 23d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | Discord/private runtime boundary | Keep for dependency lane | `requirements.txt`, Discord dependency | Do not merge into public checkpoint without Discord gateway boundary review. |
| #150 | build(deps): update transformers requirement | dependabot / `dependabot/pip/transformers-gte-5.6.2` | 23d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | model/provider dependency | Keep for dependency lane | `requirements.txt`, major transformers update | High provider/runtime compatibility risk. |
| #148 | build(deps): update pytesseract requirement | dependabot / `dependabot/pip/pytesseract-gte-0.3.13-and-lt-1.0` | 23d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | tool/media dependency | Keep for dependency lane | `requirements.txt`, 1-line bump | Needs targeted OCR/media smoke before merge. |
| #147 | build(deps): update soundfile requirement | dependabot / `dependabot/pip/soundfile-gte-0.13.1` | 23d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | media/runtime dependency | Keep for dependency lane | `requirements.txt`, 1-line bump | Needs audio smoke, not part of current public Core lane. |
| #146 | build(deps): update aiohttp requirement | dependabot / `dependabot/pip/aiohttp-gte-3.13.5-and-lt-4.0` | 23d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | API/web runtime dependency | Keep for dependency lane | `core/requirements.txt`, `requirements.txt` | Network stack dependency; run Core API tests before any merge. |
| #145 | build(deps): update pynacl requirement | dependabot / `dependabot/pip/pynacl-gte-1.6.2-and-lt-2.0` | 23d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | Discord/crypto dependency | Keep for dependency lane | `requirements.txt` | Boundary/security dependency; not a batch merge. |
| #143 | build(deps): bump chromadb | dependabot / `dependabot/pip/chromadb-1.5.8` | 30d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | optional memory lane | Keep for memory/dependency lane | `requirements-optional-memory.txt` | Memory is not complete; do not merge without memory policy decision. |
| #142 | fix(core): restore require_core_access on main v1 routers | owner / `codex/fix-core-api-access-vulnerability` | 35d | open | DIRTY | KEEP_SECURITY_REVIEW | API security | Keep, recreate if still valid | `core/src/ora_core/main.py` | Security-sensitive and conflicted; fresh current-main review required. |
| #136 | Discord log forwarding masking and channel restriction | owner / `codex/fix-unredacted-log-forwarding-issue-xxune2` | 42d | open | BEHIND | KEEP_SECURITY_REVIEW | Discord/private runtime | Keep, compare with #135 | `src/cogs/system.py`, same title as #135 | Possible duplicate, but security impact uncertain; do not close in this checkpoint. |
| #135 | Discord log forwarding masking and channel restriction | owner / `codex/fix-unredacted-log-forwarding-issue` | 42d | open | BEHIND | KEEP_SECURITY_REVIEW | Discord/private runtime | Keep, compare with #136 | `src/cogs/system.py`, same title as #136 | Possible duplicate, but security impact uncertain; do not close in this checkpoint. |
| #134 | prevent double interaction defer | owner / `codex/fix-double-defer-in-auto-style-generation` | 42d | open | BEHIND | KEEP_CORRECTNESS_REVIEW | image generation UX | Keep for correctness lane | `src/views/image_gen.py` | Old runtime surface; refresh and test before merge. |
| #133 | harden embed image fetching against SSRF | owner / `codex/fix-ssrf-risk-in-embed-image-processing` | 42d | open | BEHIND | KEEP_SECURITY_REVIEW | media/security | Keep, recreate if still valid | handler + security test | SSRF-sensitive; do not close without replacement. |
| #132 | Mitigate unbounded image upload DoS | owner / `codex/fix-unbounded-image-upload-vulnerability` | 42d | open | BEHIND | KEEP_SECURITY_REVIEW | media/security | Keep, recreate if still valid | creative/layer server files | DoS-sensitive; needs current-main patch review. |
| #131 | Restore admin-only guard for /listen | owner / `codex/propose-fix-for-/listen-command-vulnerability` | 42d | open | BEHIND | KEEP_SECURITY_REVIEW | Discord/private runtime | Keep, recreate if still valid | `src/cogs/voice_recv.py` | Authorization-sensitive; do not close. |
| #130 | restore `/say` admin check | owner / `codex/fix-authorization-bypass-in-/say-command-wsvf7m` | 42d | open | BEHIND | KEEP_SECURITY_REVIEW | Discord/private runtime | Keep, compare with #129 | `src/cogs/core.py`, same title as #129 | Possible duplicate, but security impact uncertain. |
| #129 | restore `/say` admin check | owner / `codex/fix-authorization-bypass-in-/say-command` | 42d | open | BEHIND | KEEP_SECURITY_REVIEW | Discord/private runtime | Keep, compare with #130 | `src/cogs/core.py`, same title as #130 | Possible duplicate, but security impact uncertain. |
| #128 | path traversal in dashboard user detail endpoint | owner / `codex/fix-path-traversal-vulnerability-in-api` | 42d | open | BEHIND | KEEP_SECURITY_REVIEW | Web/API security | Keep, recreate if still valid | `src/web/endpoints.py` | Path traversal-sensitive; needs current-main review. |
| #127 | lodash in `/clients/web` | dependabot / `dependabot/npm_and_yarn/clients/web/lodash-4.18.1` | 43d | open | DIRTY | KEEP_DEPENDENCY_UPDATE | temporary Web Chat MVP | Keep for web dependency lane | `clients/web/package-lock.json` | Conflicted dependency lock update. |
| #121 | restore managed-cloud mvp surface | owner / `codex/managed-cloud-mvp-phase1` | 49d | draft | DIRTY | REPLACE_WITH_V7_7_LANE | official cloud/Web | Replace, do not merge | 42 files, 13k additions, broad Web/runtime docs | Too broad and old; use v7.7 contract/control-plane lanes instead. |
| #119 | picomatch in `/clients/web` | dependabot / `dependabot/npm_and_yarn/clients/web/multi-bf05dc1ecf` | 55d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | temporary Web Chat MVP | Keep for web dependency lane | `clients/web/package-lock.json` | Needs fresh lockfile update and web build. |
| #117 | flatted in `/clients/web` | dependabot / `dependabot/npm_and_yarn/clients/web/flatted-3.4.2` | 60d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | temporary Web Chat MVP | Keep for web dependency lane | `clients/web/package-lock.json` | Needs fresh lockfile update and web build. |
| #111 | rename public-facing ORA branding | owner / `codex/public-ora-branding-cleanup` | 70d | open | DIRTY | REPLACE_WITH_V7_7_LANE | public presentation | Replace with current docs/root policy lane | touches env, workflows, clients, config, core | Much of presentation work superseded; broad dirty branch still may contain ideas. |
| #108 | license/IP valuation report | owner / `codex/evaluate-intellectual-property-value-wmiu77` | 73d | open | DIRTY | NEEDS_OWNER_DECISION | legal/IP | Keep for owner decision | README/license/IP valuation docs | Legal/license change cannot be closed or merged by maintenance triage. |
| #107 | license/IP valuation report | owner / `codex/evaluate-intellectual-property-value` | 73d | draft | DIRTY | NEEDS_OWNER_DECISION | legal/IP | Keep for owner decision | Similar to #108 | Possible duplicate, but legal decision belongs to owner. |
| #82 | structured image overview output | owner / `codex/public-generic-image-structured-output` | 73d | open | BEHIND | KEEP_CORRECTNESS_REVIEW | multimodal contract | Keep, refresh later | Core brain/context tests | May hold useful contract behavior; needs current-main review. |
| #81 | OpenAI CUA sidecar guide | owner / `feat/cua-sidecar-adoption` | 73d | open | DIRTY | NEEDS_OWNER_DECISION | Web/tools/provider-specific docs | Keep for owner decision or replace | Web CUA page and OpenAI guide | Provider-specific lane; avoid provider lock-in claim. |
| #79 | broaden generic image explanations | owner / `codex/public-image-explanation-broad-summary` | 74d | open | CLEAN on non-main base | KEEP_CORRECTNESS_REVIEW | multimodal contract | Keep, rebase only if still needed | base is `codex/public-multimodal-followup-carryover` | Stacked PR; cannot merge to main as-is. |
| #78 | preserve recent image context | owner / `codex/public-multimodal-followup-carryover` | 74d | open | DIRTY | KEEP_CORRECTNESS_REVIEW | multimodal continuity | Keep, refresh later | Core brain/context and tests | Dirty and old; evaluate after current conversation/session contracts. |
| #74 | 3-mode node split migration ledger | owner / `codex/node-3mode-planning-ledger` | 74d | open | BEHIND | REPLACE_WITH_V7_7_LANE | repo split / same experience | Replace with current v7.7 docs | docs-only 3-mode migration ledger | Likely superseded by current contracts; keep until owner confirms. |
| #67 | protect ORA Core endpoints | owner / `codex/propose-fix-for-unauthenticated-api` | 74d | open | DIRTY | KEEP_SECURITY_REVIEW | API security | Keep, recreate if still valid | auth dependency and main | Security-sensitive and conflicted; do not close. |
| #60 | image_crop_upscale SSRF validation | owner / `codex/fix-ssrf-vulnerability-in-image_crop_upscale` | 74d | open | DIRTY | KEEP_SECURITY_REVIEW | tool/media security | Keep, recreate if still valid | tool + security test | SSRF-sensitive; do not close. |
| #34 | git-auto-commit-action from 5 to 7 | dependabot / `dependabot/github_actions/stefanzweifel/git-auto-commit-action-7` | 80d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | CI/release hygiene | Keep for dependency lane | `.github/workflows/diagrams.yml` | Action may affect automation; test workflow before merge. |
| #32 | band1/band2 skeleton | owner / `feat/router-band1-band2-skeleton` | 81d | open | BEHIND | REPLACE_WITH_V7_7_LANE | routing/capability boundary | Replace with v7.7 capability boundary lane | route policy and chat handler files | Old runtime routing branch; do not merge into public Core without contract plan. |
| #26 | Cloudflare DNS/tunnel + redirect policy template | owner / `feat/domain-cloudflare-plan` | 83d | open | BEHIND | NEEDS_OWNER_DECISION | deploy/domain docs | Keep for owner/control-plane decision | domain docs | Deployment/domain lane is outside current public checkpoint. |
| #25 | route_band v1 + model_plan skeleton | owner / `feat/route-band-v1` | 83d | open | DIRTY | REPLACE_WITH_V7_7_LANE | routing/model planning | Replace, do not merge | touches `src/cogs/ora.py` and broad runtime files | Forbidden surface for this goal; create fresh contract lane instead. |
| #18 | pycountry requirement | dependabot / `dependabot/pip/pycountry-gte-22.3-and-lt-27.0` | 86d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | dependency hygiene | Keep for dependency lane | `requirements.txt` | Low-looking bump but stale; refresh before merge. |
| #7 | setup-python from 4 to 6 | dependabot / `dependabot/github_actions/actions/setup-python-6` | 121d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | CI hygiene | Keep for dependency lane | workflow files | Could be replaced by fresh Dependabot; verify before close. |
| #6 | checkout from 4 to 6 | dependabot / `dependabot/github_actions/actions/checkout-6` | 121d | open | BEHIND | KEEP_DEPENDENCY_UPDATE | CI hygiene | Keep for dependency lane | workflow files | Could be replaced by fresh Dependabot; verify before close. |

## PRs Not Closed

No PR was closed in this checkpoint.

Reason: all apparent duplicates or stale branches either touch security-sensitive code, legal/license decisions, broad product surfaces, dependency state, or owner judgment. Closing them without deeper inspection would violate the safe-close rules.

## Check Status Snapshot

The following GitHub check rollups were read after the open PR list. A passing historical check does not make a stale/behind/dirty PR merge-ready; each PR still needs current-main validation before action.

| PR | check status |
|---|---|
| #156 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #152 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #151 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #150 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #148 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #147 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #146 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #145 | `core-test=SUCCESS`; `build-and-test (3.11)=FAILURE` |
| #143 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #142 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #136 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #135 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #134 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #133 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #132 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #131 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #130 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #129 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #128 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #127 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #121 | none reported |
| #119 | `build-and-test (3.11)=SUCCESS` |
| #117 | `build-and-test (3.11)=SUCCESS` |
| #111 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #108 | `build-and-test (3.11)=SUCCESS` |
| #107 | `build-and-test (3.11)=SUCCESS` |
| #82 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #81 | none reported |
| #79 | none reported |
| #78 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #74 | `build-and-test (3.11)=SUCCESS` |
| #67 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #60 | `build-and-test (3.11)=SUCCESS` |
| #34 | `build-and-test (3.11)=SUCCESS` |
| #32 | `build-and-test (3.11)=SUCCESS` |
| #26 | `build-and-test (3.11)=SUCCESS` |
| #25 | `core-test=SUCCESS`; `build-and-test (3.11)=SUCCESS` |
| #18 | `build-and-test (3.11)=SUCCESS` |
| #7 | `build-and-test (3.11)=FAILURE` |
| #6 | `generate-diagrams=FAILURE`; `build-and-test (3.11)=FAILURE` |

## Top 10 Next PR Decisions

1. #142: API access guard security; recreate clean patch if still valid.
2. #67: unauthenticated API guard; compare with current public Core auth boundary.
3. #128: dashboard path traversal; determine whether public/private boundary makes it public-safe or private-only.
4. #133: embed image SSRF; re-evaluate against current media/tool boundary.
5. #60: image crop/upscale SSRF; re-evaluate against current tools policy.
6. #131: `/listen` authorization; private runtime/Discord boundary review.
7. #129 / #130: duplicate `/say` authorization fixes; choose one current-main replacement or close both after replacement.
8. #135 / #136: duplicate Discord log masking fixes; choose one current-main replacement or close both after replacement.
9. #127 / #119 / #117: refresh `clients/web` dependency lockfile in one web dependency lane.
10. #156 / #7 / #6 / #34: refresh GitHub Actions dependency lane with workflow validation.

## Next Safe Actions

- Do not merge any open PR directly from this backlog.
- For security PRs, create fresh current-main patches only after confirming the vulnerable surface still exists.
- For dependency PRs, prefer fresh Dependabot/rebase lanes and run the relevant test/build matrix.
- For broad product branches, replace with v7.7-scoped lanes instead of rebasing old work wholesale.
- For legal/license/IP PRs, wait for owner decision.

## Non-Claims

This triage does not claim production readiness, full security remediation, official cloud completion, hybrid completion, final Web UI completion, persistent memory completion, Discord gateway completion, or `src/cogs/ora.py` resolution.
