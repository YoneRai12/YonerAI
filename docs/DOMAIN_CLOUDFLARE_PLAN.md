# Domain Cloudflare Plan (Public Template)

## Scope
- Phase 1 subdomain design and ownership boundaries for Cloudflare.
- Public-safe template only. No real secrets, tokens, tunnel IDs, private IPs, or internal headers.

## Placeholders
- `<ROOT_DOMAIN>`: root domain (example: `example.com`).
- `<TUNNEL_CNAME>`: Cloudflare tunnel target (`<tunnel-id>.cfargotunnel.com`).
- `<PAGES_CNAME_TARGET>`: Vercel Pages/App target (`<project>.vercel.app` or `<project>.pages.dev`).

## Phase 1 Hostnames

| Hostname | Role | Placement | DNS Target Template | Notes |
|---|---|---|---|---|
| `chat.<ROOT_DOMAIN>` | User chat entry | Vercel Pages | `<PAGES_CNAME_TARGET>` | Canonical |
| `platform.<ROOT_DOMAIN>` | Product shell | Vercel Pages | `<PAGES_CNAME_TARGET>` | Canonical |
| `developers.<ROOT_DOMAIN>` | Developer docs/onboarding | Vercel Pages | `<PAGES_CNAME_TARGET>` | Canonical |
| `api.<ROOT_DOMAIN>` | Public API ingress | Cloudflare Tunnel | `<TUNNEL_CNAME>` | Canonical |
| `auth.<ROOT_DOMAIN>` | Auth/OAuth callback surface | Cloudflare Tunnel | `<TUNNEL_CNAME>` | Canonical |
| `hooks.<ROOT_DOMAIN>` | Webhook ingress | Cloudflare Tunnel | `<TUNNEL_CNAME>` | Canonical |
| `ops.<ROOT_DOMAIN>` | Ops/admin surface | Cloudflare Tunnel | `<TUNNEL_CNAME>` | Must be Cloudflare Access protected |
| `developer.<ROOT_DOMAIN>` | Alias for docs | Redirect Rule only | Any proxied edge-resolvable target | Redirect to canonical |
| `oauth.<ROOT_DOMAIN>` | Alias for auth | Redirect Rule only | Any proxied edge-resolvable target | Redirect to canonical |

## Placement Boundary

### On Cloudflare Tunnel
- `api.<ROOT_DOMAIN>`
- `auth.<ROOT_DOMAIN>`
- `hooks.<ROOT_DOMAIN>`
- `ops.<ROOT_DOMAIN>`

### On Vercel Pages
- `chat.<ROOT_DOMAIN>`
- `platform.<ROOT_DOMAIN>`
- `developers.<ROOT_DOMAIN>`

## Redirect Rules Policy

Aliases are handled at Cloudflare edge with Redirect Rules, not app-level alias logic.

- `developer.<ROOT_DOMAIN>` -> `https://developers.<ROOT_DOMAIN>` (`301` or `308`)
- `oauth.<ROOT_DOMAIN>` -> `https://auth.<ROOT_DOMAIN>` (`301` or `308`)

Requirements:
- Preserve path and query string.
- Keep canonical hostnames stable for cookies, OAuth origins, and analytics grouping.

## Public Safety Boundary
- Private runbooks/scripts remain in private repo only.
- Public repo keeps policy and templates only.
- Do not include internal environment variable names, private thresholds, diagnostic keys, exact tunnel IDs, signature formats, or token examples.
