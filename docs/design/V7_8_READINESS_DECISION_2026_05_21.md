# v7.8 Readiness Decision 2026-05-21

Decision: not ready to start v7.8.

YonerAI should remain in v7.7 implementation addendum / evidence accumulation until the missing runtime, contract, release, and boundary evidence below is present. The recent repository hardening and security-backlog work is meaningful, but it does not justify a design-version jump.

## Why Not v7.8 Yet

The recent work added real evidence in several areas:

- public local LLM access is more explicit and safer;
- root file presentation has better traceability;
- release/checkpoint hygiene is better aligned;
- large legacy/runtime surfaces are inventoried;
- stale PR/dependency/security lanes are less ambiguous.

That evidence is still not enough for v7.8 because much of it is policy, inventory, and maintenance scaffolding. A v7.8 start should require product/runtime substance, not only a cleaner repository surface.

## What Would Justify v7.8

A future v7.8 decision needs concrete artifacts such as:

- actual rows in a public-safe release/incident/acceptance ledger;
- actual JSON fixtures for API/CLI/Web/native Japanese CLI behavior;
- actual DDL or schema for any storage boundary that is public-safe to disclose;
- actual prompt text or prompt registry entries where prompts are part of the product contract;
- actual config export with redacted sample values and exact version lock;
- golden traces for representative local/API/CLI/Web flows without raw chain-of-thought;
- release ledger entries tied to tags, PRs, CI, and validation commands;
- tests that demonstrate broader public capability, not only documentation claims.

## What Remains v7.7 Implementation Addendum

The following should stay in v7.7:

- local LLM public access hardening;
- public Core API and CLI smoke refinements;
- native Japanese CLI contract and parser fixtures;
- Web smoke capability manifest alignment;
- Tools/MCP safe-subset contract and deny-by-default fixtures;
- root launcher/config migration pilots;
- security/runtime PR reproduction and fresh current-main patches;
- dependency lane drain;
- public README_JP UTF-8 restoration;
- `src/cogs/ora.py` boundary extraction planning.

## Required Gates Before Reconsidering

| gate | required evidence | current state |
|---|---|---|
| API / CLI / Web contract stability | versioned fixtures, deterministic errors, smoke and negative tests | partial |
| Native Japanese CLI | parser fixtures, ambiguity handling, dry-run and approval tests | contract-only |
| Memory | quarantine and donation fixtures without persistence overclaim | partial contract evidence |
| Tools/MCP | deny-by-default code or fixture evidence for safe subset | contract-only |
| Security backlog | relevant old PRs reproduced, patched, closed, or owner-decisioned | partial |
| Dependency backlog | lane-by-lane decisions with safe updates or documented blockers | partial |
| Root surface | reference-validated moves or explicit no-move decisions | partial |
| Release discipline | GitHub Release and markdown checkpoint stream aligned | improved by `v2026.5.21.1` |
| `src/cogs/ora.py` | owner-approved extraction lane, tests, and no private leak | not started |

## Explicit Non-Claims

This decision does not claim production readiness, shipping completeness, official-cloud completion, live-ops completion, full product completion, hybrid completion, persistent memory completion, Google login completion, Discord gateway completion, provider ecosystem completion, final Web UI completion, Tools/MCP completion, ChatGPT-equivalent parity, Pass 2 landing, all security backlog resolution, all dependency backlog resolution, v7.8 start/completion, or `src/cogs/ora.py` resolution.

## Next Review Point

Reconsider v7.8 only after at least one more implementation bundle lands with runtime evidence across API/CLI/Web or native Japanese CLI, plus validated security/dependency/root cleanup progress. The next review should cite exact PRs, commits, tests, fixtures, and release tags.
