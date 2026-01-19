
import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("VisualCortexCog")

class VisualCortex(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = "http://127.0.0.1:8004/analyze"

    @app_commands.command(name="vision_check", description="[DEBUG] Visual Cortex Status")
    async def vision_check(self, interaction: discord.Interaction):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("http://127.0.0.1:8004/docs") as resp:
                    if resp.status == 200:
                        await interaction.response.send_message("✅ Visual Cortex (T5Gemma 4B) is ONLINE.")
                    else:
                        await interaction.response.send_message(f"⚠️ Visual Cortex returned {resp.status}.")
            except Exception as e:
                await interaction.response.send_message(f"❌ Visual Cortex Offline: {e}")

    async def analyze_image_attachment(self, attachment: discord.Attachment, prompt: str = "Describe this."):
        """
        Public method to be called by ORA Brain.
        """
        async with aiohttp.ClientSession() as session:
            # Download image first
            image_data = await attachment.read()
            
            data = aiohttp.FormData()
            data.add_field("file", image_data, filename=attachment.filename)
            data.add_field("prompt", prompt)
            
            async with session.post(self.api_url, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("analysis", "No analysis returned.")
                else:
                    return f"Error: API {resp.status}"

async def setup(bot: commands.Bot):
    await bot.add_cog(VisualCortex(bot))
