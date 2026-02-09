from __future__ import annotations

import logging
from typing import Any

import discord

logger = logging.getLogger(__name__)


async def web_search_api(args: dict, message: discord.Message, status_manager=None, *, bot=None, **kwargs) -> str:
    """
    Safe web search tool that uses SearchClient (SerpApi or DuckDuckGo fallback).
    This does NOT drive a browser and does NOT download anything.
    """
    query = (args or {}).get("query")
    if not isinstance(query, str) or not query.strip():
        return "Error: query is required."
    query = query.strip()

    try:
        limit_raw = (args or {}).get("limit", 5)
        limit = int(limit_raw)
    except Exception:
        limit = 5
    limit = max(1, min(10, limit))

    # Prefer the cog-provided SearchClient if available.
    search_client = None
    if bot is not None:
        try:
            cog = bot.get_cog("ORACog")
            search_client = getattr(cog, "_search_client", None) if cog else None
        except Exception:
            search_client = None

    if search_client is None and bot is not None:
        search_client = getattr(bot, "search_client", None)

    if search_client is None:
        return "Error: Search is not configured (SearchClient missing)."

    try:
        results = await search_client.search(query, limit=limit)
    except Exception as e:
        logger.warning("web_search_api failed: %s", e)
        return f"Error: search failed ({type(e).__name__})."

    # Normalize and format output (Discord-friendly, also OK for web).
    lines: list[str] = [f"Search results for: {query}"]
    if not results:
        lines.append("(no results)")
        return "\n".join(lines)

    for i, r in enumerate(results[:limit], start=1):
        if not isinstance(r, dict):
            continue
        title = str(r.get("title") or "(no title)")
        link = str(r.get("link") or "")
        snippet = str(r.get("snippet") or "")

        # Keep snippets short to avoid wall-of-text.
        snippet = snippet.replace("\n", " ").strip()
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."

        if link:
            lines.append(f"{i}. {title}\n   {link}")
        else:
            lines.append(f"{i}. {title}")
        if snippet:
            lines.append(f"   {snippet}")

    return "\n".join(lines)

