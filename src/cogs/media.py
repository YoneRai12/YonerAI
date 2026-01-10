"""Media and search related slash commands for the ORA bot.

This cog provides commands for text-to-speech (TTS) using VOICEVOX,
external web search with progress announcements, simple image OCR and
classification, and per-user preferences for search progress narration.

The voice manager is responsible for joining the user's voice channel
and playing back generated audio. Search results are returned via
SerpApi or another configured engine. OCR relies on pytesseract and
requires Tesseract to be installed on the host system.

"""

from __future__ import annotations

import logging
import logging
from typing import Optional
import asyncio

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..storage import Store
from ..utils.voice_manager import VoiceManager, HotwordCallback, VoiceConnectionError
# Import helper utilities for YouTube playback and flag translation
from ..utils.youtube import get_youtube_audio_stream_url, download_youtube_audio
from ..utils.flag_utils import flag_to_iso, iso_to_flag, country_to_flag, get_country_name
from ..utils.search_client import SearchClient
from ..utils.llm_client import LLMClient
from ..utils import image_tools
from src.views.music_dashboard import MusicPlayerView, create_music_embed

logger = logging.getLogger(__name__)


class MediaCog(commands.Cog):
    """Commands for speaking, searching, and processing media."""

    def __init__(
        self,
        bot: commands.Bot,
        store: Store,
        voice_manager: VoiceManager,
        search_client: SearchClient,
        llm_client: LLMClient,
        speak_search_default: int,
    ) -> None:
        self.bot = bot
        self._store = store
        self._voice_manager = voice_manager
        self._search_client = search_client
        self._llm_client = llm_client
        self._speak_search_default = speak_search_default
        # Register hotword callback for "ORALLM" voice trigger
        self._voice_manager.set_hotword_callback(self._on_hotword)
        
        # Verify commands
        cmds = [c.name for c in self.get_app_commands()]
        logger.info(f"MediaCog Loaded Commands: {cmds}")

        # Mapping of guild_id -> text_channel_id where auto-read is enabled
        # We now delegate this to VoiceManager to support Hot Reloading.
        # self._voice_manager.auto_read_channels is used directly.
        
        # VC Points Tracking (User ID -> Start Timestamp)
        self.vc_start_times: dict[int, float] = {}
        
        # Dashboard Message Cache (Guild ID -> Message)
        self.dashboard_messages: dict[int, discord.Message] = {}

        # Check for Voice Dependencies
        self.check_voice_dependencies()
        
    def cog_load(self):
        """Start background tasks."""
        self.music_dashboard_loop.start()
        
    def cog_unload(self):
        """Stop background tasks."""
        self.music_dashboard_loop.cancel()

    def check_voice_dependencies(self):
        """Check if Opus and PyNaCl are available."""
        try:
            import nacl
            logger.info(f"PyNaCl 検出: {nacl.__version__}")
        except ImportError:
            logger.critical("PyNaCl が見つかりません。ボイス機能は使用できません。")

        if not discord.opus.is_loaded():
            import os
            try:
                # Try common Windows filenames with ABSOLUTE paths (Critical for Python 3.8+)
                # 1. assets/libs/ (New Standard)
                dll_path = os.path.abspath(os.path.join('assets', 'libs', 'libopus-0.dll'))
                
                if not os.path.exists(dll_path):
                    # 2. Root fallback (Legacy)
                    dll_path = os.path.abspath('libopus-0.dll')

                if not os.path.exists(dll_path):
                     # 3. x64 fallback
                    dll_path = os.path.abspath('libopus-0.x64.dll')

                if not os.path.exists(dll_path):
                    logger.critical("'libopus-0.dll' が assets/libs/ またはルートディレクトリに見つかりません。")
                    return
                
                discord.opus.load_opus(dll_path)
                logger.info(f"Opus ライブラリをロードしました: {dll_path}")
            except Exception as e:
                logger.critical(f"Opus ライブラリが見つかりません。ボイス機能がタイムアウトする可能性があります。 error={e}")
                logger.critical("'libopus-0.dll' (64-bit) をBotのルートディレクトリに配置してください。")


    async def _ephemeral_for(self, user: discord.abc.User, override: Optional[bool] = None) -> bool:
        """Return whether responses should be sent ephemerally for a user.

        If ``override`` is given, return it. Otherwise, return True for
        users with privacy set to ``private``.
        """
        if override is not None:
            return override
        privacy = await self._store.get_privacy(user.id)
        return privacy == "private"

    # ----- TTS command -----
    @app_commands.command(name="speak", description="テキストをVCで読み上げます。")
    @app_commands.describe(text="読み上げるメッセージ", ephem="エフェメラルに返信するかどうか")
    async def speak(self, interaction: discord.Interaction, text: str, ephem: Optional[bool] = None) -> None:
        """Read text aloud in the user's current voice channel and send it as a chat message.

        If the user is not in a voice channel, the message will be sent without audio.
        The ``ephem`` flag overrides the user's privacy setting for this command.
        """
        # Ensure the user exists in the DB with default preferences
        await self._store.ensure_user(
            interaction.user.id,
            privacy_default="private",
            speak_search_progress_default=self._speak_search_default,
        )
        # Determine whether the reply is private
        send_ephemeral = await self._ephemeral_for(interaction.user, ephem)
        # Defer response to allow time for TTS generation
        await interaction.response.defer(ephemeral=send_ephemeral, thinking=True)
        # Attempt to play the TTS in the user's voice channel
        played = await self._voice_manager.play_tts(interaction.user, text)
        # Enable auto-read for this guild + channel
        if interaction.guild:
             self._voice_manager.auto_read_channels[interaction.guild.id] = interaction.channel_id
        if played:
            await interaction.followup.send(text, ephemeral=send_ephemeral)
        else:
            await interaction.followup.send(
                f"読み上げ対象のボイスチャンネルが見つからないため、テキストのみ送信します\n{text}",
                ephemeral=send_ephemeral,
            )
    
    async def speak_text(self, user: discord.Member | discord.User, text: str) -> bool:
        """Helper method to speak text programmatically (not a command).
        
        Returns True if TTS was played, False otherwise.
        """
        return await self._voice_manager.play_tts(user, text)

    # ----- Search commands -----
    search_group = app_commands.Group(name="search", description="Web検索コマンド")

    @search_group.command(name="query", description="Web検索を実行します。")
    @app_commands.describe(query="検索するキーワード", ephem="エフェメラルに返信するかどうか")
    async def search_query(
        self,
        interaction: discord.Interaction,
        query: str,
        ephem: Optional[bool] = None,
    ) -> None:
        """Perform a web search and return the top results.

        Progress messages are spoken if the user has enabled search progress narration.
        """
        # Ensure the user record and load preferences
        await self._store.ensure_user(
            interaction.user.id,
            privacy_default="private",
            speak_search_progress_default=self._speak_search_default,
        )
        # Determine whether to send messages ephemerally
        send_ephemeral = await self._ephemeral_for(interaction.user, ephem)
        # Read the user's setting for search progress narration
        speak_prog = await self._store.get_speak_search_progress(interaction.user.id)
        # Defer initial response
        await interaction.response.defer(ephemeral=send_ephemeral, thinking=True)
        # Announce start of search if enabled
        if speak_prog:
            await self._voice_manager.play_tts(interaction.user, "Web検索を開始します")
        # Perform the search
        try:
            results = await self._search_client.search(query)
        except Exception as exc:
            logger.exception("検索に失敗しました", exc_info=exc)
            await interaction.followup.send("検索に失敗しました。設定とAPIキーを確認してください。", ephemeral=send_ephemeral)
            return
        # Announce end of search if enabled
        if speak_prog:
            await self._voice_manager.play_tts(interaction.user, "検索が完了しました")
        # Format results into a message
        if not results:
            msg = f"検索結果が見つかりませんでした: {query}"
        else:
            lines = [f"**{i+1}. {title}**\n{url}" for i, (title, url) in enumerate(results)]
            msg = "\n".join(lines)
        await interaction.followup.send(msg, ephemeral=send_ephemeral)

    @search_group.command(name="notify", description="検索進捗の読み上げ設定を切り替えます。")
    @app_commands.describe(mode="on で読み上げ、off で無効化")
    @app_commands.choices(mode=[
        app_commands.Choice(name="on", value="on"),
        app_commands.Choice(name="off", value="off"),
    ])
    async def search_notify(
        self,
        interaction: discord.Interaction,
        mode: app_commands.Choice[str],
    ) -> None:
        """Enable or disable search progress narration for the invoking user."""
        await self._store.ensure_user(
            interaction.user.id,
            privacy_default="private",
            speak_search_progress_default=self._speak_search_default,
        )
        val = 1 if mode.value == "on" else 0
        await self._store.set_speak_search_progress(interaction.user.id, val)
        status = "オン" if val else "オフ"
        await interaction.response.send_message(f"検索進捗の読み上げ設定を {status} にしました。", ephemeral=True)

    # ----- Image commands -----
    image_group = app_commands.Group(name="image", description="画像処理コマンド")

    @image_group.command(name="ocr", description="画像から文字を抽出します。")
    @app_commands.describe(file="OCR を行う画像", ephem="エフェメラルに返信するかどうか")
    async def image_ocr(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        ephem: Optional[bool] = None,
    ) -> None:
        """Perform OCR on an attached image and respond with the extracted text."""
        await self._store.ensure_user(
            interaction.user.id,
            privacy_default="private",
            speak_search_progress_default=self._speak_search_default,
        )
        send_ephemeral = await self._ephemeral_for(interaction.user, ephem)
        await interaction.response.defer(ephemeral=send_ephemeral, thinking=True)
        try:
            data = await file.read()
            text = image_tools.ocr_image(data)
        except Exception as exc:
            logger.exception("OCR処理に失敗しました", exc_info=exc)
            await interaction.followup.send(str(exc), ephemeral=send_ephemeral)
            return
        # Speak result if the user has enabled narration
        speak_prog = await self._store.get_speak_search_progress(interaction.user.id)
        if speak_prog:
            await self._voice_manager.play_tts(interaction.user, text)
        await interaction.followup.send(text, ephemeral=send_ephemeral)

    @image_group.command(name="classify", description="画像を簡易分類します。")
    @app_commands.describe(file="分類する画像", ephem="エフェメラルに返信するかどうか")
    async def image_classify(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        ephem: Optional[bool] = None,
    ) -> None:
        """Classify an image by basic colour and shape features."""
        await self._store.ensure_user(
            interaction.user.id,
            privacy_default="private",
            speak_search_progress_default=self._speak_search_default,
        )
        send_ephemeral = await self._ephemeral_for(interaction.user, ephem)
        await interaction.response.defer(ephemeral=send_ephemeral, thinking=True)
        try:
            data = await file.read()
            classification = image_tools.classify_image(data)
        except Exception as exc:
            logger.exception("画像分類に失敗しました", exc_info=exc)
            await interaction.followup.send(str(exc), ephemeral=send_ephemeral)
            return
        speak_prog = await self._store.get_speak_search_progress(interaction.user.id)
        if speak_prog:
            await self._voice_manager.play_tts(interaction.user, classification)
        await interaction.followup.send(classification, ephemeral=send_ephemeral)

    # ----- Hotword callback -----
    async def _on_hotword(self, member: discord.Member, command: str) -> None:
        """Handle hotword detection from voice manager.

        When a user says "ORALLM ...", this callback will be invoked.
        We attempt to treat the remainder of the utterance as a search query.
        """
        # Trim whitespace and ignore empty commands
        query = command.strip()
        if not query:
            return
        logger.info("ホットワード検出 (%s): %s", member, query)
        # Use the search client directly; do not send via Slash Command context
        if not self._search_client.enabled:
            await self._voice_manager.play_tts(member, "検索機能が利用できません")
            return
        try:
            results = await self._search_client.search(query)
        except Exception:
            logger.exception("ホットワード検索エラー")
            await self._voice_manager.play_tts(member, "検索中にエラーが発生しました")
            return
        if not results:
            await self._voice_manager.play_tts(member, "検索結果が見つかりませんでした")
            return
        # Compose a brief message and speak it
        top_title, top_url = results[0]
        summary = f"検索結果: {top_title}"
        await self._voice_manager.play_tts(member, summary)
        # Send details via DM to the member for privacy
        try:
            lines = [f"{i+1}. {title}\n{url}" for i, (title, url) in enumerate(results)]
            msg = "\n".join(lines)
            await member.send(msg)
        except Exception:
            logger.exception("Failed to DM search results to user %s", member)

    # ------------------------------------------------------------------
    # YouTube playback
    # ------------------------------------------------------------------
    @app_commands.command(name="play", description="音楽を再生します (YouTube URLまたは検索ワード)")
    @app_commands.describe(
        query="YouTube の URL または検索キーワード",
        mode="stream で直接ストリーム再生、download で音声を一時ファイルに保存して再生します (任意)",
        ephem="エフェメラルに返信するかどうか",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="stream", value="stream"),
            app_commands.Choice(name="download", value="download"),
        ]
    )
    async def play(
        self,
        interaction: discord.Interaction,
        query: str,
        mode: Optional[app_commands.Choice[str]] = None,
        ephem: Optional[bool] = None,
    ) -> None:
        """Play audio from a YouTube video or search term.

        This command will attempt to retrieve an audio-only stream for the
        provided URL or search query. When ``mode`` is ``stream`` or omitted,
        the bot streams the audio directly from YouTube. When ``mode`` is
        ``download``, the audio will be downloaded to a temporary file before
        playback, which can improve stability at the cost of a slight delay.
        The command responds with the title of the video and whether playback
        succeeded. If the user is not in a voice channel, only a chat
        message will be sent.
        """
        # Ensure user record for privacy default
        await self._store.ensure_user(
            interaction.user.id,
            privacy_default="private",
            speak_search_progress_default=self._speak_search_default,
        )
        send_ephemeral = await self._ephemeral_for(interaction.user, ephem)
        await interaction.response.defer(ephemeral=send_ephemeral, thinking=True)
        # Determine playback mode
        play_mode = mode.value if mode else "stream"
        stream_url = None
        file_path = None
        title: Optional[str] = None
        # Attempt to fetch audio
        if play_mode == "download":
            file_path, title, _duration = await download_youtube_audio(query)
        else:
            stream_url, title, _duration = await get_youtube_audio_stream_url(query)
        if not title:
            await interaction.followup.send(
                "動画の取得に失敗しました。URL またはキーワードを確認してください。",
                ephemeral=send_ephemeral,
            )
            return
        # Play audio
        played = False
        if file_path:
            played = await self._voice_manager.play_music(interaction.user, file_path, title, is_stream=False)
        elif stream_url:
            played = await self._voice_manager.play_music(interaction.user, stream_url, title, is_stream=True)
            
        # Build response message
        if played:
            state = self._voice_manager.get_music_state(interaction.guild.id)
            
            # --- MUSIC DASHBOARD INTEGRATION ---
            from ..views.music_dashboard import MusicPlayerView, create_music_embed
            
            # Create View
            view = MusicPlayerView(self, interaction.guild.id)
            
            # Create Initial Embed
            # We need track_info. VoiceManager sets this in `current`.
            # We'll fetch the fresh state.
            # state is GuildMusicState object
            
            track_info = {"title": title, "url": query if "http" in query else ""}
            queue_preview = [{"title": t[1]} for t in state.queue] # Convert tuples to dicts
            
            dashboard_embed = create_music_embed(
                track_info=track_info,
                status="Playing" if not state.queue else "Queued", 
                play_time_sec=0,
                total_duration_sec=0, # Unknown initially
                queue_preview=queue_preview,
                speed=state.speed,
                pitch=state.pitch
            )
            
            await interaction.followup.send(embed=dashboard_embed, view=view, ephemeral=send_ephemeral)
            
            # Store message for updates
            msg = await interaction.original_response()
            if not hasattr(self, "dashboard_messages"):
                self.dashboard_messages = {}
            self.dashboard_messages[interaction.guild.id] = msg
            
            # -----------------------------------
        else:
            msg = f"{title} を再生できませんでした。ボイスチャンネルに参加しているか確認してください。"
            await interaction.followup.send(msg, ephemeral=send_ephemeral)

    async def update_music_dashboard(self, guild_id: int):
        """Refreshes the music dashboard message for a guild."""
        if not hasattr(self, "dashboard_messages"): return
        msg = self.dashboard_messages.get(guild_id)
        if not msg: return
        
        try:
            from ..views.music_dashboard import MusicPlayerView, create_music_embed
            
            state = self._voice_manager.get_queue_info(guild_id)
            
            # If nothing playing and queue empty, maybe remove dashboard?
            # Or just show "Stopped"
            
            # Calculate progress
            import time
            current_start = state.get("current_start_time", 0)
            play_time = 0
            if current_start > 0:
                play_time = time.time() - current_start
            
            embed = create_music_embed(
                track_info={"title": state["current"] or "None"},
                status="Playing" if state["current"] else "Stopped",
                play_time_sec=play_time,
                total_duration_sec=state.get("current_duration", 0), 
                queue_preview=state.get("queue", []),
                speed=state.get("speed", 1.0),
                pitch=state.get("pitch", 1.0)
            )
            
            await msg.edit(embed=embed, view=MusicPlayerView(self, guild_id))
        except Exception as e:
            # logger.error(f"Failed to update music dashboard: {e}") 
            # Log verbose only if needed
            
            # If message deleted, remove from cache
            if isinstance(e, discord.NotFound):
                del self.dashboard_messages[guild_id]

    @tasks.loop(seconds=5.0)
    async def music_dashboard_loop(self):
        """Periodically update active music dashboards to animate progress bar."""
        if not hasattr(self, "dashboard_messages"): return
        
        # Iterate copy of keys
        for guild_id in list(self.dashboard_messages.keys()):
            await self.update_music_dashboard(guild_id)

    @app_commands.command(name="queue", description="現在の再生キューを表示します。")
    async def queue(self, interaction: discord.Interaction):
        state = self._voice_manager.get_queue_info(interaction.guild.id)
        if not state["current"] and not state["queue"]:
            await interaction.response.send_message("現在再生中の曲はありません。", ephemeral=True)
            return
            
        msg = f"**現在再生中:** {state['current']}\n"
        msg += f"**ループ:** {'ON' if state['is_looping'] else 'OFF'}\n"
        msg += f"**音量:** {int(state['volume'] * 100)}%\n\n"
        
        if state["queue"]:
            msg += "**キュー:**\n"
            for i, title in enumerate(state["queue"], 1):
                msg += f"{i}. {title}\n"
        else:
            msg += "キューは空です。"
            
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="loop", description="ループ再生を切り替えます。")
    @app_commands.describe(mode="ON/OFF")
    @app_commands.choices(mode=[
        app_commands.Choice(name="ON", value="on"),
        app_commands.Choice(name="OFF", value="off"),
    ])
    async def loop(self, interaction: discord.Interaction, mode: str):
        enabled = (mode == "on")
        self._voice_manager.set_loop(interaction.guild.id, enabled)
        await interaction.response.send_message(f"ループ再生を {'ON' if enabled else 'OFF'} にしました。", ephemeral=True)

    @app_commands.command(name="skip", description="現在の曲をスキップします。")
    async def skip(self, interaction: discord.Interaction):
        self._voice_manager.skip_music(interaction.guild.id)
        await interaction.response.send_message("スキップしました。", ephemeral=True)

    @app_commands.command(name="stop", description="再生を停止し、キューをクリアします。")
    async def stop(self, interaction: discord.Interaction):
        self._voice_manager.stop_music(interaction.guild.id)
        await interaction.response.send_message("再生を停止しました。", ephemeral=True)

    @app_commands.command(name="tune", description="再生速度とピッチを変更します (0.5 - 2.0)。")
    @app_commands.describe(speed="再生速度 (例: 1.0, 1.25, 1.5)", pitch="ピッチ (例: 1.0 = 標準, 1.2 = 高い)")
    async def tune(self, interaction: discord.Interaction, speed: float = 1.0, pitch: float = 1.0):
        await interaction.response.defer(ephemeral=True)
        # Validate
        speed = max(0.5, min(2.0, speed))
        pitch = max(0.5, min(2.0, pitch))
        
        self._voice_manager.set_speed_pitch(interaction.guild.id, speed, pitch)
        await interaction.followup.send(f"🎵 再生設定を変更しました: Speed={speed}, Pitch={pitch} (再生をリセットしました)")

    @app_commands.command(name="seek", description="再生位置を変更します (例: 1:30, 90)")
    @app_commands.describe(timestamp="時間 (MM:SS または 秒数)")
    async def seek(self, interaction: discord.Interaction, timestamp: str):
        await interaction.response.defer(ephemeral=True)
        
        seconds = parse_timestamp(timestamp)
        if seconds is None:
            await interaction.followup.send("時間の形式が正しくありません (例: 1:30, 90)", ephemeral=True)
            return

        self._voice_manager.seek_music(interaction.guild.id, seconds)
        await interaction.followup.send(f"⏩ 再生位置を {timestamp} ({seconds}秒) に変更しました")

    async def play_from_ai(self, ctx: commands.Context, query: str) -> None:
        """Helper for AI to play music directly via Context."""
        # Ensure Voice
        if not ctx.author.voice:
             await ctx.send("❌ ボイスチャンネルに参加してからリクエストしてください。")
             return

        # 1. Resolve URL
        stream_url, title, _duration = await get_youtube_audio_stream_url(query)
        if not title:
            await ctx.send(f"❌ '{query}' の再生に失敗しました。")
            return

        # 2. Play (Await once!)
        played = await self._voice_manager.play_music(ctx.author, stream_url, title, is_stream=True)
        
    async def play_from_ai(self, ctx: commands.Context, query: str) -> None:
        """Helper for AI to play music directly via Context."""
        # Ensure Voice
        if not ctx.author.voice:
             await ctx.send("❌ ボイスチャンネルに参加してからリクエストしてください。")
             return

        # 1. Resolve URL
        stream_url, title, _duration = await get_youtube_audio_stream_url(query)
        if not title:
            await ctx.send(f"❌ '{query}' の再生に失敗しました。")
            return

        # 2. Play (Await once!)
        played = await self._voice_manager.play_music(ctx.author, stream_url, title, is_stream=True)
        
        if played:
             # --- MUSIC DASHBOARD INTEGRATION ---
             if ctx.guild:
                 guild_id = ctx.guild.id
                 # Check if dashboard exists
                 if hasattr(self, "dashboard_messages") and self.dashboard_messages.get(guild_id):
                     # Just update
                     try:
                         await self.update_music_dashboard(guild_id)
                     except:
                         # If update fails (e.g. deleted), recreate
                         pass
                 
                 # Create New Dashboard if needed (or if update failed/didn't exist)
                 # Re-check existence to be sure
                 if not hasattr(self, "dashboard_messages") or not self.dashboard_messages.get(guild_id):
                     try:
                         from ..views.music_dashboard import MusicPlayerView, create_music_embed
                         state = self._voice_manager.get_music_state(guild_id)
                         
                         track_info = {"title": title, "url": query if "http" in query else ""}
                         queue_preview = [{"title": t[1]} for t in state.queue]
                         
                         dashboard_embed = create_music_embed(
                             track_info=track_info,
                             status="Playing" if not state.queue else "Queued",
                             play_time_sec=0,
                             total_duration_sec=0,
                             queue_preview=queue_preview,
                             speed=state.speed,
                             pitch=state.pitch
                         )
                         
                         view = MusicPlayerView(self, guild_id)
                         msg = await ctx.send(embed=dashboard_embed, view=view)
                         
                         if not hasattr(self, "dashboard_messages"):
                             self.dashboard_messages = {}
                         self.dashboard_messages[guild_id] = msg
                     except Exception as e:
                         logger.error(f"Failed to create dashboard in play_from_ai: {e}")
                         # Fallback to text if dashboard fails
                         await ctx.send(f"🎵 再生を開始します: **{title}**")
                 else:
                     # Dashboard already exists and updated, no text needed.
                     pass
        else:
             await ctx.send(f"❌ 再生エラー: VoiceClientへの接続に失敗しました。")

    async def control_from_ai(self, ctx: commands.Context, action: str) -> None:
        """Helper for AI to control music (stop/skip/loop)."""
        guild_id = ctx.guild.id
        if action == "stop":
            self._voice_manager.stop_music(guild_id)
            await ctx.send("⏹️ 再生を停止しました。")
        elif action == "skip":
            self._voice_manager.skip_music(guild_id)
            await ctx.send("⏭️ スキップしました。")
        elif action == "loop_on":
            self._voice_manager.set_loop(guild_id, True)
            await ctx.send("🔁 ループ再生を有効にしました。")
        elif action == "loop_off":
            self._voice_manager.set_loop(guild_id, False)
            await ctx.send("➡️ ループ再生を解除しました。")
        else:
            await ctx.send(f"⚠️ Unknown music action: {action}")
        
        if ctx.guild:
            await self.update_music_dashboard(ctx.guild.id)

