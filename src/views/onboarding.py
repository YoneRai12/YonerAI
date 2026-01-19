import discord
from discord.ui import Button, View


class SelectModeView(View):
    def __init__(self, cog, user_id: int):
        super().__init__(
            timeout=None
        )  # Persistent view context usually needed, but for ephemeral interaction None is ok if handled quickly.
        self.cog = cog
        self.user_id = user_id
        self.value = None

    @discord.ui.button(label="Smart 🧠 (Cloud OK)", style=discord.ButtonStyle.primary, custom_id="onboard_smart")
    async def smart_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return

        # Save Preference
        self.cog.user_prefs.set_mode(interaction.user.id, "smart")

        await interaction.response.send_message(
            "✅ **Smart Mode Selected!**\n"
            "Heavy tasks will be intelligently routed to the Cloud (Gemini/OpenAI) if safe.\n"
            "Privacy: Images and sensitive logs are always kept LOCAL.\n"
            "Usage: `/mode` to change anytime.",
            ephemeral=True,
        )
        self.value = "smart"
        self.stop()
        # Clean up the onboarding message
        try:
            await interaction.message.delete()
        except:
            pass

    @discord.ui.button(
        label="Private 🔒 (Local Only)", style=discord.ButtonStyle.secondary, custom_id="onboard_private"
    )
    async def private_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return

        self.cog.user_prefs.set_mode(interaction.user.id, "private")

        await interaction.response.send_message(
            "🔒 **Private Mode Selected!**\n"
            "All data stays on this machine. No external APIs will be used.\n"
            "Note: Complex reasoning might be slower or less capable than Cloud.",
            ephemeral=True,
        )
        self.value = "private"
        self.stop()
        try:
            await interaction.message.delete()
        except:
            pass
