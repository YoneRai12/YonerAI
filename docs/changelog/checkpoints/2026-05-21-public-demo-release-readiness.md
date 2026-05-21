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

Merge this readiness PR if CI is clean and reviews have no material blockers. Then run the final release gate on current `main`; create `v0.1.0-alpha.1` only if the gate passes.
