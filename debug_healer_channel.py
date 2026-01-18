
import os
import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CID_RAW = os.getenv("FEATURE_PROPOSAL_CHANNEL_ID")
LOG_RAW = os.getenv("ORA_LOG_CHANNEL_ID")

print(f"DEBUG: Loaded Env.")
print(f"FEATURE_PROPOSAL_CHANNEL_ID: {CID_RAW} (Type: {type(CID_RAW)})")
print(f"ORA_LOG_CHANNEL_ID: {LOG_RAW} (Type: {type(LOG_RAW)})")

if not TOKEN:
    print("FATAL: No Token.")
    exit()

if not CID_RAW:
    print("FATAL: No Feature Proposal ID found in env.")
    exit()

try:
    CID = int(CID_RAW)
except:
    print(f"FATAL: ID '{CID_RAW}' is not a valid integer.")
    exit()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    
    print(f"Attempting to fetch channel {CID}...")
    try:
        channel = await client.fetch_channel(CID)
        print(f"✅ Channel Found: {channel.name} ({channel.type})")
        
        # Try sending
        try:
            await channel.send("🧪 **Healer Notification Test**: Can you hear me?")
            print(f"✅ Message sent successfully.")
        except Exception as e:
            print(f"❌ Send Failed: {e}")
            
    except Exception as e:
        print(f"❌ Fetch Failed: {e}")
        print("Possible causes: Bot not in server, mismatch ID, or missing permissions.")
    
    await client.close()

client.run(TOKEN)
