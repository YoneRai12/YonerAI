# Domain and Cloudflare Plan (Public)

## Scope
- Single source of truth for public subdomain planning.
- Public-safe only: no secrets, no internal runbooks, no real tunnel IDs, no private host details.

## Phase Plan

| Phase | Subdomain | Purpose | Public exposure |
|---|---|---|---|
| Phase 1 | `chat.<domain>` | User chat UI entry | Public |
| Phase 1 | `platform.<domain>` | Product landing / app shell | Public |
| Phase 1 | `developers.<domain>` | Developer docs and onboarding | Public |
| Phase 1 | `auth.<domain>` | Auth UX entry and callback-facing surface | Public |
| Phase 1 | `api.<domain>` | Public API gateway | Public |
| Phase 1 | `hooks.<domain>` | Webhook receiver | Public (tight validation) |
| Phase 1 | `ops.<domain>` | Operations dashboards | Private via Cloudflare Access |
| Phase 2 | `node.<id>.<domain>` | Per-user node routing pattern | Controlled rollout |
| Phase 2 | `relay.<region>.<domain>` | Regional relay ingress | Public (rate-limited) |

## DNS Record Templates

### Template A: Vercel / Pages-style frontend
- Type: `CNAME`
- Name: `<subdomain>`
- Target: `<project>.vercel.app` or `<project>.pages.dev`
- Proxy: Enabled (orange cloud)

### Template B: VPS-backed API ingress
- Type: `A` or `AAAA`
- Name: `<subdomain>`
- Target: `<VPS_IP>`
- Proxy: Enabled

### Template C: Cloudflare Tunnel-backed origin
- Type: `CNAME`
- Name: `<subdomain>`
- Target: `<TUNNEL_ID>.cfargotunnel.com`
- Proxy: Enabled

## Redirect Rules

Canonical route policy:
- `developer.<domain>` -> `https://developers.<domain>` (HTTP 301/308)
- `oauth.<domain>` -> `https://auth.<domain>` (HTTP 301/308)

Rule requirements:
- Preserve path and query string.
- Do not create application-level aliases when edge redirect can solve it.
- Keep canonical hostnames stable for cookies, OAuth origins, and telemetry grouping.

## Security Notes
- `ops.<domain>` must be protected by Cloudflare Access (identity-aware gate).
- `api.<domain>` and `auth.<domain>` must be proxied and rate-limited.
- Never publish runbooks with private diagnostics steps in public repo.
- Never publish tunnel IDs, internal hostnames, private IPs, or token-bearing examples.
- Keep strict separation between public docs and private operational details.
