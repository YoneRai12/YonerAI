# Capability Priority Map 2026-05-20

Status: public-safe roadmap. This is not a shipping or production-readiness claim.

| rank | lane | why this order | prerequisite | risk | repo owner | expected tests | releaseability |
|---|---|---|---|---|---|---|---|
| 1 | Hybrid connector fixture | It proves local/private-to-official result transfer without trusting donated data blindly. | Signed envelope policy and control-plane ingress skeleton. | Secret leakage, replay, over-trusting signed data. | Public + control-plane | Fixture envelope, signature, replay, quarantine, audit. | CONTRACT_READY |
| 2 | Memory policy scaffold | It defines what may become memory before any persistence exists. | Hybrid donation quarantine and approval model. | Memory poisoning, raw prompt/completion ingestion, privacy leakage. | Public + control-plane | Memory candidate allowed fields, forbidden markers, approval required. | CONTRACT_READY |
| 3 | Capability / extension boundary | Tools, MCP, providers, and future skills need explicit capability grants before exposure. | Donation policy, trust registry, and same-experience matrix. | Overbroad tool permission, hidden private dependency. | Public first, private/control-plane adapters later. | Capability allowlist, denied capability, revoked issuer. | NEEDS_CONTRACT |
| 4 | Agent swarm releaseability | Multi-agent behavior must be framed as reviewable workflows, not autonomous production actions. | Capability boundary and approval gates. | Unbounded autonomous actions, hidden mutation. | Public docs + control-plane proposal queue. | Synthetic swarm proposal fixtures, no auto-merge/deploy. | NEEDS_CONTRACT |
| 5 | Tools/MCP safe subset | Useful user-visible capability, but only after capability grants and data policy are stable. | Capability boundary and secret-scan guardrails. | Secret-bearing tool calls, private repo coupling. | Public for safe contracts, private for secret-bearing connectors. | Tool allow/deny, no network where disallowed, no secret output. | TESTABLE_INTERNAL |
| 6 | `src/cogs/ora.py` extraction step | It is known runtime residue, but extraction should follow contract coverage. | Import map, facade tests, message/session/hybrid boundaries. | Broad runtime behavior drift. | Public with dedicated refactor lane. | Facade contract, smoke, no runtime behavior change. | NEEDS_REFACTOR |
| 7 | Identity / Google login | Identity should not precede memory and capability policy because it changes trust semantics. | Session semantics, memory policy, official-cloud auth contract. | False login-complete claim, cross-device data leak. | Control-plane + private runtime later. | Stub auth contract, no real Google login until approved. | CONTROL_PLANE_ONLY |
| 8 | Discord gateway | Discord should connect to stabilized Core contracts, not carry product truth itself. | Message/session/provider boundary and identity/memory decisions. | Token handling, gateway behavior drift. | Private runtime primarily. | Gateway contract fixtures, no public token dependency. | PRIVATE_ONLY |
| 9 | Web final UI | The temporary Web Chat MVP is not the final product surface. UI should wait for stable core contracts. | Session, local provider, memory policy, identity decision. | Overclaiming final product, auth/memory mismatch. | Public for distributable UI, private for official runtime. | Component/build/API contract tests. | NEEDS_CONTRACT |
| 10 | Web search | It introduces external data and safety requirements and should come after tools policy. | Tools/MCP safe subset and source/audit policy. | External network, privacy, citation/source quality. | Public contract + private adapters later. | Disabled-by-default tests, source policy tests. | UNKNOWN |

## Current Next Lane

The next recommended lane is capability / extension boundary hardening, because hybrid connector and memory policy scaffolds now provide the minimum guardrails for donated results.

## Non-Claims

This map does not claim:

- production readiness
- official cloud completion
- hybrid completion
- persistent memory completion
- final Web UI completion
- Google login completion
- Discord gateway completion
- `src/cogs/ora.py` resolution

