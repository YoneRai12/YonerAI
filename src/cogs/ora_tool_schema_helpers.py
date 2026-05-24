from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


WEB_ONLY_TOOL_NAMES = frozenset({"dom_click", "dom_read", "browser_nav"})
DISCORD_ONLY_TOOL_NAMES = frozenset(
    {
        "join_voice_channel",
        "leave_voice_channel",
        "join_voice",
        "leave_voice",
        "tts_speak",
        "speak",
        "manage_user_voice",
        "create_channel",
        "music_play",
        "music_stop",
        "music_control",
        "music_queue",
        "music_seek",
        "music_tune",
    }
)

ToolSchema = dict[str, Any]
RegistryLoader = Callable[[], Iterable[ToolSchema]]
AccessFilter = Callable[[object, int | None, Iterable[ToolSchema]], list[ToolSchema]]


def build_context_tool_schemas(
    static_tools: Iterable[ToolSchema],
    *,
    client_type: str = "discord",
    skill_loader: object | None = None,
    registry_loader: RegistryLoader | None = None,
    access_filter: AccessFilter | None = None,
    bot: object | None = None,
    user_id: int | None = None,
) -> list[ToolSchema]:
    """Merge and filter ORA tool schemas without importing Discord runtime."""
    all_tools = list(static_tools)
    all_tools.extend(iter_dynamic_skill_schemas(skill_loader))
    all_tools.extend(iter_registry_tool_schemas(registry_loader))

    filtered = filter_tool_schemas_by_client(dedupe_tool_schemas_by_name(all_tools), client_type)
    if user_id is not None and access_filter is not None:
        return access_filter(bot, user_id, filtered)
    return filtered


def iter_dynamic_skill_schemas(skill_loader: object | None) -> list[ToolSchema]:
    if skill_loader is None or not hasattr(skill_loader, "skills"):
        return []
    schemas: list[ToolSchema] = []
    for skill_name in getattr(skill_loader, "skills").keys():
        schema = skill_loader.get_schema(skill_name)
        if isinstance(schema, dict) and schema.get("name"):
            schemas.append(schema)
    return schemas


def iter_registry_tool_schemas(registry_loader: RegistryLoader | None) -> list[ToolSchema]:
    if registry_loader is None:
        return []
    schemas: list[ToolSchema] = []
    try:
        loaded = registry_loader()
        for schema in loaded:
            try:
                name = schema.get("name")
            except Exception:
                continue
            if isinstance(name, str) and name:
                schemas.append(schema)
    except Exception:
        return []
    return schemas


def dedupe_tool_schemas_by_name(tools: Iterable[ToolSchema]) -> list[ToolSchema]:
    deduped: list[ToolSchema] = []
    seen: set[str] = set()
    for tool in tools:
        try:
            name = tool.get("name")
        except Exception:
            continue
        if not name or name in seen:
            continue
        deduped.append(tool)
        seen.add(name)
    return deduped


def filter_tool_schemas_by_client(tools: Iterable[ToolSchema], client_type: str = "discord") -> list[ToolSchema]:
    filtered: list[ToolSchema] = []
    for tool in tools:
        name = tool["name"]
        if client_type == "discord" and name in WEB_ONLY_TOOL_NAMES:
            continue
        if client_type == "web" and name in DISCORD_ONLY_TOOL_NAMES:
            continue
        filtered.append(tool)
    return filtered


def tool_schema_boundary_status() -> dict[str, object]:
    sample_tools = [
        {"name": "music_play"},
        {"name": "dom_click"},
        {"name": "dangerous_unknown"},
    ]
    discord_names = {tool["name"] for tool in filter_tool_schemas_by_client(sample_tools, "discord")}
    web_names = {tool["name"] for tool in filter_tool_schemas_by_client(sample_tools, "web")}
    return {
        "name": "ora_tool_schema_boundary",
        "source": "src/cogs/ora_tool_schema_helpers.py",
        "status": "ok" if "dom_click" not in discord_names and "music_play" not in web_names else "fail",
        "discord_excludes_web_only": "dom_click" not in discord_names,
        "web_excludes_discord_only": "music_play" not in web_names,
        "unknown_tool_execution_allowed": False,
        "execution_performed": False,
        "broad_ora_refactor": False,
    }


__all__ = [
    "DISCORD_ONLY_TOOL_NAMES",
    "WEB_ONLY_TOOL_NAMES",
    "build_context_tool_schemas",
    "dedupe_tool_schemas_by_name",
    "filter_tool_schemas_by_client",
    "iter_dynamic_skill_schemas",
    "iter_registry_tool_schemas",
    "tool_schema_boundary_status",
]
