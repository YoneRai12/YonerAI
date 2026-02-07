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

## 2) Dashboard UI (Next.js) - `ora-ui/`

- Template: `ora-ui/.env.local.example`
- Your local file: `ora-ui/.env.local` (DO NOT commit)

Used for Discord OAuth login (NextAuth/Auth.js).

## 3) Web Client (Next.js) - `clients/web/`

- Template: `clients/web/.env.local.example`
- Your local file: `clients/web/.env.local` (DO NOT commit)

Used for Discord OAuth login (NextAuth/Auth.js) and talking to ORA API/Core from the browser.

