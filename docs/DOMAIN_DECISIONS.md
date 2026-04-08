# Domain Decisions (Public)

## Canonical Hostnames
- `chat.<domain>`
- `platform.<domain>`
- `developers.<domain>`
- `auth.<domain>`
- `api.<domain>`
- `hooks.<domain>`
- `ops.<domain>`

## Alias Policy
- Aliases are handled by redirect rules only.
- Application code should target canonical hostnames.
- Current planned aliases:
  - `developer.<domain>` -> `developers.<domain>`
  - `oauth.<domain>` -> `auth.<domain>`

## Governance Rules
- Public docs contain templates and abstract architecture only.
- Operational internals (exact limits, internal diagnostics keys, private runbooks) stay private.
- No tokens, no private IDs, no internal endpoints in public markdown.
