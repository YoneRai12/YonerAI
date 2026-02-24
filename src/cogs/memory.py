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

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiofiles  # type: ignore
import aiohttp
import discord
import psutil
import pytz  # type: ignore
from discord import app_commands
from discord.ext import commands, tasks

from src.config import MEMORY_DIR
from src.services.markdown_memory import MarkdownMemory
from src.utils.cloud_sync import cloud_sync

logger = logging.getLogger(__name__)

CHANNEL_MEMORY_DIR = os.path.join(MEMORY_DIR, "channels")
USER_MEMORY_DIR = os.path.join(MEMORY_DIR, "users")
GUILD_MEMORY_DIR = os.path.join(MEMORY_DIR, "guilds")


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
                            continue  # Retry
                    except FileNotFoundError:
                        continue  # Was just removed
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
    if not text:
        return text

    # 1. Handle truncated string (last char is not quote or brace/bracket)
    # If the text ends inside a string, close it.
    if text.count('"') % 2 != 0:
        text += '"'

    # 2. Close open brackets/braces based on count
    open_brackets = text.count("[") - text.count("]")
    if open_brackets > 0:
        text += "]" * open_brackets

    open_braces = text.count("{") - text.count("}")
    if open_braces > 0:
        text += "}" * open_braces

    return text


class MemoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot, llm_client, worker_mode: bool = False):
        self.bot = bot
        self._llm = llm_client
        self.worker_mode = worker_mode
        self._ensure_memory_dir()

        # Buffer: {user_id: [{"content": str, "timestamp": str}, ...]}
        self.message_buffer: Dict[int, list] = {}
        # Channel Buffer: {channel_id: [{"content": str, "timestamp": str, "author": str}, ...]}
        self.channel_buffer: Dict[int, list] = {}
        # Guild Buffer: {guild_id: [{"content": str, "timestamp": str, "author": str, "channel": str}, ...]}
        self.guild_buffer: Dict[int, list] = {}

        # Concurrency Control (Worker: 50, Main: 20)
        limit = 50 if worker_mode else 10  # Main bot keeps low profile
        self.sem = asyncio.Semaphore(limit)
        self._io_lock = asyncio.Lock()  # Prevent concurrent file access

        # [RESTORED] Hub & Spoke: Re-enabled optimization for Discord users

        # Cleanup should run in ALL modes to ensure UI is clean
        asyncio.create_task(self.cleanup_stuck_profiles())

        if self.worker_mode:
            logger.info("MemoryCog: WORKER MODE (ヘビータスク優先) で起動しました。")
        else:
            logger.info("MemoryCog: MAIN MODE (リアルタイム応答 + フォールバック) で起動しました。")

        # [Phase 29] Multi-Modal Understanding
        self.captioner = None

        # [Clawdbot] Markdown Memory Service
        md_path = os.path.join(MEMORY_DIR, "markdown_logs")
        self.md_memory = MarkdownMemory(root_dir=md_path)

        # Core memory sync safety state (diagnostics-safe metadata only).
        self._core_sync_auth_fail_streak = 0
        self._core_sync_auth_fail_threshold = 3
        self._core_sync_backoff_sec = 300
        self._core_sync_backoff_until_ts = 0
        self._core_sync_last_warn_ts = 0
        self._core_sync_reason_code: str | None = None

    async def cog_load(self):
        """Start background tasks only when successfully loaded."""
        self.memory_worker.start()
        self.name_sweeper.start()
        if self.worker_mode:
            self.status_loop.change_interval(seconds=5)
            self.scan_history_task.start()
            self.refresh_watcher.start()
            self.idle_log_archiver.start()
        else:
            self.status_loop.start()
            self.scan_history_task.start()
            self.refresh_watcher.start()

    def cog_unload(self):
        self.status_loop.cancel()
        self.memory_worker.cancel()
        self.name_sweeper.cancel()
        self.scan_history_task.cancel()
        self.idle_log_archiver.cancel()
        self.surplus_token_burner.cancel()

    async def cleanup_stuck_profiles(self):
        """Reset 'Processing' users to 'Error' on startup to fix stuck yellow status."""
        await self.bot.wait_until_ready()
        logger.info("Memory: スタックした 'Processing' ステータスのプロファイルをチェック中...")
        if not os.path.exists(USER_MEMORY_DIR):
            return
        count = 0
        for f in os.listdir(USER_MEMORY_DIR):
            if not f.endswith(".json"):
                continue
            path = os.path.join(USER_MEMORY_DIR, f)
            try:
                # Lockless read for startup recovery speed (snapshot)
                async with aiofiles.open(path, "r", encoding="utf-8") as file:
                    content = await file.read()
                    data = json.loads(content)

                if data.get("status") in ["Processing", "Pending"]:
                    data["status"] = "Idle"
                    data["impression"] = "Optimization Reset (Ready)"
                    data["last_updated"] = datetime.now().isoformat()
                    await self._save_user_profile_atomic(path, data)
                    count += 1
            except Exception:
                continue

        if count > 0:
            logger.info(f"Memory: Unstuck {count} profiles from 'Processing' state.")

    # ----- Privacy Commands -----
    privacy_group = app_commands.Group(name="privacy", description="プライバシー設定")

    @privacy_group.command(name="set", description="記憶の公開設定を変更します (Public/Private)")
    @app_commands.describe(mode="Public: サーバー内で共有, Private: 自分のみ")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Public", value="public"),
            app_commands.Choice(name="Private", value="private"),
        ]
    )
    async def privacy_set(self, interaction: discord.Interaction, mode: str):
        """Set privacy mode."""
        # Force lower case
        mode_val = mode.lower()
        if mode_val not in ["public", "private"]:
            await interaction.response.send_message("❌ 無効な設定です。", ephemeral=True)
            return

        # We actually don't have a direct "set_privacy" helper in MemoryCog exposed easily without Store abstraction,
        # BUT MemoryCog *is* the store essentially.
        # We need to update the user profile's "privacy_mode" maybe?
        # Or just use filenames?
        # The logic in `get_user_profile` merges based on channel visibility.
        # But `ora.py` or others use `store.get_privacy`.
        # `Store` class usually wraps DB.
        # Let's check `src/storage.py` or `store` injection.
        # Wait, `MemoryCog` IS the persistence layer?
        # `MediaCog` uses `self._store`.
        # Let's see if `MemoryCog` has `set_privacy`.
        # It does NOT.
        # However, `MediaCog` uses `self._store`.
        # I should probably update `src/utils/user_prefs.py` or similar if that's what controls it.
        # But for now, I will implement a basic toggle here if `Store` is not available.
        # Ah, `MediaCog` has `ensure_user`.

        # Let's assume we can import `Store` or similar, OR just save a preference file.
        # Simplest: Update the profile with "privacy_mode": "private/public"

        await interaction.response.defer(ephemeral=True)

        profile = await self.get_user_profile(interaction.user.id, interaction.guild.id)
        if not profile:
             profile = {}

        profile["privacy_mode"] = mode_val
        await self.update_user_profile(interaction.user.id, profile, interaction.guild.id)

        await interaction.followup.send(f"✅ プライバシー設定を **{mode}** に変更しました。", ephemeral=True)

    @privacy_group.command(name="check", description="現在のプライバシー設定を確認します")
    async def privacy_check(self, interaction: discord.Interaction):
        """Check privacy setting."""
        profile = await self.get_user_profile(interaction.user.id, interaction.guild.id)
        mode = profile.get("privacy_mode", "public") if profile else "public"
        await interaction.response.send_message(f"現在の設定: **{mode.capitalize()}**", ephemeral=True)

    def _ensure_memory_dir(self):
        """Ensure memory directory exists."""
        # NOTE: Some code paths still read/write profiles under MEMORY_DIR directly,
        # but current layout is MEMORY_DIR/{users,channels,...}. Ensure all exist.
        for d in [MEMORY_DIR, USER_MEMORY_DIR, CHANNEL_MEMORY_DIR, GUILD_MEMORY_DIR]:
            if not os.path.exists(d):
                try:
                    os.makedirs(d, exist_ok=True)
                    logger.info(f"Created Memory Directory: {d}")
                except Exception as e:
                    logger.error(f"Failed to create Memory Directory {d}: {e}")

    def is_public(self, channel) -> bool:
        """Returns True if @everyone has View Channel permission."""
        if not hasattr(channel, "guild"):
            return False
        everyone = channel.guild.default_role
        perms = channel.permissions_for(everyone)
        # Simplified: True if everyone can see it
        return perms.view_channel

    async def _should_process_guild(self, guild_id: int) -> bool:
        """Determine if this bot instance should process heavy tasks for this guild."""
        if self.worker_mode:
            return True  # Worker bot always processes what it's in

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False

        # Check if Worker Bot (1447556986756530296) is in this guild
        worker_id = int(os.getenv("WORKER_BOT_ID", 0))
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

    @tasks.loop(minutes=30)
    async def surplus_token_burner(self):
        """
        [Feature] Daily Surplus Burner (Optimization).
        Checks remaining daily budget at 08:30 JST (23:30 UTC) and burns it on Deep Optimization.
        """
        now = datetime.now(pytz.utc)
        # Target: 23:30 UTC = 08:30 JST (30 mins before 09:00 reset)
        if not (now.hour == 23 and now.minute >= 30):
            return

        # Access CostManager
        ora_cog = self.bot.get_cog("ORACog")
        if not ora_cog or not ora_cog.cost_manager:
            return

        remaining = ora_cog.cost_manager.get_remaining_budget("stable", "openai")
        if remaining == -1:
            return  # No limit

        # Threshold: If we have > 50,000 tokens left, use them.
        if remaining > 50000:
            logger.info(
                f"🔥 [Surplus Burner] Detected {remaining} unused tokens before reset. Engaging Deep Optimization..."
            )

            # Find users who need optimization (Pending / Oldest)
            # Scan memory dir
            candidates = []
            if os.path.exists(MEMORY_DIR):
                for f in os.listdir(MEMORY_DIR):
                    if f.endswith(".json"):
                        candidates.append(f.replace(".json", ""))  # user_id or uid_gid

            # Shuffle or pick pending
            import random

            random.shuffle(candidates)

            burned = 0
            for cid in candidates[:5]:  # Cap at 5 users to avoid timeouts
                # Parse ID
                try:
                    if "_" in cid:  # uid_gid
                        uid_str, gid_str = cid.split("_", 1)
                        if gid_str.endswith("_public") or gid_str.endswith("_private"):
                            gid_str = gid_str.replace("_public", "").replace("_private", "")
                        uid = int(uid_str)
                        gid = int(gid_str)
                    else:
                        uid = int(cid)
                        gid = None

                    # Trigger Scan
                    # Force "Deep" via usage ratio check inside _analyze_batch (which sees ratio is low -> uses Deep)
                    # wait, _analyze_batch logic uses 'usage_ratio > 0.8' to DOWNGRADE.
                    # We need to Ensure it uses UPGRADE.
                    # Actually _analyze_batch defaults to "Extreme" if budget allows.
                    # So calling it is enough.

                    # We need to load messages.
                    # This requires reading history.
                    profile = await self.get_user_profile(uid, gid)
                    raw_history = profile.get("raw_history", []) if profile else []

                    # Convert raw history to messages
                    msgs = []
                    for entry in raw_history[-50:]:
                        msgs.append({"content": entry["content"], "timestamp": entry["timestamp"]})

                    if msgs:
                        logger.info(f"🔥 [Surplus Burner] Burning tokens on {uid}...")
                        asyncio.create_task(self._analyze_wrapper(uid, msgs, gid, True))
                        burned += 1

                except Exception as e:
                    logger.error(f"Burner failed for {cid}: {e}")

            if burned > 0:
                logger.info(f"🔥 [Surplus Burner] Triggered optimization for {burned} users.")


    async def _process_media_attachments(self, message: discord.Message):
        """Analyzes attachments (Image/Video) and appends context to buffer."""
        try:
            # Always record attachment metadata (even if we skip captioning) so the optimizer can learn
            # "user sent a dog photo" style context from later assistant/user text.
            meta_lines = []
            for att in message.attachments:
                try:
                    meta_lines.append(
                        f"- filename={att.filename} size_bytes={getattr(att, 'size', None)} content_type={getattr(att, 'content_type', None)} url={att.url}"
                    )
                except Exception:
                    continue

            if meta_lines:
                if message.author.id not in self.message_buffer:
                    self.message_buffer[message.author.id] = []
                entry = {
                    "id": message.id + 1,  # Pseudo-ID
                    "content": "[System Media Attachment]\n" + "\n".join(meta_lines),
                    "timestamp": datetime.now().isoformat(),
                    "channel": message.channel.name if hasattr(message.channel, "name") else "DM",
                    "guild": message.guild.name if message.guild else "DM",
                    "guild_id": message.guild.id if message.guild else None,
                    "is_public": self.is_public(message.channel),
                }
                self.message_buffer[message.author.id].append(entry)

            # Optional: captioning for attachments (costly). Default is off unless explicitly enabled.
            cap_mode = (os.getenv("ORA_MEMORY_MEDIA_CAPTION") or "off").strip().lower()
            if cap_mode not in {"off", "on", "auto"}:
                cap_mode = "off"

            if cap_mode == "off":
                return

            current_model = os.getenv("LLM_MODEL", "gpt-5-mini").lower()
            if cap_mode == "auto" and ("gpt-5" in current_model or "o1" in current_model or "o3" in current_model):
                # In auto mode we avoid a second vision call when the main brain already sees images.
                return

            if not self.captioner:
                ora_cog = self.bot.get_cog("ORACog")
                if ora_cog and hasattr(ora_cog, "unified_client"):
                    from ..utils.vision.captioner import ImageCaptioner
                    self.captioner = ImageCaptioner(ora_cog.unified_client)
                else:
                    return

            descriptions = []
            for att in message.attachments:
                ext = att.filename.lower().split(".")[-1]
                if ext in ["png", "jpg", "jpeg", "webp", "gif", "bmp"]:
                    text = await self.captioner.describe_media(att.url, "image")
                    descriptions.append(f"[Image Context: {text}]")
                elif ext in ["mp4", "mov", "webm", "mkv"]:
                    text = await self.captioner.describe_media(att.url, "video")
                    descriptions.append(f"[Video Context: {text}]")

            if descriptions:
                full_text = "\n".join(descriptions)

                # Append to buffer as a System Context Message
                # This ensures the Optimizer sees it as part of the conversation flow.
                if message.author.id not in self.message_buffer:
                    self.message_buffer[message.author.id] = []

                entry = {
                    "id": message.id + 1,  # Pseudo-ID
                    "content": f"[System Media Context] {full_text}",
                    "timestamp": datetime.now().isoformat(),
                    "channel": message.channel.name if hasattr(message.channel, "name") else "DM",
                    "guild": message.guild.name if message.guild else "DM",
                    "guild_id": message.guild.id if message.guild else None,
                    "is_public": self.is_public(message.channel),
                }

                self.message_buffer[message.author.id].append(entry)
                # logger.info(f"Memory: Added media context for {message.author.display_name}")

        except Exception as e:
            logger.error(f"Media Analysis Error: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Buffer user messages for analysis."""
        # Worker Bot should NOT buffer real-time messages (Main Bot does that)
        if self.worker_mode:
            return

        if message.author.bot:
            return
        if not message.guild:
            # Allow DM buffering for cross-platform memory
            pass

        # [NEW] Multi-Modal Analysis Hook
        if message.attachments:
            asyncio.create_task(self._process_media_attachments(message))

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
            "is_public": is_pub,
        }
        self.message_buffer[message.author.id].append(entry)

        # [RESTORED] Local optimization trigger for real-time responsiveness
        if len(self.message_buffer[message.author.id]) >= 5:
            logger.info(f"Memory: Instant Optimization Trigger for {message.author.display_name} (5+ new msgs)")
            msgs_to_process = self.message_buffer[message.author.id][:]  # Copy
            self.message_buffer[message.author.id] = []  # Clear

            # Fire off analysis (Background)
            asyncio.create_task(
                self._analyze_wrapper(
                    message.author.id, msgs_to_process, message.guild.id if message.guild else None, is_pub
                )
            )


        # Cap buffer size (Safety net if trigger fails or backlog)
        if len(self.message_buffer[message.author.id]) > 50:
            self.message_buffer[message.author.id].pop(0)

        # Phase 32: Per-User History Persistence (with scope)
        asyncio.create_task(
            self._persist_message(message.author.id, entry, message.guild.id if message.guild else None, is_pub)
        )
        # [Clawdbot] Persistent Markdown Log
        sess_id = f"open-session-{message.guild.id if message.guild else 'dm'}"
        asyncio.create_task(
            self.md_memory.append_message(sess_id, "user", message.content)
        )




        # ---------------------------------------------------------
        # CHANNEL MEMORY BUFFERING
        # ---------------------------------------------------------
        if message.channel.id not in self.channel_buffer:
            self.channel_buffer[message.channel.id] = []

        chan_entry = {
            "content": message.content,
            "timestamp": datetime.now().isoformat(),
            "author": message.author.display_name,
        }
        self.channel_buffer[message.channel.id].append(chan_entry)

        # [RESTORED] Channel optimization trigger
        if len(self.channel_buffer[message.channel.id]) >= 10:
            # logger.info(f"Memory: Channel Optimization Trigger for {message.channel.name}")
            c_msgs = self.channel_buffer[message.channel.id][:]
            self.channel_buffer[message.channel.id] = []
            asyncio.create_task(self._analyze_channel_wrapper(message.channel.id, c_msgs))

        # ---------------------------------------------------------
        # GUILD/SERVER MEMORY BUFFERING (high-level, public only)
        # ---------------------------------------------------------
        try:
            if message.guild and is_pub:
                gid = message.guild.id
                if gid not in self.guild_buffer:
                    self.guild_buffer[gid] = []
                self.guild_buffer[gid].append(
                    {
                        "content": message.content,
                        "timestamp": datetime.now().isoformat(),
                        "author": message.author.display_name,
                        "channel": message.channel.name if hasattr(message.channel, "name") else "unknown",
                    }
                )
                # Heuristic trigger (cheap): every 25 public messages per guild
                if len(self.guild_buffer[gid]) >= 25:
                    g_msgs = self.guild_buffer[gid][:]
                    self.guild_buffer[gid] = []
                    asyncio.create_task(
                        self._update_guild_profile_heuristic(
                            gid,
                            g_msgs,
                            guild_name=message.guild.name if message.guild else "",
                        )
                    )
                # Cap buffer in case trigger doesn't run
                if len(self.guild_buffer[gid]) > 100:
                    self.guild_buffer[gid].pop(0)
        except Exception:
            pass


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

    async def add_ai_message(self, user_id: int, content: str, guild_id: Optional[int], channel_id: int, channel_name: str, guild_name: str, is_public: bool):
        """Manually inject an assistant message into the buffer to ensure balanced context."""
        timestamp = datetime.now().isoformat()

        # User Buffer
        if user_id not in self.message_buffer:
            self.message_buffer[user_id] = []

        entry = {
            "id": int(time.time() * 1000), # Pseudo-ID
            "content": f"[Assistant]: {content}",
            "timestamp": timestamp,
            "channel": channel_name,
            "guild": guild_name,
            "guild_id": guild_id,
            "is_public": is_public,
        }
        self.message_buffer[user_id].append(entry)

        # Channel Buffer
        if channel_id not in self.channel_buffer:
            self.channel_buffer[channel_id] = []

        chan_entry = {
            "content": f"[Assistant]: {content}",
            "timestamp": timestamp,
            "author": "ORA",
        }
        self.channel_buffer[channel_id].append(chan_entry)

        # Persist as raw log
        asyncio.create_task(
            self._persist_message(user_id, entry, guild_id, is_public)
        )

        # [Clawdbot] Persistent Markdown Log
        # Determine session ID (fallback to channel/guild)
        sess_id = f"open-session-{guild_id if guild_id else 'dm'}"
        asyncio.create_task(
            self.md_memory.append_message(sess_id, "assistant", content)
        )





    def _get_memory_path(self, user_id: int, guild_id: int | str = None, is_public: bool = True) -> str:
        """Get path to user memory file. Supports Scope Partitioning."""
        if guild_id:
            suffix = "_public.json" if is_public else "_private.json"
            return os.path.join(USER_MEMORY_DIR, f"{user_id}_{guild_id}{suffix}")
        return os.path.join(USER_MEMORY_DIR, f"{user_id}.json")

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

                # [Feature] Avatar & Nitro Sync
                avatar = str(user.display_avatar.url)
                banner = str(user.banner.url) if user.banner else None
                is_nitro = False

                # Heuristic for Nitro
                if user.display_avatar.is_animated():
                    is_nitro = True
                if user.banner:
                    is_nitro = True
                if isinstance(user, discord.Member) and user.premium_since:
                    is_nitro = True

                if data.get("avatar_url") != avatar:
                    data["avatar_url"] = avatar
                    changed = True

                if data.get("banner_url") != banner:
                    data["banner_url"] = banner
                    changed = True

                if data.get("is_nitro") != is_nitro:
                    data["is_nitro"] = is_nitro
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
                    "status": "New",  # Initial state
                    "last_updated": datetime.now().isoformat(),
                    "guild_name": guild_name,
                    "guild_id": guild_id_str,
                }
                await self._save_user_profile_atomic(path, data)

        except Exception as e:
            logger.error(f"Error checking name for {uid}: {e}")

    async def get_user_profile(
        self, user_id: int, guild_id: int | str = None, current_channel_id: int = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve user profile. Merges public and private layers if channel allows."""
        is_current_public = True
        if current_channel_id:
            ch = self.bot.get_channel(current_channel_id)
            if ch:
                is_current_public = self.is_public(ch)

        # 1. Load Public Profile (Primary)
        public_path = self._get_memory_path(user_id, guild_id, is_public=True)
        profile = await self._read_profile_retry(public_path)

        if not profile and not guild_id:  # Legacy/DM fallback
            path = os.path.join(MEMORY_DIR, f"{user_id}.json")
            profile = await self._read_profile_retry(path)

        if not profile:
            # Return skeleton if totally new
            return {
                "status": "New",
                "name": f"User_{user_id}",
                "guild_id": str(guild_id) if guild_id else None,
                "traits": [],
                "layer2_user_memory": {"facts": [], "traits": [], "impression": "Newcomer"},
            }

        # 2. If channel is Private, merge Private Profile
        if not is_current_public:
            private_path = self._get_memory_path(user_id, guild_id, is_public=False)
            private_profile = await self._read_profile_retry(private_path)
            if private_profile:
                # Merge traits and facts
                profile["traits"] = list(set(profile.get("traits", []) + private_profile.get("traits", [])))
                profile["layer2_user_memory"]["facts"] = list(
                    set(
                        profile.get("layer2_user_memory", {}).get("facts", [])
                        + private_profile.get("layer2_user_memory", {}).get("facts", [])
                    )
                )
                if private_profile.get("impression"):
                    profile["impression"] = f"{profile.get('impression')} | [Private] {private_profile['impression']}"

        return profile

    async def _read_profile_retry(self, path: str) -> Optional[Dict[str, Any]]:
        """Retry wrapper for reading profiles."""
        if not os.path.exists(path):
            return None
        async with SimpleFileLock(path):
            async with self._io_lock:
                for _ in range(3):
                    try:
                        async with aiofiles.open(path, "r", encoding="utf-8") as f:
                            content = await f.read()
                            if content.strip():
                                return json.loads(content)
                    except Exception:
                        await asyncio.sleep(0.1)
        return None

    async def _save_user_profile_atomic(self, path: str, data: dict) -> None:
        """Atomic write via temp file to prevent corruption, with Process Lock."""
        async with SimpleFileLock(path):
            temp_path = path + ".tmp"
            try:
                # 1. Local Save
                async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(data, indent=2, ensure_ascii=False))
                    await f.flush()

                # Windows Robustness: Retry logic for os.replace (AV scanners etc)
                for attempt in range(5):
                    try:
                        if os.path.exists(path):
                            os.replace(temp_path, path)
                        else:
                            os.rename(temp_path, path)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        await asyncio.sleep(0.2 * (attempt + 1))
                    except Exception:
                        raise

                # 2. Cloud Sync (Async Trigger)
                # Only sync USER memory files. Channel memory lives under CHANNEL_MEMORY_DIR and
                # its filenames are numeric (channel_id), which must NOT be treated as user_id.
                try:
                    norm_path = os.path.normpath(path)
                    user_root = os.path.normpath(USER_MEMORY_DIR)
                    is_user_profile = os.path.commonpath([norm_path, user_root]) == user_root
                except Exception:
                    is_user_profile = False

                if is_user_profile:
                    filename = os.path.basename(path)
                    if filename.endswith(".json"):
                        # Extract user_id from filename (e.g., "12345_guildid_public.json" or "12345.json")
                        user_id_str = filename.split(".")[0].split("_")[0]
                        try:
                            user_id = int(user_id_str)
                            asyncio.create_task(cloud_sync.sync_user_data(user_id, data))
                        except ValueError:
                            logger.warning(f"Could not parse user_id from filename for cloud sync: {filename}")

            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                logger.error(f"Atomic save failed for {path}: {e}")
                raise

    def _get_channel_memory_path(self, channel_id: int) -> str:
        """Get path to channel memory file."""
        return os.path.join(CHANNEL_MEMORY_DIR, f"{channel_id}.json")

    async def get_channel_profile(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve channel profile (Summary/Topic)."""
        path = self._get_channel_memory_path(channel_id)
        return await self._read_profile_retry(path)

    def _get_guild_memory_path(self, guild_id: int) -> str:
        """Get path to guild/server memory file."""
        return os.path.join(GUILD_MEMORY_DIR, f"{guild_id}.json")

    async def get_guild_profile(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve guild/server profile (high-level hint/topics)."""
        path = self._get_guild_memory_path(guild_id)
        return await self._read_profile_retry(path)

    async def set_guild_hint(self, guild_id: int, hint: str) -> None:
        """
        Set a high-level guild hint. This is meant to disambiguate acronyms and domain context
        (e.g., "この鯖はVALORANT中心").
        """
        if not guild_id:
            return
        hint = (hint or "").strip()
        if not hint:
            return
        path = self._get_guild_memory_path(guild_id)
        current = await self._read_profile_retry(path) or {}
        if not isinstance(current, dict):
            current = {}
        current["guild_id"] = int(guild_id)
        current["hint"] = hint
        current["hint_source"] = "manual"
        current["updated_at"] = datetime.now().isoformat()
        await self._save_user_profile_atomic(path, current)

    async def _update_guild_profile_heuristic(self, guild_id: int, entries: list[dict], guild_name: str = "") -> None:
        """
        Deterministic, low-cost guild profiling.
        This intentionally avoids LLM calls and only writes safe, high-level aggregate info.
        """
        if not guild_id or not entries:
            return

        text = "\n".join([str(e.get("content") or "") for e in entries])[:20000].lower()
        if not text.strip():
            return

        keyword_topics: dict[str, list[str]] = {
            "VALORANT": ["valorant", "valo", "バロラント", "バロ"],
            "Apex Legends": ["apex", "エーペックス", "えぺ", "apex legends"],
            "Fortnite": ["fortnite", "フォートナイト", "フォトナ"],
            "League of Legends": ["league of legends", "lol", "リーグ", "lol"],
        }

        counts: dict[str, int] = {}
        for topic, keys in keyword_topics.items():
            c = 0
            for k in keys:
                if k and k in text:
                    c += text.count(k)
            if c > 0:
                counts[topic] = c

        topics = [t for t, _c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))][:5]

        path = self._get_guild_memory_path(guild_id)
        current = await self._read_profile_retry(path) or {}
        if not isinstance(current, dict):
            current = {}

        current["guild_id"] = int(guild_id)
        if guild_name:
            current["guild_name"] = str(guild_name)[:120]
        if topics:
            current["topics"] = topics

        # If no manual hint exists, set a simple auto-hint from top topic.
        if not (current.get("hint") or "").strip() or current.get("hint_source") != "manual":
            if topics:
                current["hint"] = f"This server is primarily about {topics[0]}."
                current["hint_source"] = "auto"

        current["updated_at"] = datetime.now().isoformat()
        await self._save_user_profile_atomic(path, current)

    async def _sanitize_traits(self, traits: List[Any]) -> List[str]:
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
            if "[" in t or "{" in t:  # partial json
                continue

            if t not in seen:
                clean.append(t)
                seen.add(t)

        return clean[:15]  # Limit total count

    async def update_user_profile(
        self, user_id: int, data: Dict[str, Any], guild_id: int | str = None, is_public: bool = True
    ):
        """Standardized method to update user profile JSON with smart merging and atomic saving."""
        path = self._get_memory_path(user_id, guild_id, is_public=is_public)
        try:
            # Sanitize traits before merging
            if "traits" in data:
                data["traits"] = await self._sanitize_traits(data["traits"])

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
                    "status": "New",
                }

            # Selective Merge (keeping flat keys for compatibility)
            for k, v in data.items():
                if k == "traits":
                    current["traits"] = v
                    current["points"] = len(v)
                elif k == "layer3_recent_summaries":
                    # Smart Merge: Append and Keep Last 15 (Sliding Window)
                    old_list = current.get("layer3_recent_summaries", [])
                    if isinstance(old_list, list) and isinstance(v, list):
                        merged = old_list + v
                        current[k] = merged[-15:]  # Keep last 15
                    else:
                        current[k] = v  # Fallback if types mismatch
                else:
                    current[k] = v

            # Resolve Guild Info if missing
            if guild_id and not current.get("guild_id"):
                current["guild_id"] = str(guild_id)
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    current["guild_name"] = guild.name

            current["last_updated"] = datetime.now(pytz.utc).isoformat()

            # FIX: Force creation of Layer 1 Meta if missing to ensure Dashboard Timestamp updates
            if "layer1_session_meta" not in current or not isinstance(current["layer1_session_meta"], dict):
                current["layer1_session_meta"] = {}

            current["layer1_session_meta"]["updated"] = current["last_updated"]

            # Fallback legacy support (optional, keeping existing logic if needed)
            if "metadata" in current and isinstance(current["metadata"], dict):
                current["metadata"]["updated"] = current["last_updated"]

            # Resolve Name from Bot Cache if missing/Unknown
            if not current.get("name") or current.get("name") == "Unknown" or current.get("name").isdigit():
                user = self.bot.get_user(int(user_id))
                if user:
                    current["name"] = user.display_name
                elif data.get("name") and data["name"] != "Unknown":
                    current["name"] = data["name"]

            await self._save_user_profile_atomic(path, current)
        except Exception as e:
            logger.error(f"Failed to update profile for {user_id}: {e}")

    async def set_user_status(
        self, user_id: int, status: str, msg: str, guild_id: int | str = None, is_public: bool = True
    ):
        """Helper to quickly update user status for dashboard feedback."""
        payload = {
            "status": status,
            "status_msg": msg,
            "last_updated": datetime.now().isoformat(),
        }
        await self.update_user_profile(user_id, payload, guild_id, is_public)

    def _parse_analysis_json(self, text: str) -> Dict[str, Any]:
        """Robustly extract and parse JSON from LLM response."""
        if text is None:
            logger.error("Memory: LLM recovery failed (No response text)")
            return {}

        # 1. Clean Markdown
        cleaned_text = text.replace("```json", "").replace("```", "").strip()

        # 2. Extract JSON block (greedy outer braces)
        start = cleaned_text.find("{")
        end = cleaned_text.rfind("}")

        potential_json = cleaned_text
        if start != -1 and end != -1:
            potential_json = cleaned_text[start : end + 1]
        else:
            # Try Regex Fallback if braces not found via valid find
            import re

            match = re.search(r"\{[\s\S]*\}", cleaned_text)
            if match:
                potential_json = match.group(0)
            else:
                # If still no braces, blindly try the whole text (could be unwrapped)
                pass

        # 3. Parse with fallback repair
        if not potential_json.strip():
            logger.warning("Memory: JSON potential block is empty.")
            return {}

        try:
            return json.loads(potential_json, strict=False)
        except json.JSONDecodeError:
            try:
                # Try cleaning newlines/tabs
                return json.loads(potential_json.replace("\n", "").replace("\t", ""), strict=False)
            except Exception:
                pass

            logger.warning("Memory: JSONデコード失敗。修復を試みます...")
            repaired = robust_json_repair(potential_json)
            # Log the tail for debugging
            logger.debug(f"Truncated JSON Tail: {potential_json[-200:]}")
            try:
                return json.loads(repaired, strict=False)
            except Exception as e:
                logger.error(f"Memory: JSON final repair failed: {e}")
                return {}

    async def _analyze_batch(
        self,
        user_id: int,
        messages: list[Dict[str, Any]],
        guild_id: int | str = None,
        is_public: bool = True,
        max_output: int = 128000,
    ):
        """Analyze a batch of messages and update the user profile in the correct scope."""
        if not messages:
            return

        chat_log = "\n".join([f"[{m['timestamp']}] {m['content']}" for m in messages])

        # --- BUDGET-AWARE DEPTH SELECTION ---
        depth_mode = "Standard"
        extra_instructions = ""
        # FIX: Worker Mode (No ORACog) needs higher default than 1500 to avoid truncation of deep analysis.
        max_output = 16384

        ora_cog = self.bot.get_cog("ORACog")
        cost_manager = ora_cog.cost_manager if ora_cog else None

        if cost_manager:
            # We skip usage_ratio check for depth mode selection to honor user's request for "Extreme" always if possible,
            # but we keep the mode names for categorization.
            # However, to be safe, we default to the deepest mode within budget.
            depth_mode = "Extreme Deep Reflection"
            max_output = 16384  # Optimized for GPT-4o-mini (Cloud) and reliability
            extra_instructions = (
                "5. **Deep Psychological Profile**: 提供された会話から、ユーザーの潜在的な価値観、孤独感、承認欲求、または知的好奇心の傾向を深く洞察してください。\n"
                "6. **Relationship Analysis**: ORA（AI）や他者に対してどのような距離感を保とうとしているか分析してください。\n"
                "7. **Future Predictions**: このユーザーが次に興味を持ちそうなトピックや、陥りやすい感情的パターンを予測してください。\n"
                "Traitsは最低15個抽出してください。"
            )

            # Adjust down ONLY if we are literally about to hit the hard limit
            usage_ratio = cost_manager.get_usage_ratio("stable", "openai")
            if usage_ratio > 0.95:
                depth_mode = "Standard"
                max_output = 10000
                extra_instructions = "Cost Protection: Using standard depth."
            elif usage_ratio > 0.8:
                depth_mode = "Deep Analysis"
                max_output = 100000
                extra_instructions = "5. **Detailed Insight**: 会話の裏にある意図や感情を1段深く分析してください。Traitsは最低10個抽出してください。"

        prompt = [
            {
                "role": "developer",
                "content": (
                    f"You are a World-Class Psychologist AI implementing a '4-Layer Memory System'. Analysis Mode: {depth_mode}. Output MUST be in Japanese.\n"
                    "Layers (Strict Implementation):\n"
                    "1. **Layer 1 (Session Metadata)**: Ephemeral Environment Info (Device, Time, Mood, Activity). Context for *how* to answer (e.g., Mobile=Short, Late=Soft).\n"
                    "2. **Layer 2 (User Memory)**: Long-term Facts (The 'Axis'). Name, Goals, Prefs, Projects. Fixed facts that don't change often.\n"
                    "3. **Layer 3 (Recent Summary)**: 'Map of Interests'. A digest of recent chats (Title + Timestamp + User Snippet). continuity.\n"
                    "4. **Layer 4 (Current Session)**: Raw logs (Input).\n"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Analyze the chat logs for this user based on the 4-Layer Memory Architecture.\n"
                    f"Extract:\n"
                    f"1. **Layer 1 - Metadata**: 今回のセッションの環境的コンテキスト (e.g., 深夜, テンション高め, PC/Mobile推定, 活動内容)。\n"
                    f"2. **Layer 2 - Facts**: ユーザーの「ブレない軸」となる確定事実（名前, 職業, 継続中のプロジェクト, 価値観）。\n"
                    f"3. **Layer 3 - Digest**: 今回の会話の「タイトル＋タイムスタンプ＋ユーザー発言の要約」のリスト。\n"
                    f"4. **Interests/Impression**: 補足的な興味・印象データ。\n"
                    f"   - **Impression**: ユーザーを表す短い「一言」キャッチフレーズ（20文字以内・UI表示用）。\n"
                    f"   - **deep_analysis**: Item 5, 6, 7の内容（心理分析・人間関係・予測）をまとめた詳細テキスト。\n"
                    f"{extra_instructions}\n\n"
                    f"Chat Log:\n{chat_log}\n\n"
                    f"Output strictly in this JSON format (All values in Japanese):\n"
                    f"{{ \n"
                    f'  "layer1_session_meta": {{ "environment": "...", "mood": "...", "device_est": "..." }},\n'
                    f'  "layer2_user_memory": {{ "facts": ["..."], "traits": ["..."], "impression": "...", "interests": ["..."], "deep_analysis": "..." }},\n'
                    f'  "layer3_recent_summaries": [ {{ "title": "...", "timestamp": "...", "snippet": "..." }} ]\n'
                    f"}}\n"
                    f"IMPORTANT: Output ONLY the raw JSON. Do NOT use markdown code blocks (```json). Do not add any preamble."
                ),
            },
        ]

        # COST TRACKING PREP
        import secrets

        from src.utils.cost_manager import Usage

        est_usage = Usage(tokens_in=len(chat_log) // 4 + 500, tokens_out=max_output, usd=0.0)
        rid = secrets.token_hex(4)

        # [NEW] Atomic Check and Reserve BEFORE Execution
        if cost_manager:
            decision = cost_manager.can_call_and_reserve("optimization", "openai", user_id, rid, est_usage)
            if not decision.allowed:
                logger.warning(f"Memory: 最適化をスキップしました (ユーザー: {user_id}) - 理由: {decision.reason}")
                await self.set_user_status(user_id, "Pending", f"⛔ 制限超過: {decision.reason}", guild_id, is_public)
                return

        try:
            # 1. MARK AS PROCESSING (Visual Feedback)
            await self.set_user_status(user_id, "Processing", "Processing...", guild_id, is_public)

            response_text = ""
            actual_usage = None

            # 2. CALL LLM (Optimized Hierarchy)
            try:
                # Assuming _llm is UnifiedClient
                if hasattr(self._llm, "openai_client") or hasattr(self._llm, "google_client"):
                    # [REMOVED] Redundant reserve call here, now handled atomically above.
                    try:
                        # o1/gpt-5 ready (mapped internally)
                        # Explicitly pass None for temperature if needed, but client handles it now.
                        logger.info("Memory: 📡 Sending analysis request to OpenAI (Timeout: 600s)...")
                        start_t = time.time()
                        response_text, _, usage_dict = await asyncio.wait_for(
                            self._llm.chat("openai", prompt, temperature=None, max_tokens=max_output), timeout=600.0
                        )
                        logger.info(f"Memory: 📥 LLM Response received in {time.time() - start_t:.2f}s")
                    except asyncio.TimeoutError:
                        logger.error(f"Memory: LLM Analysis TIMED OUT for {user_id}")
                        raise Exception("Analysis Request Timed Out (3min)") from None

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
                raise Exception("JSON Extraction Failed") from None

            # 5. UPDATE PROFILE (Success)
            if data:
                # Flatten
                data["last_context"] = messages

                # Merge Layers
                l1_meta = data.get("layer1_session_meta", {})
                l2 = data.get("layer2_user_memory", {})
                l3_list = data.get("layer3_recent_summaries", [])

                # Try to resolve real name before saving
                user = self.bot.get_user(int(user_id))
                name = user.display_name if user else data.get("name", "Unknown")

                final_data = {
                    "name": name,
                    "traits": l2.get("traits", []),
                    "impression": l2.get("impression", "Analyzed"),
                    "layer1_session_meta": l1_meta,
                    "layer2_user_memory": l2,
                    "layer3_recent_summaries": l3_list,
                    "status": "Optimized",
                    "message_count": len(messages),
                }

                await self.update_user_profile(user_id, final_data, guild_id, is_public)
                logger.info(f"Memory: 分析完了: {name} ({user_id})")

                # USER REQUEST: Sync OpenAI Usage immediately after optimization
                if cost_manager:
                    try:
                        logger.info("Memory: 🔄 Triggering OpenAI Usage Sync (Post-Optimization)...")
                        # Assuming API key is in bot.config.openai_api_key, but we need to access it.
                        # memory.py doesn't have direct access to bot.config easily unless self.bot has it.
                        # self.bot is passed in __init__.
                        api_key = getattr(self.bot.config, "openai_api_key", None)
                        if api_key:
                            # Fix: specific session for sync to avoid missing session/AttributeError
                            async with aiohttp.ClientSession() as session:
                                await cost_manager.sync_openai_usage(session, api_key, update_local=True)
                    except Exception as sx:
                        logger.warning(f"Memory: Post-optimization sync failed: {sx}")

        except Exception as e:
            logger.error(f"Memory: 分析失敗 ({user_id}): {e}")
            await self.set_user_status(user_id, "Error", "分析失敗", guild_id, is_public)

    async def _analyze_wrapper(self, user_id: int, messages: list, guild_id: int | str = None, is_public: bool = True):
        """Wrapper to run analysis with concurrency limit and scope."""
        async with self.sem:
            await self._analyze_batch(user_id, messages, guild_id, is_public)

    async def _persist_message(
        self, user_id: int, entry: Dict[str, Any], guild_id: Optional[int], is_public: bool = True
    ):
        """Append a message to the user's on-disk history for robust optimization."""
        path = self._get_memory_path(user_id, guild_id, is_public=is_public)
        try:
            profile = await self.get_user_profile(user_id, guild_id, current_channel_id=None)  # get raw public/private
            # Wait, get_user_profile currently merges. I need a clean way to get just one layer.
            # Let's use _read_profile_retry directly.
            profile = await self._read_profile_retry(path)

            if not profile:
                import time

                profile = {
                    "discord_user_id": str(user_id),
                    "created_at": time.time(),
                    "status": "New",
                    "raw_history": [],
                }

            if "raw_history" not in profile:
                profile["raw_history"] = []

            profile["raw_history"].append(entry)

            # Keep last 100 messages for analysis
            if len(profile["raw_history"]) > 100:
                profile["raw_history"] = profile["raw_history"][-100:]

            await self._save_user_profile_atomic(path, profile)

            # [Sync] ORA Core API Injection
            if hasattr(self.bot, "connection_manager") and self.bot.connection_manager.mode == "API":
                try:
                    now_ts = int(time.time())
                    if self._is_core_sync_paused(now_ts):
                        if (now_ts - int(self._core_sync_last_warn_ts or 0)) >= 30:
                            self._core_sync_last_warn_ts = now_ts
                            logger.warning(
                                "Memory Sync paused (auth backoff). retry_after_sec=%s",
                                max(0, int(self._core_sync_backoff_until_ts - now_ts)),
                            )
                        return

                    payload = [{
                        "user_id": str(user_id), # Internal User ID (Discord ID maps to ID)
                        "role": "user" if "Assistant" not in entry.get("content", "") else "assistant", # Heuristic based on content label from add_ai_message
                        "content": entry["content"].replace("[Assistant]: ", "") if entry["content"].startswith("[Assistant]: ") else entry["content"],
                        "timestamp": entry["timestamp"],
                        "provider": "discord",
                        "provider_id": str(user_id)
                    }]

                    # We need a proper HTTP client. bot.session is shared.
                    # API URL: bot.config.ora_api_base_url + /v1/memory/history
                    api_url = f"{self.bot.config.ora_api_base_url}/v1/memory/history"

                    async with self.bot.session.post(api_url, json=payload) as resp:
                        if 200 <= int(resp.status) < 300:
                            self._mark_core_sync_success()
                        elif int(resp.status) in {401, 403}:
                            self._mark_core_sync_auth_failure(status_code=int(resp.status))
                            logger.warning(
                                "Memory Sync auth rejected (status=%s, streak=%s, paused=%s)",
                                int(resp.status),
                                int(self._core_sync_auth_fail_streak),
                                bool(self._is_core_sync_paused()),
                            )
                        else:
                            self._core_sync_reason_code = "core_memory_sync_http_error"
                            logger.warning(f"Memory Sync Failed ({resp.status}): {await resp.text()}")
                            # Ideally, connection_manager should know about failure, but we just log for now
                except Exception as ex:
                    self._core_sync_reason_code = "core_memory_sync_transport_error"
                    logger.debug(f"Memory Sync Error: {ex}")

        except Exception as e:
            logger.error(f"Failed to persist message for {user_id}: {e}")

    def _is_core_sync_paused(self, now_ts: int | None = None) -> bool:
        now = int(now_ts if now_ts is not None else time.time())
        return bool(int(self._core_sync_backoff_until_ts or 0) > now)

    def _mark_core_sync_success(self) -> None:
        self._core_sync_auth_fail_streak = 0
        self._core_sync_backoff_until_ts = 0
        self._core_sync_reason_code = None

    def _mark_core_sync_auth_failure(self, status_code: int) -> None:
        now_ts = int(time.time())
        self._core_sync_auth_fail_streak = int(self._core_sync_auth_fail_streak) + 1
        self._core_sync_reason_code = "core_memory_sync_auth_rejected"
        self._core_sync_last_warn_ts = now_ts
        if int(self._core_sync_auth_fail_streak) >= int(self._core_sync_auth_fail_threshold):
            self._core_sync_backoff_until_ts = now_ts + int(self._core_sync_backoff_sec)
            self._core_sync_reason_code = "core_memory_sync_auth_backoff"
            logger.warning(
                "Memory Sync entering auth backoff (status=%s, streak=%s, backoff_until_ts=%s)",
                int(status_code),
                int(self._core_sync_auth_fail_streak),
                int(self._core_sync_backoff_until_ts),
            )

    def get_core_memory_sync_status(self) -> Dict[str, Any]:
        now_ts = int(time.time())
        paused = self._is_core_sync_paused(now_ts)
        backoff_until = int(self._core_sync_backoff_until_ts or 0)
        status: Dict[str, Any] = {
            "available": True,
            "ok": (not paused),
            "paused": paused,
            "auth_fail_streak": int(self._core_sync_auth_fail_streak or 0),
            "auth_fail_threshold": int(self._core_sync_auth_fail_threshold or 0),
            "backoff_until_ts": (backoff_until if backoff_until > 0 else None),
            "backoff_remaining_sec": max(0, backoff_until - now_ts) if backoff_until > 0 else 0,
            "last_warn_ts": int(self._core_sync_last_warn_ts or 0) or None,
        }
        if self._core_sync_reason_code:
            status["reason_code"] = str(self._core_sync_reason_code)
        return status

    @tasks.loop(minutes=1)
    async def memory_worker(self):
        """Analyze buffered messages per user/guild/visibility periodically."""
        if not self.message_buffer:
            return

        # 1. Check System Load
        try:
            if psutil.cpu_percent() > 85:
                return
        except Exception:
            pass

        # 2. Process Buffered Messages
        current_buffer = self.message_buffer.copy()
        self.message_buffer.clear()

        for uid, all_msgs in current_buffer.items():
            try:
                if not all_msgs:
                    continue

                # Group messages by guild to respect partitioning
                by_guild = {}
                for m in all_msgs:
                    if not m or not isinstance(m, dict):
                        continue
                    gid = m.get("guild_id")
                    if gid not in by_guild:
                        by_guild[gid] = []
                    by_guild[gid].append(m)

                # Clear buffer for this user
                self.message_buffer[uid] = []

                for gid, g_msgs in by_guild.items():
                    # Check status per (user, guild)
                    profile = await self.get_user_profile(uid, gid)
                    if not profile:
                        status = "New"
                    else:
                        status = profile.get("status", "New")
                        profile.get("traits", [])

                    if status == "New" or len(g_msgs) >= 5:
                        logger.info(f"メモリ: {uid} (サーバー {gid}) の分析をキューに追加しました ({len(g_msgs)}件)")

                        # Set Pending Status (Queued)
                        current_profile = await self.get_user_profile(uid, gid)
                        if not current_profile:
                            current_profile = {}  # Should actally exist by now or be handled
                        current_profile["status"] = "Pending"
                        await self.update_user_profile(uid, current_profile, gid)

                        asyncio.create_task(
                            self._analyze_wrapper(uid, g_msgs, gid, is_public=True)
                        )  # Default to public in worker for now
                    else:
                        # Not enough yet, put back in buffer?
                        # Actually, if we clear it, we lose them.
                        # Better to put back ONLY what we didn't process.
                        if uid not in self.message_buffer:
                            self.message_buffer[uid] = []
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
                        collected_msgs.append(
                            {
                                "id": 0,
                                "content": m["content"],
                                "timestamp": m["timestamp"],
                                "channel": "LocalLog",
                                "guild": guild.name,
                                "is_public": True,  # Assume public for manual force unless we track it
                            }
                        )
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
                profile["status"] = "New"  # Or whatever it was? Default to New.
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

    async def _find_user_history_targeted(
        self, user_id: int, guild_id: int, scan_depth: int = 500, allow_api: bool = False
    ) -> list:
        """Find messages for a specific user. API scan is optional to prevent rate limits."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return []
        collected = []

        # 1. Try Local Logs (Optimization)
        try:
            from ..utils.log_reader import LocalLogReader

            reader = LocalLogReader()
            local_msgs = reader.get_recent_messages(guild_id, limit=50, user_id=user_id, is_public=None)
            if local_msgs:
                logger.info(f"TargetedHistory: Found {len(local_msgs)} in Local Logs for {user_id}. Using them.")
                for m in local_msgs:
                    collected.append(
                        {
                            "id": 0,
                            "content": m["content"],
                            "timestamp": m["timestamp"],
                            "channel": "LocalLog",
                            "guild": guild.name,
                            "guild_id": guild_id,
                        }
                    )
                if len(collected) >= 10:  # Lower threshold to 10 for startup
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
        destinations: List[Any] = []

        # Text Channels
        destinations.extend([c for c in guild.text_channels if c.permissions_for(guild.me).read_messages])

        # Threads (Active)
        destinations.extend([t for t in guild.threads if t.permissions_for(guild.me).read_messages])  # type: ignore

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

                    if not batch:
                        break  # End of channel history

                    # Process batch
                    for m in batch:
                        if m.author.id == user_id and not m.author.bot:
                            collected.append(
                                {
                                    "id": m.id,
                                    "content": m.content,
                                    "timestamp": m.created_at.isoformat(),
                                    "channel": channel.name,
                                    "guild": guild.name,
                                    "guild_id": guild_id,
                                }
                            )

                    cursor = batch[-1]  # Set cursor to oldest msg in batch
                    msgs_checked += len(batch)

                    if len(collected) >= 50:
                        break  # Found enough total

                    # Throttle between pages (User's "徐々に" strategy)
                    await asyncio.sleep(1.5)

            except Exception:
                continue
            if len(collected) >= 50:
                break

        logger.info(f"TargetedHistory: Fallback found {len(collected)} messages for {user_id}.")
        return collected

    @tasks.loop(minutes=60)
    async def scan_history_task(self):
        """Periodic Catch-up: Automatically optimizes ONLINE users who are 'New'."""
        await self.bot.wait_until_ready()
        # Initial wait to let bot settle if it's the first run
        if self.scan_history_task.current_loop == 0:
            logger.debug("AutoScan: Waiting 10s before initial optimization scan...")
            await asyncio.sleep(10)

        count = 0
        logger.debug("AutoScan: Searching for online 'New' users to optimize...")

        for guild in self.bot.guilds:
            if not await self._should_process_guild(guild.id):
                continue

            # 1. Identify all targets first
            target_members = []
            for member in guild.members:
                if member.bot:
                    continue
                # Quick status check (cache-friendly)
                profile = await self.get_user_profile(member.id, guild.id)
                status = profile.get("status", "New") if profile else "New"

                is_target = False
                if status == "Error":
                    # Self-heal: retry failed users after cooldown instead of skipping forever.
                    retry_after_sec = 30 * 60
                    should_retry = False
                    last_upd_raw = profile.get("last_updated") if profile else None
                    if not last_upd_raw:
                        should_retry = True
                    else:
                        try:
                            dt = datetime.fromisoformat(str(last_upd_raw).replace("Z", "+00:00"))
                            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
                            should_retry = (now - dt).total_seconds() >= retry_after_sec
                        except Exception:
                            should_retry = True

                    if should_retry:
                        logger.info(f"AutoScan: Re-queueing Error user {member.display_name} ({member.id})")
                        is_target = True
                    else:
                        logger.debug(f"AutoScan: Skipped Error user {member.display_name} ({member.id})")
                        is_target = False
                elif status == "Processing":
                     logger.debug(f"AutoScan: Skipped Processing user {member.display_name} ({member.id})")
                     is_target = False
                elif status == "New":
                    is_target = True
                elif status == "Optimized":
                    # Backlog check: Re-optimize if older than 7 days
                    last_upd = profile.get("last_updated")
                    if last_upd:
                        try:
                            # Handle ISO format
                            dt = datetime.fromisoformat(last_upd)
                            # Naive check (assuming UTC or Local consistent)
                            # If no timezone, assume local/naive.
                            if dt.tzinfo:
                                now = datetime.now(dt.tzinfo)
                            else:
                                now = datetime.now()

                            if (now - dt).days >= 7:
                                is_target = True
                                logger.debug(f"AutoScan: {member.display_name} is stale ({last_upd}). Re-queueing.")
                        except Exception:
                            is_target = True  # Bad date, re-scan

                if is_target:
                    target_members.append(member)

            if not target_members:
                continue

            # Limit to 5 users per cycle to prevent Token Explosion
            MAX_AUTO_SCAN_PER_CYCLE = 5
            if len(target_members) > MAX_AUTO_SCAN_PER_CYCLE:
                logger.info(
                    f"AutoScan: Limiting targets to {MAX_AUTO_SCAN_PER_CYCLE}/{len(target_members)} to conserve budget."
                )
                target_members = target_members[:MAX_AUTO_SCAN_PER_CYCLE]

            logger.debug(f"AutoScan: Found {len(target_members)} targets in {guild.name}. Starting BATCH scan...")

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
            scan_depth = 1000  # Deep scan for batch

            for channel in destinations:
                if not remaining_targets:
                    break  # All users satisfied

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
                                logger.warning(
                                    "AutoScan: Hit Rate Limit (429). Sleeping 60s and aborting channel scan."
                                )
                                await asyncio.sleep(60)
                                break
                            else:
                                raise e

                        if not batch:
                            break

                        # Process batch against ALL remaining targets
                        for m in batch:
                            if m.author.id in remaining_targets:
                                user_buffers[m.author.id].append(
                                    {
                                        "id": m.id,
                                        "content": m.content,
                                        "timestamp": m.created_at.isoformat(),
                                        "channel": channel.name,
                                        "guild": guild.name,
                                        "guild_id": guild.id,
                                    }
                                )
                                # If user has enough, remove from targets
                                if len(user_buffers[m.author.id]) >= 50:
                                    remaining_targets.discard(m.author.id)

                        cursor = batch[-1]
                        msgs_checked += len(batch)

                        if not remaining_targets:
                            break

                        # "Gradually" - Slow pacing to avoid 429
                        await asyncio.sleep(2.0)

                except Exception as e:
                    logger.debug(f"AutoScan: Channel {channel.name} skipped: {e}")
                    continue

            # 3. Dispatch Analysis for all collected data
            for member in target_members:
                history = user_buffers[member.id]
                if history:
                    logger.debug(
                        f"AutoScan: Batch collected {len(history)} msgs for {member.display_name}. Queueing..."
                    )
                    # Force update status
                    profile = await self.get_user_profile(member.id, guild.id) or {}
                    profile["status"] = "Pending"
                    profile["name"] = member.display_name
                    await self.update_user_profile(member.id, profile, guild.id)

                    asyncio.create_task(self._analyze_wrapper(member.id, history, guild.id))
                    count += 1
                    # Full Speed Mode (User Requested)
                    # Semaphore will control concurrency
                    await asyncio.sleep(0.1)
                else:
                    logger.debug(f"AutoScan: {member.display_name} - No history found. Marking as Optimized (Empty).")
                    # FIX: Update profile to prevent infinite loop
                    profile = await self.get_user_profile(member.id, guild.id) or {}
                    profile["status"] = "Optimized"
                    profile["impression"] = "No recent activity found during scan."
                    profile["name"] = member.display_name
                    # Initialize empty structure if missing
                    if "layer2_user_memory" not in profile:
                        profile["layer2_user_memory"] = {
                            "facts": [],
                            "traits": [],
                            "impression": "No activity.",
                            "interests": [],
                        }

                    await self.update_user_profile(member.id, profile, guild.id)

            await asyncio.sleep(1.0)  # Yield between guilds

        logger.debug(f"AutoScan: Complete. Queued {count} users for auto-optimization.")

    @tasks.loop(hours=24)
    async def name_sweeper(self):
        """Proactively resolve 'Unknown' or ID-based names for all local profiles."""
        await self.bot.wait_until_ready()
        logger.info("Memory: Starting Name Sweeper task...")

        if not os.path.exists(MEMORY_DIR):
            return

        for filename in os.listdir(MEMORY_DIR):
            if not filename.endswith(".json"):
                continue

            uid_str = filename.replace(".json", "")
            if not uid_str.isdigit():
                continue

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

            await asyncio.sleep(2)  # Avoid aggressive rate limiting

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
                await interaction.followup.send(
                    f"✅ **{target.display_name}** の履歴を{len(history)}件発見しました。分析を開始します。\n(ダッシュボードで進捗を確認できます)"
                )
            else:
                # 4. Failed
                await self.set_user_status(target.id, "New", "履歴が見つかりませんでした", guild_id)
                await interaction.followup.send(
                    f"⚠️ **{target.display_name}** の履歴が見つかりませんでした。\n(直近300件の会話またはログに存在しません)",
                    ephemeral=True,
                )

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
                    async with aiofiles.open(old_path, "r", encoding="utf-8") as f:
                        data = json.loads(await f.read())

                    gid_str = data.get("guild_id")
                    if gid_str:
                        # MIGRATE: Rename to {uid}_{gid}.json
                        new_filename = f"{uid}_{gid_str}.json"
                        new_path = os.path.join(MEMORY_DIR, new_filename)
                        if not os.path.exists(new_path):  # Don't overwrite if exists
                            os.rename(old_path, new_path)
                            logger.info(f"Migrated {filename} -> {new_filename}")
                            filename = new_filename  # Update for loop
                        else:
                            # If new path exists (duplicate?), maybe delete old or merge?
                            # For safety, keep old, but we will process new.
                            pass
                except Exception as e:
                    logger.error(f"Migration failed for {filename}: {e}")

            # Re-parse ID after potential rename
            # E.g. "123_456.json"
            base_name = filename.replace(".json", "")
            parts = base_name.split("_")

            if len(parts) == 1 and parts[0].isdigit():
                # Legacy/DM file
                uid = int(parts[0])
                guild = None  # Treating as global/DM
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
                            d["impression"] = None  # Clear stuck impression

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
            if member.bot:
                continue

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
                    profile: Dict[str, Any] = {
                        "status": "Pending",
                        "name": member.display_name,
                        "guild_id": str(guild.id),
                        "guild_name": guild.name,
                        "traits": [],
                        "impression": "Recovering history...",
                        "last_updated": datetime.now().isoformat(),
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
                        "layer2_user_memory": {
                            "facts": [],
                            "traits": [],
                            "impression": "No activity detected.",
                            "interests": [],
                        },
                        "impression": "No detected activity.",
                        "last_updated": datetime.now().isoformat(),
                    }
                    await self.update_user_profile(uid, profile, guild.id)

                processed_ghosts += 1

                # Dynamic Throttling: only sleep heavily if we actually queued an API/LLM task
                if history:
                    await asyncio.sleep(1.0)  # Throttle for Discord API History & LLM safety
                else:
                    await asyncio.sleep(0.1)  # Fast-track empty profiles

        duration = time.time() - start_time
        return f"✅ Analyzed {count} existing files. Backfilled {processed_ghosts} ghost users in {duration:.2f}s."

    @tasks.loop(seconds=5)
    async def refresh_watcher(self):
        """Watch for trigger file to refresh profiles & Process Optimize Queue."""
        # 1. Trigger File (Manual Refresh)
        trigger_path = "refresh_profiles.trigger"
        if os.path.exists(trigger_path):
            logger.info("Memory: Trigger file detected! Refreshing profiles...")
            try:
                os.remove(trigger_path)
                result = await self._perform_profile_refresh()
                logger.info(f"Memory: Refresh caused by trigger complete: {result}")
            except Exception as e:
                logger.error(f"Memory: Failed to handle refresh trigger: {e}")

        # 2. Cooperative Optimize Queue (Smart Claim + Locking)
        queue_path = r"L:\ORA_State\optimize_queue.json"
        if not os.path.exists(queue_path):
            return

        lock_path = queue_path + ".lock"

        # Simple File Lock Mechanism (Cross-Process)
        # Try to acquire lock by creating a file
        acquired = False
        try:
            # Try to create lock file (Excl mode)
            # Retries
            for _ in range(3):
                try:
                    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                    acquired = True
                    break
                except FileExistsError:
                    # Lock exists, wait a bit
                    await asyncio.sleep(0.2)

            if not acquired:
                # Could not acquire lock, skip this cycle
                return

            # --- CRITICAL SECTION ---
            try:
                # 1. Read
                async with aiofiles.open(queue_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    all_requests = json.loads(content) if content.strip() else []

                if not all_requests:
                    return

                # 2. Filter: Only claim jobs for guilds I can see
                my_jobs = []
                remaining_jobs = []

                for req in all_requests:
                    gid = req.get("guild_id")
                    if gid and self.bot.get_guild(int(gid)):
                        my_jobs.append(req)
                    else:
                        remaining_jobs.append(req)

                # 3. Write Back (Atomic-ish due to lock)
                if my_jobs:
                    async with aiofiles.open(queue_path, "w", encoding="utf-8") as f:
                        await f.write(json.dumps(remaining_jobs))

                    logger.info(f"Memory: {len(my_jobs)}件の最適化ジョブを開始します... (残り: {len(remaining_jobs)})")

                    # 4. Process
                    for req in my_jobs:
                        uid = req.get("user_id")
                        gid = req.get("guild_id")
                        if uid:
                            asyncio.create_task(self.force_user_optimization(uid, gid))
                            await asyncio.sleep(0.1)  # Faster processing

            except Exception as e:
                logger.error(f"Memory: Queue processing error inside lock: {e}")

            finally:
                # --- RELEASE LOCK ---
                if os.path.exists(lock_path):
                    os.remove(lock_path)

        except Exception as e:
            logger.error(f"Memory: Queue lock error: {e}")

    @tasks.loop(minutes=5)
    async def idle_log_archiver(self):
        """Worker Only: Slowly archives chat history (Forward & Backward) when idle."""
        if not self.worker_mode:
            return

        await self.bot.wait_until_ready()
        logger.info("IdleArchiver: Checking for channels to archive...")

        state_path = r"L:\ORA_State\archive_status.json"
        try:
            if os.path.exists(state_path):
                async with aiofiles.open(state_path, "r") as f:
                    state = json.loads(await f.read())
            else:
                state = {}
        except Exception:
            state = {}

        for guild in self.bot.guilds:
            if not await self._should_process_guild(guild.id):
                continue
            for channel in guild.text_channels:
                try:
                    if not channel.permissions_for(guild.me).read_messages:
                        continue

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
                        if not ch_state["oldest"]:
                            ch_state["oldest"] = msgs[0].id
                        await self._save_archived_msgs(guild.id, channel.id, msgs, is_public)

                    # 2. BACKWARD SCAN (Full history backfill)
                    first_id = ch_state.get("oldest")
                    if first_id:
                        back_msgs = []
                        async for m in channel.history(limit=50, before=discord.Object(id=first_id)):
                            back_msgs.append(m)

                        if back_msgs:
                            ch_state["oldest"] = back_msgs[-1].id  # oldest_first=False by default for 'before'
                            await self._save_archived_msgs(guild.id, channel.id, back_msgs, is_public)
                            logger.info(f"IdleArchiver: Backfilled {len(back_msgs)} msgs from #{channel.name}")

                    state[str(channel.id)] = ch_state

                    # Update State
                    async with aiofiles.open(state_path, "w") as f:
                        await f.write(json.dumps(state))

                    await asyncio.sleep(2)  # Throttle per channel

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
                pass  # Already running

    @status_loop.before_loop
    async def before_status_loop(self):
        await self.bot.wait_until_ready()

    @memory_worker.before_loop
    async def before_worker(self):
        await self.bot.wait_until_ready()

    async def _analyze_channel_wrapper(self, channel_id: int, messages: list):
        """Wrapper to handle channel analysis in background."""
        try:
            # Basic Concurrency Control
            async with self.sem:
                await self.analyze_channel(channel_id, messages)
        except Exception as e:
            logger.error(f"Channel Analysis Wrapper Failed: {e}")

    async def analyze_channel(self, channel_id: int, messages: list[Dict[str, Any]]):
        """Analyze channel messages and update channel summary."""
        if not messages:
            return

        # Prepare Log
        chat_log = "\n".join([f"[{m['timestamp']}] {m['author']}: {m['content']}" for m in messages])

        prompt = [
            {
                "role": "developer",
                "content": (
                    "You are an AI Observer summarizing a Discord Channel's context. Output MUST be in Japanese.\n"
                    "Goal: Update the persistent memory of this channel.\n"
                    "Output JSON format:\n"
                    "{\n"
                    '  "summary": "Current conversation summary (2-3 sentences).",\n'
                    '  "topics": ["topic1", "topic2"],\n'
                    '  "atmosphere": "chill/heated/technical/gaming etc."\n'
                    "}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Analyze these recent messages from the channel:\n{chat_log}\n\nUpdate the channel context."
                ),
            },
        ]

        try:
            # Reuse LLM Client
            if hasattr(self._llm, "chat"):
                response_text, _, _ = await self._llm.chat("openai", prompt, max_tokens=1000)

                data = self._parse_analysis_json(response_text)
                if data:
                    # Merge with existing
                    await self._update_channel_memory(channel_id, data)
                    logger.info(f"Memory: Updated Channel Memory for {channel_id}")

        except Exception as e:
            logger.error(f"Channel Analysis Failed for {channel_id}: {e}")

    async def _update_channel_memory(self, channel_id: int, new_data: dict):
        """Update channel JSON with new analysis data."""
        path = self._get_channel_memory_path(channel_id)

        try:
            current = {}
            if os.path.exists(path):
                async with SimpleFileLock(path):
                    async with aiofiles.open(path, "r", encoding="utf-8") as f:
                        try:
                            content = await f.read()
                            if content:
                                current = json.loads(content)
                        except Exception:
                            pass

            # Merge Logic
            # 1. Update/Overwrite Summary & Atmosphere (Context evolves)
            if "summary" in new_data:
                current["summary"] = new_data["summary"]
            if "atmosphere" in new_data:
                current["atmosphere"] = new_data["atmosphere"]

            # 2. Merge Topics (Keep last 10)
            if "topics" in new_data and isinstance(new_data["topics"], list):
                old_topics = current.get("topics", [])
                # Add new ones at the end, remove duplicates, keep order
                for t in new_data["topics"]:
                    if t not in old_topics:
                        old_topics.append(t)
                current["topics"] = old_topics[-10:]

            current["last_updated"] = datetime.now().isoformat()

            # Save
            await self._save_user_profile_atomic(path, current)

        except Exception as e:
            logger.error(f"Failed to save channel memory {channel_id}: {e}")


    # --------------------------------------------------------------------------
    # OpenClaw-style "Digital Immortality" & "Journaling" (Moltbook Features)
    # --------------------------------------------------------------------------

    # [RESTORED & ENHANCED] Hybrid Git Backup (Local + Cloud)
    # ⚠️ WARNING: USER MUST ENSURE REPO IS PRIVATE ⚠️
    async def backup_brain_to_git(self):
        """
        [Hybrid Backup] Pushes memory/ to Git Remotes.
        Priority:
        1. 'local_backup' (C:\... Bare Repo) - Always attempted if configured.
        2. 'origin' (GitHub/Cloud) - Only if ENABLE_PRIVATE_BACKUP=true.
        """
        import os
        import subprocess

        try:
            repo_path = os.getcwd() # Assuming bot root is repo root

            # Simple check: Is .git present?
            if not os.path.exists(os.path.join(repo_path, ".git")):
                logger.warning("Memory: 💾 Backup Skipped: Not a Git repository.")
                return

            # Defines
            has_local_remote = False
            has_origin_remote = False

            # Check Remotes
            try:
                result = subprocess.run(["git", "remote"], cwd=repo_path, capture_output=True, text=True)
                remotes = result.stdout.splitlines()
                has_local_remote = "local_backup" in remotes
                has_origin_remote = "origin" in remotes
            except Exception:
                pass

            # 1. STAGE & COMMIT (Common)
            # We want to commit changes so they can be pushed anywhere.
            # Only commit if there are changes.
            status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_path, capture_output=True, text=True)
            if status.stdout.strip():
                logger.info("Memory: 💾 Committing recent changes for backup...")
                subprocess.run(["git", "add", "data/memory/"], cwd=repo_path, capture_output=True)
                # Should we add all? Maybe just memory.
                # User asked for "Backup", implying safety. Let's stick to memory folder to avoid committing code changes/logs accidentally?
                # Actually, `git add .` might be risky if user is dev-ing.
                # Let's target data directory specifically: `data/`
                subprocess.run(["git", "add", "data/"], cwd=repo_path, capture_output=True)

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                commit_msg = f"Auto-Backup: {timestamp}"
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, capture_output=True)
            else:
                pass # Nothing to commit, but might need to push if previous push failed.

            # 2. PUSH TO LOCAL (Priority)
            if has_local_remote:
                logger.info("Memory: 💾 Pushing to LOCAL backup (C: Drive)...")
                proc = subprocess.run(["git", "push", "local_backup", "main"], cwd=repo_path, capture_output=True, text=True)
                if proc.returncode == 0:
                    logger.info("Memory: ✅ Local Backup Complete.")
                else:
                    logger.error(f"Memory: ❌ Local Backup Failed: {proc.stderr}")

            # 3. PUSH TO CLOUD (Optional)
            if has_origin_remote and os.getenv("ENABLE_PRIVATE_BACKUP", "false").lower() == "true":
                logger.info("Memory: ☁️ Pushing to CLOUD backup (GitHub/Origin)...")
                proc = subprocess.run(["git", "push", "origin", "main"], cwd=repo_path, capture_output=True, text=True)
                if proc.returncode == 0:
                    logger.info("Memory: ✅ Cloud Backup Complete.")
                else:
                    logger.warning(f"Memory: ⚠️ Cloud Backup Failed (Auth/Net?): {proc.stderr}")

        except Exception as e:
            logger.error(f"Memory: Backup Process Failed: {e}")


    async def process_daily_compaction(self):
        """
        [OpenClaw Port] 'Memory Flush' Protocol.
        Summarize previous day's logs into 'journal.md' using OpenClaw's exact strategy.
        """
        logger.info("Memory: 🦞 Starting OpenClaw-style Memory Flush...")
        if not os.path.exists(USER_MEMORY_DIR):
            return

        count = 0
        now = datetime.now(pytz.utc)
        yesterday = now - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")

        for f in os.listdir(USER_MEMORY_DIR):
            if not f.endswith(".json") or "_private" in f:
                continue

            user_id = f.replace(".json", "")
            if not user_id.isdigit():
                continue

            try:
                # Read raw memory
                path = os.path.join(USER_MEMORY_DIR, f)
                async with aiofiles.open(path, "r", encoding="utf-8") as f_obj:
                    data = json.loads(await f_obj.read())

                raw_history = data.get("raw_history", [])
                if not raw_history:
                    continue

                # Filter for yesterday
                target_msgs = []
                for m in raw_history:
                    # Check timestamp (ISO format)
                    ts = m.get("timestamp", "")
                    if ts.startswith(yesterday_str):
                        target_msgs.append(f"{m.get('role', 'User')}: {m.get('content', '')}")

                if not target_msgs:
                    continue

                # [OpenClaw Mechanism]
                summary = await self._generate_journal_summary(user_id, target_msgs, yesterday_str)

                # Check for [SILENT] token from OpenClaw protocol
                if summary and "[SILENT]" not in summary:
                    # Append to Journal
                    # OpenClaw says "use memory/YYYY-MM-DD.md".
                    # We create a per-user journal to avoid conflicts in a multi-user bot.
                    journal_filename = f"{user_id}_journal.md"
                    journal_path = os.path.join(USER_MEMORY_DIR, journal_filename)

                    mode = "a" if os.path.exists(journal_path) else "w"
                    async with aiofiles.open(journal_path, mode, encoding="utf-8") as j_file:
                        await j_file.write(f"\n## {yesterday_str}\n{summary}\n")
                    count += 1
                    logger.debug(f"Memory: Flushed {user_id} to {journal_filename}")

            except Exception as e:
                logger.warning(f"Memory Flush failed for {user_id}: {e}")

        logger.info(f"Memory: Flush Complete. Processed {count} users.")

    async def _generate_journal_summary(self, user_id: str, messages: list[str], date_str: str) -> str:
        """Helper to summarize messages via LLM using OpenClaw prompts."""
        if not self._llm:
            return ""

        # OpenClaw-style "Memory Flush" Prompt
        # Source: src/auto-reply/reply/memory-flush.ts
        SILENT_REPLY_TOKEN = "[SILENT]"

        system_prompt = (
            "Pre-compaction memory flush turn.\n"
            "The session is near auto-compaction; capture durable memories to disk.\n"
            f"You may reply, but usually {SILENT_REPLY_TOKEN} is correct."
        )

        user_prompt = (
            f"Chat Log ({date_str}):\n" + "\n".join(messages[-100:]) + "\n\n"
            "Pre-compaction memory flush.\n"
            f"Store durable memories now (use memory/{date_str}.md).\n"
            f"If nothing to store, reply with {SILENT_REPLY_TOKEN}."
        )

        try:
            prompt = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            return await self._llm.chat("openai", prompt, max_tokens=300)
        except Exception:
             return ""



async def setup(bot: commands.Bot):
    # Try getting UnifiedClient first, then fallback to llm_client
    llm = getattr(bot, "unified_client", None) or getattr(bot, "llm_client", None)
    if not llm:
        logger.warning("MemoryCog: LLM Client not found on bot. Analysis disabled.")

    cog = MemoryCog(bot, llm)
    await bot.add_cog(cog)
    # Start the retroactive scan task
    bot.loop.create_task(cog.scan_history_task())