def parse_timestamp(ts: str) -> Optional[float]:
    """Parse a timestamp like ``1:23`` or ``90`` and return seconds."""
    ts = ts.strip()
    try:
        if ":" in ts:
            parts = ts.split(":")
            if len(parts) == 2:
                m, s = map(int, parts)
                return m * 60 + s
            elif len(parts) == 3:
                h, m, s = map(int, parts)
                return h * 3600 + m * 60 + s
        else:
            return float(ts)
    except ValueError:
        return None
    return None

    # ------------------------------------------------------------------
    # Country flag translation
    # ------------------------------------------------------------------
    @app_commands.command(name="flag", description="国旗や国名を翻訳します。旗を国名に変換するか、その逆を行います。")
    @app_commands.describe(
        text="国旗の絵文字、国名、または ISO コードを入力します",
        ephem="エフェメラルに返信するかどうか",
    )
    async def flag(
        self,
        interaction: discord.Interaction,
        text: str,
        ephem: Optional[bool] = None,
    ) -> None:
        """Translate between flag emojis and country names/ISO codes.

        If the input is a flag emoji, it returns the country name and ISO code.
        If the input is a two-letter ISO code, it returns the flag and name.
        Otherwise, it attempts to treat the input as a country name and returns
        the corresponding flag and ISO code.
        """
        await self._store.ensure_user(
            interaction.user.id,
            privacy_default="private",
            speak_search_progress_default=self._speak_search_default,
        )
        send_ephemeral = await self._ephemeral_for(interaction.user, ephem)
        await interaction.response.defer(ephemeral=send_ephemeral)
        result_lines: list[str] = []
        txt = text.strip()
        # Determine type of input
        iso = None
        flag_emoji = None
        name = None
        if len(txt) == 2 and all(ord(c) > 0x1F1E5 for c in txt):  # flag emoji
            iso = flag_to_iso(txt)
            if iso:
                name = get_country_name(iso)
        elif len(txt) == 2 and txt.isalpha():  # ISO code
            iso = txt.upper()
            flag_emoji = iso_to_flag(iso)
            name = get_country_name(iso)
        else:
            # treat as country name
            flag_emoji = country_to_flag(txt)
            if flag_emoji:
                iso = flag_to_iso(flag_emoji)
                name = get_country_name(iso) if iso else None
        if not (iso or flag_emoji or name):
            await interaction.followup.send(
                "国旗や国名を認識できませんでした。別の表現を試してください。",
                ephemeral=send_ephemeral,
            )
            return
        if flag_emoji:
            result_lines.append(f"国旗: {flag_emoji}")
        if name:
            result_lines.append(f"国名: {name}")
        if iso:
            result_lines.append(f"ISO コード: {iso}")
        msg = "\n".join(result_lines)
        await interaction.followup.send(msg, ephemeral=send_ephemeral)

    # ------------------------------------------------------------------
    # Auto-read join/leave commands
    # ------------------------------------------------------------------
    @app_commands.command(name="vc", description="現在のテキストチャンネルのメッセージを VC で自動読み上げします。")
    @app_commands.describe(ephem="エフェメラルに返信するかどうか")
    async def vc(self, interaction: discord.Interaction, ephem: Optional[bool] = None) -> None:
        """Join the user's voice channel and start reading messages aloud.

        The bot will join the invoker's current voice channel and enable auto-
        reading for the current text channel. Subsequent messages sent in
        this channel will be read aloud in the voice channel until `/leavevc`
        is used.
        """
        await self._store.ensure_user(
            interaction.user.id,
            privacy_default="private",
            speak_search_progress_default=self._speak_search_default,
        )
        send_ephemeral = await self._ephemeral_for(interaction.user, ephem)
        await interaction.response.defer(ephemeral=send_ephemeral)
        # Ensure voice client exists
        try:
            from ..utils.voice_manager import VoiceConnectionError
            voice_client = await self._voice_manager.ensure_voice_client(interaction.user)
        except VoiceConnectionError as e:
            await interaction.followup.send(
                f"ボイスチャンネルへの参加に失敗しました。\n理由: {e}",
                ephemeral=send_ephemeral,
            )
            return
        # Register auto-read channel
        guild_id = interaction.guild.id if interaction.guild else None
        if guild_id is None:
            await interaction.followup.send("ギルドが取得できませんでした。", ephemeral=send_ephemeral)
            return
        self._voice_manager.auto_read_channels[guild_id] = interaction.channel.id
        await interaction.followup.send("メッセージの自動読み上げを開始しました。", ephemeral=send_ephemeral)
        
        # Announce connection via TTS
        await self._voice_manager.play_tts(interaction.user, "接続しました")

    @app_commands.command(name="leavevc", description="自動読み上げを停止し VC から退出します。")
    @app_commands.describe(ephem="エフェメラルに返信するかどうか")
    async def leavevc(self, interaction: discord.Interaction, ephem: Optional[bool] = None) -> None:
        """Stop auto-reading messages and disconnect from the voice channel."""
        await self._store.ensure_user(
            interaction.user.id,
            privacy_default="private",
            speak_search_progress_default=self._speak_search_default,
        )
        send_ephemeral = await self._ephemeral_for(interaction.user, ephem)
        await interaction.response.defer(ephemeral=send_ephemeral)
        guild_id = interaction.guild.id if interaction.guild else None
        if guild_id and guild_id in self._voice_manager.auto_read_channels:
            del self._voice_manager.auto_read_channels[guild_id]
        # Disconnect voice client if connected
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if voice_client:
            try:
                await voice_client.disconnect()
            except Exception:
                logger.exception("ボイスチャンネルからの切断に失敗しました")
        await interaction.followup.send("自動読み上げを停止しました。", ephemeral=send_ephemeral)

    # ------------------------------------------------------------------
    # Event listener for auto-read
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Read messages aloud when auto-reading is enabled for the channel.

        This listener triggers whenever a message is sent. If auto-reading
        is enabled for the guild and the message originates from the mapped
        channel, the content will be read aloud in the appropriate voice
        channel using TTS. Messages authored by bots are ignored.
        """
        # Ignore messages from bots (including ourselves)
        if message.author.bot:
            return

        # Ignore messages that are likely commands/triggers for the bot (to avoid reading "@ORA hello")
        # 1. Check for Bot Mention
        if self.bot.user in message.mentions:
            return
            
        # 2. Check for Text Triggers (@ORA, @ROA)
        content = message.content.strip()
        triggers = ["@ORA", "@ROA", "＠ORA", "＠ROA", "@ora", "@roa"]
        if any(content.startswith(t) for t in triggers):
            return
        guild = message.guild
        if guild is None:
            return
        channel_id = self._voice_manager.auto_read_channels.get(guild.id)
        
        # Logic: Read if (Mapped Channel) OR (User in same Voice Channel)
        should_read = False
        
        # 1. Check strict mapping
        if channel_id and channel_id == message.channel.id:
            should_read = True
            
        # 2. Check Co-location (Removed by User Request)
        # Users want strict separation. Only read from the channel where usage was started.
        # if not should_read and message.author.voice and message.author.voice.channel:
        #      vc = guild.voice_client
        #      if vc and vc.is_connected() and vc.channel == message.author.voice.channel:
        #          should_read = True

        if not should_read:
            return
        
        logger.info(f"読み上げ: {message.clean_content}")
        # Play the message content via TTS
        try:
            played = await self._voice_manager.play_tts(message.author, message.clean_content)
            if not played:
                # If it failed (e.g. empty text or VOICEVOX error), notify in chat
                # But only if it's not just empty text (which returns False early)
                # We can't easily distinguish here without changing return type, 
                # but for now let's just log. 
                # Actually, let's send a small reaction or message if it was a VOICEVOX error.
                # Since play_tts catches exceptions and returns False, we can assume failure.
                # However, we don't want to spam for empty messages.
                if message.content and message.content.strip():
                     await message.add_reaction("⚠️")
        except Exception:
            logger.exception("自動読み上げに失敗しました")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, 
        member: discord.Member, 
        before: discord.VoiceState, 
        after: discord.VoiceState
    ) -> None:
        """Handle VC join/leave announcements and auto-disconnect."""
        # Ignore bots (except for disconnect logic which counts bots)
        # But we don't want to announce bots joining
        
        # 1. Join/Leave Announcement Logic
        if not member.bot:
             bot_vc = member.guild.voice_client
             if bot_vc and bot_vc.is_connected():
                 # Valid bot connection
                 bot_channel = bot_vc.channel
                 
                 # User Joined Bot's Channel
                 if after.channel and after.channel.id == bot_channel.id and (not before.channel or before.channel.id != bot_channel.id):
                      await self._voice_manager.play_tts(member, f"{member.display_name}さんが参加しました")

                 # User Left Bot's Channel
                 elif before.channel and before.channel.id == bot_channel.id and (not after.channel or after.channel.id != bot_channel.id):
                      await self._voice_manager.play_tts(member, f"{member.display_name}さんが退出しました")

        # 3. VC Points Logic
        import time
        # Join Event (or Switch to new channel)
        if after.channel is not None and (before.channel is None or before.channel.id != after.channel.id):
            if not member.bot:
                 self.vc_start_times[member.id] = time.time()
        
        # Leave Event (or Switch away from channel)
        if before.channel is not None and (after.channel is None or after.channel.id != before.channel.id):
             if not member.bot and member.id in self.vc_start_times:
                 start_time = self.vc_start_times.pop(member.id)
                 duration = time.time() - start_time
                 minutes = int(duration / 60)
                 if minutes > 0:
                     await self._store.add_points(member.id, minutes)
                     logger.info(f"{member.display_name} にVC参加ボーナス {minutes} ポイントを付与しました。")

        # 2. Auto-Disconnect Logic (existing)
        # Only care about users leaving a channel
        if before.channel is None:
            return
        
        # Check if the bot is in the channel that the user left
        if member.guild.voice_client is None:
            return
        
        bot_channel = member.guild.voice_client.channel
        if before.channel.id != bot_channel.id:
            return
        
        # Count non-bot members in the channel
        non_bot_members = [m for m in bot_channel.members if not m.bot]
        
        # If only bots are left (or the channel is empty), disconnect
        if len(non_bot_members) == 0:
            logger.info(f"無人になったため {bot_channel.name} から自動切断します")
            await member.guild.voice_client.disconnect()
            # Also clear auto-read for this guild
            self._voice_manager.auto_read_channels.pop(member.guild.id, None)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Translate message when a flag reaction is added."""
        if payload.user_id == self.bot.user.id:
            return

        # Check if emoji is a flag
        emoji = str(payload.emoji)
        iso_code = flag_to_iso(emoji)
        if not iso_code:
            return

        country_name = get_country_name(iso_code)
        if not country_name:
            return

        # Fetch message
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return
        
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        except discord.Forbidden:
            return

        if not message.content:
            return

        # Translate using LLM
        logger.info(f"メッセージ {message.id} を {country_name} に翻訳中 (国旗: {emoji})")
        
        prompt = (
            f"Translate the following text to the primary language spoken in {country_name}.\n"
            f"Output ONLY the translated text. Do not add any explanations or notes.\n"
            f"\n"
            f"Text to translate:\n"
            f"{message.content}"
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            translated_text = await self._llm_client.chat(messages, temperature=0.3)
            await message.reply(f"{emoji} {translated_text}", mention_author=False)
        except Exception as e:
            logger.error(f"翻訳失敗: {e}")
            await channel.send(f"{emoji} 翻訳に失敗しました。", delete_after=5)
            await message.reply(f"{emoji} {translated_text}", mention_author=False)
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            await channel.send(f"{emoji} 翻訳に失敗しました。", delete_after=5)

    # ------------------------------------------------------------------
    # AI Control Methods (called from ORA Cog)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # AI Control Methods (called from ORA Cog)
    # ------------------------------------------------------------------
    async def play_from_ai(self, ctx: commands.Context, query: str) -> None:
        """Play music requested by AI."""
        # Ensure voice client
        if ctx.author.voice:
             await self._voice_manager.ensure_voice_client(ctx.author)
        
        # Use existing ytplay logic but simplified
        # We assume 'stream' mode for speed
        stream_url, title, _duration = await get_youtube_audio_stream_url(query)
        if not title or not stream_url:
            await ctx.send(f"動画が見つかりませんでした: {query}")
            return

        played = await self._voice_manager.play_music(ctx.author, stream_url, title, is_stream=True)
        if played:
            try:
                # Dashboard Integration
                guild_id = ctx.guild.id
                state = self._voice_manager.get_music_state(guild_id)
                
                # Create View and Embed
                # Correct Usage: No await, correct args, only Embed return
                track_info = {"title": title, "url": query if "http" in query else ""}
                queue_preview = [{"title": t[1]} for t in state.queue]
                
                embed = create_music_embed(
                    track_info=track_info,
                    status="Playing", # Assumed valid since logic falls through here
                    play_time_sec=0,
                    total_duration_sec=_duration if _duration else 0,
                    queue_preview=queue_preview,
                    speed=state.speed,
                    pitch=state.pitch
                )
                
                view = MusicPlayerView(self, guild_id)
                
                # Clean up old dashboard if exists
                if not hasattr(self, "dashboard_messages"):
                    self.dashboard_messages = {}
                    
                if guild_id in self.dashboard_messages:
                    try:
                        old_msg = self.dashboard_messages[guild_id]
                        if old_msg:
                            await old_msg.delete()
                    except:
                        pass
                
                # Send New Dashboard
                msg = await ctx.send(embed=embed, view=view)
                self.dashboard_messages[guild_id] = msg
            
            except Exception as e:
                logger.error(f"Failed to show dashboard in play_from_ai: {e}")
                await ctx.send(f"再生を開始します: {title}")

            # Start auto-disconnect monitor
            await self._start_auto_disconnect(ctx.guild.id, ctx.guild.voice_client)
        else:
            await ctx.send("再生できませんでした。")

    async def control_from_ai(self, ctx: commands.Context, action: str) -> None:
        """Control music playback requested by AI."""
        guild_id = ctx.guild.id
        if action == "skip":
            self._voice_manager.skip_music(guild_id)
            await ctx.send("スキップしました")
        elif action == "stop":
            self._voice_manager.stop_music(guild_id)
            await ctx.send("再生を停止しました")
        elif action == "loop_on":
            self._voice_manager.set_loop(guild_id, True)
            await ctx.send("ループ再生をONにしました")
        elif action == "loop_off":
            self._voice_manager.set_loop(guild_id, False)
            await ctx.send("ループ再生をOFFにしました")
        elif action == "queue_show":
            state = self._voice_manager.get_queue_info(guild_id)
            if not state["current"] and not state["queue"]:
                await ctx.send("現在再生中の曲はありません")
                return
            msg = f"**現在再生中:** {state['current']}\n"
            if state["queue"]:
                msg += "**キュー:**\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(state["queue"], 1)])
            await ctx.send(msg)
        elif action == "replay_last":
            success = self._voice_manager.replay_previous(guild_id)
            if success:
                await ctx.send("前の曲を再生します ⏮️")
            else:
                await ctx.send("履歴がありません")

    # ------------------------------------------------------------------
    # Safe Auto-Disconnect Logic
    # ------------------------------------------------------------------
    async def _start_auto_disconnect(self, guild_id: int, voice_client, *, idle_seconds: int = 300):
        task = getattr(self, "_auto_disconnect_tasks", {}).get(guild_id)
        if task and not task.done():
            task.cancel()
        self._auto_disconnect_tasks = getattr(self, "_auto_disconnect_tasks", {})
        self._auto_disconnect_tasks[guild_id] = asyncio.create_task(
            self._auto_disconnect_worker(guild_id, voice_client, idle_seconds=idle_seconds),
            name=f"auto_disconnect_{guild_id}",
        )

    async def _auto_disconnect_worker(self, guild_id: int, voice_client, *, idle_seconds: int):
        import asyncio
        try:
            idle = 0
            empty_timer = 0
            while True:
                await asyncio.sleep(1)
                vc = voice_client
                if vc is None or not vc.is_connected():
                    return

                # EMPTY CHANNEL CHECK (Backup for on_voice_state_update)
                # If only bots are present, start counting
                channel = vc.channel
                if channel:
                    non_bots = [m for m in channel.members if not m.bot]
                    if len(non_bots) == 0:
                        empty_timer += 1
                        if empty_timer >= 10: # 10 seconds grace period
                            logger.info(f"Auto-disconnecting from guild {guild_id} - Channel empty (Poller protection)")
                            await vc.disconnect()
                            self._voice_manager.auto_read_channels.pop(guild_id, None)
                            return
                    else:
                        empty_timer = 0 # Reset if someone joins
                
                playing = vc.is_playing()
                paused = vc.is_paused()
                
                # Check queue state via voice manager
                state = self._voice_manager.get_music_state(guild_id)
                queue_empty = len(state.queue) == 0
                looping = state.is_looping
                
                if playing or paused or looping or (not queue_empty):
                    idle = 0
                    continue
                
                # Check if Auto-Read (TTS) is active. If so, do not disconnect.
                if guild_id in self._voice_manager.auto_read_channels:
                    idle = 0
                    continue

                idle += 1
                if idle >= idle_seconds:
                    logger.info(f"Auto-disconnecting from guild {guild_id} due to inactivity")
                    await vc.disconnect(force=False)
                    # Clear auto-read mapping
                    self._voice_manager.auto_read_channels.pop(guild_id, None)
                    return
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("auto_disconnect_worker crashed", extra={"guild_id": guild_id})
            return

async def setup(bot: commands.Bot) -> None:
    """Load the MediaCog extension."""
    await bot.add_cog(
        MediaCog(
            bot,
            store=bot.store,
            voice_manager=bot.voice_manager,
            search_client=bot.search_client,
            llm_client=bot.llm_client,
            speak_search_default=bot.config.speak_search_progress_default,
        )
    )
