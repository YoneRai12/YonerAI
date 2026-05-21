from __future__ import annotations

import os


def load_mcp_deny_patterns() -> list[str]:
    raw = (os.getenv("ORA_MCP_DENY_TOOL_PATTERNS") or "").strip()
    if not raw:
        return [
            "delete",
            "remove",
            "rm",
            "wipe",
            "format",
            "reset",
            "push",
            "publish",
            "deploy",
            "shell",
            "exec",
            "run",
        ]
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def is_mcp_tool_denied(
    remote_tool_name: str,
    deny_patterns: list[str],
    *,
    allow_dangerous: bool = False,
) -> bool:
    if allow_dangerous:
        return False
    low_remote = str(remote_tool_name or "").strip().lower()
    if not low_remote:
        return False
    return any(str(pattern or "").strip().lower() in low_remote for pattern in deny_patterns if str(pattern or "").strip())
