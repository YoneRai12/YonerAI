"""
YonerAI skill: {{SKILL_NAME}}

Contract:
  async def execute(args: dict, message, bot=None) -> str | dict

Notes:
  - Do not use `message.client` (discord.py Message does not guarantee it).
  - Use `bot` for get_cog/config access if needed.
"""


async def execute(args: dict, message, bot=None) -> str:
    # Example: echo input
    text = (args or {}).get("input") or ""
    return f"{{SKILL_NAME}}: {text}"


# Optional tool schema to improve routing/risk scoring.
TOOL_SCHEMA = {
    "name": "{{SKILL_NAME}}",
    "description": "Describe what this skill does.",
    "parameters": {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input text"},
        },
        "required": [],
    },
    "tags": ["dynamic", "skill"],
}

