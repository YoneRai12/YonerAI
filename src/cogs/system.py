import logging
import subprocess
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Literal
import psutil

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
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.volume_interface = interface.QueryInterface(IAudioEndpointVolume)
            except Exception as e:
                logger.error(f"Failed to initialize audio interface: {e}")

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
            
            return {"status": False, "message": "不明なアクションです"}

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"status": False, "message": f"エラー: {e}"}

async def setup(bot: commands.Bot):
    await bot.add_cog(SystemCog(bot))
