# Extensions / Adding Features (YonerAI)

This repo is designed so you can add new capabilities without touching the core router loop.

The three extension points are:

1. Skills (local tools)
2. MCP servers (external tools via stdio/JSON)
3. Cogs / Web UI (Discord commands + dashboards)

## Diagrams (README System Flows)

README diagrams are committed as PNGs for reliable GitHub rendering.

Regenerate them locally:

```powershell
pwsh scripts/render_diagrams.ps1 -Scale 5
```

## 1) Add A New Skill (Local Tool)

Skills live under `src/skills/<skill_name>/`.

Quick scaffold (recommended):

```bash
python scripts/new_skill.py my_skill
```

Minimum files:

- `src/skills/<skill_name>/SKILL.md` (human description)
- `src/skills/<skill_name>/tool.py` (implementation, exposes `execute`)
- Optional: `src/skills/<skill_name>/schema.json` or `TOOL_SCHEMA` in `tool.py`

### `tool.py` contract

Your skill must provide:

```py
async def execute(args: dict, message, bot=None) -> str | dict:
    ...
```

Notes:

- Do not use `message.client` (discord.py `Message` does not guarantee it). Use the `bot` parameter.
- Return a string for normal outputs.
- Return a dict if you need structured results (e.g. `{ "result": "...", "silent": true }`).

### Risk/Approvals behavior

- Owner vs guest access is enforced by allowlists (see `src/utils/access_control.py`).
- Approvals are enforced at runtime in one place (see `src/cogs/tools/tool_handler.py`).
- If your tool is risky, add tags in `TOOL_SCHEMA["tags"]` so risk scoring can classify it.

## 2) Add An MCP Server (External Tool Provider)

MCP servers are configured via `.env` and must be explicitly allowlisted.

Typical env knobs:

- `ORA_MCP_ENABLED=1`
- `ORA_MCP_SERVERS_JSON=[{"name":"artist","command":"python scripts/mock_mcp_artist.py","allowed_tools":["generate_artwork"]}]`

Guidelines:

- Keep allowed tools explicit (no wildcard).
- Prefer safe defaults: deny dangerous tools unless owner-only.

## 3) Add A New Discord/Web Feature (Cogs / UI)

- Discord features typically live under `src/cogs/`.
- Web backend lives under `src/web/`.
- The Next.js UI lives under `ora-ui/`.

Rule of thumb:

- Put "capability" in a tool/skill.
- Put "presentation" in the UI/cog.
- Keep authorization and approvals centralized (do not re-implement per feature).

## Quick checklist (before you ship a new capability)

- It is owner-only by default, or explicitly on the safe allowlist for guests.
- It has tags for risk scoring if it can touch files/network/system.
- It cannot be executed without approvals when risk is HIGH/CRITICAL (unless owner opted out via `.env`).
- It logs audit metadata (tool_call_id, actor_id, decision).
