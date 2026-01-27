import io
import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from ..utils.comfy_client import ComfyWorkflow

logger = logging.getLogger("CreativeCog")


class CreativeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.layer_api = "http://127.0.0.1:8003/decompose"
        self.comfy_client = ComfyWorkflow()
        # Ensure we have access to UserPrefs via Bot's store
        from ..utils.user_prefs import UserPrefs
        if hasattr(bot, "store"):
            self.user_prefs = UserPrefs(bot.store)
        else:
            self.user_prefs = None # Fallback or Error?

        # Check ComfyUI connection on startup
        self.bot.loop.create_task(self._check_comfy_connection())

    async def _check_comfy_connection(self):
        """Check if ComfyUI is reachable on startup."""
        if not hasattr(self.bot, "config") or not self.bot.config.sd_api_url:
            return

        url = f"{self.bot.config.sd_api_url}/system_stats"
        for i in range(12):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=5) as resp:
                        if resp.status == 200:
                            logger.info(f"🎨 ComfyUI Connected at {self.bot.config.sd_api_url}")
                            return
            except Exception:
                pass
            await __import__("asyncio").sleep(5)
        logger.error("🎨 Could not connect to ComfyUI after 60 seconds.")

    @app_commands.command(name="imagine", description="Generate an image using AI (Flux.1)")
    @app_commands.describe(prompt="Image description", negative_prompt="What to exclude (optional)")
    async def imagine(self, interaction: discord.Interaction, prompt: str, negative_prompt: str = ""):
        """Generate an image using Flux.1 (ComfyUI)"""
        from ..views.image_gen import AspectRatioSelectView
        view = AspectRatioSelectView(self, prompt, negative_prompt, model_name="FLUX.2")
        await interaction.response.send_message(
            f"🎨 **Image Generation Assistant**\nPrompt: `{prompt}`\nPlease select an aspect ratio to begin.",
            view=view,
        )

    @app_commands.command(name="analyze", description="Analyze an image (Vision)")
    @app_commands.describe(
        image="Image to analyze",
        prompt="Question about the image (default: Describe this)",
        model="Model to use (Auto/Local/Smart)",
    )
    @app_commands.choices(
        model=[
            app_commands.Choice(name="Auto (Default)", value="auto"),
            app_commands.Choice(name="Local (Qwen/Ministral)", value="local"),
            app_commands.Choice(name="Smart (OpenAI/Gemini)", value="smart"),
        ]
    )
    async def analyze(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        prompt: str = "Describe this image in detail.",
        model: app_commands.Choice[str] = None,
    ):
        """Analyze an image using Vision AI"""
        if not image.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Image file required.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        target_model = "Qwen/Qwen2.5-VL-32B-Instruct-AWQ"
        provider = "local"
        choice = model.value if model else "auto"

        if choice == "smart":
            target_model = "gpt-4o-mini"
            provider = "openai"
        elif choice == "local":
            target_model = "Qwen/Qwen2.5-VL-32B-Instruct-AWQ"
            provider = "local"
        else:
            # Auto: Use User Preference if available
            user_mode = "private"
            if self.user_prefs:
                user_mode = self.user_prefs.get_mode(interaction.user.id) or "private"
            
            if user_mode == "smart":
                target_model = "gpt-4o-mini"
                provider = "openai"
            else:
                target_model = "Qwen/Qwen2.5-VL-32B-Instruct-AWQ"
                provider = "local"

        try:
            import base64
            img_data = await image.read()
            b64_img = base64.b64encode(img_data).decode("utf-8")

            messages = [
                {"role": "system", "content": "You are a helpful Vision AI."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}},
                    ],
                },
            ]

            start_msg = f"👁️ **Vision Analysis**\nModel: `{target_model}` ({provider.upper()})\nProcessing..."
            await interaction.followup.send(start_msg)

            # Access LLM via Bot
            if not hasattr(self.bot, "llm_client"):
                 await interaction.followup.send("❌ LLM Client not found on Bot.")
                 return
                 
            response, _, _ = await self.bot.llm_client.chat(messages=messages, model=target_model, temperature=0.1)

            if response:
                await interaction.followup.send(f"✅ **Analysis Result**:\n{response}")
            else:
                await interaction.followup.send("❌ Empty response from Vision Model.")

        except Exception as e:
            await interaction.followup.send(f"❌ Error during analysis: {e}")


    @app_commands.command(name="generate_video", description="Generate video using LTX-2 (ComfyUI)")
    @app_commands.describe(
        prompt="Video description",
        negative_prompt="What to avoid (optional)",
        width="Width (def: 768)",
        height="Height (def: 512)",
        frames="Frame count (def: 49)",
    )
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: (i.guild_id, i.user.id))
    async def generate_video(
        self,
        interaction: discord.Interaction,
        prompt: str,
        negative_prompt: str = "",
        width: int = 768,
        height: int = 512,
        frames: int = 49,
    ):
        """
        Generate a video from text using LTX-Video.
        """
        await interaction.response.defer(thinking=True)

        try:
            # Generate
            mp4_data = await self.bot.loop.run_in_executor(
                None,
                lambda: self.comfy_client.generate_video(
                    prompt, negative_prompt, width=width, height=height, frame_count=frames
                ),
            )

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
                        await interaction.followup.send(
                            content="✅ **Layer Decomposition Complete!**\nHere are your layers (PSD/PNGs):", file=f
                        )
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
