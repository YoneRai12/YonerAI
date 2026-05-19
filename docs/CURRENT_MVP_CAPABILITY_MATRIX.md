# Current MVP Capability Matrix

Status: public-safe capability truth for the current public MVP.

## Current MVP In One Sentence

The current public MVP is a credential-free local Core API health smoke, not a ChatGPT-like chat product.

## Included Now

- fresh public checkout
- dependency install
- local Core API startup
- `GET /health -> {"ok": true}`
- public smoke tests
- no Discord token required
- no provider API key required
- no private repository required

## Not Included Yet

- Web UI chat
- ChatGPT-equivalent chat
- web search
- Google login
- same conversation history across devices
- persistent natural memory
- PC-hosted smartphone Web chat
- PC-hosted Discord chat
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
| What can I verify now? | Clone, install, start local Core API, call `/health`. |

## Next Capability Ladder

The current checkpoint should grow in separate, reviewable lanes:

1. Core API message contract
2. offline/mock chat endpoint
3. Web UI chat
4. memory persistence
5. identity / Google login
6. Discord gateway
7. web search
8. self-evolution proposal-only MVP
9. official/private runtime lanes

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
