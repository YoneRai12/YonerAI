
import asyncio
import json
import logging
import os
import sys
import time

from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [SHADOW] - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("watcher.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("ShadowWatcher")

# Load configuration
load_dotenv()
# Main Token (for Alerting - wait, Watcher usually used Main Token for alerts, but now it uses Shadow Token for Presence?)
# Actually, if we use Shadow Token, we can't send alerts to the proposal channel if the Shadow Bot isn't in that server?
# Assuming Shadow Bot is also in the server.
TOKEN = os.getenv("DISCORD_TOKEN_2") # Shadow Token
if not TOKEN:
    logger.warning("DISCORD_TOKEN_2 not found! Falling back to DISCORD_BOT_TOKEN (Risk of conflict)")
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")

PROPOSAL_CHANNEL_ID = os.getenv("FEATURE_PROPOSAL_CHANNEL_ID")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

HEARTBEAT_FILE = os.path.join("data", "heartbeat.json")
BACKUP_DIR = "backups"

import discord


class ShadowWatcher(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True 
        intents.voice_states = True
        super().__init__(intents=intents)
        
        self.heartbeat_task = None
        self.active_shadow_vcs = {} # guild_id -> voice_client
        self.is_shadow_active = False

    async def setup_hook(self):
        self.heartbeat_task = self.loop.create_task(self.monitor_heartbeat())
        logger.info("🛡️ ShadowWatcher Hooked. Monitoring Heartbeat...")

    async def on_ready(self):
        logger.info(f"✅ ShadowWatcher Logged in as {self.user} (ID: {self.user.id})")
        # Set status to invisible or "Watching ORA"
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="ORA System Status"))

    async def monitor_heartbeat(self):
        await self.wait_until_ready()
        
        # Startup Grace Period
        await asyncio.sleep(10)
        
        while not self.is_closed():
            try:
                # 1. Read Heartbeat
                if not os.path.exists(HEARTBEAT_FILE):
                     logger.warning("Heartbeat file missing.")
                     await asyncio.sleep(5)
                     continue
                
                try:
                    with open(HEARTBEAT_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    await asyncio.sleep(1)
                    continue

                remote_ts = data.get("timestamp", 0)
                status = data.get("status", "unknown")
                active_vcs = data.get("active_voice_channels", [])
                
                # Check Staleness
                # If Main Bot is "booting", we treat it as DOWN (keep Shadow Active)
                # If Main Bot is "healthy" AND timestamp is fresh ( < 15s ), we treat it as UP.
                is_main_alive = False
                if status == "healthy" and (time.time() - remote_ts) < 20:
                    is_main_alive = True
                
                if is_main_alive:
                    if self.is_shadow_active:
                        logger.info("Main Bot returned! Deactivating Shadow Mode.")
                        await self.deactivate_shadow_mode()
                else:
                    # Main Bot is DOWN or LAGGING or BOOTING
                    if not self.is_shadow_active:
                         # Only activate if there were active VCs to save
                         if active_vcs:
                             logger.warning(f"Main Bot Down! Activating Shadow Clone for VCs: {active_vcs}")
                             await self.activate_shadow_mode(active_vcs)
                    
            except Exception as e:
                logger.error(f"Monitor Loop Error: {e}")
            
            await asyncio.sleep(3)

    async def activate_shadow_mode(self, channel_ids):
        self.is_shadow_active = True
        await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.playing, name="System Maintenance (Backup Active)"))
        
        # Initialize TTS Client
        # Hardcoded URL for now as we don't load full config, or use ENV
        voicevox_url = os.getenv("VOICEVOX_API_URL", "http://127.0.0.1:50021")
        
        # Import dynamically to avoid top-level issues if dependencies missing
        sys.path.append(os.getcwd()) # Ensure src is resolvable
        try:
           from src.utils.tts_client import VoiceVoxClient
           self.tts_client = VoiceVoxClient(voicevox_url, speaker_id=3) # Style 3 (Zundamon/Metan?) for Backup
        except ImportError:
           logger.error("Could not import VoiceVoxClient. TTS will be disabled.")
           self.tts_client = None

        for ch_id in channel_ids:
            try:
                channel = self.get_channel(ch_id)
                if not channel:
                     channel = await self.fetch_channel(ch_id)
                
                if channel and isinstance(channel, discord.VoiceChannel):
                    vc = await channel.connect()
                    self.active_shadow_vcs[channel.guild.id] = vc
                    
                    # Silent Takeover (Ready to read)
                    logger.info(f"Shadow joined {channel.name} (Silent Mode)")

            except Exception as e:
                logger.error(f"Failed to join {ch_id}: {e}")

    async def deactivate_shadow_mode(self):
        self.is_shadow_active = False
        await self.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.watching, name="ORA System Status"))
        
        if self.tts_client:
            # Announce handover?
            pass

        for guild_id, vc in list(self.active_shadow_vcs.items()):
            try:
                await vc.disconnect(force=True)
                logger.info(f"Shadow left guild {guild_id}")
            except Exception as e:
                logger.error(f"Failed to leave guild {guild_id}: {e}")
        
        self.active_shadow_vcs.clear()
        self.tts_client = None

    async def on_message(self, message):
        # Ignore bots
        if message.author.bot:
            return

        content = message.content.strip()

        # --- Manual Commands ---
        if content == "!sub join":
            if message.author.voice and message.author.voice.channel:
                try:
                    vc = await message.author.voice.channel.connect()
                    self.active_shadow_vcs[message.guild.id] = vc
                    await message.channel.send("🔊 サブBot、着任しました。")
                except Exception as e:
                    await message.channel.send(f"❌ 接続エラー: {e}")
            else:
                await message.channel.send("⚠️ ボイスチャンネルに入ってから読んでください。")
            return

        if content == "!sub leave":
            if message.guild.id in self.active_shadow_vcs:
                await self.active_shadow_vcs[message.guild.id].disconnect()
                del self.active_shadow_vcs[message.guild.id]
                await message.channel.send("👋 サブBot、撤収します。")
            return
            
        # --- TTS Logic ---
        # Process if we have an active VC connection in this guild (Manual OR Shadow Mode)
        if message.guild and message.guild.id in self.active_shadow_vcs:
            vc = self.active_shadow_vcs[message.guild.id]
            if vc.is_connected() and not vc.is_playing():
                # Read it!
                if self.tts_client:
                    text = message.clean_content[:100] # Limit length
                    try:
                        audio = await self.tts_client.synthesize(text, speaker_id=3)
                        
                        # Save temp
                        fname = f"temp_shadow_{message.id}.wav"
                        with open(fname, "wb") as f:
                            f.write(audio)
                            
                        def after_play(error):
                            try: os.remove(fname)
                            except: pass
                            
                        vc.play(discord.FFmpegPCMAudio(fname), after=after_play)
                    except Exception as e:
                        logger.error(f"Shadow TTS Failed: {e}")

if __name__ == "__main__":
    if not TOKEN:
        logger.critical("No Token found. Exiting.")
        sys.exit(1)
        
    client = ShadowWatcher()
    client.run(TOKEN)
