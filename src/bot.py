"""Entry point for the ORA Discord bot."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
import warnings
from typing import Optional

# [SUPPRESSION]
# Discord.py often emits "ResourceWarning: unclosed file" for FFmpeg pipes on Windows.
# This is a known benign issue with the library's cleanup of subprocess streams.
warnings.simplefilter("ignore", ResourceWarning)

import aiohttp
from dotenv import load_dotenv

# Load environment variables from .env file
# Load environment variables from .env file (Force override system vars, Explicit Path)
load_dotenv(r"C:\Users\YoneRai12\Desktop\ORADiscordBOT-main3\.env", override=True)

import discord
from discord import app_commands
from discord.ext import commands

from .cogs.core import CoreCog
from .cogs.ora import ORACog
from .config import Config, ConfigError
from .logging_conf import setup_logging
from .storage import Store
from .utils.healer import Healer
from .utils.link_client import LinkClient
from .utils.llm_client import LLMClient
from .utils.logger import GuildLogger
from .utils.search_client import SearchClient
from .utils.stt_client import WhisperClient
from .utils.tts_client import VoiceVoxClient
from .utils.voice_manager import VoiceManager

logger = logging.getLogger(__name__)


_bot_instance: Optional[ORABot] = None

def get_bot() -> Optional[ORABot]:
    return _bot_instance

class ORABot(commands.Bot):
    """Discord bot implementation for ORA."""

    def __init__(
        self,
        config: Config,
        link_client: LinkClient,
        store: Store,
        llm_client: LLMClient,
        intents: discord.Intents,
        session: aiohttp.ClientSession,
    ) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            application_id=config.app_id,
        )
        self.config = config
        self.link_client = link_client
        self.store = store
        self.llm_client = llm_client
        self.session = session
        self.healer = Healer(self, llm_client)
        self.started_at = time.time()
        self._backup_task: Optional[asyncio.Task] = None

    async def setup_hook(self) -> None:
        # 0. Initialize Google Client (Hybrid-Cloud)
        from .utils.google_client import GoogleClient
        from .utils.unified_client import UnifiedClient  # Import UnifiedClient

        if self.config.gemini_api_key:
            self.google_client = GoogleClient(self.config.gemini_api_key)
            logger.info("✅ GoogleClient (Gemini) 初期化完了")
        else:
            self.google_client = None
            logger.warning("⚠️ GoogleClient は無効です")

        # 0.5 Initialize Unified Brain (Router)
        self.unified_client = UnifiedClient(self.config, self.llm_client, self.google_client)
        logger.info("✅ UnifiedClient (Universal Brain) 初期化完了")

        # 1. Initialize Shared Resources
        # Search client using SerpApi or similar
        self.search_client = SearchClient(self.config.search_api_key, self.config.search_engine)
        
        # VOICEVOX text-to-speech
        vv_client = VoiceVoxClient(self.config.voicevox_api_url, self.config.voicevox_speaker_id)
        # Whisper speech-to-text
        stt_client = WhisperClient(model=self.config.stt_model)
        # Voice manager handles VC connections and hotword detection
        self.voice_manager = VoiceManager(self, vv_client, stt_client)

        # 2. Register Core Cogs
        await self.add_cog(CoreCog(self, self.link_client, self.store))
        
        # 3. Register ORA Cog (Main Logic)
        # Note: We keep ORACog as manual add for now, or convert it later. 
        # Using self.search_client instead of local var.
        await self.add_cog(
            ORACog(
                self,
                store=self.store,
                llm=self.llm_client,
                search_client=self.search_client,
                public_base_url=self.config.public_base_url,
                ora_api_base_url=self.config.ora_api_base_url,
                privacy_default=self.config.privacy_default,
            )
        )
        
        # 4. Register Media Cog (Loaded as Extension for Hot Reloading)
        # Depends on self.voice_manager which is now attached to bot
        await self.load_extension("src.cogs.media")
        
        # 5. Load Extensions
        extensions = [
            "src.cogs.voice_recv",
            "src.cogs.system",
            "src.cogs.resource_manager",
            "src.cogs.memory",
            "src.cogs.system_shell",
        ]
        for ext in extensions:
            try:
                await self.load_extension(ext)
            except Exception as e:
                logger.exception(f"Failed to load extension {ext}", exc_info=e)
        
        # 6. Sync Commands
        self.tree.on_error = self.on_app_command_error
        
        # Only sync if explicitly requested or in Dev environment
        # CHANGED: Default to "true" to ensure commands appear for the user
        if os.getenv("SYNC_COMMANDS", "true").lower() == "true":
            await self._sync_commands()
        else:
            logger.info("Skipping command sync (SYNC_COMMANDS != true)")

        # 7. Start Periodic Backup
        self._backup_task = self.loop.create_task(self._periodic_backup_loop())

    async def _periodic_backup_loop(self) -> None:
        """Runs backup every 6 hours."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                await asyncio.sleep(6 * 3600) # 6 hours
                logger.info("Starting periodic backup...")
                await self.store.backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic backup failed: {e}")

    async def _sync_commands(self) -> None:
        if self.config.dev_guild_id:
            try:
                guild = discord.Object(id=self.config.dev_guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(
                    "Synchronized %d commands to Dev Guild %s", len(synced), self.config.dev_guild_id
                )
            except Exception as e:
                logger.warning(f"Failed to sync to Dev Guild: {e}")

        # Always sync globally to ensure commands work in all servers
        try:
            synced = await self.tree.sync()
            logger.info("全サーバー共通コマンドを同期しました (%d個)", len(synced))
        except Exception as e:
            logger.error(f"Global sync failed: {e}")

    async def close(self) -> None:
        """Graceful shutdown."""
        logger.info("Closing bot...")
        
        # 1. Stop Periodic Backup
        if self._backup_task:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
        
        # 2. Final Backup (Shielded)
        logger.info("Performing final backup...")
        try:
            # Shield to ensure backup completes even if close is cancelled
            await asyncio.shield(self.store.backup())
        except Exception as e:
            logger.error(f"Final backup failed: {e}")

        # 3. Close Resources
        await super().close()
        # Session is managed by run_bot context manager, so we don't close it here explicitly
        # unless we want to force it. But run_bot handles it.

    async def on_ready(self) -> None:
        assert self.user is not None
        logger.info(
            "ログイン成功: %s (%s); AppID=%s; 参加サーバー数=%d",
            self.user.name,
            self.user.id,
            self.application_id,
            len(self.guilds),
        )
        # Verify Ngrok and DM owner
        self.loop.create_task(self._notify_ngrok_url())

    async def _notify_ngrok_url(self) -> None:
        """Checks for Ngrok tunnel and DMs the URL to the owner."""
        # Add dynamic admin
        target_ids = []
        if self.config.admin_user_id:
             target_ids.append(self.config.admin_user_id)
        
        # Add Startup Notification Channel
        if self.config.startup_notify_channel_id:
            target_ids.append(self.config.startup_notify_channel_id)
        ngrok_api = "http://127.0.0.1:4040/api/tunnels"
        
        # Wait a bit for Ngrok to spin up
        await asyncio.sleep(5)
        
        try:
            async with self.session.get(ngrok_api) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tunnels = data.get("tunnels", [])
                    public_url = None
                    for t in tunnels:
                        if t.get("proto") == "https":
                            public_url = t.get("public_url")
                            break
                    
                    if public_url:
                        # Add /dashboard to the ngrok URL for direct access
                        public_url = public_url.rstrip("/")
                        dashboard_url = f"{public_url}/dashboard"
                        message = f"ORA SYSTEM：コスト追跡 & 自律最適化ダッシュボード: {dashboard_url}"

                        for tid in target_ids:
                            try:
                                # Try sending to channel first, then user
                                channel = self.get_channel(tid)
                                if not channel:
                                    try:
                                        channel = await self.fetch_channel(tid)
                                    except:
                                        channel = None
                                
                                if channel:
                                    await channel.send(message)
                                    logger.info(f"Ngrok URLをチャンネルに送信: {channel.name} ({tid}) -> {dashboard_url}")
                                else:
                                    user = await self.fetch_user(tid)
                                    if user:
                                        await user.send(message)
                                        logger.info(f"Ngrok URLをユーザーに送信: {user.name} ({tid}) -> {dashboard_url}")
                            except Exception as e:
                                logger.error(f"Ngrok URLの送信に失敗しました ({tid}): {e}")
                        

                else:
                    logger.debug("Ngrok API not accessible (Status %s)", resp.status)
        except Exception as e:
            # Silent fail is fine, Ngrok might not be running
            logger.debug(f"Ngrok check skipped: {e}")

    async def on_connect(self) -> None:
        logger.info("Discordゲートウェイに接続しました。")

    async def on_disconnect(self) -> None:
        logger.warning("Disconnected from Discord gateway. Reconnection will be attempted automatically.")

    async def on_resumed(self) -> None:
        logger.info("Discordセッションを再開しました。")

    async def on_error(self, event_method: str, *args: object, **kwargs: object) -> None:
        logger.exception("Unhandled error in event %s", event_method)
        # Auto-Healer Hook for Global Events
        try:
            exc_type, value, traceback = sys.exc_info()
            if value:
                await self.healer.handle_error(event_method, value)
        except Exception as e:
            logger.error(f"Failed to trigger Healer for on_error: {e}")

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            command_name = interaction.command.qualified_name if interaction.command else "unknown"
            logger.info(
                "コマンド権限チェック失敗",
                extra={"command": command_name, "user": str(interaction.user)},
            )
            message = "このコマンドを実行する権限がありません。"
        elif isinstance(error, commands.CommandNotFound):
            return
        else:
            logger.exception("Application command error", exc_info=error)
            # Auto-Healer
            await self.healer.handle_error(interaction, error)
            message = "コマンド実行中にエラーが発生しました。自動修復システムに報告されました。"

        if interaction.guild:
            GuildLogger.get_logger(interaction.guild.id).error(
                f"AppCommand Error: {error} | User: {interaction.user} ({interaction.user.id}) | Command: {interaction.command.qualified_name if interaction.command else 'Unknown'}"
            )

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle text command errors."""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("このコマンドを実行する権限がありません。", delete_after=5)
        else:
            logger.exception("Command error", exc_info=error)
            # Auto-Healer
            if ctx.guild:
                GuildLogger.get_logger(ctx.guild.id).error(
                    f"Command Error: {error} | User: {ctx.author} ({ctx.author.id}) | Content: {ctx.message.content}"
                )
            await self.healer.handle_error(ctx, error)
            try:
                await ctx.reply("エラーが発生しました。", mention_author=False, delete_after=5)
            except discord.HTTPException:
                await ctx.send("エラーが発生しました。", delete_after=5)


def _configure_signals(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows does not support add_signal_handler for these signals in this loop type
            logger.debug("Signal handlers are not supported on this platform (Expected on Windows).")
            break


async def run_bot() -> None:
    try:
        config = Config.load()
        config.validate()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

    setup_logging(config.log_level)
    logger.info("ORA Discord Botを起動します", extra={"app_id": config.app_id})
    
    # SILENCE DISCORD HTTP LOGS (429 Spam)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)

    # Check for FFmpeg
    import shutil
    if not shutil.which("ffmpeg"):
        logger.critical("FFmpegがPATHに見つかりません。音声再生機能は動作しません。")
        print("CRITICAL: FFmpeg not found! Please install FFmpeg and add it to your PATH.", file=sys.stderr)
    else:
        logger.info("FFmpegが見つかりました。")

    intents = discord.Intents.none()
    intents.guilds = True
    intents.members = True
    intents.presences = True
    intents.voice_states = True
    intents.guild_messages = True
    intents.message_content = True

    # Create shared ClientSession
    async with aiohttp.ClientSession() as session:
        link_client = LinkClient(config.ora_api_base_url)
        llm_client = LLMClient(config.llm_base_url, config.llm_api_key, config.llm_model, session=session)
        store = Store(config.db_path)
        await store.init()
        await store.backup()

        bot = ORABot(
            config=config,
            link_client=link_client,
            store=store,
            llm_client=llm_client,
            intents=intents,
            session=session,
        )
        global _bot_instance
        _bot_instance = bot

        stop_event = asyncio.Event()
        _configure_signals(stop_event)

        async with bot:
            bot_task = asyncio.create_task(bot.start(config.token))
            stop_task = asyncio.create_task(stop_event.wait())

            done, pending = await asyncio.wait(
                {bot_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )

            if stop_task in done:
                logger.info("終了シグナルを受信しました。Botを停止します...")
                await bot.close()

            if bot_task in done:
                exc: Optional[BaseException] = bot_task.exception()
                if exc:
                    logger.exception("Botがエラーにより停止しました。")
                    raise exc
            else:
                await bot.close()
                await bot_task

            for task in pending:
                task.cancel()

            if pending:
                await asyncio.gather(*pending, return_exceptions=True)


async def main() -> None:
    try:
        await run_bot()
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        logger.info("ユーザーにより中断されました。終了します。")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
