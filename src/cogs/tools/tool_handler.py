import asyncio
import io
import logging
from typing import Optional

import aiohttp
import discord

from src.skills.admin_skill import AdminSkill
from src.skills.chat_skill import ChatSkill
from src.skills.music_skill import MusicSkill

# Modular Skills
from src.skills.system_skill import SystemSkill
from src.skills.web_skill import WebSkill

logger = logging.getLogger(__name__)

class ToolHandler:
    def __init__(self, bot, cog):
        self.bot = bot
        self.cog = cog
        
        # Initialize Skills
        self.system_skill = SystemSkill(bot)
        self.admin_skill = AdminSkill(bot)
        self.music_skill = MusicSkill(bot)
        self.web_skill = WebSkill(bot)
        self.chat_skill = ChatSkill(bot)

    async def handle_dispatch(self, tool_name: str, args: dict, message: discord.Message, status_manager=None) -> None:
        """Entry point from SSE dispatch event."""
        result = await self.execute(tool_name, args, message, status_manager)
        
        if result and "[SILENT_COMPLETION]" not in result:
             logger.info(f"Tool {tool_name} completed with visible result.")
        elif result:
             logger.info(f"Tool {tool_name} completed silently.")

    async def execute(self, tool_name: str, args: dict, message: discord.Message, status_manager=None) -> Optional[str]:
        """Executes a tool by delegating to the appropriate Skill or handling locally."""
        
        # --- Modular Skills Delegation ---
        
        # System Skill (Logs, System Control)
        if tool_name in {"get_logs", "system_control"}:
            if await self._check_permission(message.author.id, "creator"):
                return await self.system_skill.execute(tool_name, args, message)
            return "PERMISSION_DENIED"

        # Admin Skill (Roles, Channels, Cleanup, Say, User Voice)
        elif tool_name in {"manage_user_role", "create_channel", "cleanup_messages", "say", "manage_user_voice", "get_role_list"}:
             if not await self._check_permission(message.author.id, "sub_admin"):
                 return "PERMISSION_DENIED"
             return await self.admin_skill.execute(tool_name, args, message)

        # Music Skill (Media, Voice, TTS)
        elif tool_name in {"music_play", "music_control", "music_tune", "music_seek", "music_queue", "tts_speak", "join_voice_channel", "leave_voice_channel"}:
            return await self.music_skill.execute(tool_name, args, message)

        # --- Web / Chat Skills ---
        elif tool_name in {"web_search", "google_search", "search"}:
             return await self._handle_google_search(args, status_manager)
            
        elif tool_name == "read_web_page":
             return await self._handle_read_page(args, status_manager)
             
        elif tool_name in {"read_chat_history", "check_previous_context"}:
             return await self._handle_read_history(args, message)

        # --- Legacy / Unmigrated Tools (Keep Local) ---
        
        if tool_name == "google_search":
            return await self._handle_google_search(args, status_manager)

        elif tool_name == "request_feature":
            return await self._handle_request_feature(args, message)

        elif tool_name == "imagine":
            return await self._handle_imagine(args, message, status_manager)
        elif tool_name == "layer":
            return await self._handle_layer(args, message, status_manager)

        elif tool_name == "summarize":
            return await self._handle_summarize(args, message)

        return None

    # --- Permission Helper ---
    async def _check_permission(self, user_id: int, level: str = "owner") -> bool:
        """Delegate to ORACog's permission check."""
        if hasattr(self.cog, "_check_permission"):
            return await self.cog._check_permission(user_id, level)
        return user_id == self.bot.config.admin_user_id

    # --- Local Handlers (To be migrated later) ---

    async def _handle_google_search(self, args: dict, status_manager) -> str:
        try:
            query = args.get("query")
            if not query:
                return "Error: No query."
            if status_manager:
                await status_manager.next_step(f"Web Search: {query}")
            return await self.web_skill.search(query)
        except Exception as e:
            return f"Search Error: {e}"

    async def _handle_read_page(self, args: dict, status_manager) -> str:
        try:
            url = args.get("url")
            if not url:
                return "Error: No URL provided."
            if status_manager:
                await status_manager.next_step(f"Reading URL: {url}")
            return await self.web_skill.read_page(url)
        except Exception as e:
            return f"Read Page Failed: {e}"

    async def _handle_read_history(self, args: dict, message: discord.Message) -> str:
        try:
            channel_id = args.get("channel_id")
            # Default to current channel
            if not channel_id and message.channel:
                channel_id = message.channel.id
            
            if not channel_id:
                return "Error: Could not determine channel ID."

            limit = args.get("limit", 20) 
            return await self.chat_skill.read_recent_messages(int(channel_id), limit=int(limit))
        except Exception as e:
            return f"Read History Failed: {e}"

    async def _handle_request_feature(self, args: dict, message: discord.Message) -> str:
        feature = args.get("feature_request")
        context = args.get("context")
        if not feature:
            return "Error: Missing feature argument."
        if hasattr(self.bot, "healer"):
            asyncio.create_task(self.bot.healer.propose_feature(feature, context, message.author))
            return f"✅ Feature Request '{feature}' sent."
        return "Healer offline."

    async def _handle_imagine(self, args: dict, message: discord.Message, status_manager) -> str:
        prompt = args.get("prompt")
        if not prompt:
            return "Error: Missing prompt."
        if status_manager:
            await status_manager.next_step(f"Generating Image: {prompt[:30]}...")
        creative_cog = self.bot.get_cog("CreativeCog")
        if not creative_cog:
            return "Creative system offline."
        try:
            mp4_data = await self.bot.loop.run_in_executor(None, lambda: creative_cog.comfy_client.generate_video(prompt, ""))
            if mp4_data:
                f = discord.File(io.BytesIO(mp4_data), filename="ora_imagine.mp4")
                await message.reply(content=f"🎨 **Generated Visual**: {prompt}", file=f)
                return "Image generated. [SILENT_COMPLETION]"
            return "Generation failed."
        except Exception as e:
            return f"Error: {e}"

    async def _handle_layer(self, args: dict, message: discord.Message, status_manager) -> str:
        target_img = message.attachments[0] if message.attachments else None
        if not target_img and message.reference:
            ref = await message.channel.fetch_message(message.reference.message_id)
            if ref.attachments:
                target_img = ref.attachments[0]
        if not target_img:
            return "Error: No image found."
        
        if status_manager:
            await status_manager.next_step("Separating Layers...")
        creative_cog = self.bot.get_cog("CreativeCog")
        if not creative_cog:
            return "Creative system offline."

        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field("file", await target_img.read(), filename=target_img.filename)
                async with session.post(creative_cog.layer_api, data=data) as resp:
                    if resp.status == 200:
                        f = discord.File(io.BytesIO(await resp.read()), filename=f"layers_{target_img.filename}.zip")
                        await message.reply("✅ Layers Separated!", file=f)
                        return "Layering complete. [SILENT_COMPLETION]"
                    return f"Failed: {resp.status}"
        except Exception as e:
            return f"Error: {e}"

    async def _handle_summarize(self, args: dict, message: discord.Message) -> str:
        memory_cog = self.bot.get_cog("MemoryCog")
        if not memory_cog:
            return "Memory offline."
        summary = await memory_cog.get_user_summary(message.author.id)
        if summary:
            await message.reply(f"📌 **Context Summary:**\n{summary}")
            return "Summary sent. [SILENT_COMPLETION]"
        return "No summary available."
