# Discord Hybrid Signed Contract Preflight 2026-05-21

Status: v7.7 public-safe preflight contract. This is not live Discord restoration.

## Summary

This preflight defines how YonerAI can later restore Discord safely across Official Hybrid Private and Full Private Self-Host modes without turning the public Python bot or old ORA artifacts into a second production responder.

The private Discord gateway remains the canonical production reply source. The public repository may define contracts, fixtures, and synthetic tests only.

## Required Acceptance Flow

- `mention_received`
- `bootstrap_status_embed`
- one or more `progress_edit_sent`
- exactly one terminal `final` or `controlled_error`
- same-message edit flow before the terminal reply
- reply-chain continuation through stable message references
- files/download section using file references only

## Signed Envelope Boundary

Discord gateway evidence may cross into public-safe fixtures through the existing Hybrid Signed Envelope contract.

The signed envelope proves origin and payload integrity only. A valid signature does not make a Discord event trusted, approved, or production-ready. Fixture donations remain quarantined and approval-gated.

## Responder Boundary

- Production reply source: private Discord gateway.
- Public Python bot / old ORA residue: legacy public-distribution residue until proven otherwise.
- Duplicate responders are denied at contract level.
- Public code must not require live Discord credentials for synthetic tests.

## Files And Downloads

- The gateway may expose file references in terminal metadata.
- Direct arbitrary external URL download is not allowed in this preflight.
- A download entry must use `fileref:` metadata and remain owner-scoped in the downstream files contract.

## Token And Security Boundary

- No real Discord token is required.
- No live Discord connection is required.
- No production signing key or production trust store is created.
- Raw prompts, raw completions, chain-of-thought, local paths, private runtime inventory, and secrets must not appear in public fixtures.

## Synthetic Evidence Added

- `core/src/ora_core/hybrid/discord_gateway_contract.py`
- `tests/test_discord_hybrid_gateway_contract.py`

The tests verify fixture-only behavior for signed envelope quarantine, duplicate terminal denial, public responder denial, no-live-credential requirements, file-reference-only downloads, reply-chain continuation, and node identity matching.

## Synthetic vs Live Evidence Gap

Synthetic evidence proves the public contract shape. It does not prove a live Discord gateway, production retry behavior, Discord rate-limit handling, private renderer behavior, or operational readiness.

## Not Included

- live Discord chat restoration
- Discord gateway completion
- production private runtime
- production signing keys
- production trust store
- persistent memory
- Google login
- deployment
- `src/cogs/ora.py` implementation changes

## Traceability

- Builds on `docs/contracts/HYBRID_SIGNED_ENVELOPE_AND_DONATION_POLICY_2026_05_20.md`
- Clean continuation after PR #229 and PR #230
