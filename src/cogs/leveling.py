import discord
from discord import app_commands
from discord.ext import commands, tasks
import time
import logging

logger = logging.getLogger(__name__)

class LevelingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # {user_id: start_time}
        self.vc_start_times = {}
        # 1 point per minute
        self.POINTS_PER_MINUTE = 1 

    def cog_unload(self):
        # Process any remaining users in VC before unloading?
        # For simplicity, we just clear the cache. Users might lose current session points.
        self.vc_start_times.clear()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Track time spent in VC to award points."""
        if member.bot:
            return

        # Joined VC
        if not before.channel and after.channel:
            self.vc_start_times[member.id] = time.time()
            logger.debug(f"Leveling: {member.display_name} joined VC. Timer started.")

        # Left VC
        elif before.channel and not after.channel:
            if member.id in self.vc_start_times:
                start_time = self.vc_start_times.pop(member.id)
                duration_mins = (time.time() - start_time) / 60.0
                
                if duration_mins >= 1:
                    points_earned = int(duration_mins * self.POINTS_PER_MINUTE)
                    await self._add_points(member, points_earned)
                    logger.info(f"Leveling: {member.display_name} left VC. Earned {points_earned} points ({duration_mins:.1f} min).")

        # Switched Channel (Optional: restart timer or keep running? currently acting like join/leave per channel)
        # If just switching, before.channel and after.channel are both set.
        # We should treat it as continuous if we want.
        # Current logic: If they switch, it triggers neither of above blocks (both are True).
        # Wait, the logic above is specific: `not before.channel` means "was not in VC".
        # So switching channels maintains the original start time. This is good.

    async def _add_points(self, member: discord.Member, amount: int):
        """Add points to user profile via MemoryCog."""
        try:
            memory_cog = self.bot.get_cog("MemoryCog")
            if not memory_cog:
                logger.warning("Leveling: MemoryCog not found. Cannot save points.")
                return

            # Fetch current profile
            profile = await memory_cog.get_user_profile(member.id, member.guild.id)
            if not profile:
                profile = {}
            
            current_points = profile.get("points", 0)
            new_points = current_points + amount
            
            # Update only points
            await memory_cog.update_user_profile(member.id, {"points": new_points}, member.guild.id)
            
        except Exception as e:
            logger.error(f"Leveling: Failed to add points for {member.id}: {e}")

    @app_commands.command(name="rank", description="現在のランクとポイントを確認します。")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        """Show user's rank card."""
        target = member or interaction.user
        
        memory_cog = self.bot.get_cog("MemoryCog")
        if not memory_cog:
            await interaction.response.send_message("❌ システムエラー: MemoryCogが見つかりません。", ephemeral=True)
            return

        # Defer
        await interaction.response.defer()

        # Get Profile
        profile = await memory_cog.get_user_profile(target.id, interaction.guild.id)
        points = profile.get("points", 0) if profile else 0
        
        # Calculate Rank (Simple Logic)
        # 0-100: Novice
        # 100-500: Regular
        # 500-1000: Veteran
        # 1000+: Master
        rank_title = "Novice"
        if points >= 1000:
            rank_title = "Master"
        elif points >= 500:
            rank_title = "Veteran"
        elif points >= 100:
            rank_title = "Regular"

        embed = discord.Embed(title=f"🏆 {target.display_name}のランク", color=0xFFD700)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Points", value=f"{points:,} pt", inline=True)
        embed.add_field(name="Rank", value=rank_title, inline=True)
        
        # Show VC Status
        if target.id in self.vc_start_times:
            current_duration = (time.time() - self.vc_start_times[target.id]) / 60.0
            embed.set_footer(text=f"🎙️ VC参加中: {int(current_duration)}分経過 (獲得予定: {int(current_duration)}pt)")
        
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))
