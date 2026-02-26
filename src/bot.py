"""Entry point for the ORA Discord bot."""
# ruff: noqa: E402

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import IO, Dict, Optional

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
            # Use mention-only prefix to avoid clashing with other bots' `!`/`m!` prefixes.
            # Most of ORA's UX is via slash commands + @mention triggers.
            command_prefix=commands.when_mentioned,
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
        self._voice_restore_snapshot_task: Optional[asyncio.Task] = None
        self.unified_client = None
        self.google_client = None
        self.vector_memory = None
        self.search_client = None
        self.voice_manager = None
        self._tunnel_processes: Dict[str, subprocess.Popen] = {}
        self._tunnel_log_handles: Dict[str, IO[str]] = {}

    def _tunnel_pidfile_path(self, name: str) -> str:
        tdir = os.path.join(self.config.state_dir, "tunnels")
        os.makedirs(tdir, exist_ok=True)
        return os.path.join(tdir, f"{name}.pid")

    def _write_tunnel_pidfile(self, name: str, pid: int) -> None:
        try:
            with open(self._tunnel_pidfile_path(name), "w", encoding="utf-8") as f:
                f.write(str(pid))
        except Exception:
            pass

    def _remove_tunnel_pidfile(self, name: str) -> None:
        try:
            os.remove(self._tunnel_pidfile_path(name))
        except Exception:
            pass

    def _kill_stale_tunnel_from_pidfile(self, name: str) -> None:
        pid_path = self._tunnel_pidfile_path(name)
        if not os.path.exists(pid_path):
            return
        try:
            raw = (Path(pid_path).read_text(encoding="utf-8") or "").strip()
            if not raw:
                return
            pid = int(raw)
        except Exception:
            self._remove_tunnel_pidfile(name)
            return

        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        finally:
            self._remove_tunnel_pidfile(name)

    async def _stop_all_tunnels(self) -> None:
        if self._tunnel_processes:
            logger.info("Stopping tracked tunnel processes: %s", ", ".join(self._tunnel_processes.keys()))

        for name, proc in list(self._tunnel_processes.items()):
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        await asyncio.to_thread(proc.wait, 5)
                    except Exception:
                        proc.kill()
            except Exception:
                pass
            finally:
                self._remove_tunnel_pidfile(name)

        self._tunnel_processes.clear()

        for _, handle in list(self._tunnel_log_handles.items()):
            try:
                handle.close()
            except Exception:
                pass
        self._tunnel_log_handles.clear()

    async def _check_local_llm_health(self) -> None:
        """
        Best-effort sanity check: if LLM_MODEL looks local-only but the local LLM endpoint is down,
        warn early with an actionable hint. This avoids "the system feels dead" from repeated timeouts.
        """
        base = str(getattr(self.config, "llm_base_url", "") or "").strip().rstrip("/")
        model = str(getattr(self.config, "llm_model", "") or "").strip()
        if not base or not model:
            return

        base_low = base.lower()
        is_local_base = ("127.0.0.1" in base_low) or ("localhost" in base_low)
        if not is_local_base:
            return

        # Heuristic: non-cloud model IDs often contain provider namespaces or known local families.
        mlow = model.lower()
        looks_local_only = ("/" in model) or any(x in mlow for x in ["mistral", "ministral", "qwen", "llama", "gemma"])
        if not looks_local_only:
            return

        if str(os.getenv("ORA_LLM_FALLBACK_TO_OPENAI") or "").strip().lower() in {"1", "true", "yes", "on"}:
            return

        # OpenAI-compatible servers usually expose /models; since base includes /v1, append /models.
        url = f"{base}/models"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=1.5)) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass

        logger.warning(
            "⚠️ Local LLM endpoint looks down (%s) while LLM_MODEL=%s. "
            "Start your local server (e.g. vLLM/LM Studio) or set ORA_LLM_FALLBACK_TO_OPENAI=1 "
            "(and optionally ORA_LLM_FALLBACK_MODEL) to keep working via OpenAI.",
            base,
            model,
        )

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
        await self._check_local_llm_health()

        # [Clawdbot] RAG Vector Memory
        try:
            from src.services.vector_memory import VectorMemory
            self.vector_memory = VectorMemory()
            logger.info("✅ UnifiedClient (Universal Brain) & VectorMemory 初期化完了")
        except Exception as e:
            # Keep startup resilient in CI/clean envs where vector DB metadata may be invalid.
            self.vector_memory = None
            logger.warning(f"⚠️ VectorMemory 初期化失敗。RAGを無効化して継続します: {e}")

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
            "src.cogs.approvals_admin",
            "src.cogs.resource_manager",
            "src.cogs.mcp",
            "src.cogs.memory",
            "src.cogs.scheduler",
            "src.cogs.system_shell",
            "src.cogs.creative",
            "src.cogs.voice_engine",
            "src.cogs.heartbeat",
            "src.cogs.visual_cortex",
            "src.cogs.proactive", # [Clawdbot] Proactive Agent
            "src.cogs.music", # [Decomposition] Music Commands
            "src.cogs.link_manager", # [Broadcast] Link Broadcaster
            "src.cogs.leveling", # [Manifesto] Rank & Points
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

        # 8. Start periodic voice snapshot (for restart restore). Disabled by default.
        self._voice_restore_snapshot_task = self.loop.create_task(self._periodic_voice_snapshot_loop())

    async def _periodic_backup_loop(self) -> None:
        """Runs backup every 6 hours."""
        try:
            await self.wait_until_ready()
        except RuntimeError:
            # In unit tests the client isn't logged in; avoid noisy background task errors.
            return
        while not self.is_closed():
            try:
                await asyncio.sleep(6 * 3600)  # 6 hours
                logger.info("Starting periodic backup...")
                await self.store.backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic backup failed: {e}")

    async def _periodic_voice_snapshot_loop(self) -> None:
        """
        Periodically snapshot current VC connections so an unexpected restart can restore them.

        Enable with:
        - ORA_VOICE_RESTORE_SNAPSHOT=1
        - ORA_VOICE_RESTORE_SNAPSHOT_INTERVAL_SEC=20 (optional)
        """
        from src.utils.voice_restore import snapshot_voice_connections, write_snapshot

        try:
            await self.wait_until_ready()
        except RuntimeError:
            # In unit tests the client isn't logged in; avoid noisy background task errors.
            return
        enabled = (os.getenv("ORA_VOICE_RESTORE_SNAPSHOT") or "").strip().lower() in {"1", "true", "yes", "on"}
        if not enabled:
            return

        try:
            interval = int((os.getenv("ORA_VOICE_RESTORE_SNAPSHOT_INTERVAL_SEC") or "20").strip())
        except Exception:
            interval = 20
        interval = max(5, min(300, interval))

        while not self.is_closed():
            try:
                payload = snapshot_voice_connections(self, state_dir=self.config.state_dir)
                write_snapshot(payload, state_dir=self.config.state_dir)
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            await asyncio.sleep(interval)

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

        # 0. Snapshot VC connections before shutdown (best-effort).
        try:
            from src.utils.voice_restore import snapshot_voice_connections, write_snapshot

            payload = snapshot_voice_connections(self, state_dir=self.config.state_dir)
            write_snapshot(payload, state_dir=self.config.state_dir)
        except Exception:
            pass

        # 0.5 Stop periodic voice snapshot
        if self._voice_restore_snapshot_task:
            self._voice_restore_snapshot_task.cancel()
            try:
                await self._voice_restore_snapshot_task
            except asyncio.CancelledError:
                pass

        # 1. Stop Periodic Backup
        if self._backup_task:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass

        # 1.5 Stop cloudflared tunnel children spawned by this bot.
        await self._stop_all_tunnels()

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
        # self.loop.create_task(self._notify_ngrok_url())

        # Safety defaults: do not auto-open browsers or auto-expose tunnels unless explicitly enabled.
        if getattr(self.config, "auto_open_local_interfaces", False):
            self.loop.create_task(self._open_local_interfaces())
            logger.info("Auto-open local interfaces: ENABLED (ORA_AUTO_OPEN_LOCAL_INTERFACES=1)")
        else:
            logger.info("Auto-open local interfaces: disabled")

        if getattr(self.config, "auto_start_tunnels", False):
            self.loop.create_task(self._start_tunnels())
            logger.info("Auto-start tunnels: ENABLED (ORA_AUTO_START_TUNNELS=1)")
        else:
            logger.info("Auto-start tunnels: disabled")

        # Restore previous VC connections if enabled and snapshot is still fresh.
        try:
            from src.utils.voice_restore import restore_voice_connections

            result = await restore_voice_connections(self, state_dir=self.config.state_dir)
            if result.get("ok"):
                restored_n = len(result.get("restored") or [])
                failed_n = len(result.get("failed") or [])
                if restored_n or failed_n:
                    logger.info("Voice restore: restored=%d failed=%d", restored_n, failed_n)
        except Exception as e:
            logger.debug(f"Voice restore skipped: {e}")

    async def _open_local_interfaces(self) -> None:
        """Opens local web interfaces for Chat, Dashboard, API, and ComfyUI."""
        import webbrowser

        # Wait a bit for servers to stabilize
        await asyncio.sleep(5)

        urls = [
            ("Admin UI", "http://localhost:8000"),
            ("New Web UI", "http://localhost:3000"),
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
        # Use configured log dir
        log_dir = self.config.log_dir
        cf_logs = {
            "ora-web": os.path.join(log_dir, "cf_web.log"),
            "ora-dashboard": os.path.join(log_dir, "cf_dash.log"),
            "ora-api": os.path.join(log_dir, "cf_api.log"),
            "ora-comfy": os.path.join(log_dir, "cf_comfy.log")
        }

        async def poll_cf_logs():
            import re
            logger.info("Starting Cloudflare log polling (max 60s)...")
            detected_urls = set()
            cfg = self.config

            # Map of service names to their descriptive labels
            label_map = {
            "ora-main": "チャット画面",
            "ora-web": "操作ポータル",
            "ora-dashboard": "管理ダッシュボード",
            "ora-api": "APIドキュメント",
            "ora-comfy": "画像生成エンジン"
        }

            for _attempt in range(12):  # 5s * 12 = 60s max
                await asyncio.sleep(5)
                for name, log_path in cf_logs.items():
                    if name in detected_urls: continue
                    if not os.path.exists(log_path): continue

                    try:
                        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            # Find all matches (public URLs or UUIDs). Avoid mistaking the API endpoint
                            # (https://api.trycloudflare.com/tunnel) as a public URL.
                            from src.utils.cloudflare_tunnel import extract_public_tunnel_urls
                            url_matches = extract_public_tunnel_urls(content)
                            id_matches = re.findall(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", content)

                            if url_matches or id_matches:
                                jp_label = label_map.get(name, name.upper())
                                # Priority: Check for Named Tunnel Hostname in environment
                                env_hostname = os.getenv("TUNNEL_HOSTNAME")
                                if env_hostname and name == "ora-main":
                                    public_url = env_hostname if env_hostname.startswith("http") else f"https://{env_hostname}"
                                elif url_matches:
                                    # Take the LATEST assigned URL
                                    last_url = url_matches[-1]
                                    public_url = last_url if last_url.startswith("http") else f"https://{last_url}"
                                elif id_matches:
                                    # Fallback to detection from IDs
                                    last_id = id_matches[-1]
                                    public_url = f"https://{last_id}.cfargotunnel.com"
                                else:
                                    continue

                                # Construct URLs and find target channel
                                local_url = "UNKNOWN"
                                target_id = None

                                if name == "ora-main":
                                    local_url = "http://localhost:3000"
                                    target_id = cfg.startup_notify_channel_id
                                elif name == "ora-web": # This is Web Ops (Portal)
                                    local_url = "http://localhost:8000"
                                    target_id = cfg.ora_web_notify_id
                                elif name == "ora-dashboard":
                                    public_url = public_url.rstrip("/")
                                    local_url = "http://localhost:3333"
                                    target_id = cfg.log_channel_id
                                elif name == "ora-api":
                                    public_url = f"{public_url.rstrip('/')}/docs"
                                    local_url = "http://localhost:8001/docs"
                                    target_id = cfg.ora_api_notify_id
                                elif name == "ora-comfy":
                                    local_url = f"{cfg.sd_api_url}"
                                    target_id = cfg.config_ui_notify_id

                                # Final fallback for target_id
                                if not target_id:
                                    target_id = cfg.log_channel_id or cfg.admin_user_id

                                if not target_id:
                                    logger.warning(f"No notification target found for {name}")
                                    continue

                                message = f"🚀 **ORA {jp_label}**\n{public_url}"

                                # Send notification
                                sent = False
                                try:
                                    # Try Channel first
                                    target = self.get_channel(target_id) or await self.fetch_channel(target_id)
                                    if target and hasattr(target, "send"):
                                        await target.send(message)
                                        logger.info(f"Notification for {name} sent to {target_id}")
                                        sent = True
                                except Exception as channel_err:
                                    logger.debug(f"Channel notification failed for {target_id}: {channel_err}")

                                if not sent:
                                    # Fallback to User DM
                                    try:
                                        target = self.get_user(target_id) or await self.fetch_user(target_id)
                                        if target:
                                            await target.send(message)
                                            logger.info(f"Notification for {name} sent to User {target_id} (DM)")
                                            sent = True
                                    except Exception as dm_err:
                                        logger.error(f"DM notification failed for {target_id}: {dm_err}")

                                if sent:
                                    detected_urls.add(name)
                                    await asyncio.sleep(1)
                                    continue
                    except Exception as e:
                        logger.error(f"Error processing Cloudflare log {log_path}: {e}")

                if len(detected_urls) == len(cf_logs):
                    break

            logger.info(f"Cloudflare log polling finished. Detected: {len(detected_urls)}")

        # Start polling in background
        # [Legacy] LinkManager handles this now with Embeds
        # asyncio.create_task(poll_cf_logs())

    async def _start_tunnels(self) -> None:
        """Attempts to start Cloudflare tunnels for local services if not running."""
        allow_quick = bool(getattr(self.config, "tunnels_allow_quick", False))
        token = os.getenv("CLOUDFLARE_TUNNEL_TOKEN")
        if not token and not allow_quick:
            logger.warning(
                "Auto-tunnel requested but CLOUDFLARE_TUNNEL_TOKEN is missing and quick tunnels are disabled. "
                "Set ORA_TUNNELS_ALLOW_QUICK=1 to allow quick tunnels."
            )
            return

        # 1. Locate cloudflared
        cf_exe = None
        candidates = [
            os.path.join(os.getcwd(), "tools", "cloudflare", "cloudflared.exe"),
            os.path.join(os.getcwd(), "cloudflared.exe"),
            r"L:\tools\cloudflare\cloudflared.exe",
            "cloudflared" # PATH
        ]

        # Check PATH last, or specifically
        import shutil
        if shutil.which("cloudflared"):
            cf_exe = "cloudflared"

        # Check explicit paths
        for p in candidates:
            if os.path.exists(p):
                cf_exe = p
                break

        if not cf_exe:
            logger.warning("Cloudflare Tunnel: cloudflared.exe not found. Skipping auto-tunnel.")
            return

        logger.info(f"Cloudflare Tunnel: Binary found at {cf_exe}")

        # 2. Define Tunnels
        # Map: Name -> (Port, LogFile)
        # Optimized for 429 Prevention:
        # 1. ora-main (8000/Named): Main Named Tunnel (Uses Token)
        # 2. ora-dashboard (3333): Dashboard + API Proxy
        # 3. ora-chat (3000): Web Chat UI
        # 4. ora-comfy (8188): ComfyUI Interface
        tunnels = {
            "ora-main": (8000, "cf_main.log"), # Named Tunnel handles 8000
            "ora-dashboard": (3333, "cf_dash.log"),
            "ora-chat": (3000, "cf_chat.log"),
            "ora-comfy": (8188, "cf_comfy.log")
        }

        log_dir = self.config.log_dir
        os.makedirs(log_dir, exist_ok=True)

        for name, (port, log_name) in tunnels.items():
            # If previous runs left a stale child process, reclaim it now.
            self._kill_stale_tunnel_from_pidfile(name)

            log_path = os.path.join(log_dir, log_name)

            # Simple check: If log exists and is recent/active, assume running?
            # Or just try to start and if port conflicts (already tunneled?), it might fail gracefully or redundant.
            # Cloudflared allows multiple generic tunnels usually.

            # Better: Check if we already have a process tracked? No track here.
            # We simply check if the log file is "fresh" or empty.

            is_stale = True
            if os.path.exists(log_path):
                # If file modified < 10 seconds ago? No, that's unreliable.
                # Just start it. If it's already running on system, starting another might be fine (multiple tunnels) or error.
                # Safest: Use a lock file or PID?
                # Given user context: They likely have nothing running.
                pass

            # Start process
            logger.info(f"Starting Tunnel {name} (Port {port})...")
            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    # Clear log
                    pass

                # Check for Named Tunnel Token in environment
                token = os.getenv("CLOUDFLARE_TUNNEL_TOKEN")
                if token and name == "ora-main":
                    # If we have a token, use Named Tunnel Run mode usually for the main entry point
                    # The user's named tunnel is configured for 8000 in config.yaml usually, so we run it here.
                    cmd = [cf_exe, "tunnel", "run", "--token", token]
                    logger.info(f"Using Named Tunnel for {name}")
                else:
                    if not allow_quick:
                        logger.info("Skipping quick tunnel for %s (ORA_TUNNELS_ALLOW_QUICK=0)", name)
                        continue
                    # Fallback to Quick Tunnel
                    cmd = [cf_exe, "tunnel", "--url", f"http://localhost:{port}"]

                # Windows specific: explicit creation flags to show window for debugging if user asked for CMD count
                # Use CREATE_NEW_CONSOLE to ensure separate windows but keep process linked to bot
                new_console = str(os.getenv("ORA_TUNNELS_NEW_CONSOLE") or "0").strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
                creation_flags = 0
                if os.name == "nt":
                    creation_flags = subprocess.CREATE_NEW_CONSOLE if new_console else subprocess.CREATE_NO_WINDOW

                log_f = open(log_path, "w", encoding="utf-8", errors="ignore")
                proc = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    creationflags=creation_flags,
                )
                self._tunnel_processes[name] = proc
                self._tunnel_log_handles[name] = log_f
                self._write_tunnel_pidfile(name, proc.pid)
                logger.info("Tunnel %s started (pid=%s)", name, proc.pid)

                # Wait 5 seconds between each tunnel (User Request) to avoid races/limits
                logger.info("⏳ Waiting 5s before starting next tunnel...")
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Failed to launch tunnel {name}: {e}")

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

    setup_logging(config.log_level, log_dir=config.log_dir)
    logger.info("ORA Discord Botを起動します", extra={"app_id": config.app_id})
    logger.info(
        "Runtime profile: profile=%s instance_id=%s db=%s state_root=%s",
        getattr(config, "profile", None),
        getattr(config, "instance_id", None),
        getattr(config, "db_path", None),
        getattr(config, "state_root", None),
    )
    # Shared profile safety: prefer explicit guest allowlist.
    try:
        if str(getattr(config, "profile", "")).strip().lower() == "shared":
            explicit = (os.getenv("ORA_SHARED_GUEST_ALLOWED_TOOLS") or "").strip()
            if not explicit:
                logger.warning(
                    "ORA_PROFILE=shared but ORA_SHARED_GUEST_ALLOWED_TOOLS is not set. "
                    "Falling back to ORA_PUBLIC_TOOLS/DEFAULT_PUBLIC_TOOLS for guest exposure (compat mode). "
                    "Set ORA_SHARED_GUEST_ALLOWED_TOOLS to lock this down."
                )
        if str(getattr(config, "profile", "")).strip().lower() == "private":
            mode = (os.getenv("ORA_PRIVATE_OWNER_APPROVALS") or "high").strip().lower()
            skip = (os.getenv("ORA_PRIVATE_OWNER_APPROVAL_SKIP_TOOLS") or "").strip()
            if mode != "high" or skip:
                logger.warning(
                    "Private owner approvals relaxed: ORA_PRIVATE_OWNER_APPROVALS=%s ORA_PRIVATE_OWNER_APPROVAL_SKIP_TOOLS=%s",
                    mode,
                    skip,
                )
    except Exception:
        pass

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
