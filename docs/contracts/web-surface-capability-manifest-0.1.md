# Web Surface Capability Manifest 0.1

Status: v7.7 public-safe Web surface manifest. Not final Web UI.

## Purpose

This manifest records what `clients/web` is allowed to represent today. It keeps
the temporary Web Chat MVP aligned with the public Core API, normal CLI, native
Japanese CLI contract, and same-experience wording without turning the Web lane
into a final product UI implementation.

## Surface Identity

```yaml
surface_id: clients-web-temporary-chat-mvp
surface_kind: temporary_web_smoke
contract_version: web-surface-capability-manifest-0.1
repo: public
status: releaseable_demo_only
not_final_ui: true
production_ready: false
```

## Allowed Capabilities

| capability | current route / path | user-visible status | boundary |
|---|---|---|---|
| health context | Core `GET /health` via docs/runbook only | documented, not surfaced as final status center | local Core only |
| public mock/offline message | Web rewrite `/api/public/messages` -> Core `/v1/public/messages` | usable smoke path | no provider key required |
| local Ollama message | Web rewrite `/api/public/messages` -> Core `/v1/public/messages` with `mode: local`, `local_provider: ollama` | usable when loopback server is already running | loopback-only |
| local OpenAI-compatible message | Web rewrite `/api/public/messages` -> Core `/v1/public/messages` with `mode: local`, `local_provider: openai_compatible_local` | usable when loopback compatible server is already running | loopback-only |
| temporary session pass-through | returned `session_id` reused for follow-up messages | non-persistent session metadata | process-local only |
| safe error display | Core error body rendered without stack traces | usable smoke UX | no secrets/local paths |

## Denied Capabilities

| capability | status | reason |
|---|---|---|
| final Web product UI | denied | design, identity, memory, auth, and official/cloud lanes are not stable |
| Google login | denied | identity lane not implemented |
| persistent memory | denied | memory policy requires approval workflow first |
| cross-device history | denied | no official identity/session sync |
| arbitrary provider URL input | denied | local provider boundary is loopback-only |
| external provider live generation | denied | public MVP has no external provider calls |
| Discord gateway completion | denied | private/runtime boundary residue remains |
| deployment | denied | no deploy lane in this surface |

## Same-Experience Ledger

| concern | Core API | CLI | Native Japanese CLI | Web surface | status |
|---|---|---|---|---|---|
| mock/offline message | `/v1/public/messages` | `yonerai message --mode mock` | future mapping requires confirmation when ambiguous | UI mode control | aligned |
| run contract | `/api/v1/agent/run` | `yonerai run --mode mock` | future dry-run can reference run command | not directly exposed yet | partial |
| local provider boundary | loopback-only validation | loopback-only API origin, Core owns provider URL | future commands must explain local-only boundary | no arbitrary URL input | aligned |
| session metadata | `session_id`, `conversation_id`, `memory_persisted: false` | response passthrough | future audit must mark memory_persisted false | UI reuses returned session id | aligned |
| error UX | deterministic public errors | safe CLI errors | future Japanese clarification/refusal | safe Web display | aligned |
| memory policy | false / no persistence | no persistence | dry-run and approval required | no persistence | aligned |
| final product claim | denied | denied | denied | denied | aligned |

## Manifest JSON Sketch

```json
{
  "surface_id": "clients-web-temporary-chat-mvp",
  "contract_version": "web-surface-capability-manifest-0.1",
  "allowed_capabilities": [
    "public_mock_offline_message",
    "loopback_local_ollama_message",
    "loopback_local_openai_compatible_message",
    "temporary_session_pass_through",
    "safe_error_display"
  ],
  "denied_capabilities": [
    "final_web_ui",
    "google_login",
    "persistent_memory",
    "cross_device_history",
    "arbitrary_provider_url",
    "external_provider_live_generation",
    "discord_gateway_completion",
    "deployment"
  ],
  "memory_persisted": false,
  "requires_loopback_core": true,
  "requires_provider_api_key": false,
  "production_ready": false
}
```

## Required Checks Before Web Expansion

- Web capability manifest stays current with Core API and CLI contracts.
- `clients/web` lint/build passes if Web files are touched.
- No arbitrary provider URL input is added.
- No Google login, persistent memory, official cloud, or final UI claim is added.
- Safe error display remains stack-trace/secret/local-path free.
- Same-experience labels match API, CLI, and native Japanese CLI contract docs.

## Non-Claims

This manifest does not claim:

- final Web UI completion
- production readiness
- official cloud completion
- persistent memory
- Google login
- Discord gateway completion
- provider ecosystem completion
- ChatGPT-equivalent parity

## Next Gate

Only after this manifest is reviewed, the next Web lane may add a fixture-backed
capability manifest display or smoke check. It must still avoid final UI scope.
