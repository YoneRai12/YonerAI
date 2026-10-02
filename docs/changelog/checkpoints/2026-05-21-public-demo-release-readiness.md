# Alpha release readiness checkpoint - 2026-05-21

## Result

No GitHub Release or tag was created during this readiness PR.

The release train is ready for the final release gate after these merged PRs:

- #292 `fix: support semantic pre-release version checks`
- #293 `ci: support GitHub prerelease publishing`
- #294 `feat: polish YonerAI CLI demo experience`
- #295 `feat: connect memory quarantine fixture to YonerAI demo`
- #296 `fix: block unsafe embed image URLs`

The earlier public demo foundation remains in place:

- #286 `test: define YonerAI demo contract`
- #287 `feat: add YonerAI public demo command`
- #288 `feat: connect managed download guard to YonerAI demo`
- #289 `docs: add YonerAI demo quickstart`

The user-visible command is now:

```powershell
yonerai demo --pretty
yonerai demo --json
```

`yonerai quickstart` is an alias for the same public demo.

## Release readiness decision

Release readiness is met for final gate evaluation.

Gate criteria satisfied:

- `scripts/verify_version.py` accepts `0.1.0-alpha.1` and validates `v0.1.0-alpha.1` tag consistency.
- `.github/workflows/release.yml` classifies alpha/beta/rc releases as GitHub pre-releases.
- `VERSION` is set to `0.1.0-alpha.1`.
- `docs/releases/0.1.0-alpha.1.md` exists and includes Summary, Quickstart, YonerAI CLI, Demo Experience, What Works, Security / Boundary, Not Included, Validation, and Traceability.
- `yonerai demo --pretty`, `yonerai demo --json`, and `yonerai quickstart` are documented in README, README_JP, and clients/cli/README.
- The demo has at least two post-demo implementation connections: Hybrid memory quarantine fixture and embed image URL SSRF guard, in addition to the managed download guard.
- Official Managed Cloud remains external contract-only in the public repository.
- No production Oracle, live Discord, persistent memory, Google login, deployment, production trust store, or real telemetry ingestion was added.

Final gate still must re-check current `main`, CI, release existence, same-day release policy, secret/local path scan, mojibake/hidden Unicode scan, and `gh release view v0.1.0-alpha.1` before creating any tag or GitHub Release.

## Boundary confirmation

- Official Managed Cloud remains external contract-only in this public repository.
- The demo does not connect to Oracle, live Discord, external provider APIs, Google login, deployment systems, or production trust stores.
- Self-evolution remains synthetic and proposal-only.
- No production signing keys or production trust material were added.
- `src/cogs/ora.py` and `reference_clawdbot` were not modified.

## Validation evidence

- `python scripts/verify_version.py --tag v0.1.0-alpha.1`
- `python -m pytest tests/test_verify_version.py tests/test_release_workflow_prerelease.py -q`
- `python -m pytest tests/test_public_demo_script.py tests/test_surface_cli_smoke.py tests/test_public_mvp_smoke_script.py -q`
- `python -m pytest tests/test_yonerai_demo_contract.py tests/test_vision_embed_url_security.py -q`
- isolated venv README quickstart check: `python -m pip install -r core/requirements.txt httpx`, `python -m pip install -e .\clients\cli`, `yonerai demo --pretty`, `yonerai demo --json`, `yonerai quickstart --json`
- `python -m ruff check`
- `python -m compileall -q scripts/verify_version.py scripts/dev/public_demo.py core/src/ora_core/demo_contract.py clients/cli/yonerai_cli/cli.py src/cogs/handlers/vision_handler.py tests`
- `git diff --check`
- secret/local path scan
- mojibake/hidden Unicode scan

## Next action

Final release gate was run on `main` at `28416b048dc98604446d2689f1c9fc66657569b5`.

Technical release criteria passed:

- `v0.1.0-alpha.1` release and tag did not already exist.
- `python scripts/verify_version.py --tag v0.1.0-alpha.1` passed.
- targeted release/version/demo/CLI/smoke/security tests passed.
- isolated venv `yonerai demo --json`, `yonerai demo --pretty`, and `yonerai quickstart --json` passed after the documented dependencies were installed.
- `ruff`, targeted `compileall`, `git diff --check`, secret/local path scan, and mojibake/hidden Unicode scan passed.

Release creation was blocked by the release-train instruction for this run, not by implementation readiness:

- `v2026.5.21.5` was already published at `2026-05-21T08:21:07Z`.
- The current release-train prompt explicitly set a one-GitHub-Release-today cap.

No tag or GitHub Release was created for `v0.1.0-alpha.1` in this gate. The next action is to rerun the final release gate after that prompt-scoped cap no longer blocks release creation, verify that `v0.1.0-alpha.1` still does not exist, and then create the GitHub pre-release if all criteria still pass.

## Security intake rerun - 2026-05-21

The alpha gate was rerun after PR #305 `fix: harden alpha security surfaces before release` was merged into `main` at `0bc1857e0a68ff5a6f64f9679b6f849a347141a9`.

Security intake result:

- Owner-created alpha-blocking PRs #297, #298, #300, and #290 were integrated by #305.
- Owner-created PRs #301 and #302 were integrated with current-main fixes by #305.
- Owner-created PR #299 was superseded by #305 because the current-main fix uses runtime clock defaults and explicit public fixture times.
- Old PR #133 was closed as superseded by the merged embed URL SSRF guard from #296.
- Open PRs #135, #128, #60, #205, and #241 remain deferred/post-alpha or docs-only follow-up items and are not alpha CLI demo blockers.

Gate checks rerun:

- `gh release view v0.1.0-alpha.1` returned `release not found`.
- `VERSION` is `0.1.0-alpha.1`.
- `python scripts/verify_version.py --tag v0.1.0-alpha.1` passed.
- `yonerai demo --pretty` passed after installing the local CLI entry point from `clients/cli`.
- `yonerai demo --json` passed.
- `yonerai quickstart --json` passed.
- `python scripts/dev/public_mvp_smoke.py --json` passed.
- `python -m pytest tests/test_three_mode_route_preview.py tests/test_local_node_signed_action_envelope.py tests/test_local_node_enrollment_pairing.py tests/test_local_dev_control_plane_simulator.py tests/test_local_dev_control_plane_session_binding.py tests/test_final_downloads_bridge.py tests/test_surface_cli_smoke.py tests/test_public_demo_script.py tests/test_public_mvp_smoke_script.py tests/test_verify_version.py tests/test_release_workflow_prerelease.py tests/test_yonerai_demo_contract.py tests/test_vision_embed_url_security.py -q` passed.
- `python -m ruff check ...` passed for the touched alpha security and demo files.
- `python -m compileall -q ...` passed for release/demo/security surfaces and tests.
- `git diff --check` passed.
- Secret/local path scan found no secret values or local path leaks in release-critical output or changed security intake code. The only token-name hits are public demo environment-key denylist literals.
- Mojibake/hidden Unicode scan passed.

Release decision:

`v0.1.0-alpha.1` is ready to publish as a GitHub pre-release if it still does not exist immediately before tag creation.
