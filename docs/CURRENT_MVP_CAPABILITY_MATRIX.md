# Current MVP Capability Matrix

Status: public-safe capability truth for the current public MVP.

## Current MVP In One Sentence

The current public MVP is a credential-free local Core API health smoke plus a mock/offline message contract, not a ChatGPT-like chat product.

## Included Now

- fresh public checkout
- dependency install
- local Core API startup
- `GET /health -> {"ok": true}`
- `POST /v1/public/messages -> deterministic offline mock reply`
- public smoke tests
- no Discord token required
- no provider API key required
- no private repository required
- no memory persistence required

## Not Included Yet

- Web UI chat
- ChatGPT-equivalent chat
- web search
- Google login
- same conversation history across devices
- persistent natural memory
- PC-hosted smartphone Web chat
- PC-hosted Discord chat
- provider live generation
- official cloud
- deployment
- full API / Web / CLI / SNS implementation
- production readiness

## User-Facing Examples

| Question | Current answer |
|---|---|
| Can I chat with AI from Web UI? | Not yet. |
| Can it search the web? | Not yet. |
| Can I log in with Google and keep the same history? | Not yet. |
| Can I host on my PC and chat from phone Web or Discord? | Not yet. |
| Does it naturally remember what I told it before? | Not yet. |
| Can I verify a message request contract? | Yes, through the local mock/offline `POST /v1/public/messages` endpoint. |
| What can I verify now? | Clone, install, start local Core API, call `/health`, and call `/v1/public/messages` in mock mode. |

## Next Capability Ladder

The current checkpoint should grow in separate, reviewable lanes:

1. Web UI connection to the mock/offline message endpoint
2. provider adapter boundary
3. memory persistence
4. identity / Google login
5. Discord gateway
6. web search
7. self-evolution proposal-only MVP expansion
8. official/private runtime lanes

Each ladder step needs its own tests, privacy boundary, and public wording review.

## Non-Claims

This checkpoint does not claim:

- shipping-complete
- production-ready
- official-cloud complete
- live-ops complete
- full product complete
- Pass 2 landed or completed
- `src/cogs/ora.py` solved or landed
- broader SSE/product exactness closure
- Web implementation complete
- Discord gateway complete
- Google login complete
- memory complete
- ChatGPT-equivalent feature parity

## Why This Exists

The public repository now has a real local health smoke, but users should not confuse that with a finished chat product.

This matrix is the public-facing guardrail for what can be truthfully said today.
