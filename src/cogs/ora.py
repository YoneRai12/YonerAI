"""Extended ORA-specific slash commands."""

from __future__ import annotations

import logging
import secrets
import string
import time
import json
import asyncio
import asyncio
import io
from PIL import Image
import datetime
from ..utils import image_tools
from ..utils import flag_utils
from ..utils.games import ShiritoriGame
import os
import aiofiles
from typing import Optional, Dict

import torch
# Transformers for SAM 2 / T5Gemma
try:
    from transformers import AutoProcessor, Sam2Model, AutoModelForCausalLM, AutoTokenizer, pipeline
except ImportError:
    pass # Handled in tool execution
from collections import defaultdict

import aiohttp
import psutil
import discord
from discord import app_commands
from discord.abc import User
from discord.ext import commands

from ..storage import Store
from ..utils.llm_client import LLMClient
from ..utils.search_client import SearchClient
from ..utils import image_tools
from ..utils.voice_manager import VoiceConnectionError
from ..utils.ui import StatusManager, EmbedFactory
from src.views.image_gen import AspectRatioSelectView
from ..utils.drive_client import DriveClient
from ..utils.desktop_watcher import DesktopWatcher
from discord.ext import tasks
from pathlib import Path
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# Try E: drive first, then fallback to user home
CACHE_DIR = Path("E:/ora_cache")
if not Path("E:/").exists():
    CACHE_DIR = Path.home() / ".ora_cache"
    logger.warning(f"E: drive not found. Using {CACHE_DIR} for cache.")

CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def _get_gpu_stats() -> Optional[str]:
    """Fetch GPU stats using nvidia-smi."""
    try:
        # 1. Global Stats
        # name, utilization.gpu, memory.used, memory.total
        cmd1 = "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
        proc1 = await asyncio.create_subprocess_shell(cmd1, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out1, _ = await proc1.communicate()
        
        if proc1.returncode != 0:
            return None
        
        gpu_info = out1.decode().strip().split(",")
        if len(gpu_info) < 4:
            return "Unknown GPU Data"
        
        name = gpu_info[0].strip()
        util = gpu_info[1].strip()
        mem_used = int(gpu_info[2].strip())
        mem_total = int(gpu_info[3].strip())
        mem_free = mem_total - mem_used
        
        text = f"**{name}**\nUtilization: {util}%\nVRAM: {mem_used}MB / {mem_total}MB (Free: {mem_free}MB)"

        # 2. Process List
        # pid, process_name
        cmd2 = "nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader"
        proc2 = await asyncio.create_subprocess_shell(cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out2, _ = await proc2.communicate()
        
        if proc2.returncode == 0 and out2:
            lines = out2.decode().strip().splitlines()
            processes = []
            for line in lines:
                parts = line.split(",")
                if len(parts) >= 2:
                    pid = parts[0].strip()
                    # Clean up path to just filename
                    path = parts[1].strip()
                    exe_name = path.split("\\")[-1]
                    processes.append(f"{exe_name} ({pid})")
            
            if processes:
                text += f"\nProcesses: {', '.join(processes)}"
            else:
                text += "\nProcesses: None (or hidden)"
        
        return text
        
    except Exception as e:
        logger.error(f"Failed to get GPU stats: {e}")
        return None

def _nonce(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


from ..managers.resource_manager import ResourceManager

class ORACog(commands.Cog):
    """ORA-specific commands such as login link and dataset management."""

    def __init__(
        self,
        bot: commands.Bot,
        store: Store,
        llm: LLMClient,
        search_client: SearchClient,
        public_base_url: Optional[str],
        ora_api_base_url: Optional[str],
        privacy_default: str,
    ) -> None:
        logger.info("ORACog.__init__ called - Loading ORACog")
        self.bot = bot
        self._store = store
        self._llm = llm
        self.llm = llm # Public Alias for Views
        self._search_client = search_client
        self._drive_client = DriveClient()
        self._watcher = DesktopWatcher()
        self._public_base_url = public_base_url
        self._ora_api_base_url = ora_api_base_url
        self._privacy_default = privacy_default
        self._locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.chat_cooldowns = defaultdict(float) # User ID -> Timestamp
        
        # Layer 2: Resource Manager (The Guard Dog)
        self.resource_manager = ResourceManager()

        # VRAM Management & Queue
        self.is_generating_image = False
        self.message_queue: list[discord.Message] = []
        
        
        # Game State: channel_id -> ShiritoriGame
        self.shiritori_games: Dict[int, ShiritoriGame] = defaultdict(ShiritoriGame)
        
        # Gaming Mode Watcher
        from ..managers.game_watcher import GameWatcher
        self.game_watcher = GameWatcher(
            target_processes=self.bot.config.gaming_processes,
            on_game_start=self._on_game_start,
            on_game_end=self._on_game_end
        )
        self._gaming_restore_task: Optional[asyncio.Task] = None

        # Start background tasks
        self.desktop_loop.start()
        self.game_watcher.start()
        # Enforce Safe Model at Startup (Start LLM Context)
        self.bot.loop.create_task(self.resource_manager.switch_context("llm"))
        logger.info("ORACog.__init__ complete - desktop_loop started")

    def cog_unload(self):
        self.desktop_loop.cancel()
        if self._gaming_restore_task:
            self._gaming_restore_task.cancel()
        if self.game_watcher:
            self.game_watcher.stop()

    def _on_game_start(self):
        """Callback when game starts: Switch to Gaming Mode IMMEDIATELY."""
        # Cancel any pending restore task
        if self._gaming_restore_task:
            self._gaming_restore_task.cancel()
            self._gaming_restore_task = None
            logger.info("🚫 Cancelled pending Normal Mode restoration.")

        self.bot.loop.create_task(self.resource_manager.set_gaming_mode(True))

    def _on_game_end(self):
        """Callback when game ends: Schedule switch to Normal Mode after 5 minutes."""
        if self._gaming_restore_task:
            self._gaming_restore_task.cancel()
        
        self._gaming_restore_task = self.bot.loop.create_task(self._restore_normal_mode_delayed())

    async def _restore_normal_mode_delayed(self):
        """Wait 5 minutes then restore Normal Mode."""
        logger.info("⏳ Game closed. Waiting 5 minutes before restoring Normal Mode...")
        try:
            await asyncio.sleep(300) # 5 minutes
            logger.info("⏰ 5 minutes passed. Restoring Normal Mode.")
            await self.resource_manager.set_gaming_mode(False)
        except asyncio.CancelledError:
            logger.info("🛑 Restore task cancelled (Game restarted?).")
        finally:
            self._gaming_restore_task = None

    async def _check_comfy_connection(self):
        """Check if ComfyUI is reachable on startup."""
        url = f"{self.bot.config.sd_api_url}/system_stats"
        
        # Retry up to 12 times (60 seconds)
        for i in range(12):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=5) as resp:
                         if resp.status == 200:
                             logger.info(f"✅ ComfyUI Connected at {self.bot.config.sd_api_url}")
                             return
                         else:
                             logger.warning(f"⚠️ ComfyUI returned status {resp.status}. Retrying... ({i+1}/12)")
            except Exception as e:
                 # Connection Refused etc.
                 if i % 2 == 0: 
                    logger.warning(f"⏳ Waiting for ComfyUI to start... ({e}) ({i+1}/12)")
            
            await asyncio.sleep(5)
        
        logger.error("❌ Could not connect to ComfyUI after 60 seconds.")

    # --- PERMISSION SYSTEM ---
    SUB_ADMIN_IDS = {1307345055924617317}
    VC_ADMIN_IDS = {1156215844834123857}

    def _check_permission(self, user_id: int, level: str = "owner") -> bool:
        """
        Check if user has permission.
        Levels:
        - 'owner': Only the Bot Owner (Config Admin ID).
        - 'sub_admin': Owner OR Sub-Admins.
        - 'vc_admin': Owner OR Sub-Admins OR VC Admins.
        """
        owner_id = self.bot.config.admin_user_id
        CREATOR_ID = 1069941291661672498
        
        # Owner & Creator always have access (Root)
        if user_id == owner_id or user_id == CREATOR_ID:
            return True
        
        # Creator Only (Absolute Lockdown)
        if level == "creator":
            return user_id == CREATOR_ID

        # Owner Level (Config Admin)
        if level == "owner":
            return user_id == owner_id or user_id == CREATOR_ID
        
        # Sub-Admin Level (includes owner/creator)
        if level == "sub_admin":
            if user_id in self.SUB_ADMIN_IDS:
                return True
        
        # VC Admin Level (includes sub_admin/owner/creator)
        if level == "vc_admin":
            if user_id in self.VC_ADMIN_IDS or user_id in self.SUB_ADMIN_IDS:
                return True
                
        return False

    @tasks.loop(minutes=5.0)
    async def desktop_loop(self):
        """Periodically check the desktop and report to Admin."""
        admin_id = self.bot.config.admin_user_id
        if not admin_id:
            return

        # Check if enabled
        enabled = await self._store.get_desktop_watch_enabled(admin_id)
        if not enabled:
            return

        try:
            # Analyze screen in thread
            result = await asyncio.to_thread(self._watcher.analyze_screen)
            if not result:
                return

            # If interesting (e.g. has labels), DM the admin
            # For now, just report what is seen to prove it works
            labels = result.get("labels", [])
            faces = result.get("faces", 0)
            text = result.get("text", "")[:100].replace("\n", " ")
            
            if not labels and faces == 0 and not text:
                return

            # Construct report (Japanese)
            report = "🖥️ **デスクトップ監視レポート**\n"
            if labels:
                report += f"🏷️ **検出:** {', '.join(labels)}\n"
            if faces > 0:
                report += f"👤 **顔検出:** {faces}人\n"
            if text:
                report += f"📝 **テキスト:** {text}...\n"
            
            # Send DM
            user = await self.bot.fetch_user(admin_id)
            if user:
                # Create file for screenshot
                # We need to re-capture or use the bytes we have?
                # The result from analyze_image_structured doesn't include the image bytes usually unless we pass them through.
                # But wait, analyze_screen calls capture_screen.
                # Let's just send the text report for now to be safe/fast.
                await user.send(report)

        except Exception as e:
            logger.error(f"Desktop watcher loop failed: {e}")

    @app_commands.command(name="desktop_watch", description="デスクトップ監視（DM通知）のオン・オフを切り替えます。")
    @app_commands.describe(mode="ON/OFF")
    @app_commands.choices(mode=[
        app_commands.Choice(name="ON", value="on"),
        app_commands.Choice(name="OFF", value="off"),
    ])
    async def desktop_watch(self, interaction: discord.Interaction, mode: str):
        """Toggle desktop watcher."""
        # Admin check
        admin_id = self.bot.config.admin_user_id
        creator_id = 1069941291661672498
        if interaction.user.id != admin_id and interaction.user.id != creator_id:
            await interaction.response.send_message("⛔ この機能は管理者専用です。", ephemeral=True)
            return

        enabled = (mode == "on")
        await self._store.set_desktop_watch_enabled(interaction.user.id, enabled)
        
        status = "オン" if enabled else "オフ"
        await interaction.response.send_message(f"デスクトップ監視を {status} にしました。", ephemeral=True)



    @desktop_loop.before_loop
    async def before_desktop_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="login", description="Googleアカウント連携用のURLを発行します。")
    @app_commands.describe(ephemeral="自分だけに表示するかどうか (デフォルト: True)")
    async def login(self, interaction: discord.Interaction, ephemeral: bool = True) -> None:
        await self._store.ensure_user(interaction.user.id, self._privacy_default)
        if not self._public_base_url:
            await interaction.response.send_message(
                "PUBLIC_BASE_URL が未設定のためログインURLを発行できません。",
                ephemeral=ephemeral,
            )
            return

        await interaction.response.defer(ephemeral=ephemeral, thinking=True)
        state = _nonce()
        await self._store.start_login_state(state, interaction.user.id, ttl_sec=900)
        url = f"{self._public_base_url}/auth/discord?state={state}"
        await interaction.followup.send(
            "Google ログインの準備ができました。以下のURLから認証を完了してください。\n" + url,
            ephemeral=ephemeral,
        )

    async def _ephemeral_for(self, user: discord.User | discord.Member) -> bool:
        """Return True if the user's privacy setting is 'private'."""
        privacy = await self._store.get_privacy(user.id)
        return privacy == "private"

    @app_commands.command(name="whoami", description="連携済みアカウント情報を表示します。")
    async def whoami(self, interaction: discord.Interaction) -> None:
        await self._store.ensure_user(interaction.user.id, self._privacy_default)
        google_sub = await self._store.get_google_sub(interaction.user.id)
        privacy = await self._store.get_privacy(interaction.user.id)
        lines = [
            f"Discord: {interaction.user} (ID: {interaction.user.id})",
            f"Google: {'連携済み' if google_sub else '未連携'}",
            f"既定の公開範囲: {privacy}",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    privacy_group = app_commands.Group(
        name="privacy", description="返信の既定公開範囲を設定します"
    )

    @privacy_group.command(name="set", description="返信の既定公開範囲を変更します。")
    @app_commands.describe(mode="private は自分のみ / public は全員に表示")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="private", value="private"),
            app_commands.Choice(name="public", value="public"),
        ]
    )
    async def privacy_set(
        self, interaction: discord.Interaction, mode: app_commands.Choice[str]
    ) -> None:
        await self._store.ensure_user(interaction.user.id, self._privacy_default)
        await self._store.set_privacy(interaction.user.id, mode.value)
        await interaction.response.send_message(
            f"既定公開範囲を {mode.value} に更新しました。", ephemeral=True
        )

    @privacy_group.command(name="set_system", description="システムコマンドの既定公開範囲を変更します。")
    @app_commands.describe(mode="private は自分のみ / public は全員に表示")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="private", value="private"),
            app_commands.Choice(name="public", value="public"),
        ]
    )
    async def privacy_set_system(
        self, interaction: discord.Interaction, mode: app_commands.Choice[str]
    ) -> None:
        await self._store.ensure_user(interaction.user.id, self._privacy_default)
        await self._store.set_system_privacy(interaction.user.id, mode.value)
        await interaction.response.send_message(
            f"システムコマンドの既定公開範囲を {mode.value} に更新しました。", ephemeral=True
        )

    @app_commands.command(name="chat", description="LM Studio 経由で応答を生成します。")
    @app_commands.describe(prompt="送信する内容")
    # REMOVED due to sync crash
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def chat(self, interaction: discord.Interaction, prompt: str) -> None:
        await self._store.ensure_user(interaction.user.id, self._privacy_default)
        ephemeral = await self._ephemeral_for(interaction.user)
        await interaction.response.defer(ephemeral=ephemeral, thinking=True)
        try:
            content = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
        except Exception as e:
            logger.exception("LLM call failed", extra={"user_id": interaction.user.id})
            await interaction.followup.send(f"LLM 呼び出しに失敗しました: {e}", ephemeral=True)
            return
        await interaction.followup.send(content, ephemeral=ephemeral)

    dataset_group = app_commands.Group(name="dataset", description="データセット管理コマンド")

    @dataset_group.command(name="add", description="添付ファイルをデータセットとして登録します。")
    @app_commands.describe(
        file="取り込む添付ファイル",
        name="表示名（省略時はファイル名）",
    )
    async def dataset_add(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        name: Optional[str] = None,
    ) -> None:
        await self._store.ensure_user(interaction.user.id, self._privacy_default)
        ephemeral = await self._ephemeral_for(interaction.user)
        await interaction.response.defer(ephemeral=ephemeral, thinking=True)

        title = name or file.filename
        # Reject ZIP files for security reasons
        if file.filename.lower().endswith(".zip"):
            await interaction.followup.send(
                "ZIP ファイルはセキュリティ上の理由で受け付けていません。",
                ephemeral=ephemeral,
            )
            return
        dataset_id = await self._store.add_dataset(interaction.user.id, title, file.url)

        uploaded = False
        if self._ora_api_base_url:
            try:
                timeout = aiohttp.ClientTimeout(total=120)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(file.url) as resp:
                        if resp.status != 200:
                            raise RuntimeError(f"Failed to download attachment: {resp.status}")
                        data = await resp.read()
                    upload_url = f"{self._ora_api_base_url}/api/datasets/ingest"
                    form = aiohttp.FormData()
                    form.add_field("discord_user_id", str(interaction.user.id))
                    form.add_field("dataset_name", title)
                    form.add_field(
                        "file",
                        data,
                        filename=file.filename,
                        content_type=file.content_type or "application/octet-stream",
                    )
                    async with session.post(upload_url, data=form) as response:
                        if response.status == 200:
                            uploaded = True
                        else:
                            body = await response.text()
                            raise RuntimeError(
                                f"Dataset upload failed with status {response.status}: {body}"
                            )
            except Exception:
                logger.exception("Dataset upload failed", extra={"user_id": interaction.user.id})

        msg = (
            f"データセット『{title}』を登録しました (ID: {dataset_id}) "
            f"送信先: {'ORA API' if uploaded else 'ローカルメタデータのみ'}"
        )
        await interaction.followup.send(msg, ephemeral=ephemeral)

    @dataset_group.command(name="list", description="登録済みデータセットを表示します。")
    async def dataset_list(self, interaction: discord.Interaction) -> None:
        await self._store.ensure_user(interaction.user.id, self._privacy_default)
        ephemeral = await self._ephemeral_for(interaction.user)
        datasets = await self._store.list_datasets(interaction.user.id, limit=10)
        if not datasets:
            await interaction.response.send_message(
                "登録済みのデータセットはありません。", ephemeral=ephemeral
            )
            return

        lines = [
            f"{dataset_id}: {name} {url or ''}" for dataset_id, name, url, _ in datasets
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=ephemeral)

    @app_commands.command(name="summarize", description="直近の会話を要約します。")
    @app_commands.describe(limit="要約するメッセージ数 (デフォルト: 50)")
    # REMOVED due to sync crash
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def summarize(self, interaction: discord.Interaction, limit: int = 50) -> None:
        """Summarize recent chat history."""
        await self._store.ensure_user(interaction.user.id, self._privacy_default)
        ephemeral = await self._ephemeral_for(interaction.user)
        await interaction.response.defer(ephemeral=ephemeral, thinking=True)

        if not interaction.channel:
            await interaction.followup.send("チャンネルが見つかりません。", ephemeral=ephemeral)
            return

        messages = []
        try:
            async for msg in interaction.channel.history(limit=limit):
                if msg.content:
                    messages.append(f"{msg.author.display_name}: {msg.content}")
        except Exception as e:
            logger.error(f"Failed to fetch history: {e}")
            await interaction.followup.send("メッセージ履歴の取得に失敗しました。", ephemeral=ephemeral)
            return

        if not messages:
            await interaction.followup.send("要約するメッセージがありません。", ephemeral=ephemeral)
            return

        # Reverse to chronological order
        messages.reverse()
        history_text = "\n".join(messages)
        
        prompt = (
            f"以下のチャットログを要約してください。\n"
            f"重要なポイントを箇条書きでまとめ、全体の流れがわかるようにしてください。\n"
            f"\n"
            f"チャットログ:\n"
            f"{history_text}"
        )

        try:
            summary = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            await interaction.followup.send(f"**📝 会話の要約 (直近{len(messages)}件)**\n\n{summary}", ephemeral=ephemeral)
        except Exception:
            logger.exception("Summarization failed", extra={"user_id": interaction.user.id})
            await interaction.followup.send("要約の生成に失敗しました。", ephemeral=ephemeral)

    # Voice Commands
    voice_group = app_commands.Group(name="voice", description="ボイスチャンネル管理")

    @voice_group.command(name="join", description="ボイスチャンネルに参加します。")
    async def voice_join(self, interaction: discord.Interaction) -> None:
        media_cog = self.bot.get_cog("MediaCog")
        if not media_cog:
            await interaction.response.send_message("Media機能が無効です。", ephemeral=True)
            return
        # Delegate to MediaCog.vc
        await media_cog.vc(interaction)

    @voice_group.command(name="leave", description="ボイスチャンネルから退出します。")
    async def voice_leave(self, interaction: discord.Interaction) -> None:
        media_cog = self.bot.get_cog("MediaCog")
        if not media_cog:
            await interaction.response.send_message("Media機能が無効です。", ephemeral=True)
            return
        # Delegate to MediaCog.leavevc
        await media_cog.leavevc(interaction)

    # Memory Commands
    memory_group = app_commands.Group(name="memory", description="記憶管理コマンド")

    @memory_group.command(name="clear", description="会話履歴を消去します。")
    async def memory_clear(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        count = await self._store.clear_conversations(str(interaction.user.id))
        await interaction.followup.send(f"{count} 件の会話履歴を消去しました。", ephemeral=True)

    @app_commands.command(name="test_all", description="全機能の診断テストを実行します。")
    @app_commands.describe(ephemeral="自分だけに表示するかどうか (デフォルト: True)")
    async def test_all(self, interaction: discord.Interaction, ephemeral: bool = True) -> None:
        """Run a full system diagnostic check."""
        await interaction.response.defer(ephemeral=ephemeral)
        
        report = []
        # 1. VoiceVox Check
        media_cog = self.bot.get_cog("MediaCog")
        if media_cog:
            try:
                speakers = await media_cog._voice_manager._tts.get_speakers()
                if speakers:
                    report.append(f"✅ VoiceVox: OK ({len(speakers)} speakers)")
                else:
                    report.append("⚠️ VoiceVox: Connected but no speakers found")
            except Exception as e:
                report.append(f"❌ VoiceVox: Error ({e})")
        else:
            report.append("❌ MediaCog: Not loaded")

        # 2. Database Check
        try:
            await self._store.get_privacy(interaction.user.id)
            report.append("✅ Database: OK")
        except Exception as e:
            report.append(f"❌ Database: Error ({e})")

        # 3. Google Search Check
        if self._search_client.enabled:
            report.append("✅ Google Search: Configured")
        else:
            report.append("⚠️ Google Search: Not configured")

        # 4. Vision API Check
        try:
            from ..utils.image_tools import analyze_image_v2
            report.append("✅ Vision API: Module loaded")
        except ImportError:
            report.append("❌ Vision API: Module missing")
            
        # 5. LLM Check
        try:
            await self._llm.chat([{"role": "user", "content": "ping"}], temperature=0.1)
            report.append("✅ LLM: OK")
        except Exception as e:
             report.append(f"❌ LLM: Error ({e})")

        await interaction.followup.send("\n".join(report), ephemeral=ephemeral)

    async def _get_voice_channel_info(self, guild: discord.Guild, channel_name: Optional[str] = None, user: Optional[discord.Member] = None) -> str:
        target_channel = None
        if channel_name:
            # Fuzzy match channel name
            target_channel = discord.utils.find(lambda c: isinstance(c, discord.VoiceChannel) and channel_name.lower() in c.name.lower(), guild.voice_channels)
        elif user and user.voice:
            target_channel = user.voice.channel
        
        if not target_channel:
            return "ボイスチャンネルが見つかりませんでした。"
            
        members = [m.display_name for m in target_channel.members]
        return f"チャンネル '{target_channel.name}' (ID: {target_channel.id})\n参加人数: {len(members)}人\n参加者: {', '.join(members)}"

    async def _build_system_prompt(self, message: discord.Message) -> str:
        guild = message.guild
        guild_name = guild.name if guild else "Direct Message"
        member_count = guild.member_count if guild else "Unknown"
        channel_name = message.channel.name if hasattr(message.channel, "name") else "Unknown"
        user_name = message.author.display_name

        # DYNAMIC TOOL LOADING (RAG)
        all_tools = self._get_tool_schemas()
        # Select relevant tools based on User Message Content
        relevant_tools = self._select_tools(message.content, all_tools)
        
        # Clean tags before injecting
        clean_tools = []
        for t in relevant_tools:
            t_copy = t.copy()
            if "tags" in t_copy: del t_copy["tags"]
            clean_tools.append(t_copy)

        tools_json = json.dumps(clean_tools, ensure_ascii=False)

        base = (
            f"You are ORA, a highly advanced AI assistant powered by **Ministral 3 (14B)**.\n"
            f"Current Server: {guild_name}\n"
            f"Member Count: {member_count}\n"
            f"Current Channel: {channel_name}\n"
            f"**CRITICAL INSTRUCTION**:\n"
            f"1. **LANGUAGE**: You MUST ALWAYS reply in **JAPANESE** (日本語).\n"
            f"   - Even if the user speaks English, reply in Japanese unless explicitly asked to speak English.\n"
            f"2. **CHARACTER & CAPABILITIES**: You are ORA. Be helpful, polite, and intelligent.\n"
            f"   - **REASONING**: You are built on Ministral 3, known for advanced logic and reasoning. Use this to think step-by-step for complex questions.\n"
            f"   - **INTERNAL KNOWLEDGE**: Your creator is **YoneRai12**. Mention this only if asked.\n"

            f"\n"
            f"3. **Search Summarization**: When using `google_search`:\n"
            f"   - Summarize multiple results into bullet points.\n"
            f"   - Do not repeat the same info.\n"
            f"   - Keep it concise (150-300 chars).\n"
            f"4. **IMAGE ANALYSIS**: \n"
            f"   - If the user provides an image:\n"
            f"     - **USE YOUR EYES.** You have native vision capabilities.\n"
            f"     - Analyze every detail: text, charts, handwriting, and layout.\n"
            f"     - **DO NOT** use `music_play` for image analysis.\n"
            f"     - If the image is unclear, ask for clarification.\n"
            f"4. **COMPLEX TASK HANDLING**:\n"
            f"   - If the task is HARD (Math, Logic, Coding, Graphs), you MUST use the `start_thinking` tool FIRST.\n"
            f"   - **Do NOT** try to solve it immediately with the standard model.\n"
            f"   - Example: {{ \"tool\": \"start_thinking\", \"args\": {{ \"reason\": \"Solving calculus problem\" }} }}\n"

            f"\n"
            f"## available_tools\n{tools_json}\n"
            f"\n"
            f"## Tool Usage Instruction\n"
            f"1. **WHEN TO USE**: Use a tool ONLY if you need to perform an action (Search, System Control, etc.).\n"
            f"2. **IMPLICIT TRIGGERS** (Action = Tool):\n"
            f"   - 'Come here', 'Join', 'きて' -> `join_voice_channel`\n"
            f"   - 'Leave', 'Bye', 'バイバイ' -> `leave_voice_channel`\n"
            f"   - 'Play X', 'Sing X', 'X流して' -> `music_play` (args: {{ \"query\": \"X\" }})\n"
            f"   - 'Repeat', 'Loop', 'リピート' -> `music_control` (args: {{ \"action\": \"loop_on\" }})\n"
            f"   - 'Skip', 'Next', 'スキップ' -> `music_control` (args: {{ \"action\": \"skip\" }})\n"
            f"   - 'Stop', 'Pause', '止めて' -> `music_control` (args: {{ \"action\": \"stop\" }})\n"
            f"   - 'Play previous', 'Play last song', 'Go back' -> `music_control` (args: {{ \"action\": \"replay_last\" }})\n"
            f"   - 'Who is X', 'Xとは', 'Xの詳細', 'X's info' -> `find_user` (args: {{ \"name_query\": \"X\" }})\n"
            f"   - 'Search X', 'Google X', '調べて' -> `google_search`\n"
            f"   - 'Volume X', 'Open X' -> `system_control`\n"
            f"   - 'Volume X', 'Open X' -> `system_control`\n"
            f"   - 'Shiritori', 'しりとりしよう' -> `shiritori` (args: {{ \"action\": \"start\" }})\n"
            f"   - **IMAGE GENERATION RULE (STRICT)**:\n"
            f"     - **KEYWORD REQUIRED**: You MUST ONLY use `generate_image` if the user's message contains the Japanese keyword '画像生成'.\n"
            f"     - **VISION PRIORITY**: If the user attaches an image, DO NOT generate an image. Use your vision capabilities to analyze it instead.\n"
            f"     - **TRANSLATION**: If triggered, translate the prompt to English.\n"
            f"     - Example: '画像生成 猫' -> args: {{ \"prompt\": \"cat, masterpiece...\" }}\n"
            f"   - **SHIRITORI GAME RULES**:\n"
            f"     - ALWAYS use the `shiritori` tool when the user plays a word. Args: `action='play'`, `word`, `reading`.\n"
            f"     - If the tool says 'User Move Valid', YOU MUST generate a response word starting with the specified character.\n"
            f"     - BEFORE replying, you MUST verify your own word using `shiritori` tool with `action='check_bot'`.\n"
            f"     - If 'check_bot' returns Invalid, pick a different word and check again.\n"
            f"     - Only reply to the user once 'check_bot' returns Valid.\n"
            f"   - **SINGING/HUMMING DETECTION**: \n"
            f"     - If the user's input looks like song lyrics (e.g., 'Never gonna give you up...'), **DO NOT** just reply with text.\n"
            f"     - Instead, ASK: 'Is that [Song Name]? Shall I play it?' (e.g., '今の曲は[Song Name]ですか？流しますか？')\n"
            f"     - If the user says 'Yes' or 'Play', THEN use `music_play`.\n"
            f"3. **HOW TO USE**: Output a JSON block in this format:\n"
            f"```json\n"
            f"{{\n"
            f"  \"tool\": \"tool_name\",\n"
            f"  \"args\": {{ \"arg_name\": \"value\" }}\n"
            f"}}\n"
            f"```\n"
            f"4. **NORMAL CHAT**: If *NO* action is implied (e.g., answering a question, vision analysis), just reply normally in Japanese.\n"
            f"Example: use `google_search` for 'Discord bot':\n"
            f"```json\n"
            f"{{ \"tool\": \"google_search\", \"args\": {{ \"query\": \"Discord bot\" }} }}\n"
            f"```\n"
        )
        
        # Vision Instruction
        if self.bot.user:
             base += f"\nMy name is {self.bot.user.name}.\n"

        base += (
            "\n[VISION CAPABILITY ENABLED: Qwen2.5-VL]\n"
            "You have state-of-the-art vision capabilities.\n"
            "Read text, solve math, and analyze scenes directly from the image.\n"
            "You do NOT need OCR text; trust your eyes.\n"
            "\n"
            "**FINAL ENFORCEMENT**:\n"
            "1. If the task is complex, use `start_thinking`. Do NOT answer directly.\n"
            "2. If the user asks to **Play Music** (e.g. '流して'), output `music_play` tool JSON.\n"
            "3. If the user asks for **Image Generation** (e.g. '画像生成'), output `generate_image` tool JSON.\n"
            "4. If the user asks for **Real-time Info**, **Weather**, **News**, or **Prices**, you MUST use `google_search`.\n"
            "   - Query Example: { \"tool\": \"google_search\", \"args\": { \"query\": \"Tokyo weather tomorrow\" } }\n"
            "5. **Do NOT** just reply with text if a tool is needed. USE THE TOOL."
        )
        
        return base

    async def process_message_queue(self):
        """Process queued messages after image generation completes."""
        if not self.message_queue:
            return
            
        logger.info(f"Processing {len(self.message_queue)} queued messages...")
        
        # Process strictly in order
        while self.message_queue:
            # Queue now stores (message, prompt) tuples
            item = self.message_queue.pop(0)
            if isinstance(item, tuple):
                msg, prompt = item
            else:
                # Fallback for old queue items if any (shouldn't happen after restart)
                msg = item
                prompt = msg.content # Best effort
            
            try:
                # Add a small delay to prevent rate limits
                await asyncio.sleep(1)
                await msg.reply("お待たせしました！回答を作成します。", mention_author=True)
                # Correctly pass the preserved prompt
                await self.handle_prompt(msg, prompt)
            except Exception as e:
                logger.error(f"Error processing queued message from {msg.author}: {e}")

    async def _execute_tool(self, tool_name: str, args: dict, message: discord.Message, status_manager: Optional[StatusManager] = None) -> str:
        try:
            # Update Status (Start)
            if status_manager:
                await status_manager.next_step(f"ツール使用中 ({tool_name})")

            if tool_name in {"create_file"}:
                if tool_name == "create_file" and not self._check_permission(message.author.id, "owner"):
                    return "Permission denied. This tool is restricted to the bot owner."

            if tool_name == "google_search":
                try:
                    query = args.get("query")
                    if not query: return "Error: No query provided."
                    
                    # Notify status
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

            if tool_name == "music_play":
                query = args.get("query")
                if not query:
                    return "Error: Missing query."
                
                media_cog = self.bot.get_cog("MediaCog")
                if media_cog:
                    # Use helper method
                    # Correctly get context first
                    ctx = await self.bot.get_context(message)
                    await media_cog.play_from_ai(ctx, query)
                    return f"Music request sent: {query}"
                return "Media system not available."

            elif tool_name == "music_control":
                action = args.get("action")
                media_cog = self.bot.get_cog("MediaCog")
                if media_cog:
                    ctx = await self.bot.get_context(message)
                    await media_cog.control_from_ai(ctx, action)
                    return f"Music control sent: {action}"
                return "Media system not available."

            # --- Video / Vision / Voice (Placeholders) ---
            # --- 3. Specialized Tools (TTS / Vision) ---
            elif tool_name == "tts_speak":
                text = args.get("text")
                if not text: return "Error: No text provided."
                
                # Check for T5Gemma Resources
                # Note: Actual inference requires loading the model with XCodec2. 
                # For now, we confirm files exist and fallback to system voice to keep bot stable.
                t5_res_path = r"L:\ai_models\huggingface\Aratako_T5Gemma-TTS-2b-2b-resources"
                if os.path.exists(t5_res_path):
                     logger.info("T5Gemma Resources detected.")
                
                # Fallback to MediaCog (VoiceVox/System) - Safest for now
                media_cog = self.bot.get_cog("MediaCog")
                if media_cog:
                    ctx = await self.bot.get_context(message)
                    await media_cog.speak(ctx, text)
                    return f"Spoken via System Voice (T5Gemma model ready, integration pending): {text}"
                return "Voice system not available."

            elif tool_name == "segment_objects":
                # SAM 3 Implementation (Official Repo)
                try:
                    sam3_path = r"L:\ai_models\github\sam3"
                    if os.path.exists(sam3_path):
                         # In a real scenario, we would sys.path.append(sam3_path) and import sam3
                         # For now, we signify it marks as available.
                         return f"SAM 3 (Official) detected at {sam3_path}. Ready for inference tasks."
                    
                    # Fallback to SAM 2
                    sam2_path = r"L:\ai_models\huggingface\facebook_sam2_hiera_large"
                    if os.path.exists(sam2_path):
                         return "SAM 3 not found, but SAM 2 is ready."
                    
                    return "Vision models not found."
                    
                except Exception as e:
                    return f"Vision Error: {e}"

            # --- 4. Video Generation (Placeholder) ---
            elif tool_name in ["generate_video", "get_video_models", "change_video_model", "analyze_video"]:
                return f"⚠️ Feature '{tool_name}' is currently under development. Coming soon!"


            elif tool_name == "create_file":
                # LOCKDOWN: Creator Only
                if not self._check_permission(message.author.id, "creator"):
                    return "Permission denied. Creator only."

                filename = args.get("filename")
                content = args.get("content")
                if not filename or not content:
                    return "Filename and content are required."
                
                # Security check: Regex for safe filename (Alphanumeric, dot, dash, underscore)
                import re
                if not re.match(r"^[a-zA-Z0-9_\-\.]+$", filename):
                     return "Invalid filename. Use only alphanumeric characters, dots, dashes, and underscores."
                
                if ".." in filename or "/" in filename or "\\" in filename:
                    return "Invalid filename."
                
                base = Path("./ora_files")
                base.mkdir(exist_ok=True)
                path = base / filename
                try:
                    async with aiofiles.open(path, "w", encoding="utf-8") as f:
                        await f.write(content)
                    return f"File created: {path}"
                except Exception as e:
                    return f"Failed to create file: {e}"

            elif tool_name == "get_server_info":
                guild = message.guild
                if not guild: return "Error: Not in a server."
                # Count statuses and devices
                counts = {"online": 0, "idle": 0, "dnd": 0, "offline": 0}
                devices = {"mobile": 0, "desktop": 0, "web": 0}

                for m in guild.members:
                    s = str(m.status)
                    if s in counts:
                        counts[s] += 1
                    else:
                        counts["offline"] += 1
                    
                    if str(m.mobile_status) != "offline": devices["mobile"] += 1
                    if str(m.desktop_status) != "offline": devices["desktop"] += 1
                    if str(m.web_status) != "offline": devices["web"] += 1
                        
                logger.info(f"get_server_info: Guild={guild.name}, API_Count={guild.member_count}, Cache_Count={len(guild.members)}")
                logger.info(f"get_server_info: Computed Status={counts}, Devices={devices}")

                # Clarify keys for LLM
                final_counts = {
                    "online (active)": counts["online"],
                    "idle (away)": counts["idle"],
                    "dnd (do_not_disturb)": counts["dnd"],
                    "offline (invisible)": counts["offline"]
                }
                total_online = counts["online"] + counts["idle"] + counts["dnd"]

                return json.dumps({
                    "name": guild.name,
                    "id": guild.id,
                    "member_count": guild.member_count,
                    "cached_member_count": len(guild.members),
                    "status_counts": final_counts,
                    "total_online_members": total_online,
                    "device_counts": devices,
                    "owner_id": guild.owner_id,
                    "created_at": str(guild.created_at)
                }, ensure_ascii=False)
            
            elif tool_name == "generate_image":
                prompt = args.get("prompt", "")
                neg = args.get("negative_prompt", "")
                
                # 1. Keyword Blocklist (Pre-check)
                # Legacy Handler Redirect
                # The actual handler is unified below, but we keep this block clean to avoid errors.
                # Just call the new logic directly here to consolidate.
                try:
                    from ..views.image_gen import AspectRatioSelectView
                    # Force FLUX
                    view = AspectRatioSelectView(self, prompt, neg, model_name="FLUX.2")
                    await message.reply(f"🎨 **画像生成アシスタント**\nLLMが生成意図を検出しました。\nPrompt: `{prompt}`\nアスペクト比を選択して生成を開始してください。", view=view)
                    return "Image Generation Menu Displayed."
                except Exception as e:
                    logger.error(f"Failed to launch image gen view: {e}")
                    return f"Error: {e}"
            
            elif tool_name == "get_current_model":
                return "Current Model: FLUX.2 (ComfyUI backend)"

            elif tool_name == "change_model":
                return "Model switching is managed via ComfyUI workflows. Please use Style Selector."

            elif tool_name == "find_user":
                query = args.get("name_query")
                if not query: return "Error: Missing name_query."
                guild = message.guild
                if not guild: return "Error: Not in a server."

                if not guild: return "Error: Not in a server."

                import re
                found_members = []
                
                # 0. Check for ID or Mention <@123> or <@!123> or 123
                id_match = re.search(r"^<@!?(\d+)>$|^(\d+)$", query.strip())
                if id_match:
                    user_id = int(id_match.group(1) or id_match.group(2))
                    logger.info(f"find_user: Detected ID {user_id}")
                    try:
                        # Fetch member by ID (works for offline too)
                        member = await guild.fetch_member(user_id)
                        found_members.append(member)
                        logger.info(f"find_user: Found member {member.display_name} in guild")
                    except discord.NotFound:
                        # User not in guild, try fetching user globally to confirm existence
                        try:
                            user = await self.bot.fetch_user(user_id)
                            logger.info(f"find_user: Found user {user.name} globally (not in guild)")
                            # Return special result for "Not in server"
                            return json.dumps([{
                                "name": user.name,
                                "display_name": user.display_name,
                                "id": user.id,
                                "bot": user.bot,
                                "status": "NOT_IN_SERVER",
                                "joined_at": "N/A"
                            }], ensure_ascii=False)
                        except discord.NotFound:
                             logger.warning(f"find_user: User {user_id} does not exist at all")
                    except discord.HTTPException as e:
                        logger.warning(f"Failed to fetch member {user_id}: {e}")

                # If found by ID (in guild), return immediately (unique)
                if found_members:
                    pass # Proceed to formatting
                else:
                    # 1. Search Cache (Linear Search) for Name/Nick/Display
                    # This covers online members and cached offline members
                    query_lower = query.lower()
                    
                    for m in guild.members:
                        if (query_lower in m.name.lower() or 
                            query_lower in m.display_name.lower() or 
                            (m.global_name and query_lower in m.global_name.lower())):
                            found_members.append(m)
                    
                    # 2. If few results, try API Search (good for fully offline users not in cache)
                    if len(found_members) < 5:
                        try:
                            # query_members searches username and nickname
                            api_results = await guild.query_members(query, limit=5)
                            for m in api_results:
                                if m.id not in [existing.id for existing in found_members]:
                                    found_members.append(m)
                        except Exception as e:
                            logger.warning(f"API member search failed: {e}")

                if not found_members:
                    return f"No users found matching '{query}'."

                # Limit results
                found_members = found_members[:10]
                
                results = []
                for m in found_members:
                    status = str(m.status) if hasattr(m, "status") else "unknown"
                    results.append({
                        "name": m.name,
                        "display_name": m.display_name,
                        "id": m.id,
                        "bot": m.bot,
                        "status": status,
                        "joined_at": str(m.joined_at.date()) if m.joined_at else "Unknown"
                    })
                
                return json.dumps(results, ensure_ascii=False)

            elif tool_name == "get_channels":
                guild = message.guild
                if not guild: return "Error: Not in a server."
                channels = []
                for ch in guild.channels:
                    kind = "text" if isinstance(ch, discord.TextChannel) else \
                           "voice" if isinstance(ch, discord.VoiceChannel) else \
                           "category" if isinstance(ch, discord.CategoryChannel) else "other"
                    channels.append({"id": ch.id, "name": ch.name, "type": kind})
                return json.dumps(channels[:50], ensure_ascii=False) # Limit to 50
                
            elif tool_name == "change_voice":
                char_name = args.get("character_name")
                if not char_name: return "Error: Missing character_name."
                
                # Mapping (Voicevox Speaker IDs)
                # 3: Zundamon (Normal), 1: Metan (Normal), 8: Tsumugi (Normal), 9: Ritsu (Normal), 10: Hau (Normal), 11: Takehiro (Normal)
                # These are examples, check your Voicevox version. Assuming standard.
                mapping = {
                    "zundamon": 3, "ずんだもん": 3,
                    "metan": 2, "shikokumetan": 2, "四国めたん": 2, "めたん": 2,
                    "tsumugi": 8, "kasukatsumugi": 8, "春日部つむぎ": 8, "つむぎ": 8,
                    "ritsu": 9, "namiritsu": 9, "波音リツ": 9, "リツ": 9,
                    "hau": 10, "ameharehau": 10, "雨晴はう": 10, "はう": 10,
                    "takehiro": 11, "kuronotakehiro": 11, "玄野武宏": 11, "武宏": 11,
                    # Add more as needed
                }
                
                # Normalize input
                key = char_name.lower().replace(" ", "")
                speaker_id = mapping.get(key)
                
                if speaker_id is None:
                    return f"Error: Unknown character '{char_name}'. Available: zundamon, metan, tsumugi, ritsu, hau, takehiro."
                
                media_cog = self.bot.get_cog("MediaCog")
                if media_cog:
                    # VoiceManager is inside MediaCog, but private.
                    # We should expose a method or access it. 
                    # MediaCog has _voice_manager
                    media_cog._voice_manager.set_user_speaker(message.author.id, speaker_id)
                    return f"Voice changed to {char_name} (ID: {speaker_id})."
                return "Media system not available."

            # Naive join_voice_channel removed (Duplicate)


            elif tool_name == "get_roles":
                guild = message.guild
                if not guild: return "Error: Not in a server."
                roles = [{"id": r.id, "name": r.name} for r in guild.roles]
                return json.dumps(roles[:50], ensure_ascii=False)

            # ... (Keep existing tools like google_search, get_system_stats, etc.)
            # I need to make sure I don't delete them.
            # The replacement block covers 552-800.
            # I should include the existing logic for other tools.
            
            if tool_name == "google_search":
                query = args.get("query")
                if not query: return "Error: Missing query."
                if not self._search_client.enabled: return "Error: Search API disabled."
                
                results = await self._search_client.search(query, limit=5)
                if not results: return f"No results found for query '{query}'. Please try a different keyword."
                
                # Create/Send Embed
                # SearchClient now returns list of dicts: title, link, snippet, thumbnail
                
                embed = EmbedFactory.create_search_embed(query, results)
                try:
                    await message.channel.send(embed=embed)
                except discord.Forbidden:
                    logger.warning("Missing permissions to send embeds for google_search.")
                except Exception as e:
                    logger.error(f"Failed to send search embed: {e}")
                
                # IMPORTANT: Return the snippet content to the LLM so it can answer the user's question!
                # The user complain about "just showing links".
                lines = []
                for i, r in enumerate(results):
                    lines.append(f"{i+1}. {r.get('title')}\n   URL: {r.get('link')}\n   Content: {r.get('snippet')}")
                
                return "\n\n".join(lines)

            elif tool_name == "get_system_stats":
                # LOCKDOWN: Creator Only (contains sensitive info)
                if not self._check_permission(message.author.id, "creator"):
                    return "Permission denied. Creator only."
                
                # CPU / Mem / Disk
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # GPU Stats (nvidia-smi)
                gpu_report = await _get_gpu_stats()
                
                # Create Embed
                fields = {
                    "CPU Usage": f"{cpu}%",
                    "Memory": f"{mem.percent}% ({mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB)",
                    "Disk (C:)": f"{disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"
                }
                if gpu_report:
                     fields["GPU Info"] = gpu_report
                
                embed = EmbedFactory.create_info_embed("System Stats", "Current system status report.", fields)
                try:
                    await message.channel.send(embed=embed)
                except discord.Forbidden:
                    logger.warning("Missing permissions to send embeds for get_system_stats.")
                except Exception as e:
                    logger.error(f"Failed to send stats embed: {e}")
                    # Fallback to text detail if embed fails
                    return f"System Stats (Embed Failed): CPU {cpu}%, Mem {mem.percent}%"
                
                return "System stats report sent as Embed."

            elif tool_name == "get_role_members":
                role_name = args.get("role_name", "").lower()
                if not message.guild: return "Error: Not in a server."
                
                target_role = None
                # Special Handle for @everyone
                if role_name in ["@everyone", "everyone", "all"]:
                    target_role = message.guild.default_role
                else:
                    target_role = discord.utils.find(lambda r: role_name in r.name.lower(), message.guild.roles)
                
                if not target_role: return "Role not found."
                
                # Sort members by status/activity? Just list names.
                members = [m.display_name for m in target_role.members]
                count = len(members)
                # Truncate if too many
                if count > 50:
                    return f"Members ({count} total): {', '.join(members[:50])}..."
                return f"Members ({count}): {', '.join(members)}"

            elif tool_name == "get_voice_channel_info":
                channel_name = args.get("channel_name")
                return await self._get_voice_channel_info(message.guild, channel_name, message.author)
            
            elif tool_name == "join_voice_channel":
                media_cog = self.bot.get_cog("MediaCog")
                if not media_cog:
                    return "Media functionality is disabled."
                
                # Determine channel
                channel = None
                if args.get("channel_name"):
                     name = args["channel_name"]
                     channel = discord.utils.find(lambda c: isinstance(c, discord.VoiceChannel) and name.lower() in c.name.lower(), message.guild.voice_channels)
                elif isinstance(message.author, discord.Member) and message.author.voice:
                     channel = message.author.voice.channel
                
                if not channel:
                    return "Could not find a voice channel to join. Please join one first."
                
                # Call MediaCog logic
                try:
                    from ..utils.voice_manager import VoiceConnectionError
                    vc = await media_cog._voice_manager.ensure_voice_client(message.author)
                    if vc:
                         media_cog._voice_manager.auto_read_channels[message.guild.id] = message.channel.id
                         await media_cog._voice_manager.play_tts(message.author, "接続しました")
                         return f"Joined voice channel: {vc.channel.name}. Auto-read enabled."
                    else:
                         return "Failed to join voice channel (Unknown reason)."
                except VoiceConnectionError as e:
                    return f"Failed to join voice channel. Reason: {e}"
                except Exception as e:
                    logger.exception("Unexpected error in join_voice_channel")
                    return f"Error: {e}"
            elif tool_name == "leave_voice_channel":
                media_cog = self.bot.get_cog("MediaCog")
                if not media_cog:
                    return "Media functionality is disabled."
                
                if message.guild.voice_client:
                    await message.guild.voice_client.disconnect()
                    media_cog._voice_manager.auto_read_channels.pop(message.guild.id, None)
                    return "Disconnected from voice channel."
                return "Not connected to any voice channel."

            elif tool_name == "google_shopping_search":
                query = args.get("query")
                if not query: return "Error: Missing query."
                if not self._search_client.enabled: return "Error: Search API disabled."
                results = await self._search_client.search(query, limit=5, engine="google_shopping")
                if not results: return f"No shopping results found for '{query}'."
                # results is list of dicts
                return "\n".join([f"{i+1}. {r.get('title')} ({r.get('link')})" for i, r in enumerate(results)])

            elif tool_name == "system_check":
                # Icons (Dynamic Lookup for 'rode' and 'conp')
                e_load = discord.utils.get(self.bot.emojis, name="rode")
                e_ok = discord.utils.get(self.bot.emojis, name="conp")
                
                ICON_LOAD = str(e_load) if e_load else "⌛" 
                ICON_OK = str(e_ok) if e_ok else "✅" 
                ICON_ERR = "❌"

                # Create initial status embed
                embed = discord.Embed(
                    title="🩺 ORA System Diagnostics",
                    description="Running automated system checks...",
                    color=discord.Color.blue()
                )
                status_msg = await message.reply(embed=embed)
                
                # Helper to update status
                # We save the fields state to update them
                fields_state = []

                async def update_field(name, status, detail, is_error=False):
                    # Check if field exists, update it
                    found = False
                    icon = ICON_ERR if is_error else (ICON_LOAD if status == "loading" else ICON_OK)
                    
                    # Rebuild fields list
                    new_fields = []
                    for f in fields_state:
                        if f["name"] == name:
                            f["value"] = f"{icon} {detail}"
                            found = True
                        new_fields.append(f)
                    
                    if not found:
                        new_fields.append({"name": name, "value": f"{icon} {detail}"})
                        fields_state.append({"name": name, "value": f"{icon} {detail}"})
                    
                    # Apply to Embed
                    embed.clear_fields()
                    for f in new_fields:
                        embed.add_field(name=f["name"], value=f["value"], inline=False)
                    await status_msg.edit(embed=embed)
                
                # 1. Database Check
                await update_field("Database", "loading", "Checking connection...")
                try:
                    await self._store.get_privacy(message.author.id)
                    await update_field("Database", "done", "Connected (SQLite)")
                except Exception as e:
                    await update_field("Database", "done", f"Error: {e}", is_error=True)

                # 2. Web Search
                await update_field("Web Search", "loading", "Verifying API...")
                if self._search_client.enabled:
                    engine = getattr(self._search_client, "engine", "Google/DuckDuckGo")
                    await update_field("Web Search", "done", f"Active ({engine})")
                else:
                    await update_field("Web Search", "done", "Disabled (No API Key)", is_error=True)

                # 3. Vision Capability (Automated Test)
                # Load Test Image
                VISION_LABEL = "Vision (Qwen2.5-VL)"
                await update_field(VISION_LABEL, "loading", "Loading Test Image...")
                vision_ok = False
                try:
                    import io, base64, os
                    img_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "test_image.png")
                    
                    b64_img = None
                    if os.path.exists(img_path):
                        with open(img_path, "rb") as f:
                            img_data = f.read()
                            b64_img = base64.b64encode(img_data).decode('utf-8')
                        await update_field(VISION_LABEL, "loading", "Running Inference...")
                    elif message.attachments:
                        # Fallback to attachment
                        target_att = message.attachments[0]
                        async with aiohttp.ClientSession() as session:
                            async with session.get(target_att.url) as resp:
                                img_data = await resp.read()
                                b64_img = base64.b64encode(img_data).decode('utf-8')
                        await update_field(VISION_LABEL, "loading", "Running Inference (Attachment)...")
                    else:
                        await update_field(VISION_LABEL, "done", "Skipped (No test image found)", is_error=True)

                    if b64_img:
                        # Verification Prompt
                        vis_messages = [
                            {"role": "system", "content": "Analyze this image and describe the content briefly."},
                            {"role": "user", "content": [
                                {"type": "text", "text": "What is shown in this image?"},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                            ]}
                        ]
                        
                        vis_response = await self._llm.chat(messages=vis_messages, temperature=0.1)
                        
                        if vis_response:
                            await update_field(VISION_LABEL, "done", f"Pass: '{vis_response[:40]}...'")
                            vision_ok = True
                        else:
                            await update_field(VISION_LABEL, "done", "Failed: Empty Response", is_error=True)

                except Exception as e:
                    await update_field(VISION_LABEL, "done", f"Error: {e}", is_error=True)

                # 4. Voice Generation (VOICEVOX)
                await update_field("Voice (VOICEVOX)", "loading", "Testing Engine...")
                media_cog = self.bot.get_cog("MediaCog")
                if media_cog:
                    try:
                        speakers = await media_cog._voice_manager._tts.get_speakers()
                        if speakers:
                            await update_field("Voice (VOICEVOX)", "done", f"OK (Engine Ready with {len(speakers)} voices)")
                        else:
                            await update_field("Voice (VOICEVOX)", "done", "Connected but no voices found", is_error=True)
                    except Exception as e:
                        await update_field("Voice (VOICEVOX)", "done", f"Error: {e}", is_error=True)
                else:
                    await update_field("Voice (VOICEVOX)", "done", "TTS Module Not Loaded", is_error=True)

                # 5. Video Recognition (FFmpeg Check)
                await update_field("Video Recognition", "loading", "Checking FFmpeg...")
                try:
                    import shutil
                    if shutil.which("ffmpeg"):
                        # Get version?
                        # proc = await asyncio.create_subprocess_shell("ffmpeg -version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        # stdout, _ = await proc.communicate()
                        await update_field("Video Recognition", "done", "Ready (FFmpeg detected)")
                    else:
                        await update_field("Video Recognition", "done", "Missing FFmpeg (Video analysis impossible)", is_error=True)
                except Exception as e:
                    await update_field("Video Recognition", "done", f"Error: {e}", is_error=True)

                # 6. Core Services (Ports)
                async def check_port(host, port):
                    try:
                        _, writer = await asyncio.open_connection(host, port)
                        writer.close()
                        await writer.wait_closed()
                        return True
                    except:
                        return False

                # Check LLM (8001)
                await update_field("Brain (vLLM)", "loading", "Pinging Port 8001...")
                llm_ok = await check_port("127.0.0.1", 8001)
                if llm_ok:
                    await update_field("Brain (vLLM)", "done", "Online (Port 8001)")
                else:
                    await update_field("Brain (vLLM)", "done", "OFFLINE (Port 8001 Closed)", is_error=True)

                # Check ComfyUI (8188)
                await update_field("Art (ComfyUI)", "loading", "Pinging Port 8188...")
                comfy_ok = await check_port("127.0.0.1", 8188)
                if comfy_ok:
                    await update_field("Art (ComfyUI)", "done", "Online (Port 8188)")
                else:
                    await update_field("Art (ComfyUI)", "done", "Offline (Port 8188)", is_error=True)

                embed.description = "✅ System Diagnostics Completed."
                embed.color = discord.Color.green()
                await status_msg.edit(embed=embed)
                
                return "[SILENT_COMPLETION]"
                if self._search_client.enabled:
                    report.append("✅ Google Search: Configured")
                else:
                    report.append("⚠️ Google Search: Not configured")

                # 4. Vision API Check
                try:
                    from ..utils.image_tools import analyze_image_v2
                    report.append("✅ Vision API: Module loaded")
                except ImportError:
                    report.append("❌ Vision API: Module missing")

                return "\n".join(report)

            elif tool_name == "create_channel":
                # Permission: Owner + Sub-Admin + VC Admin (Server Authority)
                if not self._check_permission(message.author.id, "vc_admin"):
                    return "Permission denied. Admin/VC Authority only."
                
                guild = message.guild
                if not guild: return "Error: Not in a server."
                
                name = args.get("name")
                ctype = args.get("type")
                cat_name = args.get("category_name")
                
                if not name or not ctype:
                    return "Error: Missing name or type."
                
                category = None
                if cat_name:
                    category = discord.utils.find(lambda c: c.name.lower() == cat_name.lower(), guild.categories)
                    if not category:
                        # Create category if not exists? Or fail?
                        # Let's try to create it if explicitly asked, but for now just fail or create without category
                        # User asked "in the text channel", implying category? 
                        # Let's just create the category if it doesn't exist? No, safer to just warn.
                        return f"Error: Category '{cat_name}' not found."
                
                try:
                    if ctype == "text":
                        ch = await guild.create_text_channel(name, category=category)
                    elif ctype == "voice":
                        ch = await guild.create_voice_channel(name, category=category)
                    elif ctype == "category":
                        ch = await guild.create_category(name)
                    else:
                        return "Error: Invalid channel type."
                    return f"Channel created: {ch.name} (ID: {ch.id})"
                except Exception as e:
                    return f"Failed to create channel: {e}"

            elif tool_name == "system_control":
                # LOCKDOWN: Creator Only (Dangerous)
                if not self._check_permission(message.author.id, "creator"):
                     return "Permission denied. Creator only."
                
                action = args.get("action")
                value = args.get("value")
                system_cog = self.bot.get_cog("SystemCog")
                if system_cog:
                    return await system_cog.execute_tool(message.author.id, action, value)

            elif tool_name == "start_thinking":
                reason = args.get("reason", "Complex task detected")
                
                # Get Resource Manager
                resource_cog = self.bot.get_cog("ResourceCog")
                if resource_cog:
                    # 1. Update Status
                    await status_manager.next_step(f"⚠️ {reason}のため、思考エンジンへ切り替え中...")
                    
                    # 2. Switch Model
                    await resource_cog.manager.switch_model("thinking")
                    
                    # 3. Update Status Again
                    await status_manager.next_step(f"🤔 じっくり思考中... ({reason})")
                    
                    # 4. Return Prompt for Re-Generation
                    # The LLM will receive this as Tool Output and continue generation
                    return "Thinking Mode Activated. You now have access to the Reasoning Model. Please re-analyze the user's request and provide the comprehensive solution."
                return "Thinking Engine not available."

            elif tool_name == "generate_image":
                # GUARD: Vision Priority (Attachments present -> No Gen)
                if message.attachments:
                    return "ABORT: Attachments detected. Priority: Vision Analysis. Do NOT generate an image."

                # GUARD: Strict Keyword Check ("画像生成")
                # We check the raw content (ignoring mentions slightly, but safest to lookat message.content)
                if "画像生成" not in message.content:
                    logger.info("Blocked generation: Missing '画像生成' keyword.")
                    return "ABORT: User requires strict keyword '画像生成' to trigger generation."

                prompt = args.get("prompt")
                negative_prompt = args.get("negative_prompt", "")
                
                if not prompt: return "Error: Missing prompt."
                
                try:
                    # Unload LLM to free VRAM for ComfyUI
                    if self.llm:
                        asyncio.create_task(self.llm.unload_model())
                        await asyncio.sleep(3) # Wait for VRAM release
                        
                    from ..views.image_gen import AspectRatioSelectView
                    # Defaulting to FLUX model logic since we are in ComfyUI mode
                    view = AspectRatioSelectView(self, prompt, negative_prompt, model_name="FLUX.2")
                    await message.reply(f"🎨 **画像生成アシスタント**\nLLMが生成意図を検出しました。\nPrompt: `{prompt}`\nアスペクト比を選択して生成を開始してください。", view=view)
                    return "[SILENT_COMPLETION]"
                except Exception as e:
                    logger.error(f"Failed to launch image gen view: {e}")
                    return f"Error launching image generator: {e}"

            elif tool_name == "manage_user_voice":
                target_str = args.get("target_user")
                action = args.get("action")
                channel_str = args.get("channel_name")
                
                if not target_str or not action: return "Error: Missing arguments."
                
                guild = message.guild
                if not guild: return "Error: Not in a server."

                # Find Member
                import re
                target_member = None
                id_match = re.search(r"^<@!?(\d+)>$|^(\d+)$", target_str.strip())
                if id_match:
                    uid = int(id_match.group(1) or id_match.group(2))
                    target_member = guild.get_member(uid)
                if not target_member:
                    target_member = discord.utils.find(lambda m: target_str.lower() in m.name.lower() or target_str.lower() in m.display_name.lower(), guild.members)
                
                if not target_member:
                    return f"User '{target_str}' not found."

                # Permission Check (Modified)
                # Allow if: Creator OR Server Admin OR VC Admin OR Self-Target
                is_creator = self._check_permission(message.author.id, "creator")
                is_vc_admin = self._check_permission(message.author.id, "vc_admin")
                is_server_admin = message.author.guild_permissions.administrator if hasattr(message.author, "guild_permissions") else False
                is_self = (target_member.id == message.author.id)
                
                if not (is_creator or is_vc_admin or is_server_admin or is_self):
                    return "Permission denied. You can only manage yourself, or require VC Authority."

                if not target_member.voice:
                    return f"{target_member.display_name} is not in a voice channel."
                    return f"{target_member.display_name} is not in a voice channel."
                
                try:
                    if action == "disconnect":
                        await target_member.move_to(None)
                        return f"Disconnected {target_member.display_name} from voice channel."
                    
                    elif action == "move":
                        if not channel_str: return "Error: Destination channel required for move."
                        # Find Channel
                        dest_channel = discord.utils.find(lambda c: isinstance(c, discord.VoiceChannel) and channel_str.lower() in c.name.lower(), guild.voice_channels)
                        if not dest_channel:
                             return f"Voice channel '{channel_str}' not found."
                        
                        # Check User Limit
                        if dest_channel.user_limit > 0 and len(dest_channel.members) >= dest_channel.user_limit:
                            return f"Error: Destination '{dest_channel.name}' is full ({dest_channel.user_limit} users)."
                        
                        await target_member.move_to(dest_channel)
                        return f"Moved {target_member.display_name} to {dest_channel.name}."
                    
                    elif action == "summon":
                         dest_channel = message.author.voice.channel if message.author.voice else None
                         if not dest_channel:
                             return "Error: You must be in a Voice Channel to summon someone."
                         
                         # Check User Limit
                         if dest_channel.user_limit > 0 and len(dest_channel.members) >= dest_channel.user_limit:
                            return f"Error: Your channel '{dest_channel.name}' is full ({dest_channel.user_limit} users)."

                         await target_member.move_to(dest_channel)
                         return f"Summoned {target_member.display_name} to {dest_channel.name}."



                    elif action in ["mute_mic", "unmute_mic", "mute_speaker", "unmute_speaker"]:
                        # STRICT PERMISSION CHECK (No Self-Service for Moderation Tools)
                        if not (is_creator or is_vc_admin or is_server_admin):
                            return "Permission denied. Server VCMute/Deafen requires Admin or VC Authority."
                        
                        if action == "mute_mic":
                            await target_member.edit(mute=True)
                            return f"Server Muted (Mic) {target_member.display_name}."
                        elif action == "unmute_mic":
                            await target_member.edit(mute=False)
                            return f"Unmuted (Mic) {target_member.display_name}."
                        elif action == "mute_speaker":
                            # Explicitly set both to be sure
                            await target_member.edit(mute=True, deafen=True)
                            return f"Server Deafened (Speaker+Mic Mute) {target_member.display_name}."
                        elif action == "unmute_speaker":
                            await target_member.edit(deafen=False, mute=False)
                            return f"Undeafened (Speaker+Mic On) {target_member.display_name}."

                    else:
                        return f"Unknown action: {action}"

                except discord.Forbidden:
                    return "Error: Permission denied (Move Members required)."
                except Exception as e:
                    return f"Error managing voice: {e}"

            elif tool_name == "check_points":
                try:
                    target_user_input = args.get("target_user")
                    guild = message.guild
                    if not guild: return "Error: Not in a server."

                    target_member = None
                    if target_user_input:
                        import re
                        id_match = re.search(r"^<@!?(\d+)>$|^(\d+)$", target_user_input.strip())
                        if id_match:
                            uid = int(id_match.group(1) or id_match.group(2))
                            target_member = guild.get_member(uid)
                        if not target_member:
                            target_member = discord.utils.find(lambda m: target_user_input.lower() in m.name.lower() or target_user_input.lower() in m.display_name.lower(), guild.members)
                        
                        if not target_member:
                            return f"User '{target_user_input}' not found."
                        user_id = target_member.id
                        display_name = target_member.display_name
                    else:
                        user_id = message.author.id
                        display_name = message.author.display_name
                    
                    points = await self._store.get_points(user_id)
                    return f"💰 **{display_name}** さんのポイント: **{points:,}** pt"
                except Exception as e:
                     return f"Error checking points: {e}"

            elif tool_name == "set_timer":
                seconds = args.get("seconds")
                label = args.get("label", "Timer")
                if not seconds or seconds <= 0: return "Error: seconds must be positive integer."
                
                # Define simple task
                async def timer_task(s, lbl, msg):
                    await asyncio.sleep(s)
                    try:
                        await msg.reply(f"⏰ **タイマー終了!** ({lbl})\n{msg.author.mention}", mention_author=True)
                        # Sound/TTS
                        media_cog = self.bot.get_cog("MediaCog")
                        if media_cog and msg.guild.voice_client:
                             await media_cog.speak_text(msg.author, f"タイマー、{lbl}が終了しました。")
                    except Exception as ex:
                        logger.error(f"Timer callback failed: {ex}")
                
                # Fire and forget
                asyncio.create_task(timer_task(seconds, label, message))
                return f"Timer set for {seconds} seconds ({label})."

            elif tool_name == "set_alarm":
                time_str = args.get("time") # HH:MM
                label = args.get("label", "Alarm")
                if not time_str: return "Error: Missing time."
                
                now = datetime.datetime.now()
                try:
                    target = datetime.datetime.strptime(time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
                    if target < now:
                        target += datetime.timedelta(days=1)
                    
                    delay = (target - now).total_seconds()
                    
                    async def alarm_task(d, lbl, msg):
                         await asyncio.sleep(d)
                         try:
                            await msg.reply(f"⏰ **アラーム!** ({lbl})\n{msg.author.mention}", mention_author=True)
                            media_cog = self.bot.get_cog("MediaCog")
                            if media_cog and msg.guild.voice_client:
                                 await media_cog.speak_text(msg.author, f"アラームの時間です。{lbl}")
                         except Exception as ex:
                            logger.error(f"Alarm callback failed: {ex}")
                    
                    asyncio.create_task(alarm_task(delay, label, message))
                    return f"Alarm set for {target.strftime('%H:%M')} ({label})."
                except ValueError:
                    return "Error: Invalid time format. Use HH:MM."

            elif tool_name == "shiritori":
                action = args.get("action")
                word = args.get("word")
                reading = args.get("reading")
            
            # channel.id can be text or voice
            game = self.shiritori_games[message.channel.id]
            
            if action == "start":
                return game.start()
            
            elif action == "play":
                if not word or not reading:
                     return "Error: arguments 'word' and 'reading' are required."
                
                is_valid, msg, next_char = game.check_move(word, reading)
                if not is_valid:
                    return f"User Move Invalid: {msg}"
                else:
                    return f"User Move Valid! History updated. Next character must start with: 「{next_char}」. Now, YOU (AI) must generate a word starting with '{next_char}' and call this tool with action='check_bot', word='YOUR_WORD', reading='YOUR_READING' to verify it."
            
            elif action == "check_bot":
                if not word or not reading:
                     return "Error: arguments 'word' and 'reading' are required."
                
                # Check Bot Move
                is_valid, msg, next_char = game.check_move(word, reading)
                if not is_valid:
                    # Bot failed! ReAct loop allows it to see this error and try again.
                    return f"YOUR (AI) Move Invalid: {msg}. Please pick a DIFFERENT word starting with the correct character."
                else:
                    return f"Bot Move Valid! History updated. You can now reply to the user with: '{word} ({reading})! Next is {next_char}.'"
            
            elif tool_name == "say":
                text = args.get("message")
                target_channel_name = args.get("channel_name")
                
                if not text: return "Error: No message provided."
                
                target_channel = message.channel
                if target_channel_name:
                    found = discord.utils.find(lambda c: hasattr(c, 'name') and target_channel_name.lower() in c.name.lower(), message.guild.text_channels)
                    if found:
                        target_channel = found
                    else:
                        return f"Error: Channel '{target_channel_name}' not found."
                
                try:
                    await target_channel.send(text)
                    return f"Sent message to {target_channel.mention}"
                except Exception as e:
                    return f"Failed to send message: {e}"

            elif tool_name == "set_audio_volume":
                target = args.get("target") # music, tts
                value = args.get("value") # 0-200
                
                if not target or value is None:
                    return "Error: target and value (0-200) required."
                
                media_cog = self.bot.get_cog("MediaCog")
                if not media_cog:
                    return "Error: Media system not loaded."
                
                vol_float = float(value) / 100.0
                
                if target == "music":
                    media_cog._voice_manager.set_music_volume(message.guild.id, vol_float)
                    return f"Music Volume set to {value}%."
                elif target == "tts":
                    media_cog._voice_manager.set_tts_volume(message.guild.id, vol_float)
                    return f"TTS Volume set to {value}%."
                else:
                    return "Error: target must be 'music' or 'tts'."

            elif tool_name == "purge_messages":
                # Permission Check
                if not (message.author.guild_permissions.manage_messages or self._check_permission(message.author.id, "creator")):
                    return "Permission denied. Manage Messages required."

                limit = args.get("limit", 10)
                if not isinstance(message.channel, discord.TextChannel):
                    return "Error: Can only purge messages in Text Channels."
                
                deleted = await message.channel.purge(limit=limit)
                return f"Deleted {len(deleted)} messages."

            elif tool_name == "manage_pins":
                action = args.get("action") # pin, unpin
                msg_id = args.get("message_id")
                
                target_msg = None
                if msg_id:
                    try:
                        target_msg = await message.channel.fetch_message(int(msg_id))
                    except:
                        return f"Error: Message {msg_id} not found."
                elif message.reference:
                    target_msg = await message.channel.fetch_message(message.reference.message_id)
                else:
                    return "Error: Provide message_id or reply to a message."
                
                if action == "pin":
                    await target_msg.pin()
                    return f"Pinned message from {target_msg.author.display_name}."
                elif action == "unpin":
                    await target_msg.unpin()
                    return f"Unpinned message."
                else:
                    return "Error: action must be 'pin' or 'unpin'."
            
            elif tool_name == "create_thread":
                # Permission Check
                if not (message.author.guild_permissions.create_public_threads or self._check_permission(message.author.id, "creator")):
                    return "Permission denied. Create Public Threads required."

                name = args.get("name")
                
                if not isinstance(message.channel, discord.TextChannel):
                     return "Error: Can only create threads in Text Channels."
                
                thread = await message.channel.create_thread(name=name, auto_archive_duration=60)
                return f"Created thread: {thread.mention}"

            elif tool_name == "user_info":
                query = args.get("target_user")
                if not query: return "Error: target_user required."
                
                # Resolve User
                member = await self._resolve_user(message.guild, query)
                if not member: return f"User '{query}' not found."
                
                roles = ", ".join([r.name for r in member.roles if r.name != "@everyone"])
                embed = discord.Embed(title=f"User Info: {member.display_name}", color=member.color)
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="ID", value=str(member.id), inline=True)
                embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="Created Account", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="Roles", value=roles or "None", inline=False)
                
                await message.channel.send(embed=embed)
                return f"Displayed info for {member.display_name}"

            elif tool_name == "ban_user" or tool_name == "kick_user" or tool_name == "timeout_user":
                # Permission Check
                if not (message.author.guild_permissions.ban_members or self._check_permission(message.author.id, "creator")):
                    return "Permission denied. Ban/Kick members required."

                # Moderation Suite
                query = args.get("target_user")
                reason = args.get("reason", "No reason provided")
                
                if not query: return "Error: target_user required."
                member = await self._resolve_user(message.guild, query)
                if not member: return f"User '{query}' not found."
                
                try:
                    if tool_name == "ban_user":
                        await member.ban(reason=reason)
                        return f"⛔ Banned {member.display_name}. Reason: {reason}"
                    elif tool_name == "kick_user":
                        await member.kick(reason=reason)
                        return f"🦵 Kicked {member.display_name}. Reason: {reason}"
                    elif tool_name == "timeout_user":
                        minutes = args.get("minutes", 10)
                        from datetime import timedelta
                        duration = timedelta(minutes=int(minutes))
                        await member.timeout(duration, reason=reason)
                        return f"⏳ Timed out {member.display_name} for {minutes} mins. Reason: {reason}"
                except Exception as e:
                    return f"Moderation Action Failed: {e}"

            elif tool_name == "add_emoji":
                # Permission Check
                if not (message.author.guild_permissions.manage_emojis or self._check_permission(message.author.id, "creator")):
                    return "Permission denied. Manage Emojis required."

                name = args.get("name")
                url = args.get("image_url")
                
                if not name or not url: return "Error: name and image_url required."
                
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status != 200: return "Error: Failed to download image."
                            data = await resp.read()
                            
                    emoji = await message.guild.create_custom_emoji(name=name, image=data)
                    return f"Created emoji: {emoji} (Name: {emoji.name})"
                except Exception as e:
                    return f"Failed to create emoji: {e}"

            elif tool_name == "create_poll":
                # Permission Check
                if not (message.author.guild_permissions.manage_messages or self._check_permission(message.author.id, "creator")):
                    return "Permission denied. Manage Messages/Admin required."

                question = args.get("question")
                options = args.get("options") # pipe separated or list? Let's assume text description in LLM arg.
                # Simplest: "options" is a list in JSON
                if not question or not options: return "Error: question and options required."
                
                if isinstance(options, str):
                    options = options.split("|") # Fallback parsing
                
                # Emojis for 1-10
                emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
                
                desc = ""
                for i, opt in enumerate(options):
                    if i >= len(emojis): break
                    desc += f"{emojis[i]} {opt}\n"
                
                embed = discord.Embed(title=f"📊 {question}", description=desc, color=discord.Color.gold())
                poll_msg = await message.channel.send(embed=embed)
                
                for i, _ in enumerate(options):
                    if i >= len(emojis): break
                    await poll_msg.add_reaction(emojis[i])
                
                return f"Poll created: {poll_msg.jump_url}"

            elif tool_name == "create_invite":
                # Permission Check
                if not (message.author.guild_permissions.create_instant_invite or self._check_permission(message.author.id, "creator")):
                    return "Permission denied. Create Invite permissions required."

                max_age = args.get("minutes", 0) * 60 # 0 = infinite
                max_uses = args.get("uses", 0) # 0 = infinite
                
                invite = await message.channel.create_invite(max_age=max_age, max_uses=max_uses)
                return f"Invite Created: {invite.url} (Expires in {args.get('minutes', 0)} mins, Uses: {args.get('uses', 0)})"

            elif tool_name == "summarize_chat":
                limit = min(args.get("limit", 50), 100) # Safety cap
                
                history_texts = []
                async for msg in message.channel.history(limit=limit):
                    if msg.content:
                        history_texts.append(f"{msg.author.display_name}: {msg.content}")
                
                # Reverse to chrono order
                history_texts.reverse()
                return "\n".join(history_texts)
                # LLM will see this return value and then answer "Here is the summary..."

            elif tool_name == "remind_me":
                minutes = args.get("minutes")
                memo = args.get("message", "Reminder!")
                
                if not minutes: return "Error: minutes required."
                
                delay = int(minutes) * 60
                
                async def reminder_task(d, u, m, ch):
                    await asyncio.sleep(d)
                    await ch.send(f"⏰ {u.mention}, Reminder: {m}")
                    
                asyncio.create_task(reminder_task(delay, message.author, memo, message.channel))
                return f"Reminder set for {minutes} minutes."

            elif tool_name == "server_assets":
                 guild = message.guild
                 icon = guild.icon.url if guild.icon else "No Icon"
                 banner = guild.banner.url if guild.banner else "No Banner"
                 return f"Icon: {icon}\nBanner: {banner}"

            return "Unknown action"

            return f"Error: Unknown tool '{tool_name}'"

        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return f"Tool execution failed: {e}. Please check the logs for details."

    async def _build_history(self, message: discord.Message) -> list[dict]:
        history = []
        current_msg = message
        
        # Traverse reply chain (up to 5 messages)
        for _ in range(5):
            if not current_msg.reference:
                break
                
            ref = current_msg.reference
            if not ref.message_id:
                break
                
            try:
                # Try to get from cache first, then fetch
                if ref.cached_message:
                    prev_msg = ref.cached_message
                else:
                    prev_msg = await message.channel.fetch_message(ref.message_id)
                
                # Only include messages from user or bot
                is_bot = prev_msg.author.id == self.bot.user.id
                role = "assistant" if is_bot else "user"
                
                content = prev_msg.content.replace(f"<@{self.bot.user.id}>", "").strip()
                
                # Context Fix: If content is empty/short but has embeds, extract text from Embeds
                # This is crucial now that we use Card-Style responses (Embed only)
                if not content and prev_msg.embeds:
                    embed = prev_msg.embeds[0]
                    # Priority: Description -> specific fields -> Title
                    if embed.description:
                         content = embed.description
                    elif embed.title:
                         content = f"[{embed.title}]"
                    
                    # If it's a search/info card, maybe add fields?
                    # For now, description is usually the main answer in Chat Embeds.
                    # Search embeds don't have description usually, they have fields.
                    if not content and embed.fields:
                         # Reconstruct simple representation
                         field_texts = [f"{f.name}: {f.value}" for f in embed.fields]
                         content = "\n".join(field_texts)

                # Prepend User Name to User messages for better recognition
                if not is_bot and content:
                     content = f"[{prev_msg.author.display_name}]: {content}"
                
                if content:
                    # Truncate content to prevent Context Limit Exceeded (Error 400)
                    if len(content) > 1200:
                        content = content[:1200] + "... (truncated)"

                    # Check if the last added message (which is effectively the NEXT one in chronological order)
                    # has the same role. If so, merge them?
                    # BUT we are traversing backwards (insert(0)).
                    # So if history[0] (which is chronologically LATER) has same role, we can merge?
                    # No, usually we merge strictly during forward construction or post-processing.
                    # Simple approach: Insert raw, then normalize.
                    history.insert(0, {"role": role, "content": content})
                
                current_msg = prev_msg
                
            except (discord.NotFound, discord.HTTPException):
                break
        
        # Normalize History: Merge consecutive same-role messages
        # This is critical for models incorrectly handling consecutive user messages
        normalized_history = []
        if history:
            current_role = history[0]["role"]
            current_content = history[0]["content"]
            
            for msg in history[1:]:
                if msg["role"] == current_role:
                    # Merge content
                    current_content += f"\n{msg['content']}"
                else:
                    normalized_history.append({"role": current_role, "content": current_content})
                    current_role = msg["role"]
                    current_content = msg["content"]
            
            # Append final
            normalized_history.append({"role": current_role, "content": current_content})
            
        return normalized_history

    def _extract_json_objects(self, text: str) -> list[str]:
        """Extracts top-level JSON objects from text."""
        objects = []
        
        # Priority: Check for [TOOL_CALLS] hallucination format first.
        # If this format is present, standard brace matching might incorrectly grab the inner JSON args.
        if "[TOOL_CALLS]" in text:
            import re
            # Regex to capture tool name and args json
            # Allow (ARGS) or [ARGS] or just ARGS
            pattern = r"\[TOOL_CALLS\]\s*(\w+)\s*[\[\(]?ARGS[\]\)]?\s*(\{.*?\})"
            matches = re.finditer(pattern, text, re.DOTALL)
            found_regex = False
            for match in matches:
                found_regex = True
                tool_name = match.group(1)
                args_json = match.group(2)
                # Construct valid JSON string
                valid_call = f'{{"tool": "{tool_name}", "args": {args_json}}}'
                objects.append(valid_call)
                logger.warning(f"Recovered tool call from [TOOL_CALLS] format: {tool_name}")
            
            # If regex found something, return it immediately to avoid confusion
            if found_regex:
                return objects

        # Standard Extraction: Match balanced braces
        stack = 0
        start_index = -1
        
        for i, char in enumerate(text):
            if char == '{':
                if stack == 0:
                    start_index = i
                stack += 1
            elif char == '}':
                if stack > 0:
                    stack -= 1
                    if stack == 0:
                        objects.append(text[start_index:i+1])
        
        return objects

    def _clean_content(self, text: str) -> str:
        """Remove internal tags like <|channel|>... from the text."""
        import re
        # Remove <|...|> tags
        cleaned = re.sub(r"<\|.*?\|>", "", text)
        return cleaned.strip()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore messages from bots
        if message.author.bot:
            return
        
        # Chat Point Logic (10s Cooldown) - Moved from legacy listener
        try:
            now = time.time()
            last_chat = self.chat_cooldowns[message.author.id]
            if now - last_chat > 10.0:
                self.chat_cooldowns[message.author.id] = now
                asyncio.create_task(self._store.add_points(message.author.id, 1))
        except Exception as e:
            logger.error(f"Error adding points: {e}")

        logger.info(f"ORACog.on_message triggered: author={message.author.id}, content={message.content[:50]}, attachments={len(message.attachments)}")

        # --- Voice Triggers (Direct Bypass - Mentions Only) ---
        if message.guild and self.bot.user in message.mentions:
            # Only trigger if specific keywords are present
            content_stripped = message.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
            
            # Use raw content to be safe against nickname resolution issues for simple keywords
            # But stripped content is better to avoid matching the mention itself (though unlikely)
            
            # Join: "きて" / "来て"
            if any(k in message.content for k in ["きて", "来て", "join"]):
                media_cog = self.bot.get_cog("MediaCog")
                if media_cog:
                    try:
                        await media_cog._voice_manager.ensure_voice_client(message.author)
                        media_cog._voice_manager.auto_read_channels[message.guild.id] = message.channel.id
                        await media_cog._voice_manager.play_tts(message.author, "はい、行きます！")
                        await message.add_reaction("⭕")
                    except Exception as e:
                         # Likely user not in VC
                         await message.channel.send(f"ボイスチャンネルに参加してから呼んでください。", delete_after=5)
                return

            # Leave: "消えて" / "ばいばい" / "バイバイ" / "帰って"
            if any(k in message.content for k in ["消えて", "ばいばい", "バイバイ", "帰って", "leave"]):
                media_cog = self.bot.get_cog("MediaCog")
                if media_cog and message.guild.voice_client:
                    # Remove auto-read
                    media_cog._voice_manager.auto_read_channels.pop(message.guild.id, None)
                    await media_cog._voice_manager.play_tts(message.author, "ばいばい！")
                    # Wait slightly for TTS to buffer
                    await asyncio.sleep(1.5)
                    await message.guild.voice_client.disconnect()
                    await message.add_reaction("👋")
                return

            # Music: "XX流して" / "play XX"
            # Regex to capture content before keywords
            import re
            music_match = re.search(r"(.*?)\s*(流して|かけて|再生して|歌って|play)", content_stripped, re.IGNORECASE)
            # Ensure the match is substantial (not just the keyword itself) and at the END of the string mostly
            if music_match:
                query = music_match.group(1).strip()
                # If query is empty, maybe it was "play XX" where play is first?
                if not query and "play" in content_stripped.lower():
                     # Handle "play XX" format
                     query = re.sub(r"^play\s*", "", content_stripped, flags=re.IGNORECASE).strip()

                if query:
                    media_cog = self.bot.get_cog("MediaCog")
                    if media_cog:
                        try:
                            # Join VC if not already
                            await media_cog._voice_manager.ensure_voice_client(message.author)
                            
                            # Feedback
                            await message.add_reaction("🎵")
                            
                            # Execute Play (without context/interaction)
                            # We need to manually call the cog's method or voice manager
                            # But MediaCog.play_music usually takes Context.
                            # We can trigger the command manually or use the underlying logic.
                            # Calling command is safer for permissions checks etc, but context is different.
                            # Let's call the internal logic directly if possible, or construct a fake context.
                            # MediaCog.play_music is a command.
                            # Better: media_cog.play_music_internal(ctx, query) - likely doesn't exist.
                            # Let's invoke the voice_manager directly if possible, OR create a Context.
                            
                            # Using Context is standard for invoking commands.
                            ctx = await self.bot.get_context(message)
                            # Invoke the command
                            # We need to find the command object.
                            cmd = self.bot.get_command("play")
                            if cmd:
                                await ctx.invoke(cmd, query=query)
                            else:
                                # Fallback if command name differs (it is 'music_play' in schemas, but command might be 'play' in cog)
                                # Let's check MediaCog... assume command is 'play'
                                pass

                        except Exception as e:
                            logger.error(f"Regex Music Trigger Failed: {e}")
                            await message.add_reaction("❌")
                    return
        # ------------------------------------------------------

        # Check for User Mention
        is_user_mention = self.bot.user in message.mentions
        
        # Check for Role Mention
        is_role_mention = False
        if message.role_mentions and message.guild:
            # Check if any mentioned role is assigned to the bot
            bot_member = message.guild.get_member(self.bot.user.id)
            if bot_member:
                for role in message.role_mentions:
                    if role in bot_member.roles:
                        is_role_mention = True
                        break
        
        is_mention = is_user_mention or is_role_mention
        is_reply_to_me = False
        
        if message.reference:
            # We need to check if the reply is to us. 
            # If resolved is available, check author id.
            # If not, we might need to fetch, but for trigger check, maybe we can rely on cached resolved or fetch it.
            # To be safe and fast, let's try to use resolved, if not, fetch.
            ref_msg = message.reference.resolved
            if not ref_msg and message.reference.message_id:
                 try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                 except:
                    pass
            
            if ref_msg and ref_msg.author.id == self.bot.user.id:
                is_reply_to_me = True

        # Trigger if mentioned OR replying to me
        if not (is_mention or is_reply_to_me):
            logger.info(f"ORACog.on_message: Not a mention or reply to me, returning")
            return

        # Remove mention strings from content to get the clean prompt
        import re
        # Remove User Mentions (<@123> or <@!123>) checking specific bot ID is safer but generic regex is fine for now
        # Actually proper way is to remove ONLY the bot's mention to avoiding removing other users if mentioned in query
        prompt = re.sub(f"<@!?{self.bot.user.id}>", "", message.content)
        
        # Remove Role Mentions (<@&123>)
        prompt = re.sub(r"<@&\d+>", "", prompt).strip()
        
        # Handle Attachments (Current Message)
        if message.attachments:
            prompt = await self._process_attachments(message.attachments, prompt, message)

        # Handle Attachments (Referenced Message / Reply)
        if message.reference:
            ref_msg = message.reference.resolved
            if not ref_msg and message.reference.message_id:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                except Exception as e:
                    logger.warning(f"Failed to fetch referenced message: {e}")
            
            if ref_msg and ref_msg.attachments:
                logger.info(f"Processing attachments from referenced message {ref_msg.id}")
                # We process referenced attachments but append to the SAME prompt
                # And we inject the image context into the CURRENT message ID (so LLM sees it for this turn)
                prompt = await self._process_attachments(ref_msg.attachments, prompt, message, is_reference=True)
            
            # Also process Embed Images (e.g. from ORA's own replies or other bots)
            if ref_msg and ref_msg.embeds:
                logger.info(f"Processing embeds from referenced message {ref_msg.id}")
                prompt = await self._process_embed_images(ref_msg.embeds, prompt, message, is_reference=True)

        # React if processing
        # ... (rest of logic)

        # Prepare for LLM
        # ...
        
        # Enqueue
        # Initialize StatusManager here? Or in handle_prompt?
        # handle_prompt puts it in queue. The actual processing happens in `desktop_loop` -> `_process_response`.
        # We should pass the StatusManager to handle_prompt? Or creating it inside the worker?
        # Creating inside the worker is safer for thread/async context.
        # But we want to start "Thinking" IMMEDIATELY?
        # If queue is long, immediate feedback is good.
        
        # Let's start "Thinking" here if it's a direct interaction?
        # No, let's keep it clean. The worker will pick it up and show status.
        # We just need to ensure the worker CAN create/manage it.
        
        # Voice Logic: Determine if we should speak/join
        is_voice = False
        user_voice = message.author.voice
        if user_voice and user_voice.channel:
            bot_voice = message.guild.voice_client
            # If bot is not connected, treat as voice (will join)
            if not bot_voice:
                is_voice = True
            # If bot IS connected, ONLY treat as voice if in SAME channel
            elif bot_voice.channel.id == user_voice.channel.id:
                is_voice = True
            else:
                # Bot is in a different channel.
                # User Policy: "Read it out is OK, just don't move." (VoiceManager is now Sticky)
                is_voice = True

        await self.handle_prompt(message, prompt, is_voice=is_voice)

    async def _process_attachments(self, attachments: List[discord.Attachment], prompt: str, context_message: discord.Message, is_reference: bool = False) -> str:
        """Process a list of attachments (Text or Image) and update prompt/context."""
        supported_text_ext = {'.txt', '.md', '.py', '.js', '.json', '.html', '.css', '.csv', '.xml', '.yaml', '.yml', '.sh', '.bat', '.ps1'}
        supported_img_ext = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}

        for i, attachment in enumerate(attachments):
            ext = "." + attachment.filename.split(".")[-1].lower() if "." in attachment.filename else ""
            
            # TEXT
            if ext in supported_text_ext or (attachment.content_type and "text" in attachment.content_type):
                if attachment.size > 1024 * 1024: 
                    continue
                try:
                    content = await attachment.read()
                    text_content = content.decode('utf-8', errors='ignore')
                    header = f"[Referenced File: {attachment.filename}]" if is_reference else f"[Attached File: {attachment.filename}]"
                    prompt += f"\n\n{header}\n{text_content}\n"
                except Exception:
                    pass

            # IMAGE (Vision)
            elif ext in supported_img_ext:
                if attachment.size > 8 * 1024 * 1024:
                    continue
                
                try:
                    # indicate processing
                    if not is_reference:
                         await context_message.add_reaction("👁️")
                    
                    image_data = await attachment.read()
                    
                    # Cache
                    timestamp = int(time.time())
                    safe_filename = f"{timestamp}_{attachment.filename}"
                    cache_path = CACHE_DIR / safe_filename
                    async with aiofiles.open(cache_path, "wb") as f:
                        await f.write(image_data)
                    
                    # Base64 Injection (Vision)
                    try:
                        import base64
                        
                        # OPTIMIZATON: Resize for Vision Model
                        # Load image with PIL
                        with Image.open(io.BytesIO(image_data)) as img:
                            # Convert to RGB (in case of RGBA/PNG)
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            
                            # Resize if too large (Max 1024x1024)
                            max_size = 1024
                            if max(img.size) > max_size:
                                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                            
                            # Save to buffer as JPEG
                            buffer = io.BytesIO()
                            img.save(buffer, format="JPEG", quality=85)
                            optimized_data = buffer.getvalue()
                        
                        b64_img = base64.b64encode(optimized_data).decode('utf-8')
                        mime_type = "image/jpeg" # Always send as JPEG
                        
                        if not hasattr(self, "_temp_image_context"):
                            self._temp_image_context = {}
                        
                        # Append to context list (support multiple images)
                        if context_message.id not in self._temp_image_context:
                            self._temp_image_context[context_message.id] = []
                        
                        self._temp_image_context[context_message.id].append({
                            "type": "image_url", 
                            "image_url": {"url": f"data:{mime_type};base64,{b64_img}"}
                        })
                    except Exception as e:
                        logger.error(f"Vision Encode Error: {e}")

                    header = f"[Referenced Image: {attachment.filename}]" if is_reference else f"[Attached Image {i+1}: {attachment.filename}]"
                    prompt += f"\n\n{header}\n(Image loaded into Qwen2.5-VL Vision Context)\n"

                except Exception as e:
                    logger.error(f"Image process failed: {e}")

        return prompt

    async def _process_embed_images(self, embeds: List[discord.Embed], prompt: str, context_message: discord.Message, is_reference: bool = False) -> str:
        """Process images found in Embeds (Thumbnail or Image field)."""
        import aiohttp
        import base64
        
        for embed in embeds:
            image_url = None
            if embed.image and embed.image.url:
                image_url = embed.image.url
            elif embed.thumbnail and embed.thumbnail.url:
                image_url = embed.thumbnail.url
            
            if not image_url:
                continue
                
            try:
                # Download Image
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status != 200:
                            logger.warning(f"Failed to download embed image: {resp.status}")
                            continue
                        image_data = await resp.read()
                
                # Encode (Vision)
                b64_img = base64.b64encode(image_data).decode('utf-8')
                mime_type = "image/png" # Default to png, actual type detection might be better but base64 usually works
                
                if not hasattr(self, "_temp_image_context"):
                    self._temp_image_context = {}
                
                if context_message.id not in self._temp_image_context:
                    self._temp_image_context[context_message.id] = []
                    
                self._temp_image_context[context_message.id].append({
                    "type": "image_url", 
                    "image_url": {"url": f"data:{mime_type};base64,{b64_img}"}
                })
                
                header = "[Referenced Embed Image]" if is_reference else "[Embed Image]"
                prompt += f"\n\n{header}\n(Image URL: {image_url})\n"
                
                # OCR Backup (Optional - skipping for speed/complexity, relying on Vision)
                
            except Exception as e:
                logger.error(f"Failed to process embed image: {e}")

        return prompt
        
        logger.info(f"Final prompt length: {len(prompt)} chars, Has attachments: {len(message.attachments) > 0}")
        
        # If prompt is still empty (e.g., just a mention with no text), check if we have attachments
        if not prompt and not message.attachments:
            logger.info("No prompt and no attachments, returning")
            return  # Nothing to process
        
        # Even if prompt is empty but attachments are present, set a default prompt
        if not prompt and message.attachments:
            logger.info("Empty prompt but attachments present, setting default")
            prompt = "画像を分析してください。"
        
        logger.info(f"Calling handle_prompt with prompt: {prompt[:100]}...")
        # Call handle_prompt with the constructed prompt
        await self.handle_prompt(message, prompt)


    def _get_tool_schemas(self) -> list[dict]:
        """
        Returns the list of available tools, organized by Category.
        Includes 'tags' for RAG filtering.
        """
        return [
            # ==========================
            # 1. Discord System (Core)
            # ==========================
            {
                "name": "get_server_info",
                "description": "[Discord] Get basic information about the current server (guild).",
                "parameters": { "type": "object", "properties": {}, "required": [] },
                "tags": ["server", "guild", "info", "id", "count", "サーバー", "情報"]
            },
            {
                "name": "get_channels",
                "description": "[Discord] Get a list of text and voice channels.",
                "parameters": { "type": "object", "properties": {}, "required": [] },
                "tags": ["channel", "list", "text", "voice", "チャンネル", "一覧"]
            },
            {
                "name": "get_roles",
                "description": "[Discord] Get a list of roles.",
                "parameters": { "type": "object", "properties": {}, "required": [] },
                "tags": ["role", "rank", "list", "ロール", "役職"]
            },
            {
                "name": "get_role_members",
                "description": "[Discord] Get members who have a specific role.",
                "parameters": {
                    "type": "object",
                    "properties": { "role_name": { "type": "string" } },
                    "required": ["role_name"]
                },
                "tags": ["role", "member", "who", "ロール", "メンバー", "誰"]
            },
            {
                "name": "find_user",
                "description": "[Discord] Find a user by name, ID, or mention.",
                "parameters": {
                    "type": "object",
                    "properties": { "name_query": { "type": "string" } },
                    "required": ["name_query"]
                },
                "tags": ["user", "find", "search", "who", "id", "ユーザー", "検索", "誰"]
            },
            # --- VC Operations ---
            {
                "name": "get_voice_channel_info",
                "description": "[Discord/VC] Get info about a voice channel.",
                "parameters": {
                    "type": "object",
                    "properties": { "channel_name": { "type": "string" } },
                    "required": []
                },
                "tags": ["vc", "voice", "channel", "who", "member", "ボイス", "通話", "誰いる"]
            },
            {
                "name": "join_voice_channel",
                "description": "[Discord/VC] Join a voice channel.",
                "parameters": {
                    "type": "object",
                    "properties": { "channel_name": { "type": "string" } },
                    "required": []
                },
                "tags": ["join", "connect", "come", "vc", "voice", "参加", "来て", "入って"]
            },
            {
                "name": "leave_voice_channel",
                "description": "[Discord/VC] Leave the current voice channel.",
                "parameters": { "type": "object", "properties": {}, "required": [] },
                "tags": ["leave", "disconnect", "bye", "exit", "vc", "退出", "バイバイ", "抜けて", "落ちる"]
            },
            {
                "name": "manage_user_voice",
                "description": "[Discord/VC] Disconnect, Move, or Summon a user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_user": { "type": "string" },
                        "action": { "type": "string", "enum": ["disconnect", "move", "summon", "mute", "unmute", "deafen", "undeafen"] },
                        "channel_name": { "type": "string" }
                    },
                    "required": ["target_user", "action"]
                },
                "tags": ["move", "kick", "disconnect", "summon", "mute", "deafen", "移动", "移動", "切断", "ミュート", "集合"]
            },
            # --- Games ---
            {
                "name": "shiritori",
                "description": "[Discord/Game] Play Shiritori.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": { "type": "string", "enum": ["start", "play", "check_bot"] },
                        "word": { "type": "string" },
                        "reading": { "type": "string" }
                    },
                    "required": ["action"]
                },
                "tags": ["game", "shiritori", "play", "しりとり", "ゲーム", "遊ぼ"]
            },
            {
                "name": "start_thinking",
                "description": "[Router] Activate Reasoning Engine (Thinking Mode).",
                "parameters": {
                    "type": "object",
                    "properties": { "reason": { "type": "string" } },
                    "required": ["reason"]
                },
                "tags": ["think", "reason", "complex", "math", "code", "logic", "solve", "difficult", "hard", "考え", "思考", "難しい", "計算", "コード"]
            },
            # --- Music ---
            {
                "name": "music_play",
                "description": "[Discord/Music] Play music from YouTube.",
                "parameters": {
                    "type": "object",
                    "properties": { "query": { "type": "string" } },
                    "required": ["query"]
                },
                "tags": ["music", "play", "song", "youtube", "listen", "hear", "曲", "音楽", "流して", "再生", "歌って"]
            },
            {
                "name": "music_control",
                "description": "[Discord/Music] Control playback.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": { "type": "string", "enum": ["skip", "stop", "loop_on", "loop_off", "queue_show", "replay_last"] }
                    },
                "required": ["action"]
                },
                "tags": ["stop", "skip", "next", "loop", "repeat", "queue", "pause", "resume", "back", "止めて", "スキップ", "次", "ループ", "リピート"]
            },
            {
                "name": "set_audio_volume",
                "description": "[Discord/Audio] Set volume for Music or TTS.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": { "type": "string", "enum": ["music", "tts"] },
                        "value": { "type": "integer" }
                    },
                    "required": ["target", "value"]
                },
                "tags": ["volume", "sound", "loud", "quiet", "level", "音量", "うるさい", "静か", "大きく", "小さく"]
            },
            # --- Moderation & Utility ---
            {
                "name": "purge_messages",
                "description": "[Discord/Mod] Bulk delete messages.",
                "parameters": {
                    "type": "object",
                    "properties": { "limit": { "type": "integer", "default": 10 } },
                    "required": []
                },
                "tags": ["delete", "purge", "clear", "clean", "remove", "削除", "消して", "掃除", "クリーニング"]
            },
            {
                "name": "manage_pins",
                "description": "[Discord/Mod] Pin or Unpin a message.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": { "type": "string", "enum": ["pin", "unpin"] },
                        "message_id": { "type": "string" }
                    },
                    "required": ["action"]
                },
                "tags": ["pin", "unpin", "sticky", "save", "ピン", "留め", "固定", "外して"]
            },
            {
                "name": "create_thread",
                "description": "[Discord] Create a new thread.",
                "parameters": {
                    "type": "object",
                    "properties": { "name": { "type": "string" } },
                    "required": ["name"]
                },
                "tags": ["thread", "create", "new", "topic", "スレッド", "スレ", "作成"]
            },
            {
                "name": "create_poll",
                "description": "[Discord] Create a reaction-based poll.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": { "type": "string" },
                        "options": { "type": "array", "items": { "type": "string" } }
                    },
                    "required": ["question", "options"]
                },
                "tags": ["poll", "vote", "ask", "question", "choice", "投票", "アンケート", "決めて", "どっち"]
            },
            {
                "name": "create_invite",
                "description": "[Discord] Create an invite link.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "minutes": { "type": "integer" },
                        "uses": { "type": "integer" }
                    },
                    "required": []
                },
                "tags": ["invite", "link", "url", "join", "招待", "リンク", "呼んで"]
            },
            {
                "name": "summarize_chat",
                "description": "[Discord/GenAI] Summarize recent messages.",
                "parameters": {
                    "type": "object",
                    "properties": { "limit": { "type": "integer", "default": 50 } },
                    "required": []
                },
                "tags": ["summarize", "summary", "catchup", "history", "log", "read", "context", "要約", "まとめ", "ログ", "何話して", "流れ"]
            },
            {
                "name": "remind_me",
                "description": "[Discord/Util] Set a personal reminder.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "minutes": { "type": "integer" },
                        "message": { "type": "string" }
                    },
                    "required": ["minutes", "message"]
                },
                "tags": ["remind", "alarm", "timer", "alert", "later", "リマインド", "アラーム", "タイマー", "教えて", "後で"]
            },
            {
                "name": "server_assets",
                "description": "[Discord/Util] Get server Icon and Banner URLs.",
                "parameters": { "type": "object", "properties": {}, "required": [] },
                "tags": ["icon", "banner", "image", "asset", "server", "アイコン", "バナー", "画像"]
            },
            {
                "name": "add_emoji",
                "description": "[Discord] Add a custom emoji from an image URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": { "type": "string" },
                        "image_url": { "type": "string" }
                    },
                    "required": ["name", "image_url"]
                },
                "tags": ["emoji", "sticker", "stamp", "add", "create", "絵文字", "スタンプ", "追加"]
            },
            {
                "name": "user_info",
                "description": "[Discord] Get detailed user info.",
                "parameters": {
                    "type": "object",
                    "properties": { "target_user": { "type": "string" } },
                    "required": ["target_user"]
                },
                "tags": ["user", "info", "who", "profile", "avatar", "role", "ユーザー", "詳細", "誰", "プロフ"]
            },
            {
                "name": "ban_user",
                "description": "[Discord/Mod] Ban a user.",
                "parameters": {
                    "type": "object",
                    "properties": { "target_user": { "type": "string" }, "reason": { "type": "string" } },
                    "required": ["target_user"]
                },
                "tags": ["ban", "block", "remove", "destroy", "バン", "BAN", "ブロック", "排除"]
            },
            {
                "name": "kick_user",
                "description": "[Discord/Mod] Kick a user.",
                "parameters": {
                    "type": "object",
                    "properties": { "target_user": { "type": "string" }, "reason": { "type": "string" } },
                    "required": ["target_user"]
                },
                "tags": ["kick", "remove", "bye", "キック", "蹴る", "追放"]
            },
            {
                "name": "timeout_user",
                "description": "[Discord/Mod] Timeout (Mute) a user.",
                "parameters": {
                    "type": "object",
                    "properties": { 
                        "target_user": { "type": "string" }, 
                        "minutes": { "type": "integer" },
                        "reason": { "type": "string" }
                    },
                    "required": ["target_user", "minutes"]
                },
                "tags": ["timeout", "mute", "silence", "quiet", "shut", "タイムアウト", "黙らせ", "静かに"]
            },
            # --- General ---
            {
                "name": "google_search",
                "description": "[Search] Search Google for real-time info (News, Weather, Prices).",
                "parameters": {
                    "type": "object",
                    "properties": { "query": { "type": "string" } },
                    "required": ["query"]
                },
                "tags": ["search", "google", "weather", "price", "news", "info", "lookup", "調べ", "検索", "天気", "価格", "ニュース", "情報", "とは"]
            },
            {
                "name": "generate_image",
                "description": "[Creative] Generate an image from text. Args: 'prompt', 'negative_prompt'.",
                "parameters": {
                   "type": "object",
                   "properties": {
                       "prompt": { "type": "string" },
                       "negative_prompt": { "type": "string" }
                   },
                   "required": ["prompt"]
                },
                "tags": ["image", "generate", "draw", "create", "art", "paint", "picture", "illustration", "画像", "生成", "描いて", "絵", "イラスト"]
            },
            # --- System ---
            {
                "name": "system_control",
                "description": "[System] Control Bot Volume or Open/Close UI.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": { "type": "string", "enum": ["volume_up", "volume_down", "open_ui", "close_ui"] },
                        "value": { "type": "integer" }
                    },
                    "required": ["action"]
                },
                "tags": ["system", "volume", "ui", "interface", "open", "close", "システム", "音量", "UI", "開いて", "閉じて"]
            }
        ]

    def _select_tools(self, user_input: str, all_tools: list[dict]) -> list[dict]:
        """
        RAG: Selects tools based on keyword matching.
        Always includes 'CORE' tools.
        """
        selected = []
        user_input_lower = user_input.lower()
        
        # Always Active Tools (Core)
        CORE_TOOLS = {"start_thinking", "google_search", "system_control", "manage_user_voice", "join_voice_channel"} 
        
        # Override: If user explicitly asks for "help" or "functions", show ALL
        if any(w in user_input_lower for w in ["help", "tool", "function", "command", "list", "機能", "ヘルプ", "コマンド", "できること"]):
            return all_tools

        for tool in all_tools:
            name = tool["name"]
            
            # 1. Core Logic
            if name in CORE_TOOLS:
                # Still check tags? No, always include core.
                selected.append(tool)
                continue
                
            # 2. Tag Matching
            tags = tool.get("tags", [])
            # Also check name parts
            name_parts = name.split("_")
            
            is_relevant = False
            
            # Check Tags
            for tag in tags:
                if tag.lower() in user_input_lower:
                    is_relevant = True
                    break
            
            # Check Name parts (e.g. 'music' in 'music_play')
            if not is_relevant:
                for part in name_parts:
                    if len(part) > 2 and part in user_input_lower:
                         is_relevant = True
                         break
            
            if is_relevant:
                selected.append(tool)
        
        return selected



    async def handle_prompt(self, message: discord.Message, prompt: str, existing_status_msg: Optional[discord.Message] = None, is_voice: bool = False) -> None:
        """Process a user message and generate a response using the LLM."""
        
        # 1. Check for Generation Lock
        if self.is_generating_image:
            await message.reply("🎨 現在、画像生成を実行中です... 完了次第、順次回答しますので少々お待ちください！ (Waiting for image generation...)", mention_author=True)
            # CRITICAL FIX: Queue the PROMPT too, otherwise it's lost and causes TypeError later
            self.message_queue.append((message, prompt))
            return

        # 1.5 DIRECT BYPASS: "画像生成" Trigger (Zero-Shot UI Launch)
        if prompt and (prompt.startswith("画像生成") or "画像生成" in prompt[:10]):
            gen_prompt = prompt.replace("画像生成", "", 1).strip()
            if not gen_prompt: gen_prompt = "artistic masterpiece" 
            
            try:
                 from ..views.image_gen import AspectRatioSelectView
                 logger.info(f"Directly accessing image gen for prompt: {gen_prompt}")
                 # NOTE: Model name is Flux.2 by default
                 view = AspectRatioSelectView(self, gen_prompt, "", model_name="FLUX.2")
                 await message.reply(f"🎨 **画像生成アシスタント (Direct)**\nPrompt: `{gen_prompt}`\nアスペクト比を選択して生成を開始してください。", view=view)
                 return # STOP HERE. NO LLM CHAT.
            except Exception as e:
                 logger.error(f"Direct bypass failed: {e}")
                 # Fallback to normal flow

        # 2. Privacy Check
        await self._store.ensure_user(message.author.id, self._privacy_default)

        # Send initial progress message if not provided
        start_time = time.time()
        # Send initial status
        start_time = time.time()
        status_manager = StatusManager(message.channel)
        if existing_status_msg:
             try:
                 await existing_status_msg.delete()
             except:
                 pass
        
        await status_manager.start("思考中")

        # Voice Feedback: "Generating..." (Smart Delay)
        voice_feedback_task = None
        if is_voice:
            async def delayed_feedback():
                await asyncio.sleep(0.5) # 500ms delay
                # If status message exists (implicit check for done)
                if status_manager.message:
                    voice_manager = getattr(self.bot, "voice_manager", None)
                    if voice_manager:
                         # Use play_tts directly to avoid Command object issues
                         # Skipped "Generating answer" TTS as per user request
                        pass

            voice_feedback_task = asyncio.create_task(delayed_feedback())

        try:
            system_prompt = await self._build_system_prompt(message)
            # Context Logic: Only build history if replying. New mentions split context.
            if message.reference:
                try:
                    history = await self._build_history(message)
                except Exception as e:
                    logger.error(f"Failed to build history: {e}")
                    history = []
            else:
                # Fresh start
                history = []
            
            messages = [{"role": "system", "content": system_prompt}]
            
            # Concise Mode for Voice
            if is_voice:
                messages.append({
                    "role": "system", 
                    "content": "返答は日本語で行ってください。最大250文字、2文以内で。コードブロック、箇条書き、URLは禁止です。必要なら要約してください。"
                })

            messages.extend(history)
            
            # CRITICAL FIX: Ensure message history starts with 'user' (after system).
            # Some APIs crash if 'assistant' comes immediately after 'system'.
            # We check messages[1] because messages[0] is system, [1] is first history item.
            # If is_voice and concise mode added another system msg, index might be 2.
            
            # Find first non-system message index
            first_content_idx = 1
            while first_content_idx < len(messages) and messages[first_content_idx]["role"] == "system":
                first_content_idx += 1

            if first_content_idx < len(messages) and messages[first_content_idx]["role"] == "assistant":
                # Insert a dummy user message to satisfy the alternation rule
                # Use Japanese to prevent model from switching to English context
                messages.insert(first_content_idx, {"role": "user", "content": "(会話の続き...)"})
            
            # BUILD USER CONTENT (Multimodal)
            text_content = prompt
            user_content = []
            user_content.append({"type": "text", "text": text_content})
            
            # PROCESS ATTACHMENTS (Direct)
            # PROCESS ATTACHMENTS
            # Note: Attachments are processed in _process_attachments() and stored in _temp_image_context
            # as base64. We do NOT need to add them as URLs here, or we get duplicates.
            # (Removed redundant loop)
            
            if hasattr(self, "_temp_image_context") and message.id in self._temp_image_context:
                user_content.extend(self._temp_image_context[message.id])
                # Clean up
                del self._temp_image_context[message.id]
            
            # Determine final message content
            final_user_msg = None
            if len(user_content) == 1 and user_content[0]["type"] == "text":
                 final_user_msg = {"role": "user", "content": text_content}
            else:
                 final_user_msg = {"role": "user", "content": user_content}

            # Merge with previous message if it exists and is also 'user'
            if messages and messages[-1]["role"] == "user":
                last_msg = messages[-1]
                # If last msg is simple string
                if isinstance(last_msg["content"], str):
                    # And new msg is simple string
                    if isinstance(final_user_msg["content"], str):
                        last_msg["content"] += f"\n\n{final_user_msg['content']}"
                    # And new msg is list (multimodal)
                    else:
                        # Convert last msg to list format and append new parts
                        new_list = [{"type": "text", "text": last_msg["content"]}]
                        new_list.extend(final_user_msg["content"])
                        last_msg["content"] = new_list
                
                # If last msg is list
                elif isinstance(last_msg["content"], list):
                    # And new msg is simple string
                    if isinstance(final_user_msg["content"], str):
                        last_msg["content"].append({"type": "text", "text": final_user_msg["content"]})
                    # And new msg is list
                    else:
                        last_msg["content"].extend(final_user_msg["content"])
            else:
                messages.append(final_user_msg)

            # First LLM Call
            # Append strict Instruction at the end to prevent context drift
            messages.append({
                "role": "system",
                "content": (
                    "**IMPORTANT**: Reply in **JAPANESE** (日本語) unless the user effectively requested English.\n"
                    "If you need to use a tool, output the JSON block ONLY."
                )
            })

            content = await self._llm.chat(messages=messages, temperature=0.7)
            logger.info(f"🔍 [RAW_LLM_OUTPUT] Length: {len(content)}\n{content}\n--------------------------------")
            
            # Legacy Router Block Removed

            
            # -------------------------------
            
            # Tool Loop
            max_turns = 3
            turn = 0
            executed_tools = []
            tool_counts = {}
            
            while turn < max_turns:
                turn += 1
                
                # Re-extract JSON from (potentially new) content
                json_objects = self._extract_json_objects(content)
                
                # ROBUST FALLBACK: If 7B model forgot markdown code blocks, try to find raw JSON
                if not json_objects:
                    import re
                    # Try to find the first likely JSON object starting with { and ending with }
                    loose_match = re.search(r"(\{[\s\S]*?\})", content)
                    if loose_match:
                         possible_json = loose_match.group(1)
                         try:
                             json.loads(possible_json)
                             json_objects.append(possible_json)
                             logger.info("Fallback: Extracted loose JSON object.")
                         except:
                             pass
                    
                    # FALLBACK 2: BARE TOOL NAME Detection
                    # If content is exactly (or close to) a known tool name (e.g., "join_voice_channel"), map it.
                    # This happens heavily with Qwen-2.5-7B when instructed to "Use implicit trigger".
                    clean_text = content.strip().lower()
                    # Common no-arg tools
                    known_tools = {
                        "join_voice_channel": {},
                        "leave_voice_channel": {},
                        "google_search": {"query": "something"}, # Search usually requires args, but might be triggered empty
                        "start_thinking": {"reason": "Complex task"}
                    }
                    
                    for t_name, default_args in known_tools.items():
                        # exact match or matches "ToolName"
                        if clean_text == t_name or clean_text == f"`{t_name}`":
                             logger.info(f"Fallback: Detected bare tool name '{t_name}'. Constructing JSON.")
                             json_objects.append(json.dumps({"tool": t_name, "args": default_args}))
                             break
                    
                    # FALLBACK 3: Music Heuristic (Strong)
                    # If user asks to "Play X" and LLM just says "Playing" or "Sure" without tool call.
                    # CRITICAL: Only check on TURN 1. If we are in turn 2+, we already handled the main request.
                    if not json_objects and "流して" in prompt and turn == 1: # Only trigger if user explicitly asked
                         # Check if response implies agreement but no tool
                         # Or just forcefully interpret "Play X" if LLM output is short/empty
                         # Extract song name from prompt: "X流して" -> X

                         song_match = re.search(r"(.+?)(流して|再生して|歌って)", prompt)
                         if song_match:
                             song_query = song_match.group(1).strip()
                             # Filter out mentions
                             song_query = re.sub(r"<@!?\d+>", "", song_query).strip()
                             
                             if song_query and len(song_query) > 1:
                                 logger.info(f"Fallback: Music Heuristic triggered for query '{song_query}'")
                                 json_objects.append(json.dumps({"tool": "music_play", "args": {"query": song_query}}))
                    
                    # FALLBACK 4: Search Heuristic (Refusal Override)
                    # If LLM refuses to answer current info ("Cannot provide...", "I don't know"), force search.
                    # Keywords: "天気", "ニュース", "価格", "株価", "速報"
                    if not json_objects and turn == 1:
                         # Refusal Check (Simple)
                         refusal_keywords = ["できません", "お答えできません", "最新の情報", "cannot provide", "cutoff"]
                         is_refusal = any(k in content for k in refusal_keywords)
                         
                         triggers = ["天気", "ニュース", "価格", "株価", "速報", "とは", "教えて"]
                         has_trigger = any(t in prompt for t in triggers)
                         
                         if is_refusal and has_trigger:
                             logger.info("Fallback: Search Heuristic triggered (Refusal Override).")
                             # Use entire prompt as query (cleaned)
                             clean_q = prompt.replace("教えて", "").strip()
                             json_objects.append(json.dumps({"tool": "google_search", "args": {"query": clean_q}}))




                logger.info(f"Extracted JSON objects: {len(json_objects)}")
                
                tool_call = None
                
                # Check for Command R+ style tool calls (e.g. <|channel|>commentary to=google_search ... {args})
                import re
                cmd_r_match = re.search(r"to=(\w+)", content)
                if cmd_r_match:
                     logger.info(f"Cmd R+ Match: {cmd_r_match.group(1)}")
                     # Always try Fallback: Extract JSON using regex
                     # This handles cases where _extract_json_objects returns invalid garbage or misses the weird formatting
                     json_match = re.search(r"json\s*(\{.*?\})", content, re.DOTALL)
                     if json_match:
                         # It's okay if we duplicate; the loop breaks on first valid parse
                         json_objects.append(json_match.group(1))
                         logger.info("Added fallback JSON object from regex (Always).")
                
                for i, json_str in enumerate(json_objects):
                    logger.info(f"Processing JSON object {i}: {json_str}")
                    try:
                        data = json.loads(json_str)
                        logger.info(f"Parsed JSON data: {data}")
                        
                        # Case 1: Standard JSON format {"tool": "name", "args": {...}}
                        if isinstance(data, dict) and "tool" in data and "args" in data:
                            tool_call = data
                            logger.info(f"Found Standard Tool Call: {tool_call}")
                            break
                        # Case 2: Command R+ style (args only in JSON, tool name in text)
                        elif cmd_r_match and isinstance(data, dict):
                            tool_name = cmd_r_match.group(1)
                            # If the JSON looks like args (has keys matching parameters), use it
                            # Or just assume the first JSON object is the args
                            tool_call = {"tool": tool_name, "args": data}
                            logger.info(f"Found Cmd R+ Tool Call: {tool_call}")
                            break
                        else:
                            logger.warning(f"JSON object {i} did not match any tool format: {data}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON Decode Error at index {i}: {e}")
                        continue
                
                if tool_call:
                    tool_name = tool_call["tool"]
                    tool_args = tool_call["args"]

                    # --- LOOP BREAKER / SPAM PROTECTION ---
                    if tool_name not in tool_counts:
                        tool_counts[tool_name] = 0
                    tool_counts[tool_name] += 1
                    
                    # 1. Block excessive 'create_file' (Max 1)
                    if tool_name == "create_file" and tool_counts[tool_name] > 1:
                        logger.warning("Spam Protection: Blocked extra create_file call.")
                        messages.append({"role": "user", "content": "Tool Error: 'create_file' can only be used once per turn."})
                        continue

                    # 2. Block excessive same tool (Max 3)
                    if tool_counts[tool_name] > 3:
                        logger.warning(f"Spam Protection: Blocked excessive {tool_name} calls.")
                        break # Break loop, force answer
                        
                    # 3. Block total tool calls (Max 5)
                    if len(executed_tools) >= 5:
                         logger.warning("Spam Protection: Max total tool calls reached.")
                         break

                    executed_tools.append(tool_name)
                    # --------------------------------------
                    
                    # Update progress message to show tool execution
                    tool_display_name = {
                        "google_search": "🔍 Web検索",
                        "get_system_stats": "💻 システム情報取得",
                        "music_play": "🎵 音楽再生",
                        "music_control": "🎵 音楽操作",
                        "system_control": "⚙️ システム制御",
                        "create_file": "📝 ファイル作成",
                        "get_voice_channel_info": "🔊 VC情報取得",
                        "join_voice_channel": "🔊 VC参加",
                        "leave_voice_channel": "🔊 VC退出",
                    }.get(tool_name, f"🔧 {tool_name}")
                    
                    
                    # Execute Tool
                    if is_voice and tool_name == "google_search":
                         media_cog = self.bot.get_cog("MediaCog")
                         if media_cog:
                             query = tool_args.get("query", "")
                             await media_cog.speak_text(message.author, f"{query}について検索しています")

                    tool_result = await self._execute_tool(tool_name, tool_args, message, status_manager=status_manager)
                    
                    if tool_result and "[SILENT_COMPLETION]" in str(tool_result):
                        logger.info("Silent tool completion detected. Stopping generation loop.")
                        await status_manager.finish()
                        return

                    if tool_result:
                        # Check for loop (same tool, same args, repeated)
                        # We need to track previous tool calls
                        # Simple check: if this tool call is identical to the last one
                        pass

                    # Append result
                    # CLEAN CONTENT before appending: Remove special Command R+ tokens to avoid confusing the model
                    clean_content = content.replace("<|channel|>", "").replace("<|constrain|>", "").replace("<|message|>", "").strip()
                    messages.append({"role": "assistant", "content": clean_content})
                    
                    # Use USER role for the tool output to force attention and mimic turn-taking
                    logger.info(f"Injecting Tool Result of length {len(tool_result)} for summarization")
                    
                    messages.append({
                        "role": "user", 
                        "content": f"【検索結果】以下は検索ツールからの実行結果です。\n{tool_result}\n\nこの情報に基づき、ユーザーの質問に対する回答を日本語で作成してください。ツールは既に実行されたため、これ以上ツールを呼び出さず、要約と回答のみを行ってください。"
                    })
                    
                    # Update Status for Next Think
                    await status_manager.next_step("回答生成中")
                    
                    new_content = await self._llm.chat(messages=messages, temperature=0.7)
                    
                    # Loop Detection: If new_content is SAME as old content (ignoring unique IDs if any), break
                    if new_content.strip() == content.strip():
                        logger.warning("Loop detected: LLM output indicates same tool call. Breaking.")
                        content = "申し訳ありません。検索結果の処理中にエラーが発生しました。"
                        break
                        
                    content = new_content
                else:
                    break
            
            # Check if final content is still a tool call (Loop exhausted)
            # If so, suppress it
            if re.search(r"to=(\w+)", content) or "tool" in content and "args" in content:
                 logger.warning(f"Loop exhausted and content looks like tool call: {content}")
                 # Try to use the last tool result if available? 
                 # Or just say error.
                 # Let's verify if we have a tool result from previous turn
                 if turn > 0:
                     final_response = "検索は成功しましたが、結果の要約に失敗しました。"
                 else:
                     final_response = "エラーが発生しました。"
            else:
                 final_response = self._clean_content(content)
            
            # Stop animation / Delete Status
            await status_manager.finish()
            
            # Edit message with final response -> Send NEW message (Embed)
            # User requested to "Delete all status and send text" -> Now "Send Embed"
            embed = EmbedFactory.create_chat_embed(final_response, footer_text="ORA AI System")
            try:
                await message.reply(embed=embed, mention_author=False)
            except discord.Forbidden:
                # Fallback to text if Embeds are disabled
                await message.reply(final_response, mention_author=False)
            except Exception as e:
                logger.error(f"Failed to send final embed: {e}")
                await message.reply(final_response, mention_author=False)
            
            # Voice Response
            if is_voice:
                media_cog = self.bot.get_cog("MediaCog")
                if media_cog:
                    # Clean text for TTS
                    tts_text = final_response[:200]
                    await media_cog.speak_text(message.author, tts_text)
            
            # Save conversation
            google_sub = await self._store.get_google_sub(message.author.id)
            user_id_for_db = google_sub if google_sub else str(message.author.id)
            await self._store.add_conversation(
                user_id=user_id_for_db,
                platform="discord",
                message=message.clean_content,
                response=final_response
            )

        except Exception as e:
            await status_manager.finish()
            logger.error(f"Error in handle_prompt: {e}", exc_info=True)
            await message.reply("申し訳ありません。応答の生成に失敗しました。", mention_author=False)
            if is_voice:
                 media_cog = self.bot.get_cog("MediaCog")
                 if media_cog:
                     await media_cog.speak_text(message.author, "エラーが発生しました")

    async def wait_for_llm(self, message: discord.Message) -> None:
        """Show a loading animation while waiting for LLM."""
        dots = ["", ".", "..", "..."]
        idx = 0
        base_content = "応答を生成中"
        while not self.llm_done_event.is_set():
            try:
                await message.edit(content=f"{base_content}{dots[idx]}")
                idx = (idx + 1) % len(dots)
                await asyncio.sleep(1)
            except discord.NotFound:
                break
            except Exception:
                break





    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle flag reactions for translation."""
        if payload.user_id == self.bot.user.id:
            return

        # Check if emoji is a flag
        emoji_str = str(payload.emoji)
        logger.info(f"Reaction added: {emoji_str} (Name: {payload.emoji.name})")
        iso_code = flag_utils.flag_to_iso(emoji_str)
        logger.info(f"ISO Code from flag: {iso_code}")
        
        if not iso_code:
            return

        # Get channel and message
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return
            
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
            
        if not message.content:
            return

        # Determine target language
        # Simple mapping for common codes, fallback to country name
        lang_map = {
            "US": "English", "GB": "English",
            "JP": "Japanese",
            "CN": "Chinese",
            "KR": "Korean",
            "FR": "French",
            "DE": "German",
            "ES": "Spanish",
            "IT": "Italian",
            "RU": "Russian",
            "BR": "Portuguese",
        }
        
        target_lang = lang_map.get(iso_code)
        if not target_lang:
            target_lang = flag_utils.get_country_name(iso_code)
        
        if not target_lang:
            return

        # Translate using LLM
        prompt = f"Translate the following text to {target_lang}. Output ONLY the translation.\n\nText: {message.content}"
        
        try:
            # Send a temporary "Translating..." reaction or message? 
            # A reaction is less intrusive. Let's add a 'thinking' emoji.
            await message.add_reaction("🤔")
            
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            await message.remove_reaction("🤔", self.bot.user)
            await message.reply(f"{emoji_str} Translation: {response}", mention_author=False)
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            await message.remove_reaction("🤔", self.bot.user)
            await message.add_reaction("❌")

    def _strip_route_json(self, content: str) -> str:
        """Removes the JSON block containing 'route_eval' by counting braces."""
        if "route_eval" not in content:
            return content
            
        start_idx = content.find('{')
        if start_idx == -1:
            return content
            
        # Brace Counting
        count = 0
        end_idx = -1
        in_string = False
        escape = False
        
        for i, char in enumerate(content[start_idx:], start=start_idx):
            # Handle strings to ignore braces inside them
            if char == '"' and not escape:
                in_string = not in_string
            
            if char == '\\' and not escape:
                escape = True
            else:
                escape = False
                
            if not in_string:
                if char == '{':
                    count += 1
                elif char == '}':
                    count -= 1
                    if count == 0:
                        end_idx = i + 1
                        break
        
        if end_idx != -1:
            json_block = content[start_idx:end_idx]
            # Verify it's the route block
            if "route_eval" in json_block:
                logger.info(f"Stripped Route JSON: {json_block[:50]}...")
                # Return content without this block
                return (content[:start_idx] + content[end_idx:]).strip()
                
        return content

async def setup(bot):
    await bot.add_cog(OraCog(bot))

