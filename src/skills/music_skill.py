import asyncio
from typing import Optional

import discord


class MusicSkill:
    def __init__(self, bot):
        self.bot = bot

    async def execute(self, tool_name: str, args: dict, message: discord.Message) -> Optional[str]:
        if tool_name == "music_play":
            return await self._play(args, message)
        elif tool_name == "music_control":
            return await self._control(args, message)
        elif tool_name == "music_tune":
            return await self._tune(args, message)
        elif tool_name == "music_seek":
            return await self._seek(args, message)
        elif tool_name == "music_queue":
            return await self._queue(message)
        elif tool_name == "tts_speak" or tool_name == "speak":
             return await self._tts_speak(args, message)
        elif tool_name in {"join_voice_channel", "leave_voice_channel", "join_voice", "leave_voice"}:
             return await self._voice_connection(tool_name, message)
        return None

    async def _play(self, args: dict, message: discord.Message) -> str:
        media_cog = self.bot.get_cog("MediaCog")
        if not media_cog: return "Media system unavailable."
        ctx = await self.bot.get_context(message)
        query = args.get("query")
        if query:
            await media_cog.play_from_ai(ctx, str(query))
            return f"Music request sent: {query} [SILENT_COMPLETION]"

        # Attachment fallback: if user attached an audio file, play it.
        att = None
        for a in (getattr(message, "attachments", []) or []):
            fn = (getattr(a, "filename", "") or "").lower()
            ct = (getattr(a, "content_type", "") or "").lower()
            if fn.endswith((".mp3", ".wav", ".ogg", ".m4a")) or ct.startswith("audio/"):
                att = a
                break
        if att:
            if hasattr(media_cog, "play_attachment_from_ai"):
                await media_cog.play_attachment_from_ai(ctx, att)
                return "Music attachment request sent. [SILENT_COMPLETION]"
            return "Media system missing attachment playback helper."

        return "Error: Missing query (and no audio attachment found)."

    async def _control(self, args: dict, message: discord.Message) -> str:
        media_cog = self.bot.get_cog("MediaCog")
        if not media_cog: return "Media system unavailable."
        ctx = await self.bot.get_context(message)
        action = args.get("action")
        await media_cog.control_from_ai(ctx, action)
        return f"Music control sent: {action} [SILENT_COMPLETION]"

    async def _tune(self, args: dict, message: discord.Message) -> str:
        speed = float(args.get("speed", 1.0))
        pitch = float(args.get("pitch", 1.0))
        if hasattr(self.bot, "voice_manager"):
            self.bot.voice_manager.set_speed_pitch(message.guild.id, speed, pitch)
            return f"Tune set: Speed={speed}, Pitch={pitch} [SILENT_COMPLETION]"
        return "Voice system unavailable."

    async def _seek(self, args: dict, message: discord.Message) -> str:
        if not message.guild: return "Guild only."
        try:
            seconds = float(args.get("seconds", 0))
            if hasattr(self.bot, "voice_manager"):
                self.bot.voice_manager.seek_music(message.guild.id, seconds)
                return f"Seeked to {seconds} seconds."
        except ValueError: return "Invalid seconds."
        return "Voice manager unavailable."

    async def _queue(self, message: discord.Message) -> str:
        if hasattr(self.bot, "voice_manager"):
             state = self.bot.voice_manager.get_queue_info(message.guild.id)
             if not state["queue"] and not state["current"]: return "Queue is empty."
             track_list = ""
             for i, t in enumerate(state["queue"], 1): track_list += f"{i}. {t}\n"
             return f"**Now Playing**: {state['current']}\n**Queue**:\n{track_list}"[:1900]
        return "Voice manager unavailable."

    async def _tts_speak(self, args: dict, message: discord.Message) -> str:
        text = args.get("text")
        if not text: return "No text."
        if hasattr(self.bot, "voice_manager"):
            await self.bot.voice_manager.play_tts(message.author, text)
            return f"Speaking: {text[:30]}... [SILENT_COMPLETION]"
        return "Voice system unavailable."

    async def _voice_connection(self, tool_name: str, message: discord.Message) -> str:
        if not hasattr(self.bot, "voice_manager"): return "Voice system offline."
        
        if tool_name in ["join_voice_channel", "join_voice"]:
            try:
                await self.bot.voice_manager.ensure_voice_client(message.author)
                self.bot.voice_manager.set_auto_read(message.guild.id, message.channel.id)
                await self.bot.voice_manager.play_tts(message.author, "接続しました")
                await message.add_reaction("⭕")
                return "Joined voice channel. [SILENT_COMPLETION]"
            except Exception as e: return f"Failed to join: {e}"
            
        elif tool_name in ["leave_voice_channel", "leave_voice"]:
            if message.guild.voice_client:
                await self.bot.voice_manager.play_tts(message.author, "ばいばい！")
                await asyncio.sleep(1.5)
                await message.guild.voice_client.disconnect(force=True)
                await message.add_reaction("👋")
                return "Left voice channel. [SILENT_COMPLETION]"
            return "Not connected."
        return "Unknown voice tool."
