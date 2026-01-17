import logging
import traceback
import discord
import io
import os
import shutil
import zipfile
import subprocess
import py_compile
import time
import json
import asyncio
from typing import Optional
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

class HealerView(discord.ui.View):
    def __init__(self, bot, filepath, new_content, backup_path, analysis_text):
        super().__init__(timeout=None) # Persistent view if needed, but ephemeral logic is fine for now
        self.bot = bot
        self.filepath = filepath
        self.new_content = new_content
        self.backup_path = backup_path
        self.analysis_text = analysis_text
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # SECURITY: Only Admin
        if interaction.user.id != self.bot.config.admin_user_id:
            await interaction.response.send_message("⛔ あなたにはこの操作を行う権限がありません。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="修正を適用 (Apply)", style=discord.ButtonStyle.green, emoji="🛠️")
    async def apply_fix(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        try:
            # --- GUARDRAILS START ---
            from .backup_manager import BackupManager
            from .health_inspector import HealthInspector
            
            backup_mgr = BackupManager(os.getcwd())
            inspector = HealthInspector(self.bot)
            
            # 0. Create Snapshot
            snapshot_path = await self.bot.loop.run_in_executor(None, backup_mgr.create_snapshot, "Before_Healer_Apply")
            
            # --- GUARDRAILS END ---

            # 1. Ensure Directory Exists
            if os.path.dirname(self.filepath):
                os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

            # 2. Apply Fix
            async with aiofiles.open(self.filepath, 'w', encoding='utf-8') as f:
                await f.write(self.new_content)
            
            # 3. Reload/Load Extension
            reload_error = None
            if "src/cogs/" in self.filepath.replace("\\", "/"):
                filename = os.path.basename(self.filepath)
                rel_path = os.path.relpath(self.filepath, os.getcwd())
                ext_name = rel_path.replace("\\", ".").replace("/", ".").replace(".py", "")
                
                try:
                    if ext_name in self.bot.extensions:
                        await self.bot.reload_extension(ext_name)
                    else:
                        await self.bot.load_extension(ext_name)
                except Exception as e:
                    reload_error = str(e)

            # 4. Health Check
            diag = await inspector.run_diagnostics()
            
            # 5. Decision & Rollback
            if reload_error or not diag["ok"]:
                # ROLLBACK
                await self.bot.loop.run_in_executor(None, backup_mgr.restore_snapshot, snapshot_path)
                
                # If we rolled back, strictly speaking we should reload/unload again to match disk state?
                # But typically file restore is Step 1.
                # If reload crashed, we are in bad state.
                # Restoring file + reloading again (safely) is ideal, but complicated.
                # For now, just restoring the file is the critical "Safe Net".
                
                fail_msg = f"⛔ **自動診断失敗! ロールバックを実行しました**\n\n**理由**: {reload_error if reload_error else 'システム診断NG'}\n\n{diag['report']}"
                
                embed = interaction.message.embeds[0]
                embed.color = discord.Color.red()
                embed.title = "🚑 Auto-Healer: Rollback Triggered"
                embed.description = fail_msg
                embed.set_footer(text=f"Restored from: {os.path.basename(snapshot_path)}")
                
                # Disable buttons
                for child in self.children:
                    child.disabled = True
                    
                await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)
                return

            # SUCCESS
            msg = "✅ **修正を適用し、正常動作を確認しました**"
            msg += f"\n\n{diag['report']}"
            msg += f"\nバックアップ: `{os.path.basename(snapshot_path)}`"
            
            # Update Message
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.title = "🚑 Auto-Healer: Fixed & Verified"
            embed.clear_fields() # Clear old proposal details
            embed.description = msg
            
            # Disable buttons
            for child in self.children:
                child.disabled = True
            
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)
            
        except Exception as e:
             await interaction.followup.send(f"❌ 適用プロセス中に致命的なエラー: {e}", ephemeral=True)


    @discord.ui.button(label="破棄 (Dismiss)", style=discord.ButtonStyle.grey, emoji="🗑️")
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Update embed to show dismissed
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.dark_grey()
        embed.title = "🚑 Auto-Healer: Dismissed"
        
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(embed=embed, view=self)




