from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Optional

from discord.ext import commands

from src.cogs.mcp_policy import is_mcp_tool_denied, load_mcp_deny_patterns
from src.cogs.tools.registry import get_tool_meta, register_tool, unregister_tools
from src.utils.mcp_client import MCPStdioClient

logger = logging.getLogger(__name__)


def _is_enabled() -> bool:
    return (os.getenv("ORA_MCP_ENABLED") or "0").strip().lower() in {"1", "true", "yes", "on"}


def _safe_name(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", s)
    return s.strip("_") or "tool"


def _load_mcp_servers_from_env() -> list[dict]:
    raw = (os.getenv("ORA_MCP_SERVERS_JSON") or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    out: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        cmd = str(item.get("command") or "").strip()
        if not name or not cmd:
            continue
        out.append(item)
    return out


def _load_deny_patterns() -> list[str]:
    return load_mcp_deny_patterns()


def _load_mcp_servers_from_yaml() -> list[dict]:
    # Keep this independent of Config to avoid import cycles.
    path = os.path.join(os.getcwd(), "config.yaml")
    if not os.path.exists(path):
        return []
    try:
        import yaml  # local dependency already used in src/config.py
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return []
    servers = cfg.get("mcp_servers")
    if isinstance(servers, dict):
        servers = [servers]
    if not isinstance(servers, list):
        return []
    out: list[dict] = []
    for item in servers:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        cmd = str(item.get("command") or "").strip()
        if not name or not cmd:
            continue
        out.append(item)
    return out


class MCPCog(commands.Cog):
    """
    MCP client integration: connect to MCP tool servers and expose their tools to ORA.

    - Disabled by default (`ORA_MCP_ENABLED=0`).
    - Tools are registered dynamically under names like `mcp__<server>__<tool>`.
    - Access control is still enforced by ORA's tool allowlists (owner gets everything).
    """

    TOOL_PREFIX = "mcp__"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._clients: dict[str, MCPStdioClient] = {}
        # local tool name -> (server_name, remote_tool_name)
        self._tool_map: dict[str, tuple[str, str]] = {}

    async def cog_load(self) -> None:
        if not _is_enabled():
            logger.info("MCP: disabled (ORA_MCP_ENABLED != 1)")
            return

        # Clean previous MCP tools if any (hot reload safety).
        removed = unregister_tools(self.TOOL_PREFIX)
        if removed:
            logger.info("MCP: removed %d stale tools", removed)

        servers = _load_mcp_servers_from_env() or _load_mcp_servers_from_yaml()
        if not servers:
            logger.warning("MCP: enabled but no servers configured (ORA_MCP_SERVERS_JSON or config.yaml:mcp_servers)")
            return

        for s in servers:
            name = _safe_name(str(s.get("name") or "server"))
            cmd = str(s.get("command") or "").strip()
            if not cmd:
                continue
            cwd = str(s.get("cwd") or "").strip() or None
            env = s.get("env")
            if not isinstance(env, dict):
                env = {}
            env = {str(k): str(v) for k, v in env.items()}

            client = MCPStdioClient(name=name, command=cmd, cwd=cwd, env=env)
            self._clients[name] = client

            try:
                tools = await client.list_tools()
            except Exception as e:
                logger.warning("MCP: failed to list tools for server=%s: %s", name, e)
                continue

            allowed_tools = s.get("allowed_tools")
            if isinstance(allowed_tools, str):
                allowed_tools = [t.strip() for t in allowed_tools.split(",") if t.strip()]
            if allowed_tools is not None and not isinstance(allowed_tools, list):
                allowed_tools = None
            allowed_set = {str(t).strip() for t in (allowed_tools or []) if str(t).strip()}

            allow_dangerous = bool(s.get("allow_dangerous_tools")) or (
                (os.getenv("ORA_MCP_ALLOW_DANGEROUS", "0").strip().lower() in {"1", "true", "yes", "on"})
            )
            deny_patterns = _load_deny_patterns()

            for t in tools:
                remote_name = str(t.name or "").strip()
                if not remote_name:
                    continue
                # If allowlist is provided, register only those tools.
                if allowed_set and remote_name not in allowed_set:
                    continue
                # Deny obvious dangerous tools unless explicitly allowed.
                if is_mcp_tool_denied(remote_name, deny_patterns, allow_dangerous=allow_dangerous):
                    logger.info("MCP: skipping denied tool server=%s tool=%s", name, remote_name)
                    continue

                local_name = f"{self.TOOL_PREFIX}{name}__{_safe_name(t.name)}"
                self._tool_map[local_name] = (name, t.name)

                params = t.input_schema if isinstance(t.input_schema, dict) else {}
                if not params.get("type"):
                    params = {"type": "object", "properties": params.get("properties", {}) if isinstance(params, dict) else {}}

                schema = {
                    "name": local_name,
                    "description": (t.description or "").strip() or f"MCP tool '{t.name}' (server={name}).",
                    "parameters": params,
                    "tags": ["mcp", f"mcp_server:{name}"],
                }

                register_tool(
                    local_name,
                    impl="src.cogs.tools.mcp_tools:dispatch",
                    schema=schema,
                    tags=["mcp", "remote", name],
                    capability="mcp_remote_tool",
                    version="0.0.1",
                    meta={"server": name, "remote_tool": t.name},
                )

        logger.info("MCP: registered %d tools across %d server(s)", len(self._tool_map), len(self._clients))

    async def cog_unload(self) -> None:
        try:
            unregister_tools(self.TOOL_PREFIX)
        except Exception:
            pass
        for c in list(self._clients.values()):
            try:
                await c.close()
            except Exception:
                pass
        self._clients = {}
        self._tool_map = {}

    def resolve_local_tool(self, local_tool_name: str) -> Optional[tuple[str, str]]:
        if local_tool_name in self._tool_map:
            return self._tool_map[local_tool_name]
        # Fallback to registry meta (in case map isn't populated due to reload ordering)
        meta = get_tool_meta(local_tool_name).get("meta") or {}
        if isinstance(meta, dict) and meta.get("server") and meta.get("remote_tool"):
            return str(meta["server"]), str(meta["remote_tool"])
        return None

    async def call_local_tool(self, local_tool_name: str, arguments: Optional[dict] = None) -> dict:
        resolved = self.resolve_local_tool(local_tool_name)
        if not resolved:
            return {"ok": False, "error": "unknown_tool", "tool": local_tool_name}
        server, remote_tool = resolved
        client = self._clients.get(server)
        if not client:
            return {"ok": False, "error": "unknown_server", "server": server}
        import time
        t0 = time.time()
        try:
            res = await client.call_tool(remote_tool, arguments or {})
            res["_meta"] = {"server": server, "tool": remote_tool, "elapsed_ms": int((time.time() - t0) * 1000)}
            return res
        except Exception as e:
            return {"ok": False, "error": str(e), "_meta": {"server": server, "tool": remote_tool}}


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MCPCog(bot))
