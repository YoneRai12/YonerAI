# Dependabot Triage 2026-05-22

Status: public-safe dependency-security gate for the temporary Web Chat MVP review-gate checkpoint.

This report records the open Dependabot alert state observed before this branch is merged. It is not a full vulnerability remediation claim.

## Summary

- Open alerts observed on GitHub before this branch: 1
- Severity: 0 critical, 0 high, 1 medium, 0 low
- Ecosystem: 1 npm, 0 pip
- Core Python / local LLM adapter alerts observed for this lane: 0
- Retired `ora-ui` alert groups observed as open: 0
- Remaining observed alert before this branch: medium `postcss` in `clients/web/package-lock.json`

## Gate Decision

The temporary Web Chat MVP can proceed because the only observed alert is in the active smoke/demo web surface and has a narrow lockfile-level fix.

This branch adds an npm `overrides` entry for `postcss` and updates `clients/web/package-lock.json` so Next no longer carries the vulnerable nested `postcss` copy. Local `npm audit --omit=dev` and `npm audit` report zero vulnerabilities after the lockfile update.

GitHub Dependabot may still show the alert until this branch reaches the default branch and GitHub rescans the manifest.

## Triage Table

| alert | severity | package | ecosystem | manifest | affected range | fixed version | reachable surface | proposed action | status |
|---|---|---|---|---|---|---|---|---|---|
| #166 | medium | `postcss` | npm | `clients/web/package-lock.json` | `< 8.5.10` | `8.5.10` | temporary `clients/web` smoke/demo surface | Override to patched `postcss` and regenerate lockfile; validate with npm audit/build/lint. | FIX_NOW_SAFE |

## Not Fixed In This Branch

- No broad Next.js migration was attempted.
- No old `ora-ui` dependency remediation was attempted because `ora-ui` is retired from the active public surface.
- No alert was manually dismissed.
- Non-web dependency PRs remain separate review lanes.

## Security Boundary For This Lane

This branch keeps the temporary Web Chat MVP within the public Core API boundary.

It does not add:

- external provider calls
- arbitrary remote provider URLs
- Google login
- Discord gateway completion
- persistent memory
- `ora-ui` product usage
- deployment or production release

