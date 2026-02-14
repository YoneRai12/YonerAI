"""
Thin wrappers used by ToolHandler's central registry for voice/music tools.

Important: ToolHandler is not a Discord Cog. It's attached as `ORACog.tool_handler`.
The previous implementation looked up `bot.get_cog("ToolHandler")` and always failed,
causing tools like `music_play` to return "Music system not accessible."
"""

from __future__ import annotations

import discord

from src.skills.music_skill import MusicSkill


def _get_music_skill(bot) -> MusicSkill:
    """
    Prefer the cached MusicSkill instance owned by ORACog's ToolHandler.
    Fall back to a lightweight per-call MusicSkill.
    """
    try:
        ora_cog = bot.get_cog("ORACog") if bot else None
        tool_handler = getattr(ora_cog, "tool_handler", None) if ora_cog else None
        music_skill = getattr(tool_handler, "music_skill", None) if tool_handler else None
        if isinstance(music_skill, MusicSkill):
            return music_skill
    except Exception:
        pass
    return MusicSkill(bot)


async def play(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """Play music in the user's current voice channel (YouTube query/URL or audio attachment)."""
    if not bot:
        return "❌ Bot missing."
    result = await _get_music_skill(bot).execute("music_play", args, message)
    return result or "❌ Music system not accessible."


async def join(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """Join the invoking user's voice channel."""
    if not bot:
        return "❌ Bot missing."
    result = await _get_music_skill(bot).execute("join_voice_channel", args, message)
    return result or "❌ Music system not accessible."


async def leave(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """Leave the current guild voice channel."""
    if not bot:
        return "❌ Bot missing."
    result = await _get_music_skill(bot).execute("leave_voice_channel", args, message)
    return result or "❌ Music system not accessible."


async def speak(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """Speak TTS in the user's voice channel."""
    if not bot:
        return "❌ Bot missing."
    result = await _get_music_skill(bot).execute("tts_speak", args, message)
    return result or "❌ Music system not accessible."
