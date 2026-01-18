
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import io
import logging
from ..utils.comfy_client import ComfyWorkflow

logger = logging.getLogger("CreativeCog")

class CreativeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.layer_api = "http://127.0.0.1:8003/decompose"
        self.comfy_client = ComfyWorkflow()

    @app_commands.command(name="generate_video", description="Generate video using LTX-2 (ComfyUI)")
    @app_commands.describe(prompt="Video description", negative_prompt="What to avoid (optional)", width="Width (def: 768)", height="Height (def: 512)", frames="Frame count (def: 49)")
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: (i.guild_id, i.user.id))
    async def generate_video(self, interaction: discord.Interaction, prompt: str, negative_prompt: str = "", width: int = 768, height: int = 512, frames: int = 49):
        """
        Generate a video from text using LTX-Video.
        """
        await interaction.response.defer(thinking=True)
        
        try:
            # Generate
            mp4_data = await self.bot.loop.run_in_executor(None, lambda: self.comfy_client.generate_video(prompt, negative_prompt, width=width, height=height, frame_count=frames))
            
            if mp4_data:
                f = discord.File(io.BytesIO(mp4_data), filename="ltx_video.mp4")
                await interaction.followup.send(content=f"🎬 **Generated Video**\nPrompt: {prompt}", file=f)
            else:
                 await interaction.followup.send("❌ Video generation failed. Check logs or ComfyUI console.")
                 
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")

    @app_commands.command(name="layer", description="Decompose an image into layers (Qwen-Image-Layered)")
    @app_commands.describe(image="The image to decompose")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def layer(self, interaction: discord.Interaction, image: discord.Attachment):
        """
        Decomposes an image into a ZIP of layers.
        """
        if not image.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Image file required.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        try:
            # Send to local service
            async with aiohttp.ClientSession() as session:
                original_bytes = await image.read()
                data = aiohttp.FormData()
                data.add_field("file", original_bytes, filename=image.filename)
                
                async with session.post(self.layer_api, data=data) as resp:
                    if resp.status == 200:
                        zip_data = await resp.read()
                        
                        # Send back ZIP
                        f = discord.File(io.BytesIO(zip_data), filename=f"layers_{image.filename}.zip")
                        await interaction.followup.send(content="✅ **Layer Decomposition Complete!**\nHere are your layers (PSD/PNGs):", file=f)
                    else:
                        err = await resp.text()
                        await interaction.followup.send(f"❌ Processing Failed (Server Error): {resp.status} - {err}")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")

    # Natural Language Trigger ("@ORA layer...") defined in Bot Listeners or separate loop?
    # Usually better to keep separate.
    # Included simple Listener here.
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Check mention
        if self.bot.user in message.mentions:
             content = message.content.lower()
             if "layer" in content or "レイヤー" in content:
                 # Check attachments
                 target_img = None
                 if message.attachments:
                     target_img = message.attachments[0]
                 elif message.reference:
                     # Check reply
                     ref = await message.channel.fetch_message(message.reference.message_id)
                     if ref.attachments:
                         target_img = ref.attachments[0]
                
                 if target_img and target_img.content_type.startswith("image/"):
                     async with message.channel.typing():
                         # Reuse Logic (Refactor needed, but inline for now for speed)
                         async with aiohttp.ClientSession() as session:
                            original_bytes = await target_img.read()
                            data = aiohttp.FormData()
                            data.add_field("file", original_bytes, filename=target_img.filename)
                            
                            async with session.post(self.layer_api, data=data) as resp:
                                if resp.status == 200:
                                    zip_data = await resp.read()
                                    f = discord.File(io.BytesIO(zip_data), filename=f"layers_{target_img.filename}.zip")
                                    await message.reply("✅ レイヤー分解しました！", file=f)
                                else:
                                    await message.reply(f"❌ 失敗しました: {resp.status}")

async def setup(bot: commands.Bot):
    await bot.add_cog(CreativeCog(bot))
