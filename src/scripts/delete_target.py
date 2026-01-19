
import os

import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TARGET_MSG_ID = 1451412095143772190
PARENT_ID = 1386994311400521768

class Deleter(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        
        try:
            # Try to fetch the channel/thread first
            print(f"Fetching parent channel/thread {PARENT_ID}...")
            channel = await self.fetch_channel(PARENT_ID)
            print(f"Found Parent: {channel.name} ({channel.type})")
            
            # Fetch message
            print(f"Fetching message {TARGET_MSG_ID}...")
            msg = await channel.fetch_message(TARGET_MSG_ID)
            print(f"Found Message: {msg.content} (Author: {msg.author})")
            
            # Delete
            print("Deleting...")
            await msg.delete()
            print("Successfully deleted message.")
            
        except discord.NotFound:
            print("Error: Channel or Message not found.")
        except discord.Forbidden:
            print("Error: Permission denied (Cannot delete).")
        except Exception as e:
            print(f"Error: {e}")
        
        await self.close()

intents = discord.Intents.default()
intents.guilds = True 
intents.messages = True
intents.message_content = True

client = Deleter(intents=intents)
client.run(TOKEN)
