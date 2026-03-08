from __future__ import annotations

import json
import logging
from typing import Any, Optional

import discord

logger = logging.getLogger(__name__)


def _summarize_mcp_result(res: Any, limit: int = 2000) -> str:
    """
    Convert MCP tool response into a short string to feed back into the Core loop.
    """
    if res is None:
        return ""
    if isinstance(res, str):
        return res[:limit]
    if isinstance(res, dict):
        # Common MCP shape: {"content":[{"type":"text","text":"..."}], ...}
        content = res.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for c in content:
                if isinstance(c, dict):
                    t = c.get("text")
                    if isinstance(t, str) and t.strip():
                        parts.append(t.strip())
            if parts:
                out = "\n".join(parts).strip()
                return out[:limit]
        # Fallback to JSON
        try:
            return json.dumps(res, ensure_ascii=False)[:limit]
        except Exception:
            return str(res)[:limit]
    try:
        return str(res)[:limit]
    except Exception:
        return ""


async def dispatch(
    args: dict,
    message: discord.Message,
    status_manager=None,
    *,
    bot=None,
    tool_name: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> dict:
    """
    Dispatch an MCP tool call. The concrete MCP tool is identified by `tool_name`.
    """
    if not tool_name:
        return {"ok": False, "error": "missing_tool_name"}
    if bot is None:
        bot = getattr(message, "client", None)

    mcp_cog = None
    try:
        mcp_cog = bot.get_cog("MCPCog") if bot else None
    except Exception:
        mcp_cog = None
    if not mcp_cog:
        return {"ok": False, "error": "mcp_disabled_or_not_loaded"}

    try:
        res = await mcp_cog.call_local_tool(tool_name, args if isinstance(args, dict) else {})
    except Exception as e:
        logger.warning("MCP tool failed tool=%s cid=%s err=%s", tool_name, correlation_id, e)
        return {"ok": False, "error": str(e)}

    # Keep raw payload small; Core only needs enough to continue reasoning.
    raw = res
    try:
        raw_s = json.dumps(res, ensure_ascii=False)
        if len(raw_s) > 20000:
            raw = {"_truncated": True, "_preview": raw_s[:20000]}
    except Exception:
        pass

    summary = _summarize_mcp_result(res)
    if isinstance(res, dict) and "ok" in res:
        ok = bool(res.get("ok"))
    else:
        ok = bool(res)

    return {
        "ok": ok,
        "result": summary,
        "raw": raw,
        "silent": True,
    }
