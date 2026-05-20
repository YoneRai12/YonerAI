# Discord Restoration Boundary Map 2026-05-21

Status: v7.7 boundary map. This is not a runtime restoration plan.

## Public-Safe Surfaces

| Surface | Current role | Boundary |
| --- | --- | --- |
| `core/src/ora_core/hybrid` | signed envelope and fixture policy | public-safe contract helpers only |
| `docs/contracts` | cross-repo contract authority | no private route maps or secrets |
| `tests/test_discord_hybrid_gateway_contract.py` | synthetic contract evidence | no live Discord credentials |
| `core/src/ora_core/api` | public/core run contract | not a Discord gateway |
| `core/src/ora_core/tools/discord_proxy.py` | public proxy tool registration residue | security review before runtime claim |

## Private Or Owner-Decision Surfaces

| Surface | Status | Reason |
| --- | --- | --- |
| `src/cogs/ora.py` | do not touch in this goal | unresolved private/runtime/control-plane boundary |
| `src/bot.py` | legacy/public Discord bot residue | must not become simultaneous production responder |
| `src/cogs/handlers/chat_handler.py` | Discord handler evidence | requires dedicated gateway lane before production claims |
| `scripts/dev_discord.cmd` | local helper | not production gateway evidence |
| `scripts/verify_step3_discord.py` | verification helper | requires review before live use |
| `reference_clawdbot` | do not touch | reference-only and outside this public patch lane |

## Existing Evidence

- Core/SSE terminal behavior has tests for one terminal `final` or `error` event.
- Discord handler code shows idempotency and reply-chain intent through message references.
- File/download metadata is already contractized as file references in the public core.
- Hybrid Signed Envelope fixture policy already quarantines signed donations instead of trusting them.

## Remaining Gaps

- No live Discord gateway proof.
- No production responder election proof.
- No private gateway deployment proof.
- No `src/cogs/ora.py` resolution.
- No production trust registry or signing-key distribution.
- No live Discord token handling in public tests.

## Boundary Decision

The next safe Discord work is still contract and synthetic fixture expansion. Public code may validate gateway event shape, but it must not connect to live Discord or claim gateway restoration.
