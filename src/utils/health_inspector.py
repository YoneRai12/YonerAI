import logging
import discord
import os
import aiosqlite
import json
import time
from datetime import datetime, timedelta
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
            "memory": False,
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
        
        # 4. Memory Health Check
        mem_ok, mem_report = await self.check_memory_health()
        results["memory"] = mem_ok
        report_lines.append(mem_report)

        # 5. Syntax/Runtime Check
        # If we got here, the bot process is running, so basic Python is fine.
        
        # Decision
        # DB, Cogs, and Memory are critical. Voice depends.
        if results["database"] and results["cogs"] and results["memory"]:
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

    async def check_memory_health(self) -> (bool, str):
        """
        Checks for stuck 'Processing' states and directory access.
        """
        # A. Directory Check
        memory_dir = r"L:\ORA_Memory\users"
        if not os.path.exists(memory_dir):
             return False, "❌ メモリ診断: ディレクトリが見つかりません (L:\\ORA_Memory\\users)"
        
        # B. Stuck State Check
        stuck_users = []
        try:
            now = time.time()
            # Threshold: 20 minutes (1200 seconds)
            threshold = 1200 
            
            for f in os.listdir(memory_dir):
                if not f.endswith(".json"): continue
                path = os.path.join(memory_dir, f)
                
                try:
                    # Quick read without lock to avoid blocking checks
                    with open(path, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        
                    if data.get("status") == "Processing":
                        # Check last_updated
                        # It's usually ISO format string, but verify
                        last_up = data.get("last_updated") or data.get("layer1_session_meta", {}).get("updated")
                        if last_up:
                            try:
                                # Parse ISO
                                if "." in last_up:
                                    dt = datetime.strptime(last_up.split("+")[0], "%Y-%m-%dT%H:%M:%S.%f")
                                else:
                                    dt = datetime.strptime(last_up.split("+")[0], "%Y-%m-%dT%H:%M:%S")
                                
                                # Convert to timestamp
                                ts = dt.timestamp()
                                if now - ts > threshold:
                                    stuck_users.append(f)
                            except:
                                pass # Date parse fail, ignore
                except:
                    continue # Read fail, ignore
            
            if stuck_users:
                return False, f"⚠️ メモリ診断: {len(stuck_users)}人のユーザーが 'Processing' でスタックしています"
        
        except Exception as e:
            return False, f"❌ メモリ診断: エラー発生 ({e})"

        # C. Semaphore Check
        # C. Worker & Buffer Check
        mem_cog = self.bot.get_cog("MemoryCog")
        if mem_cog:
            if not mem_cog.memory_worker.is_running():
                 return False, "❌ メモリ診断: Worker Loopが停止しています！"
            
            buffer_size = sum(len(msgs) for msgs in mem_cog.message_buffer.values())
            if buffer_size > 100:
                 return True, f"⚠️ メモリ診断: 処理待ちメッセージが溜まっています ({buffer_size}件)"
        else:
            return False, "❌ メモリ診断: MemoryCogが見つかりません"


        return True, "✅ メモリシステム: 正常"
