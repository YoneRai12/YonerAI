# Dependabot Triage 2026-05-20

Status: public-safe dependency-security triage for the Web UI mock-chat checkpoint.

This report records the GitHub Dependabot alert state observed before this branch is merged. GitHub alert counts may not change until the branch lands on `main` and GitHub reprocesses the manifests.

## Summary

- Open alerts: 137
- Severity: 2 critical, 65 high, 56 medium, 14 low
- Ecosystem: 131 npm, 6 pip
- Hot spots: `next`, `electron`, `minimatch`, `pillow`, `undici`, `lodash`, `picomatch`
- Selected Web UI path: `clients/web`
- Deferred Web UI path: `ora-ui`

## Triage Table

| alert | severity | package | ecosystem | manifest | affected range | fixed version | open PR | reachable surface | proposed action | status |
|---|---|---|---|---|---|---|---|---|---|---|
| #36 | critical | Pillow | pip | `requirements.txt` | `<10.2.0` and related ranges | `>=12.2.0,<13.0` | #149 | Public Core dependency set | Update requirement in this branch and validate public Core tests. | FIX_NOW_SAFE |
| #12 | critical | next | npm | `ora-ui/package-lock.json` | `16.0.3` affected | `16.2.6` | #159 | Deferred `ora-ui` surface | Do not use `ora-ui` for this checkpoint; handle in dedicated dependency lane. | NEEDS_OWNER |
| grouped | high | next | npm | `clients/web/package.json`, `clients/web/package-lock.json` | `<16.2.5` / `<16.2.6` | `16.2.6` | #160 | Chosen Web UI mock-chat path | Update `clients/web` Next.js to `16.2.6` and validate build. | FIX_NOW_SAFE |
| grouped | high | undici via `discord.js` | npm | `clients/web/package-lock.json` | `<6.24.0` | `6.24.0` | none observed | Chosen Web UI dependency tree, but unused direct dependency | Remove unused `discord.js` from `clients/web`. | FIX_NOW_SAFE |
| grouped | high | flatted / minimatch / picomatch | npm | `clients/web/package-lock.json` | vulnerable dev transitive ranges | fixed transitive versions | #117 for flatted, none observed for all | Dev/build dependency surface | Run safe lockfile-only `npm audit fix`; validate lint/build. | FIX_NOW_SAFE |
| grouped | high | next / electron / minimatch / lodash / serialize-javascript / rollup / preact | npm | `ora-ui/package.json`, `ora-ui/package-lock.json` | multiple | multiple | #159, #125, #122, #77 and others | Deferred Electron/PWA/dashboard surface | Keep out of this checkpoint; requires dedicated review because it is broader than public mock-chat. | NEEDS_OWNER |
| grouped | medium | postcss via next | npm | `clients/web/package-lock.json` | `<8.5.10` nested under Next.js | no non-breaking fix from npm audit | none | Chosen Web UI dependency tree | Track. `npm audit fix` offers a breaking downgrade path, so do not force. | DEFER_TRACK |

## Local Validation Result

After local dependency changes in this branch:

- `clients/web` production audit: 0 critical, 0 high, 2 moderate
- `clients/web` full audit: 0 critical, 0 high, 2 moderate
- Remaining moderate finding is `postcss` nested under `next`; npm currently proposes a breaking forced change, so it is tracked rather than forced.

## Web UI Gate Decision

The Web UI mock-chat MVP can proceed on `clients/web` because the critical/high blockers on that chosen path were either fixed locally or moved out of the reachable path by removing unused dependency weight.

`ora-ui` remains blocked for public user-visible work until its Next/Electron/PWA dependency lane is reviewed separately.

## Not Included

- No alert was dismissed.
- No broad framework migration was performed.
- No `ora-ui` remediation was attempted in this branch.
- No deploy, production release, or GitHub Release tag was created.
