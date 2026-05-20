# v7.7 Implementation Evidence Ledger 2026-05-21

Status: public-safe evidence ledger. This document records what has actually landed in the public repository after the v7.7 design anchor. It does not create v7.8 and does not claim product completion.

## Scope

This ledger covers the recent public repository hardening sequence through `v2026.5.21.1`.

It distinguishes:

- runtime code evidence;
- tests and CI evidence;
- release / traceability evidence;
- docs-only policy or planning evidence;
- remaining blockers.

## Evidence Summary

| PR | merge commit | evidence type | changed paths | actual evidence landed | still docs-only or incomplete |
|---:|---|---|---|---|---|
| #197 | `e72537278d680c3f4d25f962e8caa3d704fad9c2` | public text hygiene | `docs/repo`, maintenance docs | public-surface text hygiene rules and mojibake cleanup record | does not fully restore every historical GitHub PR body |
| #198 | `06f809ed78fcdd12c2048f0a2bc055f208fc3c95` | PR backlog ledger | `docs/maintenance` | gh-based open/closed PR reconciliation | does not resolve all PR debt |
| #199 | `2c61644e1f2352b3b98d6126bbd7ed65af3ec3ff` | release style | `docs/repo`, `docs/RELEASE_NOTES.md` | release-note style guide and professional index structure | does not create runtime features |
| #200 | `5be49fe5a8e5388ae8f232ed38caceb7c1a1d1b9` | root/file index | `docs/repo` | public file index for root-visible entries | does not move uncertain root files |
| #201 | `eb6b8e3321ca1465a54876c0c1b4a3cc9bfa2936` | large-codebase inventory | `docs/architecture` | rough feature inventory and v7.7 integration map | does not wire legacy modules |
| #202 | `9f85b4d9997ae02ffe93a915310a389abbea8e7c` | dependency triage | `docs/security` | dependency PR lane classification | does not update runtime dependencies |
| #203 | `f636c482031021b9d21aeea1cdef1f0252e51ece` | dependency closure evidence | `docs/security` | web dependency supersession ledger | does not claim all dependency backlog resolved |
| #214 | `499692f13449c8dc2536af5526b58b99a597154c` | GitHub state reconciliation | `docs/maintenance` | public GitHub PR-count/state reconciliation | does not make public UI caches authoritative |
| #215 | `8fc3e06580a6ff59dca197b0846ebdeb21eb5dbd` | public text hygiene | `docs/repo` | hidden Unicode/mojibake policy | historical immutable content can remain |
| #216 | `f26211b89cfc30c182ea7d7c8e8435f8f67cd457` | security/runtime patch | `src`, tests, docs | fresh current-main security/runtime fixes and regression tests | not all security backlog resolved |
| #217 | `28fb11e2024b3516a7cbfa8d304d605b9f27143c` | security ledger | `docs/maintenance` | security/runtime PR triage update | unresolved PRs remain |
| #218 | `e64299142bb68a731245b03678e8531dc18b36a9` | root physical cleanup | `tools/maintenance`, docs | validated root helper move for `remove_legacy.ps1` | remaining launchers/config/entrypoints stay root-visible |
| #219 | `7f747a481150e46ae86ec1b9303c2d90f303ed40` | PR/branch reality | `docs/maintenance` | current PR/branch reality ledger | not a code feature |
| #220 | `2694503a463d52d6a2c12df72f10d394ab3de2da` | file-to-PR traceability | `docs/repo` | root-visible file-to-PR matrix | does not manipulate GitHub last-commit display |
| #221 | `146d2b5948e05775786a14d5345e192e7ce5e8f2` | architecture roadmap | `docs/architecture`, `docs/roadmap` | large-codebase integration/retirement lane board | does not integrate private or legacy code |
| #222 | `d977ab45af3957e2a7fb8a2483de975ef1c753e5` | runtime code + tests | `.env.example`, `core/src/ora_core`, tests | local LLM public access opt-in/token gate and request-derived base URL hardening | not provider ecosystem completion |
| #223 | `a4cbbdd828a3196e30fc25728a399cefc8b506d7` | dependency lane evidence | `docs/security` | 13 dependency PRs rechecked; zero open Dependabot alerts observed | no dependency PR was safe to close blindly |
| #224 | `6fe30e16cca6542b85c5ae67bd5e39486f9afb92` | root cleanup decision | `docs/repo` | reference-backed no-move decision for remaining root candidates | no physical move in that pass |
| #225 | `fcc34426b69c4c48c52b223bc9c7e4106c66cd14` | release alignment | README, release notes | `v2026.5.21.1` checkpoint note and README release alignment | does not finish release automation |

