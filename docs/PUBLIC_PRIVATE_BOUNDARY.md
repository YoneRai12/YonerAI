# YonerAI Public / Private Boundary

Last updated: 2026-04-01

This document defines the public-safe boundary for the YonerAI repositories.

It exists to answer one practical question:

> What is safe to keep in the public GitHub repo, and what must stay in the
> private GitHub repo only?

This is not a full production inventory.
It is a boundary guide for implementation and review.

## Core Rule

The public repository is the **public distribution core / shared foundation**.

The private repository is the **official runtime / official operations layer**.

If something widens production capability, exposes internal control surfaces,
or reveals exact operational details that are not needed for public use, it
belongs in private.

## Safe For Public GitHub

These are appropriate for the public repo:

- local-first node runtime code
- public-safe web entry surfaces
- public-safe chat shell
- route freeze and public architecture notes
- shared contracts and schemas
- public API route definitions
- auth/session interface code that does not expose secrets
- idempotency and safety guards
- file delivery contracts without production secrets
- relay/core patterns that are safe to publish
- tests that do not require production credentials
- `.env.example` templates without real values
- public docs for setup, release, and extension workflows

Examples for the current MVP:

- `yonerai.com` top page and CTA
- `api.yonerai.com/jp/chat`
- `/api/auth/me`
- `/api/public/chat/messages`
- `/api/public/chat/runs/{run_id}/events`
- `docs/ROUTE_FREEZE_MVP.md`

Concrete public-safe files in the current MVP branch include:

- `src/web/app.py`
- `src/web/endpoints.py`
- `src/storage.py`
- `src/web/static/index.html`
- `src/web/static/chat.html`
- `src/web/static/site.css`
- `src/web/static/site.js`
- `tests/test_managed_cloud_mvp.py`
- `docs/ROUTE_FREEZE_MVP.md`
- `docs/PUBLIC_PRIVATE_BOUNDARY.md`

## Private GitHub Only

These must stay private:

- production secrets and tokens
- OAuth client secrets and callback credentials
- exact production host inventory beyond public-safe summaries
- Oracle control plane implementation details
- official production ops and maintenance runbooks
- incident response and internal recovery procedures
- internal admin/operator/system-control surfaces
- browser-remote or machine-control surfaces
- internal gateway and webhook rollout details
- production file backend rollout details
- moderation heuristics and commercial abuse rules
- billing, commercial enforcement, and internal policy logic
- internal observability wiring and alert routing
- production-only environment values
- private historical snapshots that expose broader runtime behavior than the
  current public-safe boundary

Concrete examples that must not be pushed to public:

- `google_client_secrets.json`
- real `.env` values
- production OAuth client IDs/secrets if they are not intended for public use
- exact production Cloudflare / tunnel / webhook rollout details
- internal operator/admin pages beyond the public-safe MVP boundary
- Oracle control plane implementation and runbooks
- commercial moderation and billing internals

## Public Review Questions

Every public PR for YonerAI should be checked against these questions:

1. Does this keep the public repo within the distribution-core role?
2. Does this expose any admin/operator/system-control surface?
3. Does this widen capability beyond the current route freeze?
4. Does this reveal secrets, internal host exactness, or production rollout
   details?
5. Does this keep safe-by-default and idempotency-first behavior intact?

If any answer is "no" or "it depends", the change should stop and be reviewed
as a private-side concern instead.

## Current MVP Boundary

For the current Official Managed Cloud MVP pass:

- `yonerai.com`
  - public top page only
- `api.yonerai.com`
  - chat shell, auth, public chat API
- `files.yonerai.com`
  - reserved, not implemented in the first pass
- `hooks.yonerai.com`
  - reserved, not implemented in the first pass

Not part of this public MVP pass:

- `admin.yonerai.com`
- `chat.yonerai.com`
- `developers.yonerai.com`
- `auth.yonerai.com`
- operator panels
- browser remote execution
- local-native control
- Oracle control plane surfaces

## Practical Rule Of Thumb

If a change is needed for a user to install, run, or understand the public-safe
YonerAI node or the public-safe managed-cloud entry surface, it may belong in
public.

If a change is needed to run the official production service, operate it,
recover it, control it, or hide sensitive implementation details, it belongs in
private.