class Healer:
    def __init__(self, bot, llm: LLMClient):
        self.bot = bot
        self.llm = llm

    async def handle_error(self, ctx, error: Exception):
        """
        Analyzes the error and proposes a fix to the Debug Channel.
        """
        # Target Channel (Configured or Default)
        channel_id = getattr(self.bot.config, "log_channel_id", 0)
        
        # Get traceback
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        logger.error(f"Healer caught error: {error}")

        # Context Info
        if hasattr(ctx, 'author'):
            invoker = f"{ctx.author} ({ctx.author.id})"
            command = str(ctx.command) if ctx.command else "Unknown"
        else:
            invoker = "System/Event"
            command = str(ctx)

        # Ask LLM for analysis and patch
        try:
            prompt = f"""
            You are an expert Python debugger. The user wants to FIX the error.
            
            Error: {str(error)}
            Traceback:
            {tb[-1500:]}
            
            Context: {invoker} invoked '{command}'.
            
            Task:
            1. Analyze the root cause.
            2. Determine the file closest to the error source (from the list below or traceback).
            3. Provide the CORRECTED full content of that file (or a specific function). 
               *Currently, stick to FULL FILE content for safety unless excessively large.*
            4. Verify the fix (explain logic).
            5. Output STRICT JSON format.
            
            Project Root: {os.getcwd()}
            
            Output JSON Schema:
            {{
                "analysis": "Cause explanation in Japanese",
                "verification": "Why it works in Japanese",
                "filepath": "Relative path to file (e.g., src/cogs/ora.py)",
                "new_content": "COMPLETE content of the file with fix applied"
            }}
            """
            
            # Using 'gpt-5.1-codex' (Cloud) as requested by user ("Use this!")
            try:
                analysis_json = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}], 
                    temperature=0.0,
                    model="gpt-5.1-codex"
                )
            except Exception as e:
                logger.warning(f"Primary Cloud LLM (gpt-5.1-codex) failed: {e}. Fallback to Standard (gpt-4o).")
                analysis_json = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}], 
                    temperature=0.0,
                    model="gpt-4o"
                )
            
            # Parse JSON
            cleaned_json = analysis_json.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json.replace("```json", "").replace("```", "")
            elif cleaned_json.startswith("```"):
                cleaned_json = cleaned_json.replace("```", "")
            
            data = json.loads(cleaned_json)
            
            filepath = data.get("filepath", "")
            new_content = data.get("new_content", "")
            analysis_msg = data.get("analysis", "N/A")
            verification_msg = data.get("verification", "N/A")
            
            # Prepare Stage
            if filepath and os.path.exists(filepath) and new_content:
                # Create Backup immediately (Safety)
                timestamp = int(time.time())
                backup_path = f"{filepath}.{timestamp}.bak"
                shutil.copy2(filepath, backup_path)
                
                # Check Syntax
                try:
                    compile(new_content, filepath, 'exec')
                    
                    # Create UI
                    view = HealerView(self.bot, filepath, new_content, backup_path, analysis_msg)
                    
                    embed = discord.Embed(title="🚑 Auto-Healer Proposal", color=discord.Color.yellow())
                    embed.description = f"**Error Detected**\n`{str(error)[:200]}`\n\n**Analysis**\n{analysis_msg[:800]}\n\n**Proposed Fix**\nFile: `{filepath}`\nBackup: `{os.path.basename(backup_path)}`"
                    embed.add_field(name="Verification", value=verification_msg[:500], inline=False)
                    embed.set_footer(text=f"Triggered by: {invoker}")

                    # Send to Channel
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        await channel.send(embed=embed, view=view)
                    else:
                        logger.warning(f"Healer: Log Channel {channel_id} not found.")

                except SyntaxError as syn_err:
                    # Report Syntax Failure
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                         await channel.send(f"⚠️ Healer generated invalid code: {syn_err}")

            else:
                 # Report Analysis Only (No fix found)
                 embed = discord.Embed(title="🚑 Healer Report (No Fix)", color=discord.Color.red())
                 embed.description = f"**Error**: `{str(error)}`\n\n**Analysis**: {analysis_msg}"
                 channel = self.bot.get_channel(channel_id)
                 if channel:
                     await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Healer failed to Auto-Patch: {e}")
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(f"⚠️ **Healer Critical Failure**: {e}\nOriginal Error: {error}")
            except: pass

    def _get_file_tree(self, root_dir: str = ".") -> str:
        """Returns a string representation of the src directory tree."""
        tree_lines = []
        start_dir = os.path.join(root_dir, "src")
        if not os.path.exists(start_dir):
            return "src/ (Not Found)"
            
        for root, dirs, files in os.walk(start_dir):
            level = root.replace(start_dir, '').count(os.sep)
            indent = ' ' * 4 * (level)
            tree_lines.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                if f.endswith(".py"):
                    tree_lines.append(f"{subindent}{f}")
        return "\n".join(tree_lines)

    async def _check_duplicates(self, feature_request: str) -> Optional[str]:
        """Checks if a similar command already exists to prevent re-invention."""
        try:
            # 1. Gather all commands
            commands = []
            for cmd in self.bot.commands:
                commands.append(f"Prefix Command: {cmd.name} - {cmd.help or 'No help'}")
            
            # 2. Gather Slash Commands (Tree)
            for cmd in self.bot.tree.walk_commands():
                desc = cmd.description if hasattr(cmd, 'description') else "No description"
                commands.append(f"Slash Command: /{cmd.name} - {desc}")
            
            cmd_list = "\n".join(commands[:100]) # Limit context window
            
            # 3. Ask LLM
            prompt = f"""
            User Request: "{feature_request}"
            Existing Commands:
            {cmd_list}
            
            Does the request match an existing command?
            If YES, output strictly the Command Name (e.g., "/voice_off").
            If NO, output "NO".
            """
            
            resp = await self.llm.chat([{"role": "user", "content": prompt}], temperature=0.0)
            if "NO" in resp.upper():
                return None
            return resp.strip()
            
        except Exception as e:
            logger.error(f"Dedup check failed: {e}")
            return None

    async def execute_evolution(self, filepath: str, new_content: str, reason: str = "Autonomous Update") -> dict:
        """
        Executes an update programmatically (Auto-Pilot).
        """
        try:
            # --- GUARDRAILS START ---
            from .backup_manager import BackupManager
            from .health_inspector import HealthInspector
            
            backup_mgr = BackupManager(os.getcwd())
            inspector = HealthInspector(self.bot)
            
            # 0. Create Snapshot
            snapshot_path = await self.bot.loop.run_in_executor(None, backup_mgr.create_snapshot, reason)
            
            # 1. Ensure Directory Exists
            if os.path.dirname(filepath):
                os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # 2. Apply Fix
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(new_content)
            
            # 3. Reload/Load Extension
            reload_error = None
            if "src/cogs/" in filepath.replace("\\", "/"):
                filename = os.path.basename(filepath)
                rel_path = os.path.relpath(filepath, os.getcwd())
                ext_name = rel_path.replace("\\", ".").replace("/", ".").replace(".py", "")
                
                try:
                    if ext_name in self.bot.extensions:
                        await self.bot.reload_extension(ext_name)
                    else:
                        await self.bot.load_extension(ext_name)
                except Exception as e:
                    reload_error = str(e)

            # 4. Health Check
            diag = await inspector.run_diagnostics()
            
            # 5. Decision & Rollback
            if reload_error or not diag["ok"]:
                # ROLLBACK
                await self.bot.loop.run_in_executor(None, backup_mgr.restore_snapshot, snapshot_path)
                
                fail_msg = f"⛔ **ロールバック実行**\n理由: {reload_error if reload_error else 'システム診断NG'}\n\n{diag['report']}"
                return {"success": False, "message": fail_msg, "snapshot_path": snapshot_path}

            # SUCCESS
            msg = f"✅ **正常動作確認**\n\n{diag['report']}\nバックアップ: `{os.path.basename(snapshot_path)}`"
            return {"success": True, "message": msg, "snapshot_path": snapshot_path}

        except Exception as e:
            logger.error(f"Execution Error: {e}")
            return {"success": False, "message": f"実行エラー: {e}", "snapshot_path": None}


    async def _gather_context(self, ctx) -> str:
        """Gather recent messages from the context channel for Scope Analysis."""
        if not hasattr(ctx, "channel") or not hasattr(ctx.channel, "history"):
            return "No context available (Not a text channel)."
        
        try:
            messages = []
            async for msg in ctx.channel.history(limit=15):
                messages.append(f"[{msg.author.display_name}]: {msg.content}")
            
            return "\n".join(reversed(messages))
        except Exception as e:
            return f"Context fetch failed: {e}"


    async def _critique_code(self, code: str) -> bool:
        """Use LLM to check if code is SAFE."""
        prompt = (
            "You are a Security Auditor. Review the following Python code.\n"
            "Rules:\n"
            "1. NO creating/deleting files outside of src/.\n"
            "2. NO infinite loops.\n"
            "3. NO exfiltration of tokens/secrets.\n"
            "4. NO destructive system calls (rm, del).\n"
            "\n"
            "If SAFE, output 'SAFE'.\n"
            "If UNSAFE, output 'UNSAFE' and reason.\n"
            "\n"
            f"Code:\n{code[:3000]}"
        )
        
        resp = await self.llm.chat([{"role": "user", "content": prompt}], temperature=0.0)
        return "SAFE" in resp.upper()


    async def propose_feature(self, feature: str, context: str, requester: discord.User, ctx=None):
        """
        AI Self-Evolution with Risk & Scope Analysis (Decision Gate).
        """
        try:
            # Step -1: Pre-Flight Deduplication
            existing_cmd = await self._check_duplicates(feature)
            if existing_cmd:
                if ctx and hasattr(ctx, "send"):
                    await ctx.send(f"💡 **既存の機能が見つかりました**: `{existing_cmd}` を使ってみてください。")
                return

            # Step 0: Gather Context
            ambient_context = await self._gather_context(ctx) if ctx else "No Ambient Context"
            file_tree = self._get_file_tree(os.getcwd())
            
            # Server Context
            guild_id = ctx.guild.id if ctx and ctx.guild else 0
            guild_name = ctx.guild.name if ctx and ctx.guild else "Direct Message"
            server_info = f"Guild ID: {guild_id}\nName: {guild_name}"
            
            prompt = f"""
            You are an expert Discord Bot Architect (ORA System).
            
            Request: "{feature}"
            Requester: {requester} (ID: {requester.id})
            Server Context:
            {server_info}
            
            Chat History (Context for Rules/Scope):
            {ambient_context}
            
            Project Structure:
            {file_tree}
            
            --- PHASE 1: COMPLIANCE & RISK ANALYSIS ---
            Evaluate based on the server context and Discord ToS.
            1. **COMPLIANCE**: Does this violate server rules or ToS?
            2. **RISK**: 
               - SAFE: Simple text, generic commands, harmless.
               - RISKY: Admin abuse, file deletion, auth changes, spam.
               - AMBIGUOUS -> RISKY (Safety First).
            
            3. **SCOPE**:
               - GLOBAL: Generic feature (e.g. calculator).
               - LOCAL: Specific to THIS server (e.g. "Watch #announcements here").
            
            --- PHASE 2: IMPLEMENTATION ---
            - Generate a complete Cog file.
            - **CRITICAL RULE**: If SCOPE is LOCAL, you MUST insert this guard at the start of every command:
              ```python
              if ctx.guild.id != {guild_id}:
                  return await ctx.send("⛔ This feature is limited to specific servers.")
              ```
            
            Output STRICT JSON:
            {{
                "risk": "SAFE" or "RISKY",
                "compliance": "COMPLIANT" or "VIOLATION",
                "scope": "GLOBAL" or "LOCAL",
                "reason": "Reason for decision (Japanese)",
                "filename": "cogs/suggested_name.py",
                "code": "COMPLETE_PYTHON_CODE"
            }}
            """
            
            import json
            # Use 'gpt-5.1-codex' (Cloud) as requested by user ("Use this!")
            try:
                analysis_json = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}], 
                    temperature=0.1,
                    model="gpt-5.1-codex"
                )
            except Exception as e:
                logger.warning(f"Primary Cloud LLM (gpt-5.1-codex) failed: {e}. Fallback to Standard (gpt-4o).")
                analysis_json = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}], 
                    temperature=0.1,
                    model="gpt-4o"
                )
            
            cleaned_json = analysis_json.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json.replace("```json", "").replace("```", "")
            elif cleaned_json.startswith("```"):
                cleaned_json = cleaned_json.replace("```", "")
                
            data = json.loads(cleaned_json)
            
            # [DECISION GATE]
            risk = data.get("risk", "RISKY")
            compliance = data.get("compliance", "VIOLATION")
            scope = data.get("scope", "GLOBAL")
            reason = data.get("reason", "No reason provided")
            code = data.get("code", "")
            
            status_text = "🔒 管理者承認待ち"
            color = discord.Color.orange()
            
            # Check Auto-Evolve Conditions
            if (risk == "SAFE" or risk == "LOW") and compliance == "COMPLIANT":
                # Check Admin or Trusted Scenarios here if needed
                # For now, SAFE + COMPLIANT = GO
                status_text = "⚡ 適用実行中..."
                color = discord.Color.green()
            
            # Enhanced Notification
            await self.notify_feature_proposal(
                title="🧬 Evolution Proposal 審査結果",
                description=f"**提案**: {feature}\n"
                            f"**判定**: {risk} / {compliance}\n"
                            f"**範囲**: {scope} (ID: {guild_id if scope == 'LOCAL' else 'Global'})\n"
                            f"**理由**: {reason}\n"
                            f"**ステータス**: {status_text}",
                user_id=requester.id
            )

            if risk == "RISKY" or compliance == "VIOLATION":
                if ctx and hasattr(ctx, "send"):
                    await ctx.send(f"⚠️ **自動更新停止**: リスク判断により承認待ちとなりました。\n理由: {reason}")
                return

            if not code:
                return

            # AUTO-EVOLVE
            target_path = os.path.join("src", data.get("filename", "cogs/feature.py"))
            
            if ctx and hasattr(ctx, "send"):
                await ctx.send(f"🧬 **自己進化を開始します**\n範囲: {scope}\n理由: {reason}")
            
            # Execute
            result = await self.execute_evolution(target_path, code, f"Auto-Evolve: {feature} ({scope})")
            
            if result["success"]:
                if ctx and hasattr(ctx, "send"):
                    await ctx.send(f"✅ **進化完了**: {scope} 機能として実装されました！")
            else:
                if ctx and hasattr(ctx, "send"):
                    await ctx.send(f"⚠️ **進化失敗**: ロールバックしました。\n{result['message']}")
                
        except Exception as e:
            logger.error(f"Self-Evolution failed: {e}")
            if ctx and hasattr(ctx, "send"):
                await ctx.send(f"❌ エラーが発生しました: {e}")
        """Returns a string representation of the src directory tree."""
        tree_lines = []
        start_dir = os.path.join(root_dir, "src")
        if not os.path.exists(start_dir):
            return "src/ (Not Found)"
            
        for root, dirs, files in os.walk(start_dir):
            level = root.replace(start_dir, '').count(os.sep)
            indent = ' ' * 4 * (level)
            tree_lines.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                if f.endswith(".py"):
                    tree_lines.append(f"{subindent}{f}")
        return "\n".join(tree_lines)

    async def notify_feature_proposal(self, title: str, description: str, user_id: int) -> bool:
        """Sends a formal feature proposal to the configured channel."""
        cid = getattr(self.bot.config, "feature_proposal_channel_id", None)
        if not cid:
            return False
            
        channel = self.bot.get_channel(cid)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(cid)
            except:
                return False
            
        user = self.bot.get_user(user_id)
        user_mention = user.mention if user else f"User ID: {user_id}"
        
        embed = discord.Embed(title=f"💡 Feature Proposal: {title}", color=discord.Color.gold())
        embed.description = description
        embed.add_field(name="Proposer", value=user_mention)
        embed.set_footer(text="Sent from ORA Healer System")
        embed.timestamp = discord.utils.utcnow()
        
        try:
            await channel.send(embed=embed)
            return True
        except Exception as e:
            logger.error(f"Failed to send proposal: {e}")
            return False

    async def _check_duplicates(self, feature_request: str) -> Optional[str]:
        """Checks if a similar command already exists to prevent re-invention."""
        try:
            # 1. Gather all commands
            commands = []
            for cmd in self.bot.commands:
                commands.append(f"Prefix Command: {cmd.name} - {cmd.help or 'No help'}")
            
            # 2. Gather Slash Commands (Tree)
            # Tree commands are complex to iterate if not synced, but we try walking
            for cmd in self.bot.tree.walk_commands():
                desc = cmd.description if hasattr(cmd, 'description') else "No description"
                commands.append(f"Slash Command: /{cmd.name} - {desc}")
            
            cmd_list = "\n".join(commands[:100]) # Limit context window just in case
            
            # 3. Ask LLM
            prompt = f"""
            User Request: "{feature_request}"
            Existing Commands:
            {cmd_list}
            
            Does the request match an existing command?
            If YES, output strictly the Command Name (e.g., "/voice_off").
            If NO, output "NO".
            """
            
            resp = await self.llm.chat([{"role": "user", "content": prompt}], temperature=0.0)
            if "NO" in resp.upper():
                return None
            return resp.strip()
            
        except Exception as e:
            logger.error(f"Dedup check failed: {e}")
            return None

    # ... execute_evolution, _gather_context, _critique_code are reused from previous block ...
    # Re-pasting them here for completeness of this replacement block if needed, 
    # BUT since I am replacing the END of the file, I must include them.
    
    async def execute_evolution(self, filepath: str, new_content: str, reason: str = "Autonomous Update") -> dict:
        """
        Executes an update with Ultimate Safety Protocols (Handshake, Sandbox, Self-Repair).
        """
        try:
            # --- 1. HANDSHAKE (Signal Watcher) ---
            heartbeat_file = os.path.join("data", "heartbeat.json")
            if os.path.exists(heartbeat_file):
                try:
                    with open(heartbeat_file, 'r+') as f:
                        hdata = json.load(f)
                        hdata["watcher_expected"] = True
                        hdata["watcher_ready"] = False # Reset ready flag
                        f.seek(0)
                        json.dump(hdata, f)
                        f.truncate()
                except: pass

            # Launch Watcher in New Window
            subprocess.Popen('start "ORA Update Guardian" python src/watcher.py', shell=True)
            
            # Wait for Watcher Ready (Max 15s)
            watcher_active = False
            for _ in range(15):
                await asyncio.sleep(1)
                try:
                    if os.path.exists(heartbeat_file):
                        with open(heartbeat_file, 'r') as f:
                            if json.load(f).get("watcher_ready"):
                                watcher_active = True
                                break
                except: pass
            
            if not watcher_active:
                return {"success": False, "message": "❌ Default: Watcher Handshake Failed. Updating unsafe is prohibited.", "snapshot_path": None}

            # --- 2. ATOMIC BACKUP (Zip src/) ---
            os.makedirs("backups", exist_ok=True)
            backup_name = f"snap_{int(time.time())}.zip"
            backup_path = os.path.join("backups", backup_name)
            
            def make_zip():
                shutil.make_archive(backup_path.replace('.zip', ''), 'zip', "src")
                return backup_path
            
            await self.bot.loop.run_in_executor(None, make_zip)
            
            # --- 3. SELF-REPAIR LOOP (Syntax Check & Retry) ---
            attempts = 0
            max_retries = 3
            current_content = new_content
            
            while attempts <= max_retries:
                # A. Write File
                if os.path.dirname(filepath):
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(current_content)
                
                # B. Pre-Flight Syntax Check (Dry Run)
                try:
                    py_compile.compile(filepath, doraise=True)
                    # Check passed! Break loop and restart.
                    break 
                    
                except py_compile.PyCompileError as e:
                    attempts += 1
                    err_msg = str(e)
                    logger.warning(f"Evolution Syntax Error (Attempt {attempts}/{max_retries}): {err_msg}")
                    
                    if attempts > max_retries:
                        # ROLLBACK
                        shutil.unpack_archive(backup_path, "src")
                        return {"success": False, "message": f"⛔ Syntax Check Failed 3 times. Rolled back.\nLast Error: {err_msg}", "snapshot_path": backup_path}
                    
                    # C. Self-Repair (Ask LLM)
                    prompt = (
                        f"Fix SyntaxError in the following Python code.\n"
                        f"Error: {err_msg}\n"
                        f"Original Code:\n{current_content}\n\n"
                        f"Output ONLY the fixed complete code (no markdown)."
                    )
                    fixed_code = await self.llm.chat([{"role": "user", "content": prompt}], temperature=0.0)
                    
                    # Clean output
                    if "```" in fixed_code:
                        fixed_code = fixed_code.replace("```python", "").replace("```", "")
                    current_content = fixed_code.strip()

            # --- 4. RESTART (Watcher is guarding) ---
            # Trigger Restart Script
            subprocess.Popen("restart_ora.bat", shell=True)
            
            return {"success": True, "message": "✅ Patch Applied. System Restarting under Guardian Watch...", "snapshot_path": backup_path}

        except Exception as e:
            logger.error(f"Execution Error: {e}")
            return {"success": False, "message": f"実行エラー (Fatal): {e}", "snapshot_path": None}


    async def _gather_context(self, ctx) -> str:
        """Gather recent messages from the context channel for Scope Analysis."""
        if not hasattr(ctx, "channel") or not hasattr(ctx.channel, "history"):
            return "No context available (Not a text channel)."
        
        try:
            messages = []
            async for msg in ctx.channel.history(limit=15):
                messages.append(f"[{msg.author.display_name}]: {msg.content}")
            
            return "\n".join(reversed(messages))
        except Exception as e:
            return f"Context fetch failed: {e}"


    async def _critique_code(self, code: str) -> bool:
        """Use LLM to check if code is SAFE."""
        prompt = (
            "You are a Security Auditor. Review the following Python code.\n"
            "Rules:\n"
            "1. NO creating/deleting files outside of src/.\n"
            "2. NO infinite loops.\n"
            "3. NO exfiltration of tokens/secrets.\n"
            "4. NO destructive system calls (rm, del).\n"
            "\n"
            "If SAFE, output 'SAFE'.\n"
            "If UNSAFE, output 'UNSAFE' and reason.\n"
            "\n"
            f"Code:\n{code[:3000]}"
        )
        
        resp = await self.llm.chat([{"role": "user", "content": prompt}], temperature=0.0)
        return "SAFE" in resp.upper()


    async def propose_feature(self, feature: str, context: str, requester: discord.User, ctx=None):
        """
        AI Self-Evolution with Scope Analysis and Autonomous Execution.
        """
        try:
            # Step -1: Pre-Flight Deduplication
            existing_cmd = await self._check_duplicates(feature)
            if existing_cmd:
                if ctx:
                    await ctx.send(f"💡 **既存の機能が見つかりました**: `{existing_cmd}` を使ってみてください。")
                return

            # Step 0: Gather Context (Ambient Awareness) & File Tree
            ambient_context = await self._gather_context(ctx) if ctx else "No Ambient Context"
            file_tree = self._get_file_tree(os.getcwd())

            prompt = f"""
            You are an expert Discord Bot Architect.
            User Request: "{feature}"
            Requester: {requester}
            Context (Chat History):
            {ambient_context}
            
            Project File Tree (Use this to decide where to add code):
            {file_tree}
            
            Task:
            1. **SCOPE ANALYSIS**:
               - Is this a GLOBAL change (system-wide feature)?
               - Or a LOCAL/TEMP change (e.g. "Silence HERE", "Quiet TODAY")?
               - IF Local/Temp, DO NOT modify global logic permanently. Instead, use `bot.store` to save a flag (e.g. `guild_settings` table).
            
            2. **DESIGN**:
               - Design a Python Cog (or modifying existing one if obvious).
               - Refer to existing files in the Tree (e.g. `src/cogs/media.py` for voice).
               - If Config is needed, assume `bot.store` has methods or Create generic SQL.
            
            3. **SECURITY & PERMISSIONS (CRITICAL)**:
               - **MUST** include permission checks for any destructive or admin-level action.
               - Used `await self.bot.get_cog('ORACog')._check_permission(ctx.author.id, 'sub_admin')` for custom roles, OR `ctx.author.guild_permissions.XXX`.
               - **NEVER** generate code that allows @everyone to mod/admin settings.
               - DO NOT LEAK internal paths in the output 'analysis' text.
            
            Output STRICT JSON:
            {{
                "scope_analysis": "Explanation of Scope (Global/Local/Temp) in Japanese",
                "analysis": "Implementation Plan in Japanese",
                "security_impact": "Risk Analysis in Japanese",
                "filename": "suggested_filename.py",
                "code": "COMPLETE Python code (WITH PERMISSION CHECKS)"
            }}
            """
            
            import json
            analysis_json = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}], 
                temperature=0.2,
                model="gpt-5.1-codex"
            )
            
            cleaned_json = analysis_json.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json.replace("```json", "").replace("```", "")
            elif cleaned_json.startswith("```"):
                cleaned_json = cleaned_json.replace("```", "")
                
            data = json.loads(cleaned_json)
            
            code = data.get("code", "")
            if not code:
                return # Fail silently
            
            # Step 2: Safety Critique
            is_safe = await self._critique_code(code)
            
            # Step 3: Decision (Auto vs Manual)
            # Admin Check
            is_admin = (requester.id == self.bot.config.admin_user_id)
            auto_evolve = is_safe and is_admin 
            
            # Config Channel
            channel_id = getattr(self.bot.config, "log_channel_id", 0)
            channel = self.bot.get_channel(channel_id)
            
            # Privacy Routing
            if not is_admin and ctx:
                await ctx.send("🔄 システム更新リクエストを受理しました。管理者の承認待ちです...")
            
            if auto_evolve and channel:
                # AUTONOMOUS EXECUTION
                target_path = os.path.join("src", "cogs", data.get("filename", "feature.py"))
                
                # Notify Start
                embed = discord.Embed(title="🧬 Auto-Evolution Started", color=discord.Color.blue())
                embed.description = f"Request: {feature}\nScope: {data.get('scope_analysis')}\nStatus: **Executing...**"
                if existing_cmd: embed.add_field(name="Warning", value=f"Similar command `{existing_cmd}` detected but overridden.")
                status_msg = await channel.send(embed=embed)
                
                # Execute
                result = await self.execute_evolution(target_path, code, f"Auto-Evolve: {feature}")
                
                # Report Result
                if result["success"]:
                    embed.color = discord.Color.green()
                    embed.title = "🧬 Auto-Evolution Complete"
                    embed.description = f"**Success!**\n\n{result['message']}"
                    await status_msg.edit(embed=embed)
                    if ctx: 
                         await ctx.send(f"✅ 更新が完了しました！ ({data.get('scope_analysis')})")
                else:
                    embed.color = discord.Color.red()
                    embed.title = "🧬 Auto-Evolution Rolled Back"
                    embed.description = result['message']
                    await status_msg.edit(embed=embed)
                    if ctx:
                         await ctx.send("⚠️ 更新に失敗し、ロールバックされました。")
            
            elif channel:
                # MANUAL REVIEW
                sec_analysis = data.get("security_impact", "No analysis provided.")
                color = discord.Color.orange()

                embed = discord.Embed(title="🧬 Evolution Proposal (Manual Review)", color=color)
                embed.description = f"**Request**: {feature}\nUser: {requester.mention}\n\n**🔍 Scope Analysis**\n{data.get('scope_analysis')}\n\n**🛡️ Security Audit**\n{sec_analysis}\nSafe Code Check: {'✅ PASS' if is_safe else '❌ FAIL'}"
                
                filename = data.get("filename", "feature.py")
                file = discord.File(io.StringIO(code), filename=filename)
                
                view = HealerView(self.bot, target_path, code, f"{target_path}.bak", data.get('analysis'))
                
                await channel.send(embed=embed, file=file, view=view)
                
        except Exception as e:
            logger.error(f"Self-Evolution failed: {e}")
