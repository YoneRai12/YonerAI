import logging
from typing import TYPE_CHECKING

import discord
from discord import ui

if TYPE_CHECKING:
    from ..cogs.media import MediaCog

logger = logging.getLogger(__name__)

class MusicPlayerView(ui.View):
    def __init__(self, cog: 'MediaCog', guild_id: int):
        super().__init__(timeout=None) # Persistent view (or handled by cog loop)
        self.cog = cog
        self.guild_id = guild_id
        self.voice_manager = cog._voice_manager
        
        # Sync Button States
        self._sync_state()

    def _sync_state(self):
        try:
            state = self.voice_manager.get_music_state(self.guild_id)
            if not state:
                return

            # Loop Button
            # Button custom_id="music_loop"
            for child in self.children:
                if isinstance(child, ui.Button):
                    if child.custom_id == "music_loop":
                        child.style = discord.ButtonStyle.green if state.is_looping else discord.ButtonStyle.secondary
                    elif child.custom_id == "music_play_pause":
                        # Optional: Change style if paused
                        if state.voice_client and state.voice_client.is_paused():
                            child.style = discord.ButtonStyle.danger # Red for paused? or just Secondary
                            child.emoji = "▶️" # Show Play icon
                        else:
                            child.style = discord.ButtonStyle.primary
                            child.emoji = "⏸️" # Show Pause icon
        except Exception as e:
            logger.error(f"Failed to sync dashboard state: {e}")

    @ui.button(emoji="⏯️", style=discord.ButtonStyle.primary, custom_id="music_play_pause", row=0)
    async def play_pause(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if not vc:
             # Try to reconnect?
             return

        if vc.is_paused():
            vc.resume()
        elif vc.is_playing():
            vc.pause()
        
        # Force state sync before update
        self._sync_state()
        await self.update_dashboard(interaction)

    @ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="music_skip", row=0)
    async def skip(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        # Logic to skip
        await self.voice_manager.skip_track(interaction.guild.id)
        # Dashboard update happens via event loop usually, but force one here
        await self.update_dashboard(interaction)

    @ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="music_stop", row=0)
    async def stop(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await self.voice_manager.stop_player(interaction.guild.id)
        # await interaction.delete_original_response() # Don't delete, just show Stopped
        await self.update_dashboard(interaction)

    @ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="music_shuffle", row=1)
    async def shuffle(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.voice_manager.shuffle_queue(interaction.guild.id)
        await self.update_dashboard(interaction)

    @ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, custom_id="music_vol_down", row=0)
    async def vol_down(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        state = self.voice_manager.get_music_state(interaction.guild.id)
        new_vol = max(0.0, state.volume - 0.1)
        self.voice_manager.set_music_volume(interaction.guild.id, new_vol)
        await self.update_dashboard(interaction)

    @ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, custom_id="music_vol_up", row=0)
    async def vol_up(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        state = self.voice_manager.get_music_state(interaction.guild.id)
        new_vol = min(2.0, state.volume + 0.1)
        self.voice_manager.set_music_volume(interaction.guild.id, new_vol)
        await self.update_dashboard(interaction)

    @ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="music_loop", row=1)
    async def loop(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        mode = self.voice_manager.toggle_loop(interaction.guild.id)
        button.style = discord.ButtonStyle.green if mode else discord.ButtonStyle.secondary
        await self.update_dashboard(interaction)

    # --- Speed Controls (Row 1) ---
    
    @ui.button(label="Normal", style=discord.ButtonStyle.secondary, row=2, custom_id="music_speed_1")
    async def speed_normal(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.voice_manager.set_speed_pitch(interaction.guild.id, speed=1.0, pitch=1.0)
        await self.update_dashboard(interaction)

    @ui.button(label="x1.25", style=discord.ButtonStyle.secondary, row=2, custom_id="music_speed_125")
    async def speed_125(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.voice_manager.set_speed_pitch(interaction.guild.id, speed=1.25, pitch=1.0)
        await self.update_dashboard(interaction)

    @ui.button(emoji="🚀", label="x1.5", style=discord.ButtonStyle.secondary, row=2, custom_id="music_speed_150")
    async def speed_150(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.voice_manager.set_speed_pitch(interaction.guild.id, speed=1.5, pitch=1.0)
        await self.update_dashboard(interaction)

    @ui.button(emoji="🌙", label="Nightcore", style=discord.ButtonStyle.primary, row=2, custom_id="music_speed_nightcore")
    async def speed_nightcore(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        # Nightcore typically: speed ~1.25, pitch ~1.25
        self.voice_manager.set_speed_pitch(interaction.guild.id, speed=1.25, pitch=1.25)
        await self.update_dashboard(interaction)


    async def update_dashboard(self, interaction: discord.Interaction):
        # Trigger an update of the embed
        # This requires the view to know which message it is attached to, 
        # OR the media cog handles the update.
        # Ideally, we call a method on the Cog.
        await self.cog.update_music_dashboard(self.guild_id)

def create_music_embed(
    track_info: dict, 
    status: str, 
    play_time_sec: float, 
    total_duration_sec: float, 
    queue_preview: list,
    speed: float = 1.0,
    pitch: float = 1.0
) -> discord.Embed:
    """
    Generates the Dashboard Embed.
    track_info: {title, url, thumbnail, requester}
    """
    embed = discord.Embed(color=discord.Color.from_rgb(29, 185, 84)) # Spotify Green
    
    title = track_info.get("title", "Unknown Track")
    url = track_info.get("url", "")
    
    # Status Adjustment
    status_text = status
    if speed != 1.0 or pitch != 1.0:
        status_text += f" (Speed: x{speed}, Pitch: x{pitch})"
        
    embed.set_author(name=f"Now Playing: {status_text}", icon_url="https://i.imgur.com/SBMH84I.png")
    embed.title = title
    if url: embed.url = url
    
    # Progress Bar
    # [====>-------] 1:20 / 3:45
    bar_length = 20
    if total_duration_sec > 0:
        # Effective progress
        current_pos = play_time_sec * speed
        progress = min(1.0, max(0.0, current_pos / total_duration_sec))
        # Custom "Diagonal" Style
        filled = int(progress * bar_length)
        empty = bar_length - filled
        # Filled: ▧ (Diagonal Crosshatch), Empty: ▱ (Hollow Parallelogram) or ▨
        bar = "▧" * filled + "🔘" + "▱" * empty
        
        t_curr = format_time(current_pos)
        t_total = format_time(total_duration_sec)
        embed.description = f"`{bar}`\n`{t_curr} / {t_total}`"
    else:
        # Duration 0: Could be Live Stream OR Stopped/Loading
        if "Stopped" in status_text or status == "Stopped":
             embed.description = "`⏹️ Stopped`"
        else:
             embed.description = "`🔘 Live Stream`"

    # Thumbnail
    thumb = track_info.get("thumbnail")
    if thumb: embed.set_thumbnail(url=thumb)

    # Queue Preview
    if queue_preview:
        q_text = ""
        # Limit to 10 items to prevent Embed oversize
        limit = 10
        visible_queue = queue_preview[:limit]
        
        for i, t in enumerate(visible_queue):
            title_text = t.get('title', 'Unknown')
            # Truncate long titles
            if len(title_text) > 40:
                title_text = title_text[:37] + "..."
            q_text += f"`{i+1}.` {title_text}\n"
        
        remaining = len(queue_preview) - limit
        if remaining > 0:
            q_text += f"...and **{remaining}** more."
            
        embed.add_field(name=f"Next Up ({len(queue_preview)})", value=q_text, inline=False)
    else:
        embed.add_field(name="Next Up", value="Empty", inline=False)

    # Footer
    req = track_info.get("requester")
    
    footer_text = f"Status: {status}"
    if req:
        footer_text = f"Requested by {req} | {footer_text}"
    
    if speed != 1.0:
        footer_text += f" | ⚡ x{speed}"
    if pitch != 1.0:
        footer_text += f" | 🎤 x{pitch}"
        
    embed.set_footer(text=footer_text)
    
    return embed

def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
