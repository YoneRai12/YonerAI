# YonerAI Control Spine 実使用検証ログ - 2026-06

Status: public-safe real-use log.

## Anchors

- Latest stable release checked: `v0.7.0`.
- Latest prerelease checked: `v0.21.0-alpha.1`.
- Staging API host: `api-staging.yonerai.com`.
- Production login: disabled.
- Production Oracle/cloud runtime: not included.

## Short Commands

Verified user-facing commands:

```powershell
yonerai update
yonerai update stable
yonerai update alpha
yonerai login
yonerai whoami
yonerai sessions
yonerai revoke <session_id>
yonerai projects
yonerai ping
yonerai rate-limit
```

## Update UX

`yonerai update` now shows a two-step choice screen:

- stable: `yonerai update stable`
- alpha: `yonerai update alpha`

The screen does not download, install, mutate PATH, run remote code, force
updates, or auto-apply updates.

`yonerai update stable` now selects the public stable manifest
`manifest.v0.7.0.json`.

`yonerai update alpha` now selects the latest alpha manifest
`manifest.v0.21.0-alpha.1.json`.

## Staging API Real-Use Check

`yonerai rate-limit`:

- Result: success.
- Shows public rate-limit headers.
- Shows `agent:run` as disabled and threat-model-gated.
- Shows `admin:*` as disabled and threat-model-gated.
- Drops known private operational metadata from the staging response.

`yonerai ping`, `yonerai whoami`, `yonerai sessions`, `yonerai projects`,
`yonerai projects current`, and `yonerai projects use <project_id>` without a
saved session:

- Result: controlled unauthenticated state.
- User-facing Japanese next action: `yonerai login`.
- No stack trace.
- No local path.
- No token output.

`yonerai logout` without a saved session:

- Result: controlled no-session state.
- User-facing next action: `yonerai login`.
- No token output.

## Login E2E

Real-browser staging login E2E succeeded with a temporary config path.

Evidence is summarized in:

```text
docs/dogfood/LOGIN_E2E_2026-06.md
```

## Stale Test Triage

`tests/test_official_bridge_foundation.py` was stale. It expected the default
stable manifest to be `manifest.v0.6.0.json`.

Current truth:

- stable default: `manifest.v0.7.0.json`
- alpha explicit: `manifest.v0.21.0-alpha.1.json`

The test now verifies the current behavior instead of quarantining it.

## CURRENT_TRUTH Workflow

Verified:

- `.github/workflows/release.yml` has a `current-truth` job.
- The job runs on weekly schedule and workflow dispatch.
- The release job regenerates `CURRENT_TRUTH.md` before packaging.
- Local generation on 2026-06-11 selected:
  - latest stable: `v0.7.0`
  - latest prerelease: `v0.21.0-alpha.1`
  - staging host: `api-staging.yonerai.com`

## Remaining UX Notes

- `yonerai update` is still a safe check/plan surface, not an auto-updater.
- `yonerai ping` and protected account/project/session commands require
  staging login.
- Production login remains unavailable.
- Production installer signing/trust store remains unavailable.
