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

`core-test` and `build-and-test (3.11)` are the existing baseline checks.
The other contexts come from `.github/workflows/quality-wall.yml`.

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
