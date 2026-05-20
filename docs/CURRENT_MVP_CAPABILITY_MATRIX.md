# Current MVP Capability Matrix

Status: public-safe capability truth for the current public MVP.

## Current MVP In One Sentence

The current public MVP is a credential-free local Core API health smoke plus message contracts for mock/offline and loopback-only local LLM conversation, with `clients/web` as a temporary Web Chat MVP / smoke-demo surface and `clients/cli` as a local smoke CLI. It is not a ChatGPT-like finished product.

## Included Now

- fresh public checkout
- dependency install
- local Core API startup
- `GET /health -> {"ok": true}`
- `POST /v1/public/messages -> deterministic offline mock reply`
- `POST /v1/public/messages` with `mode: "local"` can call supported loopback-only local LLM runtimes
- `POST /v1/public/messages` returns non-persistent conversation session metadata: `session_id`, `turn_index`, `history_count`, and `memory_persisted: false`
- `POST /api/v1/agent/run` starts a public-safe in-memory run surface for mock/offline smoke and loopback-only local mode
- `GET /api/v1/agent/runs/{run_id}/events` returns the in-memory public run event snapshot
- `POST /api/v1/agent/runs/{run_id}/results` records public-safe continuation result metadata with `trusted: false` and `memory_persisted: false`
- `clients/cli` can call loopback Core API health, public mock/offline messages, and the Surface API run smoke path
- local provider choices: `ollama` and `openai_compatible_local`
- OpenAI-compatible local examples: LM Studio, llama.cpp / llama-cpp-python server, text-generation-webui with OpenAI API enabled, and LocalAI where compatible
- `clients/web` temporary Web Chat MVP page that posts to `/api/public/messages`
- `clients/web` mode controls for mock/offline, local Ollama, and OpenAI-compatible local smoke checks
- safe local LLM error display in the temporary Web Chat MVP
- public-safe Official Cloud Control Plane MVP planning contracts
- public-safe Hybrid Signed Envelope / Donation Policy contract and test fixtures for future hybrid ingress
- synthetic Hybrid Connector Fixture for memory candidate, self-evolution signal, and improvement proposal envelopes
- memory candidate donation policy scaffold: quarantine first, `memory_persisted: false`, approval required before persistence
- capability priority map for the next design lanes
- public smoke tests
- no Discord token required
- no provider API key required
- no private repository required
- no memory persistence required
- no session metadata persisted across process restart
- no external provider API key required for local mode
- no arbitrary remote local-provider URL accepted by default
- no donated hybrid payload trusted solely because it is signed

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
- full hybrid connector
- production hybrid connector
- persistent donation-backed memory
- full API / Web / CLI / SNS implementation
- final SSE framing for the Surface API alias
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
| Can I verify a run-oriented public API surface? | Yes, through the local `POST /api/v1/agent/run`, `GET /api/v1/agent/runs/{run_id}/events`, and `POST /api/v1/agent/runs/{run_id}/results` smoke contract. It is in-memory and not production cloud. |
| Can I use a CLI? | Yes, `clients/cli` provides a local smoke CLI for `yonerai health`, `yonerai message --mode mock "hello"`, and `yonerai run --mode mock "hello"` after local install. It only accepts loopback origins and is not the final CLI product. |
| Can I send follow-up messages in one temporary session? | Yes. The public endpoint returns and accepts `session_id` for in-memory turn metadata. This is not persistent memory or cross-device history. |
| Can I use a local LLM? | Yes, if you run an Ollama-compatible runtime on `localhost`, `127.0.0.1`, or `::1` and call `mode: "local"`. |
| Can I use LM Studio or llama.cpp server? | Yes, when it exposes a loopback OpenAI-compatible `/v1/chat/completions` endpoint and you select `local_provider: "openai_compatible_local"`. |
| Can I choose a different local model? | Yes. Pass `model` in the request or set `ORA_LOCAL_LLM_MODEL`; availability depends on the local server. |
| Can I point it at a remote provider URL? | No. Local LLM mode rejects arbitrary remote, LAN, tunnel, and control-plane endpoints by default. |
| Is official cloud available now? | Not yet. The repository now has planning contracts for the Official Cloud Control Plane MVP, but no deployed official cloud product. |
| What can I verify now? | Clone, install, start local Core API, call `/health`, call `/v1/public/messages` in mock mode, optionally call local LLM mode, use the temporary `clients/web` chat smoke page, and run synthetic hybrid connector fixture tests. |

## Next Capability Ladder

The current checkpoint should grow in separate, reviewable lanes:

1. native Japanese CLI confirmation contract
2. Web surface capability manifest
3. Growth/SNS claim guardrails
4. local LLM error/reporting hardening
5. capability / extension boundary hardening
6. agent swarm releaseability map
7. tools/MCP safe subset
8. `src/cogs/ora.py` extraction step
9. identity / Google login
10. Discord gateway
11. final Web UI replacement or clean product surface decision
12. web search
13. memory persistence only after approval workflow and privacy policy are stable
14. official/private runtime lanes
15. retired UI cleanup follow-through for old PRs and alerts

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
