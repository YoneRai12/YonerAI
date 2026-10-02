# Post-alpha security intake - 2026-05-22

## Result

Post-alpha security intake was completed after `v0.1.0-alpha.1`.

No GitHub Release or tag was created during this intake.

## Current-main baseline

- Baseline before this intake branch: `3f16bb08`.
- Alpha release already exists as a prerelease at `v0.1.0-alpha.1`.
- This checkpoint covers only public-safe, current-main-relevant follow-up work.

## PR classification

| PR | Classification | Decision |
| --- | --- | --- |
| #135 `security-sensitive Discord log forwarding issue` | POST_ALPHA_PATCHED | Replaced with a fresh current-main patch that redacts forwarded log text, limits message length, and disables forwarding to channels readable by `@everyone`. |
| #205 `docs security ledger disclosure` | POST_ALPHA_PATCHED | Replaced by current-main public-ledger redaction in this patch. |
| #241 `docs security backlog disclosure` | POST_ALPHA_PATCHED | Replaced by current-main public-ledger redaction in this patch. |
| #128 `security-sensitive dashboard user profile issue` | DUPLICATE_OR_SUPERSEDED | Current main already includes hardened dashboard profile path parsing and regression tests. |
| #60 `security-sensitive image fetch issue` | DUPLICATE_OR_SUPERSEDED | Current main already includes image URL host/IP guards and regression tests. |

## Integrated patch scope

- Discord log forwarding now uses shared best-effort redaction before building Discord embeds.
- Forwarded Discord log messages are whitespace-normalized and length-limited.
- Discord log forwarding is disabled when the configured guild channel is readable by `@everyone`.
- Discord webhook URL redaction was fixed in `src.utils.redaction`.
- Public maintenance ledgers no longer expose detailed open security backlog titles, branches, files, or tactical issue classes.

## Boundary confirmation

- No production Oracle, live Discord, deploy, production trust store, persistent memory, Google login, telemetry ingestion, provider live generation, npm publish, winget, or network-executing installer behavior was added.
- Official Managed Cloud remains contract-only/external in the public repository.
- `src/cogs/ora.py` and `reference_clawdbot` were not modified.

## Follow-up

- Remaining security-sensitive backlog should continue through restricted, current-main replacement lanes.
- This intake does not claim full security remediation, production readiness, Discord restoration, official cloud runtime completion, installer readiness, or `src/cogs/ora.py` resolution.
