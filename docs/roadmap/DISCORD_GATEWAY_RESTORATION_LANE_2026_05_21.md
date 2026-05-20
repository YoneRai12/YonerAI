# Discord Gateway Restoration Lane 2026-05-21

Status: v7.7 next-lane board. This does not start v7.8.

## Lane 1: Signed Gateway Contract Fixtures

- Why it matters: prevents private gateway restoration from bypassing the public contract.
- Affected paths: `core/src/ora_core/hybrid`, `tests/test_discord_hybrid_gateway_contract.py`, `docs/contracts`.
- Risk: low while synthetic-only.
- Tests needed: signed envelope quarantine, duplicate responder denial, terminal once-only, file-reference-only downloads.
- Owner approval required: no for public-safe fixtures; yes before live gateway work.
- Claim after completion: public preflight contract exists.
- Must not claim: Discord gateway complete.

## Lane 2: Private Gateway Adapter Inventory

- Why it matters: separates canonical private gateway from public Python bot residue.
- Affected paths: `src/bot.py`, `src/cogs/handlers/chat_handler.py`, `src/cogs/ora.py`, private gateway repo.
- Risk: high because private/runtime boundaries are unresolved.
- Tests needed: responder election, same-message edit lifecycle, retry/timeout handling, reply-chain continuity.
- Owner approval required: yes.
- Claim after completion: adapter inventory is current.
- Must not claim: production responder restored.

## Lane 3: File Delivery Bridge

- Why it matters: Discord replies need safe file/download summaries without arbitrary external URL fetches.
- Affected paths: public files contract, private gateway adapter, Discord status manager.
- Risk: medium.
- Tests needed: file-ref-only terminal metadata, owner-scoped ticket issue, no direct external URL downloads.
- Owner approval required: yes before private runtime integration.
- Claim after completion: file contract can be consumed by the gateway.
- Must not claim: production download delivery complete.

## Lane 4: `src/cogs/ora.py` Boundary Resolution

- Why it matters: old ORA code remains a sensitive boundary surface.
- Affected paths: `src/cogs/ora.py`, associated handler imports, private/runtime docs.
- Risk: high.
- Tests needed: import boundary, no duplicate responder, no raw chain-of-thought, no private inventory exposure.
- Owner approval required: yes.
- Claim after completion: only what the dedicated boundary lane verifies.
- Must not claim: `src/cogs/ora.py` solved before that lane lands.

## Immediate Next Safe Patch List

1. Extend synthetic Discord gateway fixtures for controlled-error terminal behavior.
2. Add responder-election fixture tests before touching live adapters.
3. Inventory `src/cogs/handlers/chat_handler.py` reply-chain behavior in a private-runtime boundary doc.
4. Keep `src/cogs/ora.py` read-only until a dedicated boundary lane is approved.
