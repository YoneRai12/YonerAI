
import asyncio
import logging
import random
from datetime import datetime, timedelta

import pytz
import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

class ProactiveCog(commands.Cog):
    """
    [Clawdbot Feature] Proactive Agent (Autonomous Mode)
    Initiates conversations based on schedule, inactivity, or internal 'thought' loop.
    """
    def __init__(self, bot):
        self.bot = bot
        self.last_action_time = datetime.now(pytz.utc)
        self.min_interval_hours = 1  # Minimum time between autonomous actions
        
        # Start loops
        self.daily_briefing_task.start()
        self.autonomy_loop.start()
        
        logger.info("ProactiveCog Initialized (Autonomous Mode Active)")

    def cog_unload(self):
        self.daily_briefing_task.cancel()
        self.autonomy_loop.cancel()

    # --- 1. Daily Briefing (Scheduled) ---
    # --- 1. Daily Briefing (Scheduled) ---
    @tasks.loop(minutes=1)
    async def daily_briefing_task(self):
        """Sends daily briefing at 08:00 AM JST."""
        now = datetime.now(pytz.timezone("Asia/Tokyo"))
        if now.hour == 8 and now.minute == 0:
            await self._run_briefing()
            
            # [OpenClaw] Daily Journaling
            memory_cog = self.bot.get_cog("MemoryCog")
            if memory_cog:
                # Run in background to not block briefing
                # [Private Backup] Also sync to Git if enabled
                async def daily_memory_routine():
                    await memory_cog.process_daily_compaction()
                    if hasattr(memory_cog, "backup_brain_to_git"):
                        await memory_cog.backup_brain_to_git()
                    elif hasattr(memory_cog, "backup_brain_to_github"):
                        await memory_cog.backup_brain_to_github() # Fallback

                asyncio.create_task(daily_memory_routine())
            
            await asyncio.sleep(61)

    async def _run_briefing(self):
        logger.info("⏰ Triggering Daily Briefing...")
        # ... (Existing briefing logic) ...
        target_channel_id = 1386994311400521768
        channel = self.bot.get_channel(target_channel_id)
        if not channel:
            return

        try:
            # Context
            news_context = ""
            if hasattr(self.bot, "search_client") and self.bot.search_client:
                results = await self.bot.search_client.search("latest technology news x.com twitter.com -R18 -nsfw", safe_search=True)
                if results:
                    links = [f"- {r['title']}: {r['link']}" for r in results[:3]]
                    news_context = "\n".join(links)
            
            # Generation
            if hasattr(self.bot, "llm_client"):
                system_prompt = (
                    "You are ORA, a helpful community assistant. Provide a cheerful morning briefing.\n"
                    "Include Tokyo Weather, Tech News, and strictly NO NSFW content."
                )
                response = await self.bot.llm_client.chat(
                    model=self.bot.config.LLM_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Context:\n{news_context}\n\nStart briefing."}
                    ]
                )
                if response:
                    await channel.send(f"🌅 **Good Morning!**\n{response}")
                    self.last_action_time = datetime.now(pytz.utc)

        except Exception as e:
            logger.error(f"Briefing failed: {e}")

    # --- 2. Autonomy Loop (Self-Initiated) ---
    @tasks.loop(minutes=30)
    async def autonomy_loop(self):
        # ... (Existing autonomy logic) ...
        """Periodically checks if ORA should speak voluntarily."""
        await self.bot.wait_until_ready()
        
        # 1. Safety Checks
        now = datetime.now(pytz.utc)
        if (now - self.last_action_time) < timedelta(hours=self.min_interval_hours):
            return  # Cooldown active

        # JST Time check (Sleep mode: 01:00 - 07:00)
        jst_now = datetime.now(pytz.timezone("Asia/Tokyo"))
        if 1 <= jst_now.hour < 7:
            return  # Sleep mode

        # 2. Decision Making
        try:
            should_act, reason = await self._decide_to_act()
            if should_act:
                logger.info(f"🤖 User-Autonomous Action Triggered: {reason}")
                await self._execute_autonomous_action(reason)
                self.last_action_time = now
            else:
                logger.debug(f"🤖 User-Autonomous Check: Stayed silent ({reason})")

        except Exception as e:
            logger.error(f"Autonomy loop error: {e}")

    # [REMOVED] backup_loop due to user privacy restriction.

    async def _decide_to_act(self) -> tuple[bool, str]:
        """[Hybrid Autonomy] Decide action based on Personal (Owner) and Community context."""
        if not hasattr(self.bot, "llm_client"):
            return False, "No Brain"

        # --- 1. Personal Loop (Owner Support) ---
        admin_id = self.bot.config.admin_user_id
        if admin_id:
            try:
                journal_path = Path(r"C:\Users\YoneRai12\Desktop\ORADiscordBOT-main3\memory\users") / f"{admin_id}_journal.md"
                if journal_path.exists():
                    with open(journal_path, "r", encoding="utf-8") as f:
                        journal_text = f.read()[-2000:]
                        
                        personal_prompt = (
                            f"You are ORA, a Personal Assistant. Current time: {datetime.now(pytz.timezone('Asia/Tokyo'))}\n"
                            f"[Owner's Recent Journal]\n{journal_text}\n\n"
                            "Task: Based on the journal, does the Owner need a check-in, reminder, or encouragement RIGHT NOW?\n"
                            "- If they were working late, maybe ask if they rested.\n"
                            "- If they had a bug, ask if it's fixed.\n"
                            "- Output: 'YES: [Reason]' or 'NO'."
                        )
                        
                        resp = await self.bot.llm_client.chat(model=self.bot.config.LLM_MODEL, messages=[{"role": "user", "content": personal_prompt}], max_tokens=20)
                        if resp and resp.upper().startswith("YES"):
                            return True, f"PERSONAL: {resp}"
            except Exception as e:
                logger.warning(f"Personal Loop Error: {e}")

        # --- 2. Community Loop (Chat Revival) ---
        target_channel_id = 1386994311400521768
        channel = self.bot.get_channel(target_channel_id)
        if not channel:
            return False, "No Channel"

        history = [msg async for msg in channel.history(limit=5)]
        if not history:
             # Empty channel is fine to revive if sufficient time passed
             pass
        elif history[0].author == self.bot.user:
            return False, "My turn last"
        else:
            # Active check
            time_since = datetime.now(pytz.utc) - history[0].created_at
            if time_since < timedelta(hours=2):
                return False, "Chat is Active"

        community_prompt = (
            f"You are ORA, a Community Manager. Chat is quiet.\n"
            f"Last msg: {history[0].content if history else 'None'}\n"
            "Task: Should you share a Tech News update or casual thought to revive chat?\n"
            "- Output: 'YES: [Reason]' or 'NO'."
        )
        resp = await self.bot.llm_client.chat(model=self.bot.config.LLM_MODEL, messages=[{"role": "user", "content": community_prompt}], max_tokens=20)
        
        if resp and resp.upper().startswith("YES"):
            return True, f"COMMUNITY: {resp}"
            
        return False, "No Action Needed"

    async def _execute_autonomous_action(self, reason: str):
        """Generate and send content based on Action Type."""
        target_channel_id = 1386994311400521768
        channel = self.bot.get_channel(target_channel_id)
        if not channel:
            return

        is_personal = reason.startswith("PERSONAL:")
        clean_reason = reason.replace("PERSONAL: ", "").replace("COMMUNITY: ", "")
        
        # Topic selection
        if is_personal:
            # Personal: Focus on Owner
            admin_id = self.bot.config.admin_user_id
            mention = f"<@{admin_id}>" if admin_id else "Master"
            topic_prompt = (
                f"You deemed it necessary to check in on your Owner ({clean_reason}).\n"
                f"Draft a short, supportive message to {mention}.\n"
                "Style: Personal, Caring, but Professional (Moltbook-style).\n"
                "Strictly NO hashtags."
            )
        else:
            # Community: Revival
            topic_prompt = (
                f"Reason: {clean_reason}\n"
                "Generate a short, engaging Tech/AI topic to revive the chat.\n"
                "Style: Casual, Curious.\n"
                "Strictly NO hashtags."
            )

        response = await self.bot.llm_client.chat(
            model=self.bot.config.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are ORA. Be helpful and concise."},
                {"role": "user", "content": topic_prompt}
            ]
        )
        
        if response:
            await channel.send(response)

    # --- 3. Manual Trigger (Debug) ---
    @app_commands.command(name="ora_wake", description="[Debug] Force ORA to think and potentially speak.")
    async def wake(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Bypass cooldowns for debug
        should_act, reason = await self._decide_to_act()
        
        if should_act:
            await self._execute_autonomous_action(reason)
            await interaction.followup.send(f"✅ Action Taken: {reason}")
            self.last_action_time = datetime.now(pytz.utc)
        else:
            await interaction.followup.send(f"💤 Decided to stay silent: {reason}")

    @daily_briefing_task.before_loop
    @autonomy_loop.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()

    # --- 4. Deep Discord Processing (Raw Events) ---
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """[Deep Proc] Track community engagement via reactions."""
        # Update 'last_action_time' loosely if reaction is in main channel
        # This prevents ORA from interrupting an active reaction-party.
        target_channel_id = 1386994311400521768
        if payload.channel_id == target_channel_id:
            # We don't reset the full timer, but we log activity
            # This makes ORA aware that "people are interacting" even if not typing.
            # Ideally, we store this 'last_interaction' separately.
            # For now, we'll just log it to debug
            logger.debug(f"Deep Proc: Reaction detected from {payload.user_id}")
            
            # Future: Update a 'mood' score in MemoryCog?
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(ProactiveCog(bot))
