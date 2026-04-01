# YonerAI Official Managed Cloud MVP Route Freeze

Last updated: 2026-04-01

This document freezes the minimum public MVP surface for restoring the
Official Managed Cloud entrypoint.

It is intentionally narrower than older public web snapshots.
The goal is not to restore all historical pages. The goal is to restore the
smallest safe surface that matches the current YonerAI direction.

## Scope

This freeze applies only to:

- `yonerai.com`
- `api.yonerai.com`

`files.yonerai.com` and `hooks.yonerai.com` remain reserved, but they are not
part of the first MVP implementation pass.

## Architecture Position

YonerAI is not three separate products.
It is one common base that switches between three modes:

1. `Full Private Self-Host`
2. `Official Hybrid Private`
3. `Official Managed Cloud`

This public repository is the public distribution core / shared foundation.
It is not the full official production runtime.

The private runtime remains the official source for:

- official `yonerai.com` operations
- official app runtime
- official Discord gateway
- files / hooks / maintenance / ops
- Oracle control plane and production operations

## Freeze Rule

For this MVP, use:

- `yonerai.com` as the site host
- `api.yonerai.com` as the chat/auth/API host

Do not introduce extra vanity subdomains in this phase.

## Host Responsibilities

### `yonerai.com`

Allowed:

- `/`
- `/jp`

Role:

- official top page
- explanation of what YonerAI is
- public-safe product framing
- CTA that sends users to chat

Not allowed in this phase:

- `/login`
- direct auth handling
- admin/operator/system control
- browser remote control
- local-native control
- deep Discord operations

Behavior:

- root is informational only
- the main CTA points to `https://api.yonerai.com/jp/chat`

### `api.yonerai.com`

Allowed in Phase 1:

- `/jp/chat`
- `/api/auth/*`
- `/api/public/chat/messages`
- `/api/public/chat/runs/{run_id}/events`

Optional later in MVP:

- `/api/public/attachments/*`

Role:

- web chat shell
- auth/session handling
- public chat request entrypoint
- public chat SSE stream

## Reserved For Later

Reserved but not implemented now:

- `files.yonerai.com`
- `hooks.yonerai.com`
- `relay.yonerai.com`
- `core.yonerai.com`
- `admin.yonerai.com`

Not part of the current strongest implementation direction:

- `chat.yonerai.com`
- `developers.yonerai.com`
- `auth.yonerai.com`

## Public-Safe Boundary

This MVP must stay within a public-safe boundary.

Do not expose:

- admin panels
- operator panels
- browser remote execution
- system control endpoints
- local machine control
- internal rollout or maintenance controls
- Oracle control plane surfaces
- arbitrary external fetch capability

Oracle control plane is not removed from the architecture.
It is only excluded from the public MVP surface.

## Route Behavior Notes

### Auth

The chat host owns auth.

- `yonerai.com` does not own login
- `api.yonerai.com` owns web auth/session
- if a user is unauthenticated, the chat host is responsible for sending the
  user into Google sign-in flow

### Chat

The first MVP chat loop only needs:

- session check
- message submit
- SSE response stream

### Memory-Lite

This MVP should not degrade into a stateless API wrapper.

The minimum YonerAI memory for this phase is:

- user identity bound to a web session
- persisted per-user conversation history
- reuse of recent turns when generating the next response

Not required in this phase:

- full MemoryCog behavior
- vector memory
- editable memory management UI
- long-term facts / traits panels
- cross-device synchronization UI

### Attachments

Attachments are not required for the first pass.
If enabled, they must stay controlled:

- short-lived
- owner checked
- no-store
- auditable

Do not reintroduce unsafe static file shortcuts.

## Implementation Notes

This route freeze is based on two kinds of evidence:

1. architecture/design truth
2. strongest surviving implementation direction

The strongest surviving implementation direction points to:

- `yonerai.com`
- `api.yonerai.com`
- `files.yonerai.com`
- `hooks.yonerai.com`

However, this document is still a working implementation freeze, not a
claim that every hostname here is already the final canonical production truth.

## Phase Split

### Phase 1

- route freeze
- public-safe top page
- `/jp/chat` shell
- `/api/auth/*`
- `/api/public/chat/messages`
- `/api/public/chat/runs/{run_id}/events`
- memory-lite conversation persistence and recent-turn reuse

### Phase 2

- `/api/public/attachments/*`
- reserved host preparation for `files.yonerai.com`
- stronger smoke tests for auth/chat/session boundaries

### Later

- hooks / gateway host
- relay host
- internal-only admin host
- production-specific control plane integration

## Non-Goals

This MVP does not aim to:

- restore every historical public page
- restore every old route exactly as it was
- expose private production behavior
- collapse public/private boundaries

The rule is:

**restore the minimum safe Official Managed Cloud surface, not the entire past web stack.**
