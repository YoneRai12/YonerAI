# Environment Files (Templates)

ORA has multiple components. Each component reads env vars from a different file.
This repo includes commit-safe templates you can copy and fill in.

## 1) ORA Bot + ORA Web Backend (Python)

- Template: `.env.example`
- Your local file: `.env` (DO NOT commit)
- Used by:
  - Bot process (`python main.py` / `src/bot.py`)
  - Web backend (`uvicorn src.web.app:app`)
  - Docker Compose (`docker-compose.yml` uses `env_file: .env`)

The minimum required env var is `DISCORD_BOT_TOKEN`.
Most other items are optional and only enable features.

## Profiles (private/shared) and Instance IDs

ORA can isolate state for different "profiles" on the same machine (M1).

- `ORA_PROFILE=private|shared` (default: `private`)
  - Separates DB/logs/memory/temp/secrets under `ORA_DATA_ROOT/instances/<instance_id>/<profile>/`.
- `ORA_INSTANCE_ID` (optional)
  - Stable identifier per PC install. If missing, ORA generates and persists one under `ORA_DATA_ROOT/instance_id.txt`.
- `ORA_LEGACY_DATA_LAYOUT=1` (optional)
  - Escape hatch for older ORA_State/ORA_Logs layouts (disables the instances/profile directory layout).

Optional secret files (per profile) under `<...>/secrets/` are supported:
- `ora_web_api_token.txt` -> `ORA_WEB_API_TOKEN`
- `browser_remote_token.txt` -> `BROWSER_REMOTE_TOKEN` / `ORA_BROWSER_REMOTE_TOKEN`
- `admin_dashboard_token.txt` -> `ADMIN_DASHBOARD_TOKEN`

## 2) Dashboard UI (Next.js) - `ora-ui/`

- Template: `ora-ui/.env.example`
- Your local file: `ora-ui/.env.local` (DO NOT commit)

Used for Discord OAuth login (NextAuth/Auth.js).

## 3) Web Client (Next.js) - `clients/web/`

- Template: `clients/web/.env.example`
- Your local file: `clients/web/.env.local` (DO NOT commit)

Used for Discord OAuth login (NextAuth/Auth.js) and talking to ORA API/Core from the browser.
