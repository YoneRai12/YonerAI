# ORA Boundary Extraction Plan 2026-05-21

Status: implementation precursor, read-only inspection of `src/cogs/ora.py`.

This plan converts the old `DO_NOT_TOUCH` posture into a test-first extraction lane. It does not edit `src/cogs/ora.py`, does not adopt preserved dirty changes, and does not claim the ORA boundary is solved.

## Verified File Facts

- Path: `src/cogs/ora.py`
- Size: 3,280 lines on the inspected clean `main` branch.
- Encoding note: the file begins with a UTF-8 BOM; AST inspection must use `utf-8-sig` until a separate cleanup PR proves no behavior or tooling impact.
- Shape: one large `ORACog` class plus module helpers, Discord commands/listeners, private/runtime-adjacent helpers, tool schema builders, and legacy handlers.
- Not changed in this PR: yes.

## Responsibility Map

| Responsibility | Current line areas | Current role | Risk | Extraction readiness | Required tests before edit |
| --- | --- | --- | --- | --- | --- |
| Initialization and handler wiring | 124-215 | wires `ToolHandler`, `VisionHandler`, `ChatHandler`, vector memory fallback, cost manager, SafeShell | high coupling; constructor side effects | medium | constructor fixture with fake bot, no live Discord, no private paths |
| Dashboard/tunnel startup | 254-340 | exposes dashboard URL and can start ngrok through subprocess | control-plane behavior mixed into Discord cog | low for direct extraction, high risk to change | contract tests for dashboard URL decision; no subprocess execution in public tests |
| Startup sync and usage loops | 341-600 | startup sync, OpenAI usage sync, optimization scan | provider/account and local runtime coupling | low | fake cost manager tests, no live provider calls |
| System/admin commands | 707-824, 1215-1334 | reload, desktop watch, system info, process list, override, credits | host/system and admin-only behavior | low | access-control tests, no process mutation, no local host truth in fixtures |
| Slash-command chat/dataset/summarize | 873-1040 | Discord command ingress, file upload, summarization | Discord UX mixed with provider calls and attachments | medium | synthetic interaction tests, upload size/path tests, provider stub |
| Memory/RAG commands | 1064-1075, 1234-1262, 1878-1905 | memory clear/profile update/tool schema RAG reference | persistent memory boundary | low | quarantine/disabled-by-default memory fixtures |
| Voice/media | 1028-1139, 1616-1688, 1801-1814 | voice channel lookup, VoiceVox diagnostics, auto-read join/leave residue | live Discord/voice behavior | low | pure voice state fixture; no live gateway |
| Message ingress and dispatch | 1530-1822 | `on_message`, mention/reply filtering, prompt cleanup, attachment routing, chat handler dispatch | canonical Discord reply-source boundary | medium | duplicate responder denial, final once-only contract, mention/reply fixture |
| File/attachment/embed handling | 1759-1866 | attachment and embed image processing through `VisionHandler` | SSRF/DoS/file contract risk | medium-high | SSRF/size/managed-file contract tests before extraction |
| Safety/moderation helpers | 1362-1476 | spam detection, input spam detection, AI guardrail check | security-sensitive but partly pure | high for pure helpers | pure unit tests for spam/guardrail request construction; provider stub |
| Tool schema and capability filtering | 226-229, 1868-1905, 2979-3060 | static schemas, dynamic skills, registry injection, client/user filtering | capability widening risk | high | manifest parity tests, deny-by-default tests, no dynamic execution |
| Legacy prompt/reaction/rank helpers | 3064-3240 | delegated prompt handler, mock interaction, translation reaction, rank/points | mixed legacy/user-facing | medium | synthetic Discord event tests; store stub |

## Extraction Order

1. **Pure safety helper extraction**
   - Extract `_detect_spam`, `_is_input_spam`, and JSON/content cleaning helpers into a public-safe utility module.
   - First tests: compression-ratio spam, repetition spam, `[TOOL_CALLS]` recovery, content cleaning.
   - Claim after completion: pure helper behavior is covered and movable.
   - Must not claim: ORA runtime solved.

2. **Tool schema manifest boundary**
   - Move schema construction toward a manifest builder that returns data only.
   - First tests: client filtering, owner/non-owner filtering, dynamic registry does not bypass deny-by-default.
   - Claim after completion: public capability surface is testable without Discord runtime.
   - Must not claim: Tools/MCP complete or unrestricted execution enabled.

3. **Message ingress fixture seam**
   - Add fixture-level tests for mention/reply detection and prompt cleanup before moving dispatch code.
   - Keep private Discord gateway as canonical production reply source.
   - Claim after completion: public PythonBot residue has a tested non-responder boundary.
   - Must not claim: Discord restored.

4. **Attachment/embed contract seam**
   - Put attachment/embed handling behind a managed-file contract with SSRF/size tests.
   - Claim after completion: files/download behavior is constrained by tests.
   - Must not claim: arbitrary external URL download support.

5. **Control-plane removal seam**
   - Replace dashboard/tunnel subprocess behavior with a request/status contract only after owner decision.
   - Claim after completion: public repo no longer owns host process startup.
   - Must not claim: deployment or live operations complete.

## Owner / Private-Runtime Decisions Required

- Whether official Discord gateway runtime remains entirely in `YonerAI-private` with public repo keeping only contract tests.
- Whether dashboard/tunnel startup belongs only in `YonerAI-oracle-control-plane`.
- Whether legacy public PythonBot behavior should be retired, kept as public-distribution demo, or converted into a non-responder adapter.
- Whether memory/RAG commands remain disabled or become private-runtime-only.
- Which moderation/system/host tools are allowed outside owner-only private runtime.

## First Safe PR

Recommended first implementation PR:

- Title: `refactor: extract ora pure safety helpers`
- Scope: pure helpers only; no Discord import changes beyond call-site import replacement.
- Files likely touched: new `src/utils/ora_safety.py`, `src/cogs/ora.py`, focused tests.
- Required proof: current helper tests pass before and after extraction; public smoke tests pass; `src/cogs/ora.py` behavior diff is only import/call-site relocation.
- Stop condition: if BOM/encoding or import side effects make a no-behavior-change diff unclear, stop and split a test-only PR first.

## Stop Conditions

- Any change requires live Discord, live provider credentials, production signing keys, production trust stores, deployment, persistent memory enablement, Google login, private runtime truth, or control-plane internals.
- Any safe extraction requires changing `reference_clawdbot`.
- Hidden Unicode or mojibake appears in new code paths and safe cleanup is unclear.
- Tests fail twice for the same class.

## Non-Claims

This plan does not claim production readiness, full product completion, Discord gateway completion, live Discord restoration, persistent memory completion, Tools/MCP completion, v7.8 start, or `src/cogs/ora.py` resolution.
