# v7.7 Integration Map 2026-05-21

Status: public-safe integration map. This is not a migration, deletion, or implementation PR.

## Design Truth

YonerAI v7.7 keeps one common distribution core and separates behavior through contracts, profiles, connectors, trust boundaries, capability manifests, and approval gates.

## Current Active Public Lanes

| lane | current status | active path/docs | next gate |
|---|---|---|---|
| Public Core API | active smoke/run contract | `core/`, `docs/contracts/external-agent-api.md` | strengthen error/schema/idempotency without production auth claims. |
| Local LLM | active loopback-only local mode | `core/`, local provider tests | model listing and safer local UX, no remote provider widening. |
| CLI | active local smoke CLI | `clients/cli/` | packaging and install UX, not native Japanese CLI. |
| Native Japanese CLI | contract-only | `docs/contracts/native-japanese-cli-contract-0.1.md` | parser/dry-run fixtures before commands. |
| Web | temporary smoke MVP | `clients/web/`, `docs/contracts/web-surface-capability-manifest-0.1.md` | capability manifest display and dropoff events, not final UI. |
| Self-evolution | public proposal-only | self-evolution tests/docs | approval UI/queue contracts, no auto mutation. |
| Hybrid signed envelope | fixture/policy boundary | `core/src/ora_core/hybrid/`, hybrid docs/tests | durable replay/trust registry lane, no production keys. |
| Tools/MCP | contract-only safe subset | `docs/contracts/tools-mcp-safe-subset-0.1.md` | safe decision fixture, no dynamic runtime execution. |

## Connect Later, Not Now

| area | likely path | classification | why not now | next safe lane |
|---|---|---|---|---|
| Discord gateway | `src/cogs/`, `src/bot.py` | `PRIVATE_OR_CONTROL_PLANE_BOUNDARY` | auth/command/private runtime risks | Discord boundary and security replacement PRs. |
| Memory | `memory/`, `src/*memory*`, optional requirements | `PUBLIC_CONTRACT_ONLY` | persistent memory is not implemented/claimed | memory candidate approval and storage policy lane. |
| Dashboard/operator surfaces | `src/web/`, dashboard scripts | `SECURITY_REVIEW_REQUIRED` | auth/private/runtime exposure risks | dashboard boundary audit. |
| Media/image/video | image/video scripts and cogs | `SECURITY_REVIEW_REQUIRED` | SSRF/DoS and provider/tool risks | media security PR replacement lane. |
| Deploy/ops | compose, cloudflare, scripts/tools | `PRIVATE_OR_CONTROL_PLANE_BOUNDARY` | public repo must not deploy or expose live ops | control-plane/private repo contracts only. |
| Provider ecosystem | provider markers across code/docs | `CONNECT_CANDIDATE` | provider independence is a design truth, not provider completion | provider manifest and local-only policy lane. |
| `src/cogs/ora.py` | `src/cogs/ora.py` | `DO_NOT_TOUCH` | explicit boundary residue | separate extraction lane only. |
| `reference_clawdbot` | gitlink | `DO_NOT_TOUCH` | external/broken gitlink risk | owner decision only. |

## Repo Split Alignment

- Public repo: common Core, public contracts, safe fixtures, public clients, capability manifests, and public-safe tests.
- Private runtime repo: official/private runtime implementation, secret-bearing config, official Discord/runtime details, and private memory surfaces.
- Official control-plane repo: official orchestration, audit, approval, rollback/test evidence, provider orchestration policy, and official self-evolution proposal queue.

## Non-Claims

This map does not claim production readiness, shipping completion, official-cloud completion, hybrid completion, persistent memory completion, Google login completion, Discord gateway completion, provider ecosystem completion, final Web UI completion, Tools/MCP completion, private runtime completion, official cloud runtime completion, or `src/cogs/ora.py` resolution.
