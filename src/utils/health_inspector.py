import logging
import discord
import os
import aiosqlite
from discord.ext import commands

logger = logging.getLogger(__name__)

class HealthInspector:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def run_diagnostics(self) -> dict:
        """
        Runs a suite of health checks.
        Returns a dict of results. {'ok': bool, 'report': str, 'details': dict}
        """
        results = {
            "database": False,
            "voice": False,
            "cogs": False,
            "overall": False
        }
        report_lines = []

        # 1. Database Check
        try:
            # Assume Store is at bot.store (standard in this bot)
            # Or assume we can connect to the DB file manually if we know path
            db_path = getattr(self.bot, "db_path", "ora_v2.sqlite") # Fallback
            if hasattr(self.bot, "store") and hasattr(self.bot.store, "_db_path"):
                 db_path = self.bot.store._db_path
            
            async with aiosqlite.connect(db_path) as db:
                await db.execute("SELECT 1")
            results["database"] = True
            report_lines.append("✅ データベース接続: OK")
        except Exception as e:
            report_lines.append(f"❌ データベース接続: 失敗 ({e})")

        # 2. Voice Dependencies Check
        if discord.opus.is_loaded():
            results["voice"] = True
            report_lines.append("✅ 音声ライブラリ (Opus): OK")
        else:
            # On Windows, sometimes it's lazy loaded? 
            # But usually should be loaded by startup.
            report_lines.append("⚠️ 音声ライブラリ (Opus): 未ロード")
            # voice is not critical for bot boot, so maybe don't fail overall?
            # User specifically cares about Voice Control though.
            results["voice"] = False

        # 3. Cogs Check
        # Check if core cogs are loaded
        core_cogs = ["src.cogs.ora", "src.cogs.system", "src.cogs.memory"]
        loaded_cogs = list(self.bot.extensions.keys())
        missing_cogs = [c for c in core_cogs if c not in loaded_cogs]
        
        if not missing_cogs:
            results["cogs"] = True
            report_lines.append("✅ コア機能: 全てロード済み")
        else:
            report_lines.append(f"❌ コア機能欠損: {', '.join(missing_cogs)}")
        
        # 4. Syntax/Runtime Check
        # If we got here, the bot process is running, so basic Python is fine.
        
        # Decision
        # DB and Cogs are critical. Voice depends.
        if results["database"] and results["cogs"]:
            results["overall"] = True
            report_lines.insert(0, "**自動診断レポート: 正常**")
        else:
            results["overall"] = False
            report_lines.insert(0, "**自動診断レポート: 異常あり**")
            
        full_report = "\n".join(report_lines)
        return {
            "ok": results["overall"],
            "report": full_report,
            "details": results
        }
