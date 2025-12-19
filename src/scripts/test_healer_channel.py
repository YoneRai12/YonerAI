
import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
HEALER_CHANNEL_ID = 1386994311400521768

class HealerTester(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        
        try:
            print(f"Fetching channel {HEALER_CHANNEL_ID}...")
            channel = await self.fetch_channel(HEALER_CHANNEL_ID)
            print(f"Found Channel: {channel.name} ({channel.type})")
            
            print("Sending test message...")
            await channel.send("🚑 **Auto-Healer Test**\nIf you see this, the notification system is connected correctly.")
            print("Message sent successfully.")
            
        except discord.NotFound:
            print("Error: Channel not found. ID might be wrong or bot not in server.", HEALER_CHANNEL_ID)
        except discord.Forbidden:
            print("Error: Permission denied (Cannot send messages).")
        except Exception as e:
            print(f"Error: {e}")
        
        await self.close()

intents = discord.Intents.default()
client = HealerTester(intents=intents)
client.run(TOKEN)
