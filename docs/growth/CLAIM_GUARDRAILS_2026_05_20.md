# YonerAI Claim Guardrails 2026-05-20

Status: public-safe Growth/SNS guardrail for v7.7. This is not a production launch plan.

## Purpose

This document defines what public demo, SNS, README, release-note, and short-form
copy may truthfully say about YonerAI today. It keeps distribution messaging
aligned with provider independence, same-experience boundaries, approval-gated
self-evolution, and privacy-preserving learning without turning a checkpoint into
a production claim.

## Approved Short Claims

Use claims like:

- YonerAI is a provider-independent AI execution foundation.
- The public repo has a local Core API smoke surface.
- The public repo supports mock/offline messages and loopback-only local LLM modes.
- The public repo has a temporary Web Chat MVP / smoke-demo surface.
- The public repo has a local smoke CLI for health, message, and run checks.
- The public repo has contract docs for API, CLI, native Japanese CLI, Web, hybrid signed envelopes, and official cloud planning.
- Self-evolution work is approval-gated and proposal-only in the public surface.
- Hybrid donated data is not trusted only because it is signed.

## Required Qualifiers

When describing current capability, include at least one qualifier when context
could be misunderstood:

- local MVP
- temporary smoke surface
- contract checkpoint
- proposal-only
- in-memory
- loopback-only
- not production
- not final UI
- not official cloud

## Do Not Claim

Do not claim:

- production-ready
- shipping-complete
- official-cloud complete
- hybrid complete
- provider ecosystem complete
- ChatGPT-equivalent
- final Web UI complete
- Google login complete
- persistent memory complete
- Discord gateway complete
- full product complete
- Pass 2 landed
- `src/cogs/ora.py` solved

## Provider Independence Wording

Prefer:

- "provider-independent foundation"
- "local provider compatibility"
- "model/provider boundary"
- "OpenAI-compatible local runtime when running on loopback"

Avoid:

- "OpenAI replacement"
- "Gemini/Anthropic/OpenAI complete"
- "works with every provider"
- "official cloud is live"
- "no provider limits"

## Demo Copy Pattern

Use this order:

1. What works locally now.
2. What contract is being demonstrated.
3. What is deliberately not included yet.
4. Which next lane closes the gap.

Example:

> YonerAI can now run a local public Core API smoke flow: health, mock/offline
> message, loopback local LLM mode, a run-oriented API contract, a local CLI, and
> a temporary Web smoke surface. This is a v7.7 checkpoint, not a production
> cloud launch, final Web product, persistent memory system, or provider-parity
> claim.

## Traceability

Use release notes and contract docs for traceability. PR numbers may appear in
audit or PR bodies, but public-facing summary copy should lead with capability
and boundary, not internal review numbers.

