"""
Access control policy for ORA tool execution.

Goal:
- Creator (ADMIN_USER_ID) can use all tools/skills (full capability).
- Everyone else is restricted to a small safe allowlist by default.

This is enforced in two places:
1) Tool list filtering (so Core never sees restricted tools for non-owners).
2) Runtime guard in ToolHandler (so even if Core dispatches, it won't execute).
"""

from __future__ import annotations

import os
from typing import Iterable, Optional, Set


def _parse_csv_env(name: str) -> Set[str]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


# Minimal safe tool set for non-owner users.
# Keep this intentionally small; widen via ORA_PUBLIC_TOOLS if needed.
DEFAULT_PUBLIC_TOOLS: Set[str] = {
    "weather",
    "read_web_page",
    "read_chat_history",
    "get_role_list",
}

# Known high-risk / admin-only tools. This list is *advisory* because non-owner access
# is allowlist-based; still useful for readability and future policy changes.
DEFAULT_OWNER_ONLY_TOOLS: Set[str] = {
    # Local codebase inspection tools
    "fs_action",
    "read_file",
    "list_files",
    "search_code",
    "code_grep",
    "code_find",
    "code_read",
    "code_tree",
    # Remote browser control / automation / recording
    "web_remote_control",
    "web_action",
    "web_navigate",
    "web_set_view",
    "web_record_screen",
    # Downloading / saving large artifacts
    "web_download",
    # System/host control
    "system_control",
    "system_override",
    # Moderation / server management
    "ban_user",
    "kick_user",
    "timeout_user",
    "add_emoji",
    # Evolution hooks
    "request_feature",
}


def public_tools_allowlist() -> Set[str]:
    # If env is set, treat it as additive (not replacement) to avoid lockouts.
    return DEFAULT_PUBLIC_TOOLS | _parse_csv_env("ORA_PUBLIC_TOOLS")


def subadmin_tools_allowlist() -> Set[str]:
    # Default is empty. This keeps "creator only" behavior unless explicitly widened.
    return _parse_csv_env("ORA_SUBADMIN_TOOLS")


def owner_only_tools() -> Set[str]:
    return DEFAULT_OWNER_ONLY_TOOLS | _parse_csv_env("ORA_OWNER_ONLY_TOOLS")


def is_owner(bot: object, user_id: Optional[int]) -> bool:
    if not bot or user_id is None:
        return False
    cfg = getattr(bot, "config", None)
    owner_id = getattr(cfg, "admin_user_id", None)
    return bool(owner_id) and int(user_id) == int(owner_id)


def is_sub_admin(bot: object, user_id: Optional[int]) -> bool:
    if not bot or user_id is None:
        return False
    cfg = getattr(bot, "config", None)
    try:
        subs = getattr(cfg, "sub_admin_ids", set()) or set()
        return int(user_id) in {int(x) for x in subs}
    except Exception:
        return False


def is_tool_allowed(bot: object, user_id: Optional[int], tool_name: str) -> bool:
    if not tool_name:
        return False

    # Owner: full access.
    if is_owner(bot, user_id):
        return True

    # Sub-admin: strict allowlist (public + optional sub-admin additions).
    if is_sub_admin(bot, user_id):
        return tool_name in (public_tools_allowlist() | subadmin_tools_allowlist())

    # Non-owner: strict public allowlist.
    return tool_name in public_tools_allowlist()


def filter_tool_schemas_for_user(
    bot: object,
    user_id: Optional[int],
    tools: Iterable[dict],
) -> list[dict]:
    if is_owner(bot, user_id):
        return list(tools)

    allowed = public_tools_allowlist()
    if is_sub_admin(bot, user_id):
        allowed |= subadmin_tools_allowlist()
    out: list[dict] = []
    for t in tools:
        try:
            name = t.get("name")
        except Exception:
            continue
        if name in allowed:
            out.append(t)
    return out
