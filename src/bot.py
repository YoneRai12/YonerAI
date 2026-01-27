"""Entry point for the ORA Discord bot."""
# ruff: noqa: E402

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

import aiohttp  # noqa: E402
from dotenv import load_dotenv

# Load environment variables from .env file
# Load environment variables from .env file
load_dotenv(".env", override=True)

import discord  # noqa: E402
from discord import app_commands  # noqa: E402
from discord.ext import commands  # noqa: E402

from .cogs.core import CoreCog  # noqa: E402
from .cogs.ora import ORACog  # noqa: E402
from .config import Config, ConfigError  # noqa: E402
from .logging_conf import setup_logging
from .storage import Store
from .utils.connection_manager import ConnectionManager
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
        connection_manager: ConnectionManager,
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
        self.connection_manager = connection_manager
        self.healer = Healer(self, llm_client)
        self.started_at = time.time()
        self._backup_task: Optional[asyncio.Task] = None

    async def setup_hook(self) -> None:
        # -1. Check Connection Health (Determine Mode)
        is_healthy = await self.connection_manager.check_health()
        mode_label = "API MODE" if is_healthy else "STANDALONE MODE"
        logger.info(f"🌐 Startup Mode Check: [{mode_label}] (Standalone: {self.connection_manager.is_standalone})")

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
        
        # [Clawdbot] RAG Vector Memory
        from src.services.vector_memory import VectorMemory
        self.vector_memory = VectorMemory()
        logger.info("✅ UnifiedClient (Universal Brain) & VectorMemory 初期化完了")

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
            "src.cogs.creative",
            "src.cogs.voice_engine",
            "src.cogs.heartbeat",
            "src.cogs.visual_cortex",
            "src.cogs.proactive", # [Clawdbot] Proactive Agent
            "src.cogs.music", # [Decomposition] Music Commands
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
                await asyncio.sleep(6 * 3600)  # 6 hours
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
                logger.info("✅ 開発用ギルド (%s) に %d 個のコマンドを即時同期しました。", self.config.dev_guild_id, len(synced))
            except Exception as e:
                logger.warning(f"⚠️ 開発用ギルドへの同期に失敗しました: {e}")

        # Always sync globally to ensure commands work in all servers
        try:
            synced = await self.tree.sync()
            logger.info("🌐 全サーバー共通（グローバル）コマンドを同期しました (総数: %d個)", len(synced))
            if len(synced) < 50:
                logger.warning("📉 同期されたコマンド数が少ないようです (%d個)。一部の Cog が読み込まれていない可能性があります。", len(synced))
        except Exception as e:
            logger.error(f"❌ グローバル同期に失敗しました: {e}")

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
        
        # [User Request] Open all web interfaces locally
        self.loop.create_task(self._open_local_interfaces())

    async def _open_local_interfaces(self) -> None:
        """Opens local web interfaces for Chat, Dashboard, API, and ComfyUI."""
        import webbrowser
        
        # Wait a bit for servers to stabilize
        await asyncio.sleep(5)
        
        urls = [
            ("Chat UI", "http://localhost:3333"),
            # Dashboard is likely part of Next.js app now
            ("Dashboard", "http://localhost:3333"), 
            ("API Docs", "http://localhost:8001/docs"),
            ("ComfyUI", "http://127.0.0.1:8188"),
        ]
        
        logger.info("🖥️ Opening local web interfaces...")
        for name, url in urls:
            try:
                webbrowser.open(url)
                logger.info(f"Opened {name}: {url}")
            except Exception as e:
                logger.warning(f"Failed to open {name}: {e}")

    async def _notify_ngrok_url(self) -> None:
        """Checks for multiple Ngrok tunnels and DMs labels to their respective owners."""
        # Notification mapping: Tunnel Name -> Config Field/Display
        notify_map = {
            "ora-web": self.config.ora_web_notify_id,
            "ora-api": self.config.ora_api_notify_id,
            "ora-dashboard": self.config.startup_notify_channel_id,
            "ora-comfy": self.config.admin_user_id
        }
        
        ngrok_api = "http://127.0.0.1:4040/api/tunnels"
        await asyncio.sleep(15) # Wait for Ngrok tunnels to stabilize

        try:
            async with self.session.get(ngrok_api) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tunnels = data.get("tunnels", [])
                    
                    if not tunnels:
                        logger.warning("Ngrok API reached but no tunnels found. Is Ngrok configured correctly?")
                        return

                    for t in tunnels:
                        name = t.get("name")
                        public_url = t.get("public_url")
                        if not public_url:
                            continue
                        
                        target_id = notify_map.get(name) or self.config.admin_user_id
                        if not target_id:
                            continue

                        # Formatting
                        final_url = public_url
                        if name == "ora-dashboard":
                            final_url = f"{public_url.rstrip('/')}/dashboard"
                        elif name == "ora-api":
                            final_url = f"{public_url.rstrip('/')}/docs"
                        
                        label = name.upper().replace("-", " ")
                        message = f"🚀 ORA {label}：{final_url}"
                        
                        # Send to target (Channel or User)
                        try:
                            # 1. Try User
                            target = self.get_user(target_id) or await self.fetch_user(target_id)
                            if target:
                                await target.send(message)
                                logger.info(f"Ngrok URL ({name}) sent to User {target_id}")
                                continue
                        except Exception:
                            pass
                        
                        try:
                            # 2. Try Channel
                            target = self.get_channel(target_id) or await self.fetch_channel(target_id)
                            if target:
                                await target.send(message)
                                logger.info(f"Ngrok URL ({name}) sent to Channel {target_id}")
                        except Exception as e:
                            logger.error(f"Failed to notify for tunnel {name} (ID: {target_id}): {e}")
                else:
                    logger.debug("Ngrok API not accessible (Status %s)", resp.status)
        except Exception as e:
            # Mask IP in exception message
            err_msg = str(e).replace("127.0.0.1", "[RESTRICTED]").replace("localhost", "[RESTRICTED]")
            logger.warning(f"Could not reach Ngrok local API: {err_msg}")

        # --- Cloudflare Tunnel Detection (Log Polling) ---
        cf_logs = {
            "ora-web": "logs/cf_web.log",
            "ora-dashboard": "logs/cf_dash.log",
            "ora-api": "logs/cf_api.log",
            "ora-comfy": "logs/cf_comfy.log"
        }
        
        async def poll_cf_logs():
            logger.info("Starting Cloudflare log polling (max 60s)...")
            detected_urls = set()
            import re
            
            for _attempt in range(12):  # 5s * 12 = 60s max
                await asyncio.sleep(5)
                for name, log_path in cf_logs.items():
                    if name in detected_urls: continue
                    
                    abs_log_path = os.path.join(os.getcwd(), log_path)
                    if not os.path.exists(abs_log_path): continue
                    
                    try:
                        with open(abs_log_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
                            if match:
                                public_url = match.group(0)
                                if name == "ora-dashboard":
                                    public_url = f"{public_url.rstrip('/')}/api/dashboard/admin?token=ADMIN_VIEW"
                                    # Use configured Admin User ID
                                    target_id = self.config.admin_user_id 
                                elif name == "ora-api":
                                    public_url = f"{public_url.rstrip('/')}/docs"

                                # Priority: 1. Service-specific target (Channel/User), 2. Admin User
                                # If target_id was not overruled above, use map
                                if not target_id:
                                    target_id = notify_map.get(name) or self.config.admin_user_id
                                if not target_id: continue

                                # Descriptive Japanese labels
                                label_map = {
                                    "ora-web": "ウェブ操作画面",
                                    "ora-dashboard": "管理ダッシュボード (全サーバー表示)",
                                    "ora-api": "APIドキュメント",
                                    "ora-comfy": "画像生成 (ComfyUI)"
                                }
                                jp_label = label_map.get(name, name.upper())
                                message = f"🚀 ORA {jp_label} (外部アクセス)：\n{public_url}"
                                
                                # Send notification
                                try:
                                    target = self.get_user(target_id) or await self.fetch_user(target_id)
                                    if target:
                                        await target.send(message)
                                        logger.info(f"Cloudflare URL ({name}) sent to User {target_id}")
                                        detected_urls.add(name)
                                        await asyncio.sleep(1)  # Small gap to prevent rate limit or ordering issues
                                        continue
                                except Exception:
                                    pass
                                
                                # Send notification: Try Channel first, then User DM fallback
                                sent = False
                                try:
                                    target = self.get_channel(target_id) or await self.fetch_channel(target_id)
                                    if target:
                                        await target.send(message)
                                        logger.info(f"Cloudflare URL ({name}) sent to Channel {target_id}")
                                        sent = True
                                except Exception:
                                    pass
                                
                                if not sent:
                                    try:
                                        target = self.get_user(target_id) or await self.fetch_user(target_id)
                                        if target:
                                            await target.send(message)
                                            logger.info(f"Cloudflare URL ({name}) sent to User {target_id}")
                                            sent = True
                                    except Exception:
                                        pass
                                
                                if sent:
                                    detected_urls.add(name)
                                    await asyncio.sleep(1)  # Gap to prevent ordering issues
                                    continue
                    except Exception as e:
                        logger.error(f"Error reading Cloudflare log {log_path}: {e}")
                
                if len(detected_urls) == len(cf_logs):
                    break
            
            logger.info(f"Cloudflare log polling finished. Detected: {len(detected_urls)}")

        # Start polling in background
        asyncio.create_task(poll_cf_logs())

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

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
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
        raise SystemExit(99) from exc

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
        connection_manager = ConnectionManager(
            api_base_url=config.ora_api_base_url, 
            force_standalone=config.force_standalone
        )

        link_client = LinkClient(config.ora_core_api_url)
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
            connection_manager=connection_manager,
        )
        global _bot_instance
        _bot_instance = bot

        stop_event = asyncio.Event()
        _configure_signals(stop_event)

        async with bot:
            bot_task = asyncio.create_task(bot.start(config.token))
            stop_task = asyncio.create_task(stop_event.wait())

            done, pending = await asyncio.wait({bot_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)

            if stop_task in done:
                logger.info("終了シグナルを受信しました。Botを停止します...")
                await bot.close()
                await connection_manager.close()

            if bot_task in done:
                task_exc: Optional[BaseException] = bot_task.exception()
                if task_exc:
                    logger.exception("Botがエラーにより停止しました。")
                    await connection_manager.close()
                    raise task_exc
            else:
                await bot.close()
                await connection_manager.close()
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
