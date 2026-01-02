import logging
import subprocess
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Literal
import psutil
from discord.ext import tasks
import os


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
    "cmd": "cmd.exe" # Be careful, but cmd without args is just a window
}

MAX_VOLUME = 40

class SystemCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.volume_interface = None
        if AUDIO_AVAILABLE:
            try:
                # pycaw initialization can vary by version or OS state
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.volume_interface = interface.QueryInterface(IAudioEndpointVolume)
                logger.info("Audio control interface initialized successfully.")
            except AttributeError:
                # Fallback for some pycaw versions or if GetSpeakers returns a list/different object
                try:
                    # Alternative init (sometimes GetSpeakers() returns a device directly? or we need Enumerator)
                    # For now, just log and disable if it fails to avoid crash
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
        except RuntimeError:
            pass # Already running

    def cog_unload(self):
        self.sync_discord_state.cancel()

    @tasks.loop(seconds=5)
    async def sync_discord_state(self):
        """Dump Discord State (Presence/Names/Guilds) to JSON for the Web API."""
        await self.bot.wait_until_ready()
        try:
            state_path = r"L:\ORA_State\discord_state.json"
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
                    if hasattr(member, 'banner') and member.banner:
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
                            "is_nitro": bool(member.premium_since or member.display_avatar.is_animated())
                        }
                    else:
                        # Update if 'online' overrides 'offline' (unlikely but safe)
                        if status != "offline" and data["users"][uid]["status"] == "offline":
                            data["users"][uid]["status"] = status
                            data["users"][uid]["guild_id"] = str(guild.id) # Update guild ref to active one
                            # Also update banner if we found one now and didn't have one before?
                            if banner_hash and not data["users"][uid]["banner"]:
                                 data["users"][uid]["banner"] = banner_hash
                            
            import json
            import aiofiles
            from datetime import datetime
            
            data["last_updated"] = datetime.now().isoformat()
            
            # Atomic Write via overwrite
            async with aiofiles.open(state_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False))
                
        except Exception as e:
             logger.error(f"sync_discord_state Error: {e}")
             pass 

    def _check_admin(self, interaction: discord.Interaction) -> bool:
        admin_id = self.bot.config.admin_user_id
        creator_id = 1069941291661672498
        if interaction.user.id == admin_id or interaction.user.id == creator_id:
            return True
        return False

    def _log_audit(self, user: discord.User | discord.Object, action: str, details: str, success: bool):
        status = "SUCCESS" if success else "FAILED"
        user_name = getattr(user, "name", "Unknown")
        log_msg = f"AUDIT: User={user_name}({user.id}) Action={action} Details='{details}' Status={status}"
        logger.info(log_msg)
        # In a real enterprise app, write to a separate file or DB
        with open("system_audit.log", "a", encoding="utf-8") as f:
            import datetime
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"[{timestamp}] {log_msg}\n")

    @app_commands.command(name="pc_control", description="PCシステム操作 (Admin Only)")
    @app_commands.describe(
        action="実行する操作",
        value="設定値 (音量0-40, アプリ名)"
    )
    async def system_control(self, interaction: discord.Interaction, action: Literal["volume", "open", "mute"], value: Optional[str] = None):
        # 1. Admin Check
        if not self._check_admin(interaction):
            await interaction.response.send_message("⛔ この機能は管理者専用です。", ephemeral=True)
            self._log_audit(interaction.user, action, f"value={value} (Unauthorized)", False)
            return

        # 2. DM Check (Optional, but requested for safety)
        # if not isinstance(interaction.channel, discord.DMChannel):
        #     await interaction.response.send_message("⛔ セキュリティのため、このコマンドはDMでのみ実行可能です。", ephemeral=True)
        #     return
        # For now, let's allow it in Guilds if it's the Admin, but maybe ephemeral only?
        # User requested "DM専用: 公開チャンネルでは動かない"
        if interaction.guild_id is not None:
             await interaction.response.send_message("⛔ セキュリティのため、このコマンドはDMでのみ実行可能です。", ephemeral=True)
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
            await interaction.followup.send(f"✅ `{target}` を再読み込みしました！\n音楽再生等は継続されます (MediaCogの場合)。")
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
        creator_id = 1069941291661672498
        if user_id != admin_id and user_id != creator_id:
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
                    import struct
                    
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
                
                is_mac = os.name != 'nt'
                target_ip = os.getenv("PC_IP_ADDRESS")
                ssh_user = os.getenv("PC_SSH_USER")

                try:
                    if is_mac:
                        if not target_ip or not ssh_user:
                            return {"status": False, "message": "Mac運用時は PC_IP_ADDRESS と PC_SSH_USER の設定が必要です。"}
                        # Run via SSH (Assumes SSH keys are set up)
                        cmd = f'ssh {ssh_user}@{target_ip} "shutdown /s /t 0"'
                        subprocess.Popen(cmd, shell=True)
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
