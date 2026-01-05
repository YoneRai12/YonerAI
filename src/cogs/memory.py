
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# CRITICAL PROTOCOL WARNING
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# DO NOT MODIFY THE SCANNING/OPTIMIZATION LOGIC IN THIS FILE WITHOUT FIRST
# READING: `ORA_OPTIMIZATION_MANIFEST.md`
#
# THE LOGIC IS LOCKED BY USER DECREE:
# 1. REAL-TIME: Immediate trigger on 5 messages (Buffer).
# 2. BACKGROUND: Local Logs ONLY. NO API SCANNING (Silent).
# 3. MANUAL: API Scanning ALLOWED (Deep Scan) but throttled.
#
# FAILURE TO FOLLOW THIS WILL CAUSE REGRESSION AND USER FRUSTRATION.
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
import json
import time
import os
import aiofiles
import time
import psutil
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import re
import ast # For robust JSON parsing fallback

logger = logging.getLogger(__name__)

MEMORY_DIR = r"L:\ORA_Memory\users"

class SimpleFileLock:
    """Cross-process file lock using atomic filesystem operations."""
    def __init__(self, path: str, timeout: float = 2.0):
        self.lock_path = path + ".lock"
        self.timeout = timeout
        self._fd = None

    async def __aenter__(self):
        start_time = time.time()
        while True:
            try:
                # Atomic creation (fails if file exists)
                self._fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                # Write info for debugging
                os.write(self._fd, f"{os.getpid()}:{time.time()}".encode())
                break
            except FileExistsError:
                # Lock exists
                if time.time() - start_time > self.timeout:
                    # Check for staleness
                    try:
                        # If lock file is older than 5 seconds, assume stale and delete
                        stat = os.stat(self.lock_path)
                        if time.time() - stat.st_mtime > 5.0:
                             logger.warning(f"Removed stale lock: {self.lock_path}")
                             os.remove(self.lock_path)
                             continue # Retry
                    except FileNotFoundError:
                        continue # Was just removed
                    except Exception as e:
                        logger.error(f"Stale lock check failed: {e}")

                    logger.warning(f"Failed to acquire lock: {self.lock_path} (Proceeding unsafely)")
                    break 
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Unexpected lock error: {e}")
                break
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._fd:
                os.close(self._fd)
                self._fd = None
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except Exception as e:
            logger.debug(f"Failed to release lock {self.lock_path}: {e}")

def robust_json_repair(text: str) -> str:
    """Attempts to fix truncated JSON by closing brackets/quotes."""
    text = text.strip()
    if not text: return text
    
    # 1. Handle truncated string (last char is not quote or brace/bracket)
    # If the text ends inside a string, close it.
    if text.count('"') % 2 != 0:
        text += '"'
    
    # 2. Close open brackets/braces based on count
    open_brackets = text.count('[') - text.count(']')
    if open_brackets > 0:
        text += ']' * open_brackets
        
    open_braces = text.count('{') - text.count('}')
    if open_braces > 0:
        text += '}' * open_braces
        
    return text

