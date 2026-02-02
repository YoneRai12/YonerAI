import discord

async def play(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """Wrapper calling MusicSkill."""
    if not bot: return "❌ Bot missing."
    # MusicSkill is likely attached to a cog or ToolHandler.
    # Since we are lazy loading, we can inspect existing cogs or instantiate if needed.
    # Ideally reuse existing MusicSkill instance to reuse voice clients.
    
    # Try to find ToolHandler cog?
    tool_cog = bot.get_cog("ToolHandler") # Might be named differently 'Tools' or something
    if tool_cog and hasattr(tool_cog, "music_skill"):
        return await tool_cog.music_skill.execute("music_play", args, message)
    
    # Fallback: Check if we can find it elsewhere
    return "❌ Music system not accessible."

async def join(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    if not bot: return "❌ Bot missing."
    tool_cog = bot.get_cog("ToolHandler")
    if tool_cog: return await tool_cog.music_skill.execute("join_voice_channel", args, message)
    return "❌ Music system not accessible."

async def leave(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    if not bot: return "❌ Bot missing."
    tool_cog = bot.get_cog("ToolHandler")
    if tool_cog: return await tool_cog.music_skill.execute("leave_voice_channel", args, message)
    return "❌ Music system not accessible."

async def speak(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    if not bot: return "❌ Bot missing."
    tool_cog = bot.get_cog("ToolHandler")
    if tool_cog: return await tool_cog.music_skill.execute("tts_speak", args, message)
    return "❌ Music system not accessible."
