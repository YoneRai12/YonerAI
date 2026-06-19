# YonerAI Required Checks

This file defines the checks that should block merges to `main` after the
YonerAI quality wall is enabled. It is intentionally explicit so future Codex,
Gemini, Dependabot, or human changes do not treat CI as optional.

## Required Branch Protection Checks

Enable these contexts as required status checks for `main`:

- `build-and-test (3.11)`
- `core-test`
- `core-unit`
- `cli-smoke`
- `tui-smoke`
- `provider-boundary`
- `hybrid-zero-trust`
- `installer-manifest`
- `security-static`
- `release-gate`
- `windows-cli-smoke`
- `windows-installer-manifest`
- `macos-cli-smoke`
- `macos-installer-manifest`
- `review-intake-required`

`core-test` and `build-and-test (3.11)` are the existing baseline checks.
Most contexts come from `.github/workflows/quality-wall.yml`.
`review-intake-required` comes from `.github/workflows/pr-intake-gate.yml`.

## Quality Wall Coverage Notes

- `security-static` runs `git diff --check`, `scripts/ci_quality_scans.py --changed`,
  `ruff`, `compileall`, and focused security boundary tests for auth,
  redaction, Cloudflare Access, MCP/tool deny policy, workspace file access, and
  CLI output formatting.
- `cli-smoke`, `windows-cli-smoke`, and `macos-cli-smoke` include dry-run auth
  and shell/terminal-output contracts, including Google OAuth PKCE/state
  reporting without token or verifier output.
- `installer-manifest`, `windows-installer-manifest`, and
  `macos-installer-manifest` include manifest/schema/trust, install/update plan,
  local bootstrap, and v0.8 install/auth boundary tests.
- `release-gate` blocks tag/version/manifest mismatch, mutable or unversioned
  release assets, SHA256 mismatch, prerelease flag mismatch, unresolved blocker
  markers, and public release overclaim phrasing.
- `review-intake-required` marks new, updated, or newly reviewed PRs as
  `needs-intake` and blocks merge until a maintainer-controlled
  `intake-reviewed` label confirms current PR/review/comment/CI intake.

## GitHub UI Setup

Use GitHub repository settings:

1. Open `Settings` -> `Branches`.
2. Add or edit the rule for `main`.
3. Enable `Require a pull request before merging`.
4. Enable `Require status checks to pass before merging`.
5. Enable `Require branches to be up to date before merging`.
6. Select every check listed in `Required Branch Protection Checks`.
7. Enable `Require conversation resolution before merging`.
8. Do not enable release, deploy, production Google login, or shared OpenAI
   traffic automation from this branch rule.

## Merge Policy

Before merging a delivery PR:

- read GitHub, Gemini, Codex, and human review comments;
- classify each comment as P0, P1, P2, P3, outdated, duplicate, or false-positive;
- fix P0/P1/security/correctness findings before merge;
- rerun targeted local validation after material fixes;
- wait for all required GitHub checks to pass.

OpenAI shared traffic and Google OAuth production login remain disabled in the
public repo. Their current CLI surfaces are status/dry-run contracts only.

## Release Gate Policy

`release-gate` must remain required before any future release automation can be
trusted. It verifies version/tag alignment, release note presence, manifest
presence, versioned asset names, SHA256 consistency when an artifact is present,
prerelease/stable mismatch, unresolved blocker markers, and production overclaim
phrasing.