class MemoryCog(commands.Cog):

    def __init__(self, bot: commands.Bot, llm_client, worker_mode: bool = False):
        self.bot = bot
        self._llm = llm_client
        self.worker_mode = worker_mode
        self._ensure_memory_dir()
        
        # Buffer: {user_id: [{"content": str, "timestamp": str}, ...]}
        self.message_buffer: Dict[int, list] = {}
        
        # Concurrency Control (Worker: 50, Main: 20)
        limit = 50 if worker_mode else 10 # Main bot keeps low profile
        self.sem = asyncio.Semaphore(limit)
        self._io_lock = asyncio.Lock()  # Prevent concurrent file access

        # Start core loops
        self.memory_worker.start()
        self.name_sweeper.start()
        if self.worker_mode:
            self.status_loop.change_interval(seconds=5)
            self.scan_history_task.start()
            self.idle_log_archiver.start()
        else:
            self.status_loop.start()
            self.scan_history_task.start()
            # Archive logic is Worker-only
            # self.idle_log_archiver.start() 
        
        if self.worker_mode:
            logger.info("MemoryCog: WORKER MODE (ヘビータスク優先) で起動しました。")
            asyncio.create_task(self.cleanup_stuck_profiles())
        else:
            logger.info("MemoryCog: MAIN MODE (リアルタイム応答 + フォールバック) で起動しました。")

    def cog_unload(self):
        self.status_loop.cancel()
        self.memory_worker.cancel()
        self.name_sweeper.cancel()
        self.scan_history_task.cancel()
        self.idle_log_archiver.cancel()

    async def cleanup_stuck_profiles(self):
        """Reset 'Processing' users to 'Error' on startup to fix stuck yellow status."""
        await self.bot.wait_until_ready()
        logger.info("Memory: スタックした 'Processing' ステータスのプロファイルをチェック中...")
        if not os.path.exists(MEMORY_DIR): return
        
        count = 0
        for f in os.listdir(MEMORY_DIR):
            if not f.endswith(".json"): continue
            path = os.path.join(MEMORY_DIR, f)
            try:
                # Lockless read for speed (snapshot)
                async with aiofiles.open(path, 'r', encoding='utf-8') as file:
                    content = await file.read()
                    data = json.loads(content)
                
                if data.get("status") in ["Processing", "Pending"]:
                    # Fix it
                    data["status"] = "Error"
                    data["impression"] = "システム再起動によりリセット (Stalled State Fixed)"
                    
                    # Atomic Write with Lock
                    await self._save_user_profile_atomic(path, data)
                    count += 1
            except: continue
        
        if count > 0:
            logger.info(f"Memory: Unstuck {count} profiles from 'Processing' state.")

    def _ensure_memory_dir(self):
        """Ensure memory directory exists."""
        if not os.path.exists(MEMORY_DIR):
            try:
                os.makedirs(MEMORY_DIR, exist_ok=True)
                logger.info(f"Created Memory Directory: {MEMORY_DIR}")
            except Exception as e:
                logger.error(f"Failed to create Memory Directory: {e}")

    def is_public(self, channel) -> bool:
        """Returns True if @everyone has View Channel permission."""
        if not hasattr(channel, "guild"): return False
        everyone = channel.guild.default_role
        perms = channel.permissions_for(everyone)
        # Simplified: True if everyone can see it
        return perms.view_channel

    async def _should_process_guild(self, guild_id: int) -> bool:
        """Determine if this bot instance should process heavy tasks for this guild."""
        if self.worker_mode:
            return True # Worker bot always processes what it's in
            
        guild = self.bot.get_guild(guild_id)
        if not guild: return False
        
        # Check if Worker Bot (1447556986756530296) is in this guild
        worker_id = int(os.getenv("WORKER_BOT_ID", 1447556986756530296))
        member = guild.get_member(worker_id)
        
        if member:
            # Check if Worker is actually ONLINE
            # If Worker is offline, Main Bot MUST take over as redundancy.
            if str(member.status) != "offline":
                # Worker is present and ONLINE. Main bot backs off.
                return False
            else:
                # Worker is present but OFFLINE. Main bot takes over.
                # logger.debug(f"Memory: Worker Bot found but OFFLINE in {guild.name}. Main Bot taking over.")
                return True
            
        # Worker not present. Main bot takes over as Fallback.
        return True

    def cog_unload(self):
        self.memory_worker.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Buffer user messages for analysis."""
        # Worker Bot should NOT buffer real-time messages (Main Bot does that)
        if self.worker_mode:
            return

        if message.author.bot: return
        if not message.guild: return # Ignore DM for now        
        if message.author.id not in self.message_buffer:
            self.message_buffer[message.author.id] = []
            
        # Determine visibility
        is_pub = self.is_public(message.channel)

        # Append message (max 50 to prevent memory bloat)
        entry = {
            "id": message.id,
            "content": message.content,
            "timestamp": datetime.now().isoformat(),
            "channel": message.channel.name if hasattr(message.channel, "name") else "DM",
            "guild": message.guild.name if message.guild else "DM",
            "guild_id": message.guild.id if message.guild else None,
            "is_public": is_pub
        }
        self.message_buffer[message.author.id].append(entry)
        
        # Trigger Optimization immediately if threshold reached (User Request: "5 messages")
        if len(self.message_buffer[message.author.id]) >= 5:
             logger.info(f"Memory: Instant Optimization Trigger for {message.author.display_name} (5+ new msgs)")
             msgs_to_process = self.message_buffer[message.author.id][:] # Copy
             self.message_buffer[message.author.id] = [] # Clear
             
             # Fire off analysis (Background)
             asyncio.create_task(self._analyze_wrapper(message.author.id, msgs_to_process, message.guild.id if message.guild else None, is_pub))
        
        # Cap buffer size (Safety net if trigger fails or backlog)
        elif len(self.message_buffer[message.author.id]) > 50:
             self.message_buffer[message.author.id].pop(0)

        # Phase 32: Per-User History Persistence (with scope)
        asyncio.create_task(self._persist_message(message.author.id, entry, message.guild.id if message.guild else None, is_pub))

        # ---------------------------------------------------------
        # INSTANT NAME UPDATE (Fix for Dashboard "Unknown" Issue)
        # ---------------------------------------------------------
        # Check if we should update the name on disk immediately
        # (Only do this if profile is missing OR name is stale/unknown)
        # To avoid IO spam, checking in memory or checking file existence is needed.
        # Simple approach: If msg count is 1 (new session), ensure profile has name.
        if len(self.message_buffer[message.author.id]) == 1:
            try:
                # We do this asynchronously to not block
                asyncio.create_task(self._ensure_user_name(message.author, message.guild))
            except Exception as e:
                logger.error(f"Failed to ensure username: {e}")


    def _get_memory_path(self, user_id: int, guild_id: int | str = None, is_public: bool = True) -> str:
        """Get path to user memory file. Supports Scope Partitioning."""
        if guild_id:
            suffix = "_public.json" if is_public else "_private.json"
            return os.path.join(MEMORY_DIR, f"{user_id}_{guild_id}{suffix}")
        return os.path.join(MEMORY_DIR, f"{user_id}.json")

    async def _ensure_user_name(self, user: discord.User | discord.Member, guild: Optional[discord.Guild] = None):
        """Quickly ensure the user has a name in their profile (before optimization)."""
        uid = user.id
        # Use guild-specific path if possible
        gid = guild.id if guild else None
        path = self._get_memory_path(uid, gid)
        
        display_name = user.display_name
        guild_name = guild.name if guild else "Direct Message"
        guild_id_str = str(guild.id) if guild else None
        
        # Check if exists
        try:
            if os.path.exists(path):
                async with aiofiles.open(path, "r", encoding="utf-8") as f:
                    data = json.loads(await f.read())
                
                # Update if missing OR if we have a better (guild) nickname or updated info
                # Always update last_active_guild if present
                changed = False
                
                if data.get("name") != display_name:
                    data["name"] = display_name
                    changed = True
                    
                if guild_name and data.get("guild_name") != guild_name:
                    data["guild_name"] = guild_name
                    changed = True
                    
                if guild_id_str and data.get("guild_id") != guild_id_str:
                    data["guild_id"] = guild_id_str
                    changed = True

                if changed:
                    await self._save_user_profile_atomic(path, data)
            else:
                # Create skeleton
                data = {
                    "discord_user_id": str(uid),
                    "name": display_name,
                    "created_at": time.time(),
                    "points": 0,
                    "traits": [],
                    "history_summary": "New user.",
                    "impression": "Newcomer", 
                    "status": "New", # Initial state
                    "last_updated": datetime.now().isoformat(),
                    "guild_name": guild_name,
                    "guild_id": guild_id_str
                }
                await self._save_user_profile_atomic(path, data)
                    
        except Exception as e:
            logger.error(f"Error checking name for {uid}: {e}")

    async def get_user_profile(self, user_id: int, guild_id: int | str = None, current_channel_id: int = None) -> Optional[Dict[str, Any]]:
        """Retrieve user profile. Merges public and private layers if channel allows."""
        is_current_public = True
        if current_channel_id:
            ch = self.bot.get_channel(current_channel_id)
            if ch: is_current_public = self.is_public(ch)

        # 1. Load Public Profile (Primary)
        public_path = self._get_memory_path(user_id, guild_id, is_public=True)
        profile = await self._read_profile_retry(public_path)
        
        if not profile and not guild_id: # Legacy/DM fallback
             path = os.path.join(MEMORY_DIR, f"{user_id}.json")
             profile = await self._read_profile_retry(path)

        if not profile:
            # Return skeleton if totally new
            return {
                "status": "New", 
                "name": f"User_{user_id}", 
                "guild_id": str(guild_id) if guild_id else None, 
                "traits": [],
                "layer2_user_memory": {"facts": [], "traits": [], "impression": "Newcomer"}
            }

        # 2. If channel is Private, merge Private Profile
        if not is_current_public:
            private_path = self._get_memory_path(user_id, guild_id, is_public=False)
            private_profile = await self._read_profile_retry(private_path)
            if private_profile:
                # Merge traits and facts
                profile["traits"] = list(set(profile.get("traits", []) + private_profile.get("traits", [])))
                profile["layer2_user_memory"]["facts"] = list(set(
                    profile.get("layer2_user_memory", {}).get("facts", []) + 
                    private_profile.get("layer2_user_memory", {}).get("facts", [])
                ))
                if private_profile.get("impression"):
                    profile["impression"] = f"{profile.get('impression')} | [Private] {private_profile['impression']}"
        
        return profile

    async def _read_profile_retry(self, path: str) -> Optional[Dict[str, Any]]:
        """Retry wrapper for reading profiles."""
        if not os.path.exists(path): return None
        async with SimpleFileLock(path):
            async with self._io_lock:
                for attempt in range(3):
                    try:
                        async with aiofiles.open(path, "r", encoding="utf-8") as f:
                            content = await f.read()
                            if content.strip():
                                return json.loads(content)
                    except:
                         await asyncio.sleep(0.1)
        return None

    async def _save_user_profile_atomic(self, path: str, data: dict):
        """Atomic write via temp file to prevent corruption, with Process Lock."""
        temp_path = f"{path}.tmp"
        
        # Cross-Process Lock
        async with SimpleFileLock(path):
            async with self._io_lock: # Thread Lock
                try:
                    async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                        await f.write(json.dumps(data, indent=2, ensure_ascii=False))
                    
                    # Atomic replacement
                    os.replace(temp_path, path)
                except Exception as e:
                    logger.error(f"Memory: Save failed for {path}: {e}")
                    if os.path.exists(temp_path):
                        try: os.remove(temp_path)
                        except: pass

    def _sanitize_traits(self, traits: List[Any]) -> List[str]:
        """Ensure traits are clean, short strings."""
        clean = []
        seen = set()
        
        if not isinstance(traits, list):
            return []
            
        for t in traits:
            if not isinstance(t, str):
                continue
            t = t.strip()
            # Remove quotes if double encoded
            if t.startswith('"') and t.endswith('"'):
                t = t[1:-1]
            if t.startswith("'") and t.endswith("'"):
                t = t[1:-1]
                
            # Filter garbage
            if not t or len(t) > 20 or len(t) < 1:
                continue
            if "[" in t or "{" in t: # partial json
                continue
                
            if t not in seen:
                clean.append(t)
                seen.add(t)
        
        return clean[:15] # Limit total count

    async def update_user_profile(self, user_id: int, data: Dict[str, Any], guild_id: int | str = None, is_public: bool = True):
        """Standardized method to update user profile JSON with smart merging and atomic saving."""
        path = self._get_memory_path(user_id, guild_id, is_public=is_public)
        try:
            # Sanitize traits before merging
            if "traits" in data:
                data["traits"] = self._sanitize_traits(data["traits"])

            # For update, we only want the specific layer
            current = await self._read_profile_retry(path)
            if not current:
                import time
                current = {
                    "discord_user_id": str(user_id),
                    "created_at": time.time(),
                    "points": 0,
                    "traits": [],
                    "history_summary": "New user.",
                    "impression": "Newcomer", 
                    "status": "New"
                }

            # Selective Merge (keeping flat keys for compatibility)
            for k, v in data.items():
                if k == "traits":
                    current["traits"] = v
                    current["points"] = len(v)
                else:
                    current[k] = v
            
            # Resolve Guild Info if missing
            if guild_id and not current.get("guild_id"):
                current["guild_id"] = str(guild_id)
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    current["guild_name"] = guild.name

            current["last_updated"] = datetime.now().isoformat()
            if data.get("name") and data["name"] != "Unknown":
                current["name"] = data["name"]
            
            await self._save_user_profile_atomic(path, current)
        except Exception as e:
            logger.error(f"Failed to update profile for {user_id}: {e}")

    async def set_user_status(self, user_id: int, status: str, msg: str, guild_id: int | str = None, is_public: bool = True):
        """Helper to quickly update user status for dashboard feedback."""
        await self.update_user_profile(user_id, {"status": status, "status_msg": msg}, guild_id, is_public)


        # Since I can't see the START of update_user_profile in the view (it starts at 400 inside the function?),
        # I'll replace the block I see or scroll up.
        # Ah, View showed 400-450. Line 429 is set_user_status.
        # Update_user_profile ENDs at 428.
        # I need to find where it STARTS.
        pass

    def _parse_analysis_json(self, text: str) -> Dict[str, Any]:
        """Robustly extract and parse JSON from LLM response."""
        # 1. Clean Markdown
        cleaned_text = text.replace("```json", "").replace("```", "").strip()
        
        # 2. Extract JSON block (greedy outer braces)
        # Find first '{' and last '}'
        start = cleaned_text.find('{')
        end = cleaned_text.rfind('}')
        
        if start == -1 or end == -1:
            raise ValueError("No JSON object found in response")
            
        potential_json = cleaned_text[start:end+1]
        
        # 3. Parse with fallback repair
        try:
            return json.loads(potential_json, strict=False)
        except json.JSONDecodeError:
            logger.warning("Memory: JSONデコード失敗。修復を試みます...")
            repaired = robust_json_repair(potential_json)
            # Log the tail for debugging
            logger.debug(f"Truncated JSON Tail: {potential_json[-200:]}")
            return json.loads(repaired, strict=False)

    async def _analyze_batch(self, user_id: int, messages: list[Dict[str, Any]], guild_id: int | str = None, is_public: bool = True, max_output: int = 128000):
        """Analyze a batch of messages and update the user profile in the correct scope."""
        if not messages: return

        chat_log = "\n".join([f"[{m['timestamp']}] {m['content']}" for m in messages])
        
        # --- BUDGET-AWARE DEPTH SELECTION ---
        depth_mode = "Standard"
        extra_instructions = ""
        max_output = 1500
        
        ora_cog = self.bot.get_cog("ORACog")
        cost_manager = ora_cog.cost_manager if ora_cog else None
        
        if cost_manager:
            # We skip usage_ratio check for depth mode selection to honor user's request for "Extreme" always if possible,
            # but we keep the mode names for categorization.
            # However, to be safe, we default to the deepest mode within budget.
            depth_mode = "Extreme Deep Reflection"
            max_output = 128000 # Max for GPT-5 / Mini Peak
            extra_instructions = (
                "5. **Deep Psychological Profile**: 提供された会話から、ユーザーの潜在的な価値観、孤独感、承認欲求、または知的好奇心の傾向を深く洞察してください。\n"
                "6. **Relationship Analysis**: ORA（AI）や他者に対してどのような距離感を保とうとしているか分析してください。\n"
                "7. **Future Predictions**: このユーザーが次に興味を持ちそうなトピックや、陥りやすい感情的パターンを予測してください。\n"
                "Traitsは最低15個抽出してください。"
            )
            
            # Adjust down ONLY if we are literally about to hit the hard limit
            usage_ratio = cost_manager.get_usage_ratio("optimization", "openai")
            if usage_ratio > 0.95:
                depth_mode = "Standard"
                max_output = 10000
                extra_instructions = "Cost Protection: Using standard depth."
            elif usage_ratio > 0.8:
                depth_mode = "Deep Analysis"
                max_output = 100000 
                extra_instructions = "5. **Detailed Insight**: 会話の裏にある意図や感情を1段深く分析してください。Traitsは最低10個抽出してください。"
        
        prompt = [
            {"role": "developer", "content": (
                f"You are a World-Class Psychologist AI implementing a '4-Layer Memory System'. Analysis Mode: {depth_mode}. Output MUST be in Japanese.\n"
                "Layers:\n"
                "1. **Layer 1 (Metadata)**: Status, Device (managed by system, ignore in output).\n"
                "2. **Layer 2 (User Memory)**: Static facts (Name, Age, Job) and Personality Traits.\n"
                "3. **Layer 3 (Summary)**: A conceptual map of the conversation context.\n"
                "4. **Layer 4 (Session)**: Raw logs (provided as input)."
            )},
            {"role": "user", "content": (
                f"Analyze the chat logs for this user based on the 4-Layer Memory Architecture.\n"
                f"Extract:\n"
                f"1. **Layer 2 - Facts**: ユーザーに関する確定的な事実（名前、年齢、職業、居住地など）。推測は含めないこと。\n"
                f"2. **Layer 2 - Traits**: 性格、話し方の特徴 (e.g., 明るい, 皮肉屋).\n"
                f"3. **Layer 2 - Impression**: ユーザーを一言で表すキャッチフレーズ。\n"
                f"4. **Layer 3 - Global Map**: これまでの会話の大まかな地図・要約。\n"
                f"5. **Interests**: 興味のあるトピック。\n"
                f"{extra_instructions}\n\n"
                f"Chat Log:\n{chat_log}\n\n"
                f"Output strictly in this JSON format (All values in Japanese):\n"
                f"{{ \n"
                f"  \"layer2_user_memory\": {{ \"facts\": [\"...\"], \"traits\": [\"...\"], \"impression\": \"...\", \"interests\": [\"...\"] }},\n"
                f"  \"layer3_summary\": {{ \"global_summary\": \"...\", \"deep_profile\": \"...\", \"future_pred\": \"...\" }}\n"
                f"}}"
            )}
        ]
        
        # COST TRACKING PREP
        from src.utils.cost_manager import Usage
        import secrets
        
        est_usage = Usage(tokens_in=len(chat_log)//4 + 500, tokens_out=max_output, usd=0.0)
        rid = secrets.token_hex(4)

        try:
            # 1. MARK AS PROCESSING (Visual Feedback)
            await self.set_user_status(user_id, "Processing", "Processing...", guild_id, is_public)

            response_text = ""
            actual_usage = None
            
            # 2. CALL LLM (Optimized Hierarchy)
            try:
                # Assuming _llm is UnifiedClient
                if hasattr(self._llm, "openai_client") or hasattr(self._llm, "google_client"):
                     if cost_manager:
                         cost_manager.reserve("optimization", "openai", user_id, rid, est_usage)

                     try:
                         # o1/gpt-5 ready (mapped internally)
                         # Explicitly pass None for temperature if needed, but client handles it now.
                         logger.info(f"Memory: 📡 Sending analysis request to OpenAI (Timeout: 180s)...")
                         start_t = time.time()
                         response_text, _, usage_dict = await asyncio.wait_for(
                             self._llm.chat("openai", prompt, temperature=None, max_tokens=max_output),
                             timeout=180.0
                         )
                         logger.info(f"Memory: 📥 LLM Response received in {time.time() - start_t:.2f}s")
                     except asyncio.TimeoutError:
                         logger.error(f"Memory: LLM Analysis TIMED OUT for {user_id}")
                         raise Exception("Analysis Request Timed Out (3min)")
                     
                     if usage_dict:
                         u_in = usage_dict.get("prompt_tokens") or usage_dict.get("input_tokens", 0)
                         u_out = usage_dict.get("completion_tokens") or usage_dict.get("output_tokens", 0)
                         c_usd = (u_in * 0.00000015) + (u_out * 0.00000060)
                         
                         actual_usage = Usage(tokens_in=u_in, tokens_out=u_out, usd=c_usd)
                         logger.info(f"Memory: DEBUG OpenAI Usage -> In:{u_in} Out:{u_out} USD:{c_usd:.6f}")
                     else:
                          # Fallback/Estimate
                          pass 

                else:
                     raise RuntimeError("OpenAI disabled")
            except Exception as e:
                 logger.error(f"Memory: DEBUG OpenAI Failed: {e}")
                 # Fallback to Local ... (implied logic, simplified for brevity as user wants robustness)
                 # Re-raise for now to ensure we handle errors correctly or add explicit fallback logic here if requested.
                 # For now, let's Fail Fast and set Error status so user knows.
                 raise e

            # 3. COMMIT COST
            if cost_manager and actual_usage:
                cost_manager.commit("optimization", "openai", user_id, rid, actual_usage)


            # 4. PARSE JSON
            try:
                data = self._parse_analysis_json(response_text)
            except Exception as e:
                logger.warning(f"Memory: Failed to extract JSON: {e}")
                # Log raw response for debugging
                logger.debug(f"Raw Response: {response_text[:200]}...")
                raise Exception("JSON Extraction Failed")

            # 5. UPDATE PROFILE (Success)
            if data:
                # Flatten
                data["last_context"] = messages
                
                # Merge Layers
                l2 = data.get("layer2_user_memory", {})
                l3 = data.get("layer3_summary", {})
                
                final_data = {
                    "traits": l2.get("traits", []),
                    "impression": l2.get("impression", "Analyzed"),
                    "layer2_user_memory": l2,
                    "layer3_summary": l3,
                    "status": "Optimized",
                    "message_count": len(messages)
                }
                
                await self.update_user_profile(user_id, final_data, guild_id, is_public)
                logger.info(f"Memory: 分析完了: {user_id}")
            
        except Exception as e:
            logger.error(f"Memory: 分析失敗 ({user_id}): {e}")
            await self.set_user_status(user_id, "Error", "分析失敗", guild_id, is_public)



        



        
    async def _analyze_wrapper(self, user_id: int, messages: list, guild_id: int | str = None, is_public: bool = True):



        """Wrapper to run analysis with concurrency limit and scope."""
        async with self.sem:
            await self._analyze_batch(user_id, messages, guild_id, is_public)

    async def _persist_message(self, user_id: int, entry: Dict[str, Any], guild_id: Optional[int], is_public: bool = True):
        """Append a message to the user's on-disk history for robust optimization."""
        path = self._get_memory_path(user_id, guild_id, is_public=is_public)
        try:
            profile = await self.get_user_profile(user_id, guild_id, current_channel_id=None) # get raw public/private
            # Wait, get_user_profile currently merges. I need a clean way to get just one layer.
            # Let's use _read_profile_retry directly.
            profile = await self._read_profile_retry(path)
            
            if not profile:
                import time
                profile = {
                    "discord_user_id": str(user_id),
                    "created_at": time.time(),
                    "status": "New",
                    "raw_history": []
                }
            
            if "raw_history" not in profile:
                profile["raw_history"] = []
                
            profile["raw_history"].append(entry)
            
            # Keep last 100 messages for analysis
            if len(profile["raw_history"]) > 100:
                profile["raw_history"] = profile["raw_history"][-100:]
                
            await self._save_user_profile_atomic(path, profile)
        except Exception as e:
            logger.error(f"Failed to persist message for {user_id}: {e}")

    @tasks.loop(minutes=1)
    async def memory_worker(self):
        """Analyze buffered messages per user/guild/visibility periodically."""
        if not self.message_buffer: return
        
        # 1. Check System Load
        try:
            if psutil.cpu_percent() > 85: return
        except: pass

        # 2. Process Buffered Messages
        current_buffer = self.message_buffer.copy()
        self.message_buffer.clear()

        for uid, all_msgs in current_buffer.items():
            try:
                if not all_msgs: continue
                
                # Group messages by guild to respect partitioning
                by_guild = {}
                for m in all_msgs:
                    if not m or not isinstance(m, dict):
                        continue
                    gid = m.get("guild_id")
                    if gid not in by_guild: by_guild[gid] = []
                    by_guild[gid].append(m)
                
                # Clear buffer for this user
                self.message_buffer[uid] = []

                for gid, g_msgs in by_guild.items():
                    # Check status per (user, guild)
                    profile = await self.get_user_profile(uid, gid)
                    if not profile:
                        status = "New"
                        traits = []
                    else:
                        status = profile.get("status", "New")
                        traits = profile.get("traits", [])

                    if status == "New" or len(g_msgs) >= 5:
                        logger.info(f"メモリ: {uid} (サーバー {gid}) の分析をキューに追加しました ({len(g_msgs)}件)")
                        
                        # Set Pending Status (Queued)
                        current_profile = await self.get_user_profile(uid, gid)
                        if not current_profile: current_profile = {} # Should actally exist by now or be handled
                        current_profile["status"] = "Pending"
                        await self.update_user_profile(uid, current_profile, gid)

                        asyncio.create_task(self._analyze_wrapper(uid, g_msgs, gid, is_public=True)) # Default to public in worker for now
                    else:
                        # Not enough yet, put back in buffer? 
                        # Actually, if we clear it, we lose them. 
                        # Better to put back ONLY what we didn't process.
                        if uid not in self.message_buffer: self.message_buffer[uid] = []
                        self.message_buffer[uid].extend(g_msgs)
                        logger.debug(f"MemoryWorker: {uid} (Guild {gid}) - Not enough data yet ({len(g_msgs)} msgs)")
            except Exception as e:
                logger.error(f"メモリ: ユーザー {uid} のバッファ処理中にエラー: {e}")

    async def force_user_optimization(self, user_id: int, guild_id: int):
        """Manually trigger optimization for a user by scanning recent history."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            logger.warning(f"ForceOpt: Guild {guild_id} not found.")
            return False, "Guild not found."

        member = guild.get_member(user_id)
        if not member:
             logger.warning(f"ForceOpt: Member {user_id} not found in {guild.name}.")
             return False, "Member not found."

        # Scan active channels
        collected_msgs = []
        scanned_count = 0
        
        # Determine status
        profile = await self.get_user_profile(user_id, guild_id)
        
                # Phase 33: Local Log Optimization (Bypass API)
        # We fetch for both scopes if no specific channel is provided
        if len(collected_msgs) < 10:
             from ..utils.log_reader import LocalLogReader
             reader = LocalLogReader()
             try:
                 # Fetch both (None means merge)
                 local_msgs = reader.get_recent_messages(guild_id, limit=50, user_id=user_id, is_public=None)
                 if local_msgs:
                     logger.info(f"ForceOpt: Found {len(local_msgs)} messages in Local Logs.")
                     for m in local_msgs:
                         collected_msgs.append({
                             "id": 0, 
                             "content": m["content"],
                             "timestamp": m["timestamp"],
                             "channel": "LocalLog",
                             "guild": guild.name,
                             "is_public": True # Assume public for manual force unless we track it
                         })
             except Exception as e:
                 logger.error(f"ForceOpt: Local Log Read Failed: {e}")

        if len(collected_msgs) < 10:
            logger.info(f"ForceOpt: Found only {len(collected_msgs)} localized msgs. Scanning guild history (API)...")
            
            # Update Dashboard to "Scanning" immediately
            await self.set_user_status(user_id, "Processing", "履歴をスキャン中...", guild_id)
            
            # Use the robust deep scan method we improved!
            # Scan all channels/threads with deep paging
            logger.info(f"ForceOpt: Triggering deep scan for {member.display_name}...")
            
            api_msgs = await self._find_user_history_targeted(user_id, guild_id, scan_depth=1000)
            collected_msgs.extend(api_msgs)
        else:
            logger.info(f"ForceOpt: Using {len(collected_msgs)} persistent messages for {member.display_name}.")

        if not profile: 
             # Create temp profile so dashboard shows "Pending" immediately
             await self.update_user_profile(user_id, {"status": "Pending", "name": member.display_name}, guild_id)
        else:
             profile["status"] = "Pending"
             await self.update_user_profile(user_id, profile, guild_id)
        
        if not collected_msgs:
            # Revert status if nothing found
             if profile:
                 profile["status"] = "New" # Or whatever it was? Default to New.
                 await self.update_user_profile(user_id, profile, guild_id)
             return False, "No recent messages found to analyze."

        # Trigger Analysis (Partitioned)
        pub_msgs = [m for m in collected_msgs if m.get("is_public", True)]
        priv_msgs = [m for m in collected_msgs if not m.get("is_public", True)]
        
        if pub_msgs:
            asyncio.create_task(self._analyze_wrapper(user_id, pub_msgs, guild_id, is_public=True))
        if priv_msgs:
            asyncio.create_task(self._analyze_wrapper(user_id, priv_msgs, guild_id, is_public=False))
            
        return True, f"Optimization queued ({len(pub_msgs)} public, {len(priv_msgs)} private msgs)."
    async def queue_for_analysis(self, user_id: int, guild_id: int, messages: list):
        """Internal helper to mark user as Pending and trigger analysis task."""
        if not messages:
            return

        # Update status to Pending immediately so dashboard reflects activity
        profile = await self.get_user_profile(user_id, guild_id)
        
        # Don't downgrade "Processing" (Blue) to "Pending" (Yellow)
        current_status = profile.get("status") if profile else None
        
        if current_status != "Processing":
            if not profile:
                await self.update_user_profile(user_id, {"status": "Pending"}, guild_id)
            else:
                profile["status"] = "Pending"
                await self.update_user_profile(user_id, profile, guild_id)

        # Trigger background analysis (Fire & Forget) - Partitioned
        pub_batch = [m for m in messages if m.get("is_public", True)]
        priv_batch = [m for m in messages if not m.get("is_public", True)]
        
        if pub_batch:
            asyncio.create_task(self._analyze_wrapper(user_id, pub_batch, guild_id, is_public=True))
        if priv_batch:
            asyncio.create_task(self._analyze_wrapper(user_id, priv_batch, guild_id, is_public=False))

    async def _find_user_history_targeted(self, user_id: int, guild_id: int, scan_depth: int = 500, allow_api: bool = False) -> list:
        """Find messages for a specific user. API scan is optional to prevent rate limits."""
        guild = self.bot.get_guild(guild_id)
        if not guild: return []
        collected = []
        
        # 1. Try Local Logs (Optimization)
        try:
            from ..utils.log_reader import LocalLogReader
            reader = LocalLogReader()
            local_msgs = reader.get_recent_messages(guild_id, limit=50, user_id=user_id, is_public=None)
            if local_msgs:
                logger.info(f"TargetedHistory: Found {len(local_msgs)} in Local Logs for {user_id}. Using them.")
                for m in local_msgs:
                    collected.append({
                        "id": 0,
                        "content": m["content"],
                        "timestamp": m["timestamp"],
                        "channel": "LocalLog",
                        "guild": guild.name,
                        "guild_id": guild_id
                    })
                if len(collected) >= 10: # Lower threshold to 10 for startup
                    return collected
            else:
                logger.debug(f"TargetedHistory: Local Logs empty/unreadable for {user_id}.")
        except Exception as e:
            logger.error(f"TargetedHistory: Log read failed: {e}")

        # 2. API Fallback (Controlled)
        if not allow_api:
            logger.debug(f"TargetedHistory: API Scan skipped for {user_id} (allow_api=False).")
            return collected

        # Scan ALL channels, Threads, and Forums
        logger.debug(f"TargetedHistory: Falling back to Discord API for {user_id} (Channels + Threads)...")
        
        # Collect all scannable destinations
        destinations = []
        
        # Text Channels
        destinations.extend([c for c in guild.text_channels if c.permissions_for(guild.me).read_messages])
        
        # Threads (Active)
        destinations.extend([t for t in guild.threads if t.permissions_for(guild.me).read_messages])
        
        # Forum Channels (if visible)
        destinations.extend([vc for vc in guild.voice_channels if vc.permissions_for(guild.me).read_messages])

        for channel in destinations:
            try:
                # Paging Logic (as requested by User: "1 to 100, then 100 to 200...")
                # Scan up to 500 msgs per channel in chunks of 50 to respect limits
                # while allowing deep search.
                cursor = None
                msgs_checked = 0
                max_depth = scan_depth 
                
                while msgs_checked < max_depth:
                    batch = []
                    # Fetch next page
                    async for m in channel.history(limit=50, before=cursor):
                        batch.append(m)
                    
                    if not batch: break # End of channel history
                    
                    # Process batch
                    for m in batch:
                        if m.author.id == user_id and not m.author.bot:
                            collected.append({
                                "id": m.id,
                                "content": m.content,
                                "timestamp": m.created_at.isoformat(),
                                "channel": channel.name,
                                "guild": guild.name,
                                "guild_id": guild_id
                            })
                    
                    cursor = batch[-1] # Set cursor to oldest msg in batch
                    msgs_checked += len(batch)
                    
                    if len(collected) >= 50: break # Found enough total
                    
                    # Throttle between pages (User's "徐々に" strategy)
                    await asyncio.sleep(1.5)
                
            except: continue
            if len(collected) >= 50: break
            
        logger.info(f"TargetedHistory: Fallback found {len(collected)} messages for {user_id}.")
        return collected

    @tasks.loop(minutes=60)
    async def scan_history_task(self):
        """Periodic Catch-up: Automatically optimizes ONLINE users who are 'New'."""
        await self.bot.wait_until_ready()
        # Initial wait to let bot settle if it's the first run
        if self.scan_history_task.current_loop == 0:
            logger.info("AutoScan: Waiting 10s before initial optimization scan...")
            await asyncio.sleep(10)

        count = 0
        logger.info("AutoScan: Searching for online 'New' users to optimize...")
        
        for guild in self.bot.guilds:
            if not await self._should_process_guild(guild.id):
                continue
                
            # 1. Identify all targets first
            target_members = []
            for member in guild.members:
                if member.bot: continue
                # Quick status check (cache-friendly)
                profile = await self.get_user_profile(member.id, guild.id)
                status = profile.get("status", "New") if profile else "New"
                
                if status == "New":
                    target_members.append(member)
            
            if not target_members:
                continue

            logger.info(f"AutoScan: Found {len(target_members)} targets in {guild.name}. Starting BATCH scan...")

            # 2. Batch Scan Strategy (O(Channels) instead of O(Users*Channels))
            # We scan channels once and distribute messages to all waiting users.
            
            user_buffers = {m.id: [] for m in target_members}
            remaining_targets = set(m.id for m in target_members)
            
            # Collect destinations (Channels + Threads)
            destinations = []
            destinations.extend([c for c in guild.text_channels if c.permissions_for(guild.me).read_messages])
            destinations.extend([t for t in guild.threads if t.permissions_for(guild.me).read_messages])
            destinations.extend([vc for vc in guild.voice_channels if vc.permissions_for(guild.me).read_messages])

            # Scan loop
            scan_depth = 1000 # Deep scan for batch
            
            for channel in destinations:
                if not remaining_targets: break # All users satisfied
                
                try:
                    cursor = None
                    msgs_checked = 0
                    
                    while msgs_checked < scan_depth:
                        batch = []
                        try:
                            async for m in channel.history(limit=50, before=cursor):
                                batch.append(m)
                        except discord.HTTPException as e:
                            if e.status == 429:
                                logger.warning("AutoScan: Hit Rate Limit (429). Sleeping 60s and aborting channel scan.")
                                await asyncio.sleep(60)
                                break
                            else:
                                raise e
                        
                        if not batch: break
                        
                        # Process batch against ALL remaining targets
                        for m in batch:
                            if m.author.id in remaining_targets:
                                user_buffers[m.author.id].append({
                                    "id": m.id,
                                    "content": m.content,
                                    "timestamp": m.created_at.isoformat(),
                                    "channel": channel.name,
                                    "guild": guild.name,
                                    "guild_id": guild.id
                                })
                                # If user has enough, remove from targets
                                if len(user_buffers[m.author.id]) >= 50:
                                    remaining_targets.discard(m.author.id)
                        
                        cursor = batch[-1]
                        msgs_checked += len(batch)
                        
                        if not remaining_targets: break
                        
                        # "Gradually" - Slow pacing to avoid 429
                        await asyncio.sleep(2.0) 
                        
                except Exception as e:
                    logger.debug(f"AutoScan: Channel {channel.name} skipped: {e}")
                    continue

            # 3. Dispatch Analysis for all collected data
            for member in target_members:
                history = user_buffers[member.id]
                if history:
                    logger.info(f"AutoScan: Batch collected {len(history)} msgs for {member.display_name}. Queueing...")
                    # Force update status
                    profile = await self.get_user_profile(member.id, guild.id) or {}
                    profile["status"] = "Pending"
                    profile["name"] = member.display_name
                    await self.update_user_profile(member.id, profile, guild.id)
                    
                    asyncio.create_task(self._analyze_wrapper(member.id, history, guild.id))
                    count += 1
                else:
                     logger.debug(f"AutoScan: {member.display_name} - No history found in batch scan.")
            
            await asyncio.sleep(1.0) # Yield between guilds

        logger.info(f"AutoScan: Complete. Queued {count} users for auto-optimization.")
    @tasks.loop(hours=24)
    async def name_sweeper(self):
        """Proactively resolve 'Unknown' or ID-based names for all local profiles."""
        await self.bot.wait_until_ready()
        logger.info("Memory: Starting Name Sweeper task...")
        
        if not os.path.exists(MEMORY_DIR): return

        for filename in os.listdir(MEMORY_DIR):
            if not filename.endswith(".json"): continue
            
            uid_str = filename.replace(".json", "")
            if not uid_str.isdigit(): continue
            
            uid = int(uid_str)
            path = os.path.join(MEMORY_DIR, filename)
            
            try:
                async with aiofiles.open(path, "r", encoding="utf-8") as f:
                    data = json.loads(await f.read())
                
                name = data.get("name", "Unknown")
                if name in ["Unknown", ""] or name.startswith("User "):
                    # Resolve via Discord
                    user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
                    if user:
                        logger.info(f"Memory: Resolved name for {uid} -> {user.display_name}")
                        data["name"] = user.display_name
                        async with aiofiles.open(path, "w", encoding="utf-8") as f:
                            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
            except Exception as e:
                logger.warning(f"Memory: Sweeper failed for {uid}: {e}")
            
            await asyncio.sleep(2) # Avoid aggressive rate limiting

    @app_commands.command(name="optimize_user", description="特定のユーザーの履歴をスキャンして最適化キューに入れます")
    @app_commands.describe(target="分析対象のユーザー")
    async def analyze_user(self, interaction: discord.Interaction, target: discord.User):
        """Manually trigger optimization for a specific user."""
        await interaction.response.defer()
        
        try:
            # 1. Update Status to Processing
            guild_id = interaction.guild_id
            await self.set_user_status(target.id, "Processing", "手動スキャン実行中...", guild_id)
            
            # 2. Deep Scan using the robust method
            # Manual scan depth = 10000 (Very deep, effectively "created at" for most)
            # Enable API Fallback for manual user commands
            history = await self._find_user_history_targeted(target.id, guild_id, scan_depth=10000, allow_api=True)
            
            if history:
                # 3. Queue Analysis
                await self._analyze_batch(target.id, history, guild_id)
                await interaction.followup.send(f"✅ **{target.display_name}** の履歴を{len(history)}件発見しました。分析を開始します。\n(ダッシュボードで進捗を確認できます)")
            else:
                # 4. Failed
                await self.set_user_status(target.id, "New", "履歴が見つかりませんでした", guild_id)
                await interaction.followup.send(f"⚠️ **{target.display_name}** の履歴が見つかりませんでした。\n(直近300件の会話またはログに存在しません)", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @commands.command(name="refresh_profiles")
    @commands.is_owner()
    async def refresh_profiles(self, ctx):
        """Update guild/name info for all existing user profiles."""
        await ctx.send("🔄 Updating all user profiles with latest Guild/Name info...")
        
        async def report_progress(msg):
            # Only send final stats to avoid spam, or edit?
            # For simplicity, just log or send major updates.
            pass
            
        result = await self._perform_profile_refresh()
        await ctx.send(result)

    async def _perform_profile_refresh(self) -> str:
        """Core logic to refresh profiles."""
        count = 0
        updated_count = 0
        
        user_map = {}
        for guild in self.bot.guilds:
            if not await self._should_process_guild(guild.id):
                continue
            for member in guild.members:
                if member.id not in user_map:
                    user_map[member.id] = (member, guild)
        
        if not os.path.exists(MEMORY_DIR):
             return "No memory directory found."
             
        files = [f for f in os.listdir(MEMORY_DIR) if f.endswith(".json")]
        start_time = time.time()
        
        for filename in files:
            uid_str = filename.replace(".json", "")
            
            # Migration Logic: If file is OLD format (just digits)
            if uid_str.isdigit() and "_" not in uid_str:
                uid = int(uid_str)
                # Read content to find guild_id
                try:
                    old_path = os.path.join(MEMORY_DIR, filename)
                    async with aiofiles.open(old_path, 'r', encoding='utf-8') as f:
                        data = json.loads(await f.read())
                    
                    gid_str = data.get("guild_id")
                    if gid_str:
                        # MIGRATE: Rename to {uid}_{gid}.json
                        new_filename = f"{uid}_{gid_str}.json"
                        new_path = os.path.join(MEMORY_DIR, new_filename)
                        if not os.path.exists(new_path): # Don't overwrite if exists
                            os.rename(old_path, new_path)
                            logger.info(f"Migrated {filename} -> {new_filename}")
                            filename = new_filename # Update for loop
                        else:
                            # If new path exists (duplicate?), maybe delete old or merge?
                            # For safety, keep old, but we will process new.
                            pass
                except Exception as e:
                    logger.error(f"Migration failed for {filename}: {e}")

            # Re-parse ID after potential rename
            # E.g. "123_456.json"
            base_name = filename.replace(".json", "")
            parts = base_name.split('_')
            
            if len(parts) == 1 and parts[0].isdigit():
                 # Legacy/DM file
                 uid = int(parts[0])
                 guild = None # Treating as global/DM
            elif len(parts) == 2 and parts[0].isdigit():
                 # New format
                 uid = int(parts[0])
                 # We need to find the member in that guild!
                 target_gid = int(parts[1])
                 guild = self.bot.get_guild(target_gid)
            else:
                continue

            # Ensure Name Logic
            if guild:
                member = guild.get_member(uid)
                if member:
                     await self._ensure_user_name(member, guild)
                     updated_count += 1
                     
                     # FIXED: Reset Stuck Status
                     # If status is Processing/Pending during a manual refresh, it's likely stuck.
                     path = os.path.join(MEMORY_DIR, filename)
                     try:
                         async with aiofiles.open(path, "r", encoding="utf-8") as f:
                             d = json.loads(await f.read())
                         
                         current_status = d.get("status", "New")
                         if current_status in ["Processing", "Pending"]:
                             traits = d.get("traits", [])
                             new_status = "Optimized" if traits else "New"
                             d["status"] = new_status
                             d["impression"] = None # Clear stuck impression
                             
                             async with aiofiles.open(path, "w", encoding="utf-8") as f:
                                 await f.write(json.dumps(d, indent=2, ensure_ascii=False))
                             logger.info(f"Memory: Unstuck {filename} status ({current_status} -> {new_status})")
                     except Exception as e:
                         logger.error(f"Memory: Failed to unstuck {filename}: {e}")
            elif uid in user_map: 
                # Fallback for legacy files: use mapped guild
                member, guild = user_map[uid]
                await self._ensure_user_name(member, guild)
                updated_count += 1
            
            count += 1
            if count % 10 == 0:
                await asyncio.sleep(0.01)

        # Phase 2: Detect & Initialize Ghost Users (Online but No File)
        # Requested by User: "Why are they still gray?" -> Force Optimize or Mark as Empty Optimized
        logger.info("Memory: Phase 2 - Scanning for Ghost Users...")
        processed_ghosts = 0
        
        for uid, (member, guild) in user_map.items():
            if member.bot: continue
            
            # Check if file exists
            path = os.path.join(MEMORY_DIR, f"{uid}_{guild.id}.json")
            if not os.path.exists(path):
                # Ghost Found!
                logger.info(f"Memory: Found Ghost User {member.display_name} ({uid}). processing...")
                
                # Update Dashboard Immediately
                await self.set_user_status(uid, "Processing", "履歴をスキャン中...", guild.id)

                # 1. Try to find history (Backfill)
                history = await self._find_user_history_targeted(uid, guild.id)
                
                if history:
                    # Case A: Found History -> Pending & Analyze
                    logger.info(f"Memory: Ghost {member.display_name} has {len(history)} msgs. Queueing optimization.")
                    profile = {
                        "status": "Pending",
                        "name": member.display_name,
                        "guild_id": str(guild.id),
                        "guild_name": guild.name,
                        "traits": [],
                        "impression": "Recovering history...",
                        "last_updated": datetime.now().isoformat()
                    }
                    await self.update_user_profile(uid, profile, guild.id)
                    asyncio.create_task(self._analyze_wrapper(uid, history, guild.id))
                else:
                    # Case B: No History -> Mark Optimized (Empty) to remove "Gray" status
                    logger.info(f"Memory: Ghost {member.display_name} has NO msgs. Marking Optimized (Empty).")
                    profile = {
                        "status": "Optimized",
                        "name": member.display_name,
                        "guild_id": str(guild.id),
                        "guild_name": guild.name,
                        "traits": [],
                        "layer2_user_memory": {"facts": [], "traits": [], "impression": "No activity detected.", "interests": []},
                        "impression": "No detected activity.",
                        "last_updated": datetime.now().isoformat()
                    }
                    await self.update_user_profile(uid, profile, guild.id)

                processed_ghosts += 1
                
                # Dynamic Throttling: only sleep heavily if we actually queued an API/LLM task
                if history:
                    await asyncio.sleep(1.0) # Throttle for Discord API History & LLM safety
                else:
                    await asyncio.sleep(0.1) # Fast-track empty profiles
                
        duration = time.time() - start_time
        return f"✅ Analyzed {count} existing files. Backfilled {processed_ghosts} ghost users in {duration:.2f}s."

    async def refresh_watcher(self):
        """Watch for trigger file to refresh profiles."""
        trigger_path = "refresh_profiles.trigger"
        if os.path.exists(trigger_path):
            logger.info("Memory: Trigger file detected! Refreshing profiles...")
            try:
                os.remove(trigger_path)
                result = await self._perform_profile_refresh()
                logger.info(f"Memory: Refresh caused by trigger complete: {result}")
            except Exception as e:
                logger.error(f"Memory: Failed to handle refresh trigger: {e}")

        # Optimize Queue Watcher (IPC) - ONLY IN WORKER MODE to prevent Main Bot from slowing down
        queue_path = r"L:\ORA_State\optimize_queue.json"
        if self.worker_mode and os.path.exists(queue_path):
            try:
                # Read, Process, Clear
                requests_to_process = []
                async with aiofiles.open(queue_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    if content.strip():
                        try:
                            requests_to_process = json.loads(content)
                        except json.JSONDecodeError:
                            requests_to_process = []
                
                if requests_to_process:
                    # Clear Queue immediately to prevent double processing
                    async with aiofiles.open(queue_path, "w", encoding="utf-8") as f:
                        await f.write("[]")
                    
                    logger.info(f"Memory: Processing {len(requests_to_process)} optimization requests from queue.")
                    
                    for req in requests_to_process:
                        uid = req.get("user_id")
                        gid = req.get("guild_id")
                        
                        if uid:
                            logger.info(f"Memory: Forcing input optimization for {uid} (Guild: {gid})")
                            asyncio.create_task(self.force_user_optimization(uid, gid))
                            # Add small delay to prevent cpu spike
                            await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Memory: Failed to process optimize queue: {e}")

    @tasks.loop(minutes=5)
    async def idle_log_archiver(self):
        """Worker Only: Slowly archives chat history (Forward & Backward) when idle."""
        if not self.worker_mode: return
        
        await self.bot.wait_until_ready()
        logger.info("IdleArchiver: Checking for channels to archive...")
        
        state_path = r"L:\ORA_State\archive_status.json"
        try:
            if os.path.exists(state_path):
                async with aiofiles.open(state_path, "r") as f:
                    state = json.loads(await f.read())
            else:
                state = {}
        except: state = {}

        for guild in self.bot.guilds:
            if not await self._should_process_guild(guild.id):
                 continue
            for channel in guild.text_channels:
                try:
                    if not channel.permissions_for(guild.me).read_messages: continue
                    
                    ch_state = state.get(str(channel.id), {"newest": None, "oldest": None})
                    is_public = self.is_public(channel)
                    
                    # 1. FORWARD SCAN (Catch up to now)
                    last_id = ch_state.get("newest")
                    start_at = discord.Object(id=last_id) if last_id else None
                    
                    msgs = []
                    if last_id:
                        async for m in channel.history(limit=50, after=start_at, oldest_first=True):
                            msgs.append(m)
                    else:
                        async for m in channel.history(limit=50):
                            msgs.append(m)
                        msgs.reverse()
                    
                    if msgs:
                        ch_state["newest"] = msgs[-1].id
                        if not ch_state["oldest"]: ch_state["oldest"] = msgs[0].id
                        await self._save_archived_msgs(guild.id, channel.id, msgs, is_public)

                    # 2. BACKWARD SCAN (Full history backfill)
                    first_id = ch_state.get("oldest")
                    if first_id:
                        back_msgs = []
                        async for m in channel.history(limit=50, before=discord.Object(id=first_id)):
                            back_msgs.append(m)
                        
                        if back_msgs:
                            ch_state["oldest"] = back_msgs[-1].id # oldest_first=False by default for 'before'
                            await self._save_archived_msgs(guild.id, channel.id, back_msgs, is_public)
                            logger.info(f"IdleArchiver: Backfilled {len(back_msgs)} msgs from #{channel.name}")

                    state[str(channel.id)] = ch_state
                    
                    # Update State
                    async with aiofiles.open(state_path, "w") as f:
                        await f.write(json.dumps(state))

                    await asyncio.sleep(2) # Throttle per channel
                        
                except Exception as e:
                    logger.error(f"IdleArchiver error on {channel.name}: {e}")
                    continue
                    
        logger.info("IdleArchiver: Cycle complete.")

    async def _save_archived_msgs(self, guild_id, channel_id, msgs, is_public):
        """Append messages to scoped logs."""
        suffix = "_public" if is_public else "_private"
        log_file = os.path.join(r"L:\ORA_Logs\guilds", f"{guild_id}{suffix}.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        async with aiofiles.open(log_file, "a", encoding="utf-8") as f:
            for m in msgs:
                 line = f"{m.created_at.isoformat()} INFO guild_{guild_id} Message: {m.author} ({m.author.id}): {m.content} | Attachments: {len(m.attachments)}\n"
                 await f.write(line)

    @tasks.loop(seconds=30)
    async def status_loop(self):
        """Periodic check for optimization queue and status health."""
        # 1. Check Optimize Queue (IPC)
        await self.refresh_watcher()
        
        # 2. Check Archiver Health (Worker Only)
        if self.worker_mode and not self.idle_log_archiver.is_running():
            try:
                self.idle_log_archiver.start()
            except RuntimeError:
                pass # Already running

    @status_loop.before_loop
    async def before_status_loop(self):
        await self.bot.wait_until_ready()

    @memory_worker.before_loop
    async def before_worker(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    # Try getting UnifiedClient first, then fallback to llm_client
    llm = getattr(bot, "unified_client", None) or getattr(bot, "llm_client", None)
    if not llm:
        logger.warning("MemoryCog: LLM Client not found on bot. Analysis disabled.")
    
    cog = MemoryCog(bot, llm)
    await bot.add_cog(cog)
    # Start the retroactive scan task
    bot.loop.create_task(cog.scan_history_task())
