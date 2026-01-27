import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger("MusicCog")

class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    music_group = app_commands.Group(name="music", description="Legacy Music Playback (YouTube)")

    @music_group.command(name="play", description="Play music from YouTube")
    @app_commands.describe(query="Song Name or URL")
    async def music_play(self, interaction: discord.Interaction, query: str) -> None:
        media_cog = self.bot.get_cog("MediaCog")
        if not media_cog:
            await interaction.response.send_message("Media system unavailable.", ephemeral=True)
            return
        await media_cog.ytplay(interaction, query)

    @music_group.command(name="stop", description="Stop Playback")
    async def music_stop(self, interaction: discord.Interaction) -> None:
        media_cog = self.bot.get_cog("MediaCog")
        if not media_cog:
            await interaction.response.send_message("Media system unavailable.", ephemeral=True)
            return
        await media_cog.stop(interaction)

    @music_group.command(name="skip", description="Skip to next track")
    async def music_skip(self, interaction: discord.Interaction) -> None:
        media_cog = self.bot.get_cog("MediaCog")
        if not media_cog:
            await interaction.response.send_message("Media system unavailable.", ephemeral=True)
            return
        await media_cog.skip(interaction)

    @music_group.command(name="loop", description="Loop music (off/track/queue)")
    @app_commands.describe(mode="Loop mode")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Off", value="off"),
            app_commands.Choice(name="Track", value="track"),
            app_commands.Choice(name="Queue", value="queue"),
        ]
    )
    async def music_loop(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        """Loop music"""
        media_cog = self.bot.get_cog("MediaCog")
        if media_cog:
            await media_cog.loop(interaction, mode.value)
        else:
            await interaction.response.send_message("❌ Media system not available.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
