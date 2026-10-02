# ora-ui Retirement Decision 2026-05-21

Status: active public-surface retirement decision

## Decision

The legacy `ora-ui/` dashboard is retired from the active public repository surface.

The public product path is now:

- Core API health smoke
- public mock/offline message endpoint
- loopback-only local LLM message mode
- `clients/web/` as a smoke/demo web surface only

New public feature work must not build on `ora-ui/`.

## Evidence

- Current Core/local LLM tests and GitHub Actions do not depend on `ora-ui/`.
- Current public capability docs already describe `clients/web/` as the smoke/demo surface.
- Open Dependabot alerts before this cleanup were concentrated in `ora-ui/package-lock.json`: 71 of 72 open alerts.
- The active Core/local LLM path had no observed Dependabot blocker.

## Cleanup

This cleanup removes:

- the `ora-ui/` source tree and dependency lockfile
- old `ora-ui` compose service entries
- legacy Windows launchers that still started the retired dashboard
- public docs that described the retired dashboard as active

## Not Included

This decision does not add a new UI, does not remediate the old UI dependencies, and does not claim production readiness.

It also does not implement Google login, persistent memory, Discord gateway completion, external provider calls, deployment, or `src/cogs/ora.py` refactor work.

## Follow-up

After this cleanup reached `main`, the previously identified `ora-ui` Dependabot PRs were closed unmerged because their target manifest no longer exists.

The remaining active-surface security work should focus on the `clients/web` smoke/demo surface and Core API dependencies.
