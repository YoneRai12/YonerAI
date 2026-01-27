import discord
import asyncio
import os
import sys

from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.config import Config

async def main():
    load_dotenv()
    try:
        cfg = Config.load()
    except Exception as e:
        print(f"Failed to load config: {e}")
        return

    # User requested channel
    TARGET_CHANNEL_ID = 1454335076048568401
    
    # 1. Determine Public URL
    # Try to find a cloudflare log or use Public URL from config
    public_url = cfg.public_base_url or "http://localhost:8001"
    
    # Quick check for cloudflare local log if avail
    cf_log = os.path.join(os.getcwd(), "cloudflare.log")
    if os.path.exists(cf_log):
        # Naive parse
        pass # Not implemented yet fully, relying on config or localhost fallback

    # Construct Admin URL
    # Using a dummy secure token or timestamp for now
    dashboard_url = f"{public_url}/api/dashboard/admin?token=ADMIN_VIEW"
    
    print(f"🔗 Generated URL: {dashboard_url}")

    # 2. Setup Min-Bot
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")
        channel = client.get_channel(TARGET_CHANNEL_ID)
        if not channel:
            print(f"❌ Channel {TARGET_CHANNEL_ID} not found.")
            await client.close()
            return
        
        await channel.send(
            f"🚀 **ORA 管理ダッシュボード (全サーバー表示)**\n"
            f"以下のリンクから管理者ビューにアクセスできます:\n"
            f"{dashboard_url}"
        )
        print("✅ Message sent!")
        await client.close()

    try:
        await client.start(cfg.token)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
