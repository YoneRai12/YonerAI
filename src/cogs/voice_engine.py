
import io
import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("VoiceEngineCog")

class VoiceEngine(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.speak_url = "http://127.0.0.1:8002/speak"
        self.clone_url = "http://127.0.0.1:8002/clone_speaker"

    @app_commands.command(name="voice_check", description="[DEBUG] Voice Engine Status")
    async def voice_check(self, interaction: discord.Interaction):
        async with aiohttp.ClientSession() as session:
            try:
                # Assuming /docs exists on FastAPI
                async with session.get("http://127.0.0.1:8002/docs") as resp:
                    if resp.status == 200:
                        await interaction.response.send_message("✅ Voice Engine (Aratako TTS) is ONLINE.")
                    else:
                        await interaction.response.send_message(f"⚠️ Voice Engine returned {resp.status}.")
            except Exception as e:
                await interaction.response.send_message(f"❌ Voice Engine Offline: {e}")

    @app_commands.command(name="doppelganger", description="Register your voice for Doppelganger Mode (Cloning).")
    @app_commands.describe(sample="Upload a clear audio sample (10s+) of your voice.")
    async def doppelganger(self, interaction: discord.Interaction, sample: discord.Attachment):
        if not sample.content_type.startswith("audio/"):
            await interaction.response.send_message("❌ Audio file required.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        async with aiohttp.ClientSession() as session:
            audio_data = await sample.read()
            data = aiohttp.FormData()
            data.add_field("user_id", str(interaction.user.id))
            data.add_field("audio", audio_data, filename=sample.filename)
            
            async with session.post(self.clone_url, data=data) as resp:
                if resp.status == 200:
                    await interaction.followup.send(f"✅ Voice Registered! ORA can now speak as {interaction.user.display_name}.")
                else:
                    await interaction.followup.send(f"❌ Registration Failed: {resp.status}")

    async def generate_speech(self, text: str, user_id: str = None) -> io.BytesIO:
        """
        Internal API for ORA Brain to speak.
        If user_id is provided, it attempts to use the cloned voice.
        """
        async with aiohttp.ClientSession() as session:
            data = {"text": text}
            if user_id:
                data["speaker_id"] = str(user_id)
            
            # Note: For cloning, we might need to verify if user has registered data.
            # Ideally the VoiceEngine server handles fallback if ID not found.
            
            async with session.post(self.speak_url, data=data) as resp:
                if resp.status == 200:
                    audio_bytes = await resp.read()
                    return io.BytesIO(audio_bytes)
                else:
                    logger.error(f"TTS Failed: {resp.status}")
                    return None

    @app_commands.command(name="voices", description="List available VoiceVox speakers.")
    async def list_voices(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Access VoiceManager from bot
        vm = getattr(self.bot, "voice_manager", None)
        if not vm:
            await interaction.followup.send("❌ VoiceManager not initialized.")
            return

        speakers = await vm.get_speakers()
        if not speakers:
            await interaction.followup.send("❌ No speakers found or VoiceVox is offline.")
            return

        # Format output
        # VoiceVox structure: [{'name': '四国めたん', 'styles': [{'id': 2, 'name': 'ノーマル'}, ...], 'speaker_uuid': '...'}]
        embed = discord.Embed(title="🎙️ Available Voices (VoiceVox)", color=discord.Color.blue())
        
        description = ""
        for sp in speakers:
            name = sp.get("name", "Unknown")
            styles = sp.get("styles", [])
            style_list = ", ".join([f"{s['name']}(ID:{s['id']})" for s in styles])
            description += f"**{name}**: {style_list}\n"

        if len(description) > 4000:
            description = description[:4000] + "..."
            
        embed.description = description
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="voice_set", description="Set your TTS voice (Speaker ID).")
    @app_commands.describe(speaker_id="The ID of the speaker style (e.g. 3 for Zundamon Normal)")
    async def set_voice(self, interaction: discord.Interaction, speaker_id: int):
        vm = getattr(self.bot, "voice_manager", None)
        if not vm:
            await interaction.response.send_message("❌ VoiceManager not initialized.", ephemeral=True)
            return

        vm.set_user_speaker(interaction.user.id, speaker_id)
        await interaction.response.send_message(f"✅ Voice set to Speaker ID: **{speaker_id}**", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceEngine(bot))
