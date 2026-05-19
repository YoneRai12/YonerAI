# Current MVP Capability Matrix

Status: public-safe capability truth for the current public MVP.

## Current MVP In One Sentence

The current public MVP is a credential-free local Core API health smoke plus message contracts for mock/offline and loopback-only local LLM conversation, with `clients/web` as a temporary Web Chat MVP / smoke-demo surface. It is not a ChatGPT-like finished product.

## Included Now

- fresh public checkout
- dependency install
- local Core API startup
- `GET /health -> {"ok": true}`
- `POST /v1/public/messages -> deterministic offline mock reply`
- `POST /v1/public/messages` with `mode: "local"` can call supported loopback-only local LLM runtimes
- local provider choices: `ollama` and `openai_compatible_local`
- OpenAI-compatible local examples: LM Studio, llama.cpp / llama-cpp-python server, text-generation-webui with OpenAI API enabled, and LocalAI where compatible
- `clients/web` temporary Web Chat MVP page that posts to `/api/public/messages`
- `clients/web` mode controls for mock/offline, local Ollama, and OpenAI-compatible local smoke checks
- safe local LLM error display in the temporary Web Chat MVP
- public smoke tests
- no Discord token required
- no provider API key required
- no private repository required
- no memory persistence required
- no external provider API key required for local mode
- no arbitrary remote local-provider URL accepted by default

## Not Included Yet

- live Web AI chat
- ChatGPT-equivalent chat
- web search
- Google login
- same conversation history across devices
- persistent natural memory
- PC-hosted smartphone Web chat
- PC-hosted Discord chat
- provider live generation
- arbitrary remote provider URL
- retired `ora-ui` as the product foundation
- official cloud
- deployment
- full API / Web / CLI / SNS implementation
- production readiness

## User-Facing Examples

| Question | Current answer |
|---|---|
| Can I chat from a Web UI? | You can use `clients/web` as a temporary local Web Chat MVP for mock/offline and loopback local LLM smoke checks. It is not the final product UI. |
| Can it search the web? | Not yet. |
| Can I log in with Google and keep the same history? | Not yet. |
| Can I host on my PC and chat from phone Web or Discord? | Not yet. |
| Does it naturally remember what I told it before? | Not yet. |
| Can I verify a message request contract? | Yes, through the local mock/offline `POST /v1/public/messages` endpoint. |
| Can I use a local LLM? | Yes, if you run an Ollama-compatible runtime on `localhost`, `127.0.0.1`, or `::1` and call `mode: "local"`. |
| Can I use LM Studio or llama.cpp server? | Yes, when it exposes a loopback OpenAI-compatible `/v1/chat/completions` endpoint and you select `local_provider: "openai_compatible_local"`. |
| Can I choose a different local model? | Yes. Pass `model` in the request or set `ORA_LOCAL_LLM_MODEL`; availability depends on the local server. |
| Can I point it at a remote provider URL? | No. Local LLM mode rejects arbitrary remote, LAN, tunnel, and control-plane endpoints by default. |
| What can I verify now? | Clone, install, start local Core API, call `/health`, call `/v1/public/messages` in mock mode, optionally call local LLM mode, and use the temporary `clients/web` chat smoke page. |

## Next Capability Ladder

The current checkpoint should grow in separate, reviewable lanes:

1. local LLM error/reporting hardening
2. optional local model listing endpoint if it stays loopback-only and small
3. provider adapter boundary for non-loopback private lanes
4. final Web UI replacement or clean product surface decision
5. memory persistence
6. identity / Google login
7. Discord gateway
8. web search
9. self-evolution proposal-only MVP expansion
10. official/private runtime lanes
11. retired UI cleanup follow-through for old PRs and alerts

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
- final Web product UI complete
- Discord gateway complete
- Google login complete
- memory complete
- ChatGPT-equivalent feature parity

## Why This Exists

The public repository now has a real local health smoke, but users should not confuse that with a finished chat product.

This matrix is the public-facing guardrail for what can be truthfully said today.
