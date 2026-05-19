# Dependabot Triage 2026-05-21

Status: public-safe dependency-security gate for the Local LLM Conversation MVP and provider-compatibility follow-up.

This report records the open Dependabot alert state observed before this branch is merged. It is not a full vulnerability remediation claim.

## Summary

- Open alerts: 72
- Severity: 1 critical, 32 high, 32 medium, 7 low
- Ecosystem: 72 npm, 0 pip
- Core Python dependency alerts observed for this lane: 0
- `ora-ui` alerts: 71
- `clients/web` alerts: 1 medium `postcss` alert

## Gate Decision

The Local LLM Conversation MVP can proceed as a Core API lane because the remaining critical/high alerts are not on the Core API or local LLM path.

Recheck for the provider compatibility lane found the same open-alert shape: no current Dependabot alert targets the Core Python local LLM adapter path.

The old `ora-ui` surface remains deferred. It must not be used as the product foundation until its dedicated dependency-security lane is handled.

`clients/web` remains a smoke/demo surface only. Its remaining observed alert is a medium `postcss` advisory nested under Next.js; this does not block the Core local LLM lane.

## Triage Table

| group | severity | package | ecosystem | manifest | reachable surface | proposed action | status |
|---|---|---|---|---|---|---|---|
| #12 | critical | `next` | npm | `ora-ui/package-lock.json` | old/deferred `ora-ui` | Do not build on `ora-ui`; handle in dedicated dependency-security lane. | DEFER_TRACK |
| grouped | high | `next` | npm | `ora-ui/package-lock.json` | old/deferred `ora-ui` | Dedicated `ora-ui` refresh or retirement decision. | DEFER_TRACK |
| grouped | high | `electron` | npm | `ora-ui/package-lock.json` | old/deferred `ora-ui` | Dedicated Electron/PWA review; do not mix into Core local LLM branch. | NEEDS_OWNER |
| grouped | high | `minimatch`, `fast-uri`, `lodash`, `lodash-es`, `serialize-javascript`, `rollup`, `preact`, `picomatch`, `flatted`, `@babel/plugin-transform-modules-systemjs` | npm | `ora-ui/package-lock.json` | old/deferred `ora-ui` | Dedicated dependency lane. | DEFER_TRACK |
| grouped | medium | `postcss` | npm | `clients/web/package-lock.json` | smoke/demo `clients/web` | Track separately; do not force a broad or breaking package migration in this Core lane. | DEFER_TRACK |

## Not Fixed In This Branch

- No `ora-ui` dependency migration was attempted.
- No old UI cleanup or deletion was attempted.
- No broad framework migration was attempted.
- No alert was dismissed.

## Security Boundary For This Lane

The Local LLM Conversation MVP adds a Core adapter that only accepts loopback local LLM endpoints.

The provider compatibility follow-up keeps the same boundary: Ollama and OpenAI-compatible local servers are supported only through loopback URLs, and external provider URLs remain rejected by default.

It does not add:

- external provider calls
- arbitrary remote provider URLs
- Google login
- Discord gateway completion
- persistent memory
- `ora-ui` product usage
- deployment or release tag creation
