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

        tools_schema = self._get_tool_schemas()
        tools_json = json.dumps(tools_schema, ensure_ascii=False)

        base = (
            f"You are ORA, a helpful AI assistant on Discord.\n"
            f"Current Server: {guild_name}\n"
            f"Member Count: {member_count}\n"
            f"Current Channel: {channel_name}\n"
            f"**CRITICAL INSTRUCTION**:\n"
            f"1. **LANGUAGE**: You MUST ALWAYS reply in **JAPANESE** (日本語).\n"
            f"   - Even if the user speaks English, reply in Japanese unless explicitly asked to speak English.\n"
            f"2. **CHARACTER**: You are ORA. Be helpful, polite, and slightly futuristic.\n"
            f"   - **INTERNAL KNOWLEDGE (DO NOT SPEAK UNSOLICITED)**: Your creator is **YoneRai12**.\n"
            f"   - **REVEAL CONDITION**: Only mention your creator if the user EXPLICITLY asks 'Who made you?' or similar. Never use it as a greeting.\n"

            f"\n"
            f"7. **Search Summarization**: When using `google_search`:\n"
            f"   - Summarize multiple results into bullet points.\n"
            f"   - Do not repeat the same info.\n"
            f"   - Keep it concise (150-300 chars).\n"
            f"7. **CRITICAL: IMAGE ANALYSIS vs MUSIC/SEARCH**\n"
            f"   - If the user provides an image:\n"
            f"     - **USE YOUR EYES.** The image is provided as visual input.\n"
            f"     - **USE YOUR EYES.** The image is provided as visual input (Qwen2.5-VL-32B).\n"
            f"     - Analyze every detail: text, charts, handwriting, and layout.\n"
            f"     - **DO NOT** use `music_play` for image analysis.\n"
            f"     - If the image is unclear, ask for clarification.\n"
            f"\n"
            f"4. **ROUTING EVALUATION (MANDATORY)**:\n"
            f"   - You act as the 'Router'. Before answering, EVALUATE the user's request.\n"
            f"   - If the task requires complex reasoning (Math, Graphs, Proofs, Long Logic), set `needs_thinking: true`.\n"
            f"   - **JSON FORMAT**: You MUST output this classification JSON as the VERY FIRST line of your response.\n"
            f"   ```json\n"
            f"   {{ \"route_eval\": {{ \"needs_thinking\": false, \"confidence\": 0.95, \"detected_task\": [\"chat\"] }} }}\n"
            f"   ```\n"
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
            "You do NOT need OCR text; trust your eyes."
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

            elif tool_name == "join_voice_channel":
                # Find channel to join
                target_channel = message.author.voice.channel if message.author.voice else None
                if not target_channel:
                    return "Error: User is not in a voice channel."
                
                # Check User Limit
                if target_channel.user_limit > 0 and len(target_channel.members) >= target_channel.user_limit:
                     # Check if bot has "Move Members" or "Administrator" to bypass? 
                     # Discord API allows bots to connect if they have "Move Members" I think?
                     # But user requested "Cannot join", so let's be strict.
                     return f"Error: The voice channel '{target_channel.name}' is full (Limit: {target_channel.user_limit})."

                media_cog = self.bot.get_cog("MediaCog")
                if media_cog:
                    # 1. Join
                    try:
                        vc = await target_channel.connect()
                        # 2. Enable Auto-Read
                        if hasattr(media_cog, '_auto_read_channels'):
                            media_cog._auto_read_channels[message.guild.id] = message.channel.id
                        
                        return f"Joined {target_channel.name} and enabled auto-read for this channel."
                    except discord.ClientException:
                         # Already connected, just update text channel
                        if hasattr(media_cog, '_auto_read_channels'):
                            media_cog._auto_read_channels[message.guild.id] = message.channel.id
                        return "Error: Already connected. Auto-read enabled for this channel."
                    except Exception as e:
                        return f"Error joining: {e}"
                return "Media system not available."

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
                         media_cog._auto_read_channels[message.guild.id] = message.channel.id
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
                    media_cog._auto_read_channels.pop(message.guild.id, None)
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
                    await self._store.get_privacy(message.author.id)
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
        await self.handle_prompt(message, prompt)

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
        Structure:
        1. Discord System
        2. Image Generation
        3. Voice Generation
        4. Video Generation (Placeholder)
        5. Video Recognition (Placeholder)
        6. Search
        7. Admin & System
        """
        return [
            # --- 1. Discord System ---
            {
                "name": "get_server_info",
                "description": "[Discord] Get basic information about the current server (guild).",
                "parameters": { "type": "object", "properties": {}, "required": [] }
            },
            {
                "name": "get_channels",
                "description": "[Discord] Get a list of text and voice channels in the server.",
                "parameters": { "type": "object", "properties": {}, "required": [] }
            },
            {
                "name": "get_roles",
                "description": "[Discord] Get a list of roles in the server.",
                "parameters": { "type": "object", "properties": {}, "required": [] }
            },
            {
                "name": "get_role_members",
                "description": "[Discord] Get members who have a specific role.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "role_name": { "type": "string", "description": "Role name to search for." }
                    },
                    "required": ["role_name"]
                }
            },
            {
                "name": "find_user",
                "description": "[Discord] Find a user by name, ID, or mention.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name_query": { "type": "string", "description": "Name, ID, or Mention." }
                    },
                    "required": ["name_query"]
                }
            },
            {
                "name": "get_voice_channel_info",
                "description": "[Discord/VC] Get info about a voice channel (members). Default: current channel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel_name": { "type": "string", "description": "Optional channel name." }
                    },
                    "required": []
                }
            },
            {
                "name": "join_voice_channel",
                "description": "[Discord/VC] Join a voice channel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel_name": { "type": "string", "description": "Optional channel to join." }
                    },
                    "required": []
                }
            },
            {
                "name": "leave_voice_channel",
                "description": "[Discord/VC] Leave the current voice channel.",
                "parameters": { "type": "object", "properties": {}, "required": [] }
            },
            {
                "name": "manage_user_voice",
                "description": "[Discord/VC] Disconnect, Move, or Summon a user. (Admin/Self only)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_user": { "type": "string", "description": "Target user (Name/ID/Mention)." },
                        "action": { "type": "string", "enum": ["disconnect", "move", "summon"], "description": "Action to perform." },
                        "channel_name": { "type": "string", "description": "Destination channel (for move)." }
                    },
                    "required": ["target_user", "action"]
                }
            },
            {
                "name": "shiritori",
                "description": "[Discord/Game] Play Shiritori (Word Chain).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": { "type": "string", "enum": ["start", "play", "check_bot"] },
                        "word": { "type": "string" },
                        "reading": { "type": "string" }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "music_play",
                "description": "[Discord/Music] Play music from YouTube.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": { "type": "string", "description": "Song name or URL." }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "music_control",
                "description": "[Discord/Music] Control playback (skip, stop, loop, queue).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": { "type": "string", "enum": ["skip", "stop", "loop_on", "loop_off", "queue_show", "replay_last"] }
                    },
                    "required": ["action"]
                }
            },

            # --- 2. Image Generation ---
            {
                "name": "generate_image",
                "description": "[Image] Generate an image using Stable Diffusion (FLUX).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": { "type": "string", "description": "English prompt for generation." },
                        "negative_prompt": { "type": "string" },
                        "width": { "type": "integer", "default": 512 },
                        "height": { "type": "integer", "default": 512 }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "get_current_model",
                "description": "[Image] Get current image generation model.",
                "parameters": { "type": "object", "properties": {}, "required": [] }
            },
            {
                "name": "change_model",
                "description": "[Image] Change image generation model.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "model_name": { "type": "string", "description": "Model name." }
                    },
                    "required": ["model_name"]
                }
            },

            # --- 3. Voice Generation ---
            {
                "name": "change_voice",
                "description": "[Voice] Change TTS character (Zundamon, Metan, etc).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "character_name": { "type": "string", "description": "Target character name." }
                    },
                    "required": ["character_name"]
                }
            },
            {
                "name": "tts_speak",
                "description": "[Voice] (Placeholder) Speak text directly.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": { "type": "string" }
                    },
                    "required": ["text"]
                }
            },

            # --- 4. Video Generation (Placeholder) ---
            {
                "name": "generate_video",
                "description": "[Video] (Placeholder) Generate video from prompt.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": { "type": "string" }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "get_video_models",
                "description": "[Video] (Placeholder) Get available video models.",
                "parameters": { "type": "object", "properties": {}, "required": [] }
            },
            {
                "name": "change_video_model",
                "description": "[Video] (Placeholder) Change video generation model.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "model_name": { "type": "string" }
                    },
                    "required": ["model_name"]
                }
            },

            # --- 5. Video Recognition (Placeholder) ---
            {
                "name": "analyze_video",
                "description": "[VideoAnalysis] (Placeholder) Analyze video content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "video_path": { "type": "string" }
                    },
                    "required": ["video_path"]
                }
            },
            {
                "name": "segment_objects",
                "description": "[VideoAnalysis] (Placeholder) Segment objects in video.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "video_path": { "type": "string" },
                        "prompt": { "type": "string" }
                    },
                    "required": ["video_path"]
                }
            },

            # --- 6. Search ---
            {
                "name": "google_search",
                "description": "[Search] Search Google for information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": { "type": "string" }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "google_shopping_search",
                "description": "[Search] Search Google Shopping for products.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": { "type": "string" }
                    },
                    "required": ["query"]
                }
            },

            # --- 7. Admin & System ---
            {
                "name": "create_file",
                "description": "[Admin] Create a file (Creator only).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": { "type": "string" },
                        "content": { "type": "string" }
                    },
                    "required": ["filename", "content"]
                }
            },
            {
                "name": "create_channel",
                "description": "[Admin] Create a server channel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": { "type": "string" },
                        "type": { "type": "string", "enum": ["text", "voice", "category"] },
                        "category_name": { "type": "string" }
                    },
                    "required": ["name", "type"]
                }
            },
            {
                "name": "get_system_stats",
                "description": "[Admin] Get PC system stats.",
                "parameters": { "type": "object", "properties": {}, "required": [] }
            },
            {
                "name": "system_control",
                "description": "[Admin] Control PC system (Volume/App). Creator only.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": { "type": "string", "enum": ["set_volume", "open_app", "mute"] },
                        "value": { "type": "string" }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "system_check",
                "description": "[Admin] Run functionality check.",
                "parameters": { "type": "object", "properties": {}, "required": [] }
            },
            {
                "name": "set_timer",
                "description": "[Admin/Time] Set a timer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "seconds": { "type": "integer" },
                        "label": { "type": "string" }
                    },
                    "required": ["seconds"]
                }
            },
            {
                "name": "set_alarm",
                "description": "[Admin/Time] Set an alarm (HH:MM).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "time": { "type": "string", "description": "HH:MM format" },
                        "label": { "type": "string" }
                    },
                    "required": ["time"]
                }
            },
            {
                "name": "check_points",
                "description": "[Admin/Point] Check user points.",
                "parameters": {
                     "type": "object",
                     "properties": {
                         "target_user": { "type": "string" }
                     },
                     "required": []
                }
            }
        ]


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
            async def delayed_feedback():
                await asyncio.sleep(0.5) # 500ms delay
                # If status message exists (implicit check for done)
                if status_manager.message:
                    media_cog = self.bot.get_cog("MediaCog")
                    if media_cog:
                        await media_cog.speak(message.channel, "回答を生成しています")
            voice_feedback_task = asyncio.create_task(delayed_feedback())

        try:
            system_prompt = await self._build_system_prompt(message)
            try:
                history = await self._build_history(message)
            except Exception as e:
                logger.error(f"Failed to build history: {e}")
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
            
            # --- ROUTER LOGIC (Advanced) ---
            from ..config import Config
            config = Config.load()
            
            # Try to parse route_eval
            import re
            route_match = re.search(r"route_eval.*?(\{.*?\})", content, re.DOTALL | re.IGNORECASE)
            # Support cases where it creates a json codeblock for it
            if not route_match:
                 route_match = re.search(r"```json\s*(\{.*?route_eval.*?\})\s*```", content, re.DOTALL | re.IGNORECASE)

            if route_match:
                try:
                    route_data_raw = route_match.group(1)
                    # Parsing potentially nested JSON
                    route_json = json.loads(route_data_raw)
                    # Extract internal object if nested
                    eval_data = route_json.get("route_eval", route_json) 
                    
                    needs_thinking = eval_data.get("needs_thinking", False)
                    confidence = eval_data.get("confidence", 1.0)
                    
                    logger.info(f"🧩 Router Eval: Needs Thinking={needs_thinking}, Confidence={confidence}")

                    # --- HYBRID/FAST PASS Check ---
                    # If prompt is short (< 25 chars), ignore "needs_thinking" (likely false positive or simple greeting)
                    # This prevents heavy switching for "Hello" or "Good morning"
                    if len(prompt) < 25:
                        logger.info("⚡ Fast Pass: Short input detected. Skipping escalation.")
                        needs_thinking = False

                    # Check Router Thresholds
                    # Force thinking if confidence is low or explicitly requested
                    is_low_conf = confidence < config.router_thresholds.get("confidence_cutoff", 0.72)
                    
                    if (needs_thinking or is_low_conf):
                        resource_manager = self.bot.get_cog("ResourceCog").manager
                        
                        # Only switch if we are NOT already in Thinking mode
                        # (We infer mode from current script or just force it for now)
                        # A better check would be in ResourceManager, but we'll specificy explicit target here
                        
                        # Only switch if we are in 'instruct' or 'gaming' mode (implied default)
                        # Ideally ResourceManager keeps track of current mode. 
                        # For now, we trust the switch_model call to handle no-ops if same mode.
                        
                        if resource_manager.current_context == "llm": # Ensure we are in LLM context
                             logger.info("⚡ Router triggered ESCALATION to Thinking Mode.")
                             await status_manager.next_step("⚠️ 難問検知: 思考エンジンへ切り替え中...")
                             
                             # 1. Hot Swap
                             await resource_manager.switch_model("thinking")
                             
                             # 2. Add Context for Thinking Model
                             # context_handover = f"Instruct Model Analysis: {eval_data}\n\nUser Question: {prompt}\n\nPlease solve this step-by-step."
                             # Actually, we just continue the conversation but now with a smarter brain.
                             # We should remove the "router" instruction from the last user message to avoid confusion?
                             # Or just append a system note.
                             
                             await status_manager.next_step("🤔 じっくり思考中...")
                             
                             # 3. Re-Generate with Thinking Model
                             # NOTE: We use the SAME messages history, but the new model will answer
                             content = await self._llm.chat(messages=messages, temperature=0.7)
                             logger.info(f"🧠 Thinking Model Response: {content}")

                except Exception as e:
                    logger.error(f"Router parsing failed: {e}")
            
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
                        "content": f"The tool has been executed successfully. Here is the result:\n{tool_result}\n\nUsing the information above, please answer my original question in Japanese. Do not call the tool again."
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

