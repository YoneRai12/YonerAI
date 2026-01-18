
import logging
import asyncio
import discord
from typing import Optional
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

class ToolHandler:
    def __init__(self, bot, cog):
        self.bot = bot
        self.cog = cog

    async def execute(self, tool_name: str, args: dict, message: discord.Message, status_manager = None) -> Optional[str]:
        """
        Executes a tool. Returns the result string, or None if the tool is not handled by this handler.
        """
        # 1. Update Status
        if status_manager:
            # Avoid overwriting status if it's already specific (handled inside specific tools if needed)
            # But generic status is good.
            # actually ORACog does this, so we might skip or duplicate. 
            # ORACog calls this check line 1286. 
            pass 

        if tool_name == "google_search":
            return await self._handle_google_search(args, status_manager)
            
        elif tool_name == "request_feature":
            return await self._handle_request_feature(args, message)

        elif tool_name in {"music_play", "music_control", "music_tune", "music_seek"}:
            return await self._handle_music(tool_name, args, message)

        return None

    async def _handle_google_search(self, args: dict, status_manager) -> str:
        try:
            query = args.get("query")
            if not query: return "Error: No query provided."
            
            if status_manager:
                await status_manager.next_step(f"Web検索中: {query}")
            
            results = DDGS().text(query, max_results=3)
            if not results:
                return "No results found."
                
            formatted = []
            for r in results:
                title = r.get('title', 'No Title')
                body = r.get('body', '')
                href = r.get('href', '')
                formatted.append(f"### [{title}]({href})\n{body}")
                
            return "\\n\\n".join(formatted)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"Search Error: {e}"

    async def _handle_request_feature(self, args: dict, message: discord.Message) -> str:
        feature = args.get("feature_request")
        context = args.get("context")
        if not feature or not context:
            return "Error: Missing arguments (feature_request, context)."
        
        if hasattr(self.bot, 'healer'):
            asyncio.create_task(self.bot.healer.propose_feature(feature, context, message.author))
            return f"✅ Feature Request '{feature}' has been sent to the Developer Channel for analysis."
        else:
            return "Error: Healer system is not active."

    async def _handle_music(self, tool_name: str, args: dict, message: discord.Message) -> str:
        media_cog = self.bot.get_cog("MediaCog")
        if not media_cog:
            return "Media system not available."
            
        ctx = await self.bot.get_context(message)

        if tool_name == "music_play":
            query = args.get("query")
            if not query: return "Error: Missing query."
            await media_cog.play_from_ai(ctx, query)
            return f"Music request sent: {query} [SILENT_COMPLETION]"

        elif tool_name == "music_control":
            action = args.get("action")
            await media_cog.control_from_ai(ctx, action)
            return f"Music control sent: {action} [SILENT_COMPLETION]"

        elif tool_name == "music_tune":
            speed = float(args.get("speed", 1.0))
            pitch = float(args.get("pitch", 1.0))
            if hasattr(self.bot, "voice_manager"):
                self.bot.voice_manager.set_speed_pitch(message.guild.id, speed, pitch)
                return f"Tune set: Speed={speed}, Pitch={pitch} [SILENT_COMPLETION]"
            return "Voice system not available."
            
        elif tool_name == "music_seek":
             if not message.guild: return "Command must be used in a guild."
             try:
                 seconds = float(args.get("seconds", 0))
                 if hasattr(media_cog, "_voice_manager"):
                     media_cog._voice_manager.seek_music(message.guild.id, seconds)
                     return f"Seeked to {seconds} seconds."
             except ValueError:
                 return "Invalid seconds format."
        
        return "Unknown music tool."