## Runtime Code Evidence

The strongest runtime evidence in this sequence is PR #222:

- `.env.example` now documents explicit local LLM opt-in and public token configuration.
- `core/src/ora_core/providers/local_llm.py` defaults local LLM enablement to disabled unless explicitly opted in.
- `core/src/ora_core/api/routes/public_messages.py` requires the configured public-token header for local LLM public message mode.
- public-message tests cover missing token, wrong token, accepted token, redacted provider failures, no request-derived base URL, and existing mock/offline behavior.

This is real runtime code and test evidence. It is still narrow: it does not add external provider live generation, persistent memory, production auth, deployment, or a complete provider ecosystem.

## Test And CI Evidence

The recent hardening lanes used:

- `python -m pytest tests/test_public_core_message_mvp.py tests/test_local_llm_provider.py tests/test_surface_api_run_contract.py -q`
- `python -m pytest tests/test_public_runnable_smoke.py tests/test_runtime_env_loader.py -q`
- `python -m ruff check` on touched Python paths
- `python -m compileall` on touched Python package paths
- `git diff --check`
- changed-file secret scans
- changed-file local absolute path / username / hostname scans
- mojibake and hidden Unicode scans for changed docs

GitHub checks `core-test` and `build-and-test (3.11)` passed on the merged PRs in this sequence.

## Release And Traceability Evidence

- GitHub Release `v2026.5.21.1` targets `fcc34426b69c4c48c52b223bc9c7e4106c66cd14`.
- `docs/releases/v2026.5.21.1-public-repository-hardening-checkpoint.md` records the checkpoint body.
- `docs/RELEASE_NOTES.md`, `README.md`, and `README_JP.md` point to the current checkpoint.
- `docs/repo/FILE_PR_TRACEABILITY_MATRIX_2026_05_21.md` explains root-visible file context without mass-touching files to change GitHub last-commit messages.

## Still Docs-Only Evidence

The following areas remain mostly or entirely documents, inventories, or contracts:

- PR/branch reality ledgers.
- File-to-PR traceability.
- Large-codebase integration and retirement map.
- Dependency PR drain evidence.
- Root no-move decision for remaining launcher/config/entrypoint candidates.
- Release-note style and public text hygiene policies.

These are useful maintenance evidence, but they are not runtime implementation completion.

## Remaining Blockers

- `src/cogs/ora.py` remains a separate do-not-touch boundary lane.
- Discord gateway completion is not proven.
- Persistent memory is not implemented as a public completed product feature.
- Google login is not implemented.
- Production signing, production trust store, and deploy/runtime supervision remain out of public scope.
- Tools/MCP remains a bounded safe-subset contract, not complete runtime execution.
- Dependency and security PR backlogs are reduced or classified but not fully resolved.
- README_JP still needs a dedicated public UTF-8 restoration pass beyond release-link updates.

## Non-Claims

This evidence ledger does not claim production readiness, shipping completeness, official-cloud completion, live-ops completion, full product completion, hybrid completion, persistent memory completion, Google login completion, Discord gateway completion, provider ecosystem completion, final Web UI completion, Tools/MCP completion, ChatGPT-equivalent parity, Pass 2 landing, all security backlog resolution, all dependency backlog resolution, v7.8 start/completion, or `src/cogs/ora.py` resolution.
