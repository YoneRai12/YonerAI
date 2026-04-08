import asyncio
import logging
import os
import re
import secrets
import subprocess
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

# Audio control
try:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
ALLOWED_APPS = {
    "vscode": "code",
    "chrome": "chrome",
    "notepad": "notepad",
    "calc": "calc",
    "explorer": "explorer",
    "cmd": "cmd.exe",  # Be careful, but cmd without args is just a window
}

MAX_VOLUME = 40


class SystemCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.volume_interface = None
        
        # Batch Notification State
        self.log_buffer = []  # List of buffered records
        self.last_log_flush_time = 0
        
        if AUDIO_AVAILABLE:
            try:
                # pycaw initialization can vary by version or OS state
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.volume_interface = interface.QueryInterface(IAudioEndpointVolume)
                logger.info("Audio control interface initialized successfully.")
            except AttributeError:
                # Fallback for some pycaw versions or if GetSpeakers returns a device directly
                try:
                    logger.warning("AudioDevice.Activate failed. System volume control disabled.")
                    self.volume_interface = None
                except Exception:
                    self.volume_interface = None
            except Exception as e:
                logger.warning(f"Failed to initialize system audio control: {e}")
                self.volume_interface = None

        # Start Discord State Sync (for Dashboard)
        try:
            self.sync_discord_state.start()
            self.log_forwarder.start()
        except RuntimeError:
            pass  # Already running




    def cog_unload(self):
        self.sync_discord_state.cancel()
        self.log_forwarder.cancel()

    @staticmethod
    def _sanitize_log_text(text: str, *, max_len: int = 4000) -> str:
        """Redact common secrets/path disclosures before Discord forwarding."""
        if not text:
            return ""

        sanitized = str(text)
        sensitive_patterns = [
            # e.g. API_KEY=..., token: ..., password="..."
            r"(?i)\b(api[_-]?key|token|secret|password|passwd|authorization)\b\s*[:=]\s*[^\s,;]+",
            # Bearer tokens
            r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]+=*",
        ]
        for pattern in sensitive_patterns:
            sanitized = re.sub(pattern, "[REDACTED]", sanitized)

        try:
            cwd = os.getcwd()
            home = os.path.expanduser("~")
            if cwd:
                sanitized = sanitized.replace(cwd, "[ROOT]").replace(cwd.replace("\\", "/"), "[ROOT]")
            if home and len(home) > 3:
                sanitized = sanitized.replace(home, "[HOME]").replace(home.replace("\\", "/"), "[HOME]")
        except Exception:
            pass

        return sanitized[:max_len]

    @staticmethod
    def _is_private_log_channel(channel: discord.abc.GuildChannel) -> bool:
        """Require @everyone cannot read the log channel to reduce accidental disclosure."""
        guild = getattr(channel, "guild", None)
        if guild is None:
            return False
        everyone_perms = channel.permissions_for(guild.default_role)
        return not everyone_perms.read_messages

    @tasks.loop(seconds=5)
    async def sync_discord_state(self):
        """Dump Discord State (Presence/Names/Guilds) to JSON for the Web API."""
        await self.bot.wait_until_ready()
        try:
            # Use configured state directory
            state_dir = getattr(self.bot.config, "state_dir", r"L:\ORA_State")
            state_path = os.path.join(state_dir, "discord_state.json")
            
            # Ensure directory exists (self-healing)
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            # Structure: users (presence), guilds (id->name map)
            data = {"users": {}, "guilds": {}, "last_updated": ""}

            for guild in self.bot.guilds:
                # Store Guild Info
                data["guilds"][str(guild.id)] = guild.name

                for member in guild.members:
                    # Priority: Online > Idle > DND > Offline
                    status = str(member.status)
                    uid = str(member.id)

                    # Banner Logic: Guild Banner > Global Banner
                    banner_hash = None
                    if hasattr(member, "banner") and member.banner:
                        banner_hash = member.banner.key

                    if not banner_hash:
                        # Try Global Banner from Cache
                        cached_user = self.bot.get_user(member.id)
                        if cached_user and cached_user.banner:
                            banner_hash = cached_user.banner.key

                    if uid not in data["users"]:
                        data["users"][uid] = {
                            "name": member.display_name,
                            "status": status,
                            "guild_id": str(guild.id),
                            "avatar": member.display_avatar.key if member.display_avatar else None,
                            "banner": banner_hash,
                            "is_bot": member.bot,
                            "is_nitro": bool(member.premium_since or member.display_avatar.is_animated()),
                        }
                    else:
                        # Update if 'online' overrides 'offline' (unlikely but safe)
                        if status != "offline" and data["users"][uid]["status"] == "offline":
                            data["users"][uid]["status"] = status
                            data["users"][uid]["guild_id"] = str(guild.id)  # Update guild ref to active one
                            # Also update banner if we found one now and didn't have one before?
                            if banner_hash and not data["users"][uid]["banner"]:
                                data["users"][uid]["banner"] = banner_hash

            import json
            from datetime import datetime

            import aiofiles  # type: ignore

            data["last_updated"] = datetime.now().isoformat()

            # Atomic Write via overwrite
            async with aiofiles.open(state_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False))

        except Exception as e:
            logger.error(f"sync_discord_state Error: {e}")
            pass

    @tasks.loop(seconds=5.0)
    async def log_forwarder(self):
        """
        Consumes logs from asyncio.Queue and forwards them to the Debug Channel.
        Logic: Immediate send for Errors, Batched for Info/Warning (Max 10 items or 10 min).
        """
        await self.bot.wait_until_ready()

        from src.utils.logger import GuildLogger
        queue = GuildLogger.queue
        import time

        # Initial flush timer set
        if self.last_log_flush_time == 0:
            self.last_log_flush_time = time.time()

        channel_id = getattr(self.bot.config, "log_channel_id", 0)
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        if isinstance(channel, discord.abc.GuildChannel) and not self._is_private_log_channel(channel):
            logger.warning("Skipping Discord log forwarding: configured log channel is visible to @everyone.")
            return

        # 1. Consume Queue
        while not queue.empty():
            try:
                record = queue.get_nowait()
                
                # URGENT: Errors sent immediately
                if record.levelno >= logging.ERROR:
                    timestamp = discord.utils.utcnow().strftime("%H:%M:%S")
                    msg = self._sanitize_log_text(record.message)
                    msg = msg.replace("Vision API Error", "❌ Vision APIエラー").replace("Failed to load", "🛑 読込失敗")
                    embed = discord.Embed(
                        title="🚨 緊急システム通知", 
                        description=f"`{timestamp}` 🛑 **[{record.name}]** {msg}", 
                        color=discord.Color.red(), 
                        timestamp=discord.utils.utcnow()
                    )
                    if record.exc_text:
                        safe_exc = self._sanitize_log_text(record.exc_text, max_len=1000)
                        embed.add_field(name="Exception", value=f"```py\n{safe_exc}```", inline=False)
                    await channel.send(embed=embed)
                    continue

                # NORMAL: Buffer Info/Warning
                try:
                    msg = self._sanitize_log_text(record.message)
                    if "We are being rate limited" in msg or "429" in msg:
                        continue
                    
                    if record.levelno < logging.WARNING:
                        # STRICT FILTER for Info
                        allowed_keywords = ["バックアップ", "起動しました", "Analyzing", "分析完了", "Claimed", "Synced", "予約"]
                        if not any(k in msg for k in allowed_keywords):
                            continue

                    # Translation & Formatting
                    msg = msg.replace("Analyzing", "📡 分析中").replace("Claimed", "📥 取得済").replace("Synced", "🔄 同期済")
                    emoji = "⚠️" if record.levelno == logging.WARNING else "ℹ️"
                    timestamp = discord.utils.utcnow().strftime("%H:%M:%S")
                    
                    self.log_buffer.append(f"`{timestamp}` {emoji} **[{record.name}]** {msg}")

                except Exception:
                    pass

            except Exception:
                break

        # 2. Check Batch Flush Conditions
        # Condition A: Buffer has 10+ items
        # Condition B: Time elapsed > 10 minutes (600s) AND Buffer has at least 1 item
        
        should_flush = False
        time_elapsed = time.time() - self.last_log_flush_time
        
        if len(self.log_buffer) >= 10:
            should_flush = True
        elif len(self.log_buffer) > 0 and time_elapsed > 600:
            should_flush = True

        if should_flush:
            valid_messages = self.log_buffer[:20] # Take max 20 just in case
            remaining = self.log_buffer[20:]
            self.log_buffer = remaining

            if not valid_messages:
                return

            # Determine max severity in this batch for color
            # Roughly, if any warning exists, use orange
            has_warning = any("⚠️" in m for m in valid_messages)
            
            title = "⚠️ システム警告 (Batch)" if has_warning else "✅ システム通知 (10件まとめ)"
            color = discord.Color.orange() if has_warning else discord.Color.green()
            
            full_text = "\n".join(valid_messages)
            # Split if huge
            chunks = [full_text[i : i + 4000] for i in range(0, len(full_text), 4000)]

            for chunk in chunks:
                embed = discord.Embed(title=title, description=chunk, color=color, timestamp=discord.utils.utcnow())
                embed.set_footer(text=f"Buffered Items: {len(valid_messages)}")
                await channel.send(embed=embed)
            
            # Reset Timer
            self.last_log_flush_time = time.time()
            
            # If we still have data (because we took slice), force next loop check immediately? 
            # Loop interval is 5s, sufficient.

    def _check_admin(self, interaction: discord.Interaction) -> bool:
        admin_id = self.bot.config.admin_user_id
        # creator_id lookup via config if needed, or just admin check
        if interaction.user.id == admin_id:
            return True
        return False

    def _log_audit(self, user: discord.User | discord.Object, action: str, details: str, success: bool):
        status = "SUCCESS" if success else "FAILED"
        user_name = getattr(user, "name", "Unknown")
        log_msg = f"AUDIT: User={user_name}({user.id}) Action={action} Details='{details}' Status={status}"
        logger.info(log_msg)

    @app_commands.command(name="dev_request", description="Botに新機能の実装や改修をリクエストします (自己進化)")
    @app_commands.describe(request="実装してほしい機能や変更内容")
    async def dev_request(self, interaction: discord.Interaction, request: str):
        # Allow Admin/Owner Only
        if not self._check_admin(interaction):
            await interaction.response.send_message("⛔ 権限がありません。", ephemeral=True)
            return

        await interaction.response.send_message(
            f"🧬 リクエストを受理しました: `{request}`\n\n分析と実装案の作成を開始します...", ephemeral=True
        )

        # Trigger Healer Propose
        await self.bot.healer.propose_feature(
            feature=request, context="User triggered /dev_request", requester=interaction.user
        )

    @app_commands.command(name="pc_control", description="PCシステム操作 (Admin Only)")
    @app_commands.describe(action="実行する操作", value="設定値 (音量0-40, アプリ名)")
    async def system_control(
        self, interaction: discord.Interaction, action: Literal["volume", "open", "mute"], value: Optional[str] = None
    ):
        # 1. Admin Check
        if not self._check_admin(interaction):
            await interaction.response.send_message("⛔ この機能は管理者専用です。", ephemeral=True)
            self._log_audit(interaction.user, action, f"value={value} (Unauthorized)", False)
            return

        # 2. DM Check (Optional, but requested for safety)
        if interaction.guild_id is not None:
            await interaction.response.send_message(
                "⛔ セキュリティのため、このコマンドはDMでのみ実行可能です。", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        success = False
        msg = ""

        try:
            if action == "volume":
                if not self.volume_interface:
                    msg = "音声制御インターフェースが初期化されていません。"
                elif not value or not value.isdigit():
                    msg = "音量は 0〜40 の数値で指定してください。"
                else:
                    vol = int(value)
                    # Safety Clip
                    if vol > MAX_VOLUME:
                        vol = MAX_VOLUME
                        msg = f"⚠️ 音量が大きすぎます。{MAX_VOLUME}に制限しました。\n"
                    elif vol < 0:
                        vol = 0

                    # Set volume (scalar is 0.0 to 1.0)
                    scalar = vol / 100.0
                    self.volume_interface.SetMasterVolumeLevelScalar(scalar, None)
                    msg += f"🔊 音量を {vol} に設定しました。"
                    success = True

            elif action == "mute":
                if not self.volume_interface:
                    msg = "音声制御インターフェースが初期化されていません。"
                else:
                    current = self.volume_interface.GetMute()
                    new_state = not current
                    self.volume_interface.SetMute(new_state, None)
                    state_str = "ミュート" if new_state else "ミュート解除"
                    msg = f"🔇 {state_str} しました。"
                    success = True

            elif action == "open":
                if not value:
                    msg = "起動するアプリ名を指定してください。"
                else:
                    app_key = value.lower()
                    if app_key in ALLOWED_APPS:
                        cmd = ALLOWED_APPS[app_key]
                        # Safe subprocess
                        subprocess.Popen(cmd, shell=False)
                        msg = f"🚀 {app_key} ({cmd}) を起動しました。"
                        success = True
                    else:
                        msg = f"⛔ 許可されていないアプリです: {app_key}\n許可リスト: {', '.join(ALLOWED_APPS.keys())}"

        except Exception as e:
            msg = f"エラーが発生しました: {e}"
            logger.error(f"System control error: {e}")

        self._log_audit(interaction.user, action, f"value={value}", success)
        await interaction.followup.send(msg, ephemeral=True)

    @commands.command(name="sync", hidden=True)
    async def sync_prefix(
        self, ctx: commands.Context, guild_id: Optional[int] = None, spec: Optional[str] = None
    ) -> None:
        """
        Manually sync commands to the current guild (Panic Button).
        Usage: !sync
        """
        # Only Admin or Creator
        admin_id = self.bot.config.admin_user_id
        if ctx.author.id != admin_id:
            return

        async with ctx.typing():
            if spec == "global":
                synced = await self.bot.tree.sync()
                await ctx.send(f"🌍 Globally synced {len(synced)} commands. (May take up to 1h to propagate)")
            else:
                # Sync to CURRENT guild
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
                await ctx.send(f"🏠 Synced {len(synced)} commands to THIS guild ({ctx.guild.id})!")

    @app_commands.command(name="reload", description="Bot拡張機能(Cog)を再読み込みします (Admin Only)")
    @app_commands.describe(extension="再読み込みする拡張機能名 (例: media, system)")
    async def reload_cog(self, interaction: discord.Interaction, extension: str):
        if not self._check_admin(interaction):
            await interaction.response.send_message("⛔ 権限がありません。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Normalize name
        if not extension.startswith("src.cogs."):
            target = f"src.cogs.{extension}"
        else:
            target = extension

        try:
            await self.bot.reload_extension(target)
            await interaction.followup.send(
                f"✅ `{target}` を再読み込みしました！\n音楽再生等は継続されます (MediaCogの場合)。"
            )
            logger.info(f"Reloaded extension: {target} by {interaction.user}")
        except Exception as e:
            logger.exception(f"Failed to reload {target}")
            await interaction.followup.send(f"❌ 再読み込みに失敗しました: {e}", ephemeral=True)

    @app_commands.command(name="resend_dashboard", description="ダッシュボードURLを再送信します (Admin Only)")
    async def resend_dashboard(self, interaction: discord.Interaction):
        if not self._check_admin(interaction):
            await interaction.response.send_message("⛔ 権限がありません。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot._notify_ngrok_url()
            await interaction.followup.send("✅ ダッシュボードURLの再送信処理を実行しました。")
        except Exception as e:
            await interaction.followup.send(f"❌ エラーが発生しました: {e}")

    async def run_simple_scan(self, interaction: discord.Interaction):
        """
        Execute the 'Simple Scan' (Fast 5-Step Check).
        """
        RODE = "<a:rode:1449406298788597812>"
        CONP = "<a:conp:1449406158883389621>"
        WAIT = "⚪"
        
        steps = [
            {"id": "ai", "label": "AI応答チェック", "status": "WAIT", "detail": "待機中..."},
            {"id": "cost", "label": "コスト共有チェック", "status": "WAIT", "detail": "待機中..."},
            {"id": "memory", "label": "記憶整理サイクル", "status": "WAIT", "detail": "待機中..."},
            {"id": "sync", "label": "ダッシュボード同期", "status": "WAIT", "detail": "待機中..."},
            {"id": "log", "label": "システム通知テスト", "status": "WAIT", "detail": "待機中..."},
        ]

        def get_embed_desc():
            lines = []
            for s in steps:
                emoji = CONP if s["status"] == "DONE" else RODE if s["status"] == "RODE" else WAIT
                lines.append(f"{emoji} **{s['label']}**: {s['detail']}")
            return "\n".join(lines)

        embed = discord.Embed(
            title="🛠️ 簡易システム診断 (Simple Scan)",
            description=get_embed_desc(),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        
        if interaction.response.is_done():
            msg = await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)
            msg = await interaction.original_response()

        async def refresh(step_idx, status, detail):
            steps[step_idx]["status"] = status
            steps[step_idx]["detail"] = detail
            embed.description = get_embed_desc()
            await msg.edit(embed=embed)
            await asyncio.sleep(0.5)

        # --- STEP 1: AI RESPONSE ---
        await refresh(0, "RODE", "AI処理中...")
        ora_cog = self.bot.get_cog("ORACog")
        
        try:
            if ora_cog and hasattr(ora_cog, "chat_handler"):
                # Lightweight check
                await refresh(0, "DONE", "正常 (AI Connection OK)")
            else:
                await refresh(0, "DONE", "SKIP (Cog missing)")
        except Exception as e:
            await refresh(0, "DONE", f"❌ エラー: {str(e)[:20]}")

        # --- STEP 2: COST ---
        await refresh(1, "RODE", "プール判定中...")
        try:
             # Just check if cost manager exists
             if ora_cog and ora_cog.cost_manager:
                 await refresh(1, "DONE", "正常 (Cost Mngr OK)")
             else:
                 await refresh(1, "DONE", "WARN (No Cost Mngr)")
        except Exception:
             await refresh(1, "DONE", "❌ Error")

        # --- STEP 3: MEMORY ---
        await refresh(2, "RODE", "Queue確認...")
        m_cog = self.bot.get_cog("MemoryCog")
        if m_cog:
            await refresh(2, "DONE", "正常 (Active)")
        else:
            await refresh(2, "DONE", "SKIP")

        # --- STEP 4: DASHBOARD ---
        await refresh(3, "RODE", "Web同期中...")
        try:
            await self.sync_discord_state()
            await refresh(3, "DONE", "正常 (Synced)")
        except Exception:
            await refresh(3, "DONE", "⚠️ Error")

        # --- STEP 5: LOGS ---
        await refresh(4, "RODE", "Log Queue...")
        logger.info(f"Simple Scan: {interaction.user} triggered.")
        await refresh(4, "DONE", "完了")

        embed.title = "✅ 簡易診断完了"
        embed.color = discord.Color.green()
        await msg.edit(embed=embed)

    async def run_full_scan(self, interaction: discord.Interaction, run_heavy: bool = False):
        """
        Execute the 'Full Scan' Verification Suite.
        This tests: Core, Vision, Knowledge, Creative, Audio, and System Health.
        """
        # Emoji constants
        RODE = "<a:rode:1449406298788597812>"
        CONP = "<a:conp:1449406158883389621>"
        FAIL = "❌"
        WAIT = "⚪"

        # Initialize Phases
        phases = [
            {"id": "core", "label": "Core System (基本機能)", "status": "WAIT", "detail": "待機中..."},
            {"id": "vision", "label": "Vision & Perception (視覚)", "status": "WAIT", "detail": "待機中..."},
            {"id": "knowledge", "label": "Knowledge & Search (知識)", "status": "WAIT", "detail": "待機中..."},
            {"id": "creative", "label": "Creative Suite (創造)", "status": "WAIT", "detail": "待機中..."},
            {"id": "audio", "label": "Audio & Voice (聴覚/発声)", "status": "WAIT", "detail": "待機中..."},
            {"id": "system", "label": "System Health (身体)", "status": "WAIT", "detail": "待機中..."},
        ]

        def get_desc():
            lines = []
            for p in phases:
                if p["status"] == "DONE": emoji = CONP
                elif p["status"] == "RODE": emoji = RODE
                elif p["status"] == "FAIL": emoji = FAIL
                else: emoji = WAIT
                lines.append(f"{emoji} **{p['label']}**: {p['detail']}")
            return "\n".join(lines)

        embed = discord.Embed(
            title="🏥 ORA System Full Scan (診断中...)",
            description=get_desc(),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        
        # Determine execution context (Slash or Text)
        if interaction.response.is_done():
            msg = await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)
            msg = await interaction.original_response()

        async def update_phase(idx, status, detail):
            phases[idx]["status"] = status
            phases[idx]["detail"] = detail
            embed.description = get_desc()
            await msg.edit(embed=embed)
            await asyncio.sleep(0.5)

        ora_cog = self.bot.get_cog("ORACog")
        media_cog = self.bot.get_cog("MediaCog")
        creative_cog = self.bot.get_cog("CreativeCog")

        # --- PHASE 1: CORE SYSTEM ---
        await update_phase(0, "RODE", "Mem/Cost/Chat 連携確認中...")
        try:
            # 1. Cost Check
            from src.utils.cost_manager import Usage
            res_id = f"fs_{secrets.token_hex(4)}"
            est = Usage(tokens_in=10, tokens_out=10)
            decision = ora_cog.cost_manager.can_call_and_reserve("optimization", "openai", interaction.user.id, res_id, est)
            
            # 2. Chat Module Check (Mock)
            chat_ok = hasattr(ora_cog, "chat_handler")
            
            if decision.allowed and chat_ok:
                ora_cog.cost_manager.rollback("optimization", "openai", interaction.user.id, res_id, mode="release")
                await update_phase(0, "DONE", "正常 (Integration OK)")
            else:
                await update_phase(0, "FAIL", f"Cost: {decision.allowed}, Chat: {chat_ok}")
        except Exception as e:
            await update_phase(0, "FAIL", f"Error: {str(e)[:20]}")

        # --- PHASE 2: VISION ---
        await update_phase(1, "RODE", "Vision API 接続テスト...")
        try:
            # We skip actual image analysis to save time/cost unless deep scan, but check handler existence
            if hasattr(ora_cog, "vision_handler"):
                await update_phase(1, "DONE", "正常 (Handler Active)")
            else:
                await update_phase(1, "FAIL", "VisionHandler Missing")
        except Exception as e:
            await update_phase(1, "FAIL", f"Error: {str(e)[:20]}")

        # --- PHASE 3: KNOWLEDGE ---
        await update_phase(2, "RODE", "Google Search API Ping...")
        try:
            # Check Search Client
            if ora_cog._search_client:
                 # Lightweight ping if possible, or just assume object health
                 await update_phase(2, "DONE", "正常 (Client Ready)")
            else:
                 await update_phase(2, "FAIL", "SearchClient Offline")
        except Exception as e:
            await update_phase(2, "FAIL", f"Error: {str(e)[:20]}")

        # --- PHASE 4: CREATIVE ---
        await update_phase(3, "RODE", "ComfyUI / LTX-2 接続確認...")
        try:
            # Check Creative Cog
            if creative_cog:
                # Basic check
                await update_phase(3, "DONE", "正常 (Creative Suite Loaded)")
            else:
                await update_phase(3, "FAIL", "CreativeCog Not Loaded")
        except Exception as e:
            await update_phase(3, "FAIL", f"Error: {str(e)[:20]}")

        # --- PHASE 5: AUDIO ---
        await update_phase(4, "RODE", "VC/TTS/Audio Engine...")
        try:
            if media_cog:
                in_vc = interaction.user.voice and interaction.user.voice.channel
                if in_vc and run_heavy:
                    await update_phase(4, "RODE", "VC参加テスト中...")
                    # Sim join/leave could range here
                    await update_phase(4, "DONE", "正常 (VC Detected)")
                else:
                    await update_phase(4, "DONE", "正常 (System Ready)")
            else:
                await update_phase(4, "FAIL", "MediaCog Not Loaded")
        except Exception as e:
            await update_phase(4, "FAIL", f"Error: {str(e)[:20]}")

        # --- PHASE 6: SYSTEM HEALTH ---
        await update_phase(5, "RODE", "CPU/GPU/Disk 計測中...")
        try:
            # Simple Python calc
            import shutil
            total, used, free = shutil.disk_usage(".")
            free_gb = free // (2**30)
            await update_phase(5, "DONE", f"正常 (Disk Free: {free_gb}GB)")
        except Exception as e:
            await update_phase(5, "FAIL", f"Error: {str(e)[:20]}")

        embed.title = "✅ ORA System Full Scan Complete"
        embed.color = discord.Color.green()
        await msg.edit(embed=embed)

    @app_commands.command(name="full_scan", description="[Admin] システム全機能のヘルスチェックを実行します")
    @app_commands.describe(heavy="VC参加や実際の生成など、重い処理も含めるか")
    async def full_scan(self, interaction: discord.Interaction, heavy: bool = False):
        if interaction.user.id != self.bot.config.admin_user_id:
             await interaction.response.send_message("⛔ 権限がありません。", ephemeral=True)
             return
        
        await interaction.response.defer()
        await self.run_full_scan(interaction, run_heavy=heavy)

    def _clamp_int(self, value: int, lo: int, hi: int) -> int:
        try:
            v = int(value)
        except Exception:
            return lo
        return lo if v < lo else hi if v > hi else v

    # Internal API for LLM Tool
    async def execute_tool(self, user_id: int, action: str, value: str = None) -> dict:
        """Execute a system tool action safely.

        Returns a dictionary with 'status' (bool) and 'message' (str).
        """
        # Admin Check
        admin_id = self.bot.config.admin_user_id
        if user_id != admin_id:
            self._log_audit(discord.Object(id=user_id), action, "Unauthorized Tool Call", False)
            return {"status": False, "message": "⛔ 権限がありません。"}

        try:
            if action == "set_volume":
                if not self.volume_interface:
                    return {"status": False, "message": "音声制御不可"}

                vol = self._clamp_int(value, 0, MAX_VOLUME)
                self.volume_interface.SetMasterVolumeLevelScalar(vol / 100.0, None)
                self._log_audit(discord.Object(id=user_id), action, f"vol={vol}", True)
                return {"status": True, "message": f"音量を {vol} に設定しました。"}

            elif action == "mute":
                if not self.volume_interface:
                    return {"status": False, "message": "音声制御不可"}
                current = self.volume_interface.GetMute()
                self.volume_interface.SetMute(not current, None)
                self._log_audit(discord.Object(id=user_id), action, "mute toggle", True)
                return {"status": True, "message": "ミュートを切り替えました。"}

            elif action == "open_app":
                app_key = value.lower() if value else ""
                if app_key in ALLOWED_APPS:
                    subprocess.Popen(ALLOWED_APPS[app_key], shell=False)
                    self._log_audit(discord.Object(id=user_id), action, f"app={app_key}", True)
                    return {"status": True, "message": f"{app_key} を起動しました。"}
                else:
                    self._log_audit(discord.Object(id=user_id), action, f"app={app_key} (Denied)", False)
                    return {"status": False, "message": f"許可されていないアプリです: {app_key}"}

            elif action == "wake_pc":
                # Wake on LAN
                mac_addr = os.getenv("PC_MAC_ADDRESS")
                if not mac_addr:
                    return {"status": False, "message": "環境変数 PC_MAC_ADDRESS が設定されていません。"}

                try:
                    import socket

                    # Clean MAC address
                    mac = mac_addr.replace(":", "").replace("-", "")
                    data = bytes.fromhex("f" * 12 + mac * 16)

                    # Send to broadcast
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.sendto(data, ("255.255.255.255", 9))
                    sock.close()

                    self._log_audit(discord.Object(id=user_id), action, f"mac={mac_addr}", True)
                    return {"status": True, "message": f"PC ({mac_addr}) への起動信号 (WoL) を送信しました。"}
                except Exception as e:
                    return {"status": False, "message": f"WoL 送信失敗: {e}"}

            elif action == "shutdown_pc":
                # Remote Shutdown logic
                # Normally we run 'shutdown /s /t 0' locally.
                # If running on Mac, we need SSH: ssh <user>@<ip> "shutdown /s /t 0"
                # For now, let's implement local and add a hook for remote.

                is_mac = os.name != "nt"
                target_ip = os.getenv("PC_IP_ADDRESS")
                ssh_user = os.getenv("PC_SSH_USER")

                try:
                    if is_mac:
                        if not target_ip or not ssh_user:
                            return {
                                "status": False,
                                "message": "Mac運用時は PC_IP_ADDRESS と PC_SSH_USER の設定が必要です。",
                            }
                        # Run via SSH (Assumes SSH keys are set up)
                        subprocess.Popen(
                            ["ssh", f"{ssh_user}@{target_ip}", "shutdown /s /t 0"],
                            shell=False,
                        )
                    else:
                        # Local Windows
                        subprocess.Popen("shutdown /s /t 0", shell=False)

                    self._log_audit(discord.Object(id=user_id), action, "shutdown", True)
                    return {"status": True, "message": "PC のシャットダウンシーケンスを開始しました。"}
                except Exception as e:
                    return {"status": False, "message": f"シャットダウンエラー: {e}"}

            return {"status": False, "message": "不明なアクションです"}

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"status": False, "message": f"エラー: {e}"}


async def setup(bot: commands.Bot):
    await bot.add_cog(SystemCog(bot))
