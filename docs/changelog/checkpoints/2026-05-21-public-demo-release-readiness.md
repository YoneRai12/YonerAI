# Public demo release readiness checkpoint - 2026-05-21

## Result

No GitHub Release or tag was created for this checkpoint.

The public runnable demo slice landed on `main` through these merged PRs:

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

The demo command and README quickstart criteria are met, but the repository release tooling is not yet ready for the requested semantic pre-release shape.

Release blockers:

- `scripts/verify_version.py` accepts only `X.Y.Z` or `YYYY.M.D`; it rejects `0.1.0-alpha.1`.
- `.github/workflows/release.yml` creates a normal published release on `v*` tags and does not mark releases as pre-release.
- The release workflow requires `docs/releases/${VERSION}.md`, so a semantic pre-release would also need a matching release note file and a safe release-tooling update before tagging.

Because of those blockers, creating `v0.1.0-alpha.1` now would either fail the release workflow or risk publishing with the wrong release classification.

## Boundary confirmation

- Official Managed Cloud remains external contract-only in this public repository.
- The demo does not connect to Oracle, live Discord, external provider APIs, Google login, deployment systems, or production trust stores.
- Self-evolution remains synthetic and proposal-only.
- No production signing keys or production trust material were added.
- `src/cogs/ora.py` and `reference_clawdbot` were not modified.

## Next action

Before creating `v0.1.0-alpha.1`, add a small release-tooling PR that supports semantic pre-release versions, marks alpha releases as pre-release, and adds the matching public release note.
