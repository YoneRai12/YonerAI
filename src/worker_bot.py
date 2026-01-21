import asyncio
import logging
import os
import sys

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.cogs.memory import MemoryCog  # noqa: E402

# Imports from src
from src.config import Config  # noqa: E402
from src.utils.google_client import GoogleClient  # noqa: E402
from src.utils.llm_client import LLMClient  # noqa: E402
from src.utils.unified_client import UnifiedClient  # noqa: E402

# Setup Logging
log_dir = os.path.join(os.getcwd(), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/worker_bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logging.getLogger("discord.http").setLevel(logging.WARNING)
logging.getLogger("discord.gateway").setLevel(logging.WARNING)

logger = logging.getLogger("WorkerBot")

# Load Env
load_dotenv(override=True)
TOKEN = os.getenv("DISCORD_TOKEN_2")
if not TOKEN:
    logger.critical("DISCORD_TOKEN_2 not found in .env! Exiting.")
    sys.exit(99) # Specific exit code for "no token" to stop batch loop

# Paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)


class WorkerBot(commands.Bot):
    def __init__(self, config: Config, session: aiohttp.ClientSession):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = True  # Needed to scan online users

        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.session = session

        # Initialize Clients for UnifiedClient
        self.base_llm = LLMClient(
            base_url=config.llm_base_url, api_key=config.llm_api_key, model=config.llm_model, session=session
        )

        self.google_client = None
        if config.gemini_api_key:
            self.google_client = GoogleClient(config.gemini_api_key)

        self.llm_client = UnifiedClient(config, self.base_llm, self.google_client)

    async def setup_hook(self):
        # MemoryCog expects (bot, llm_client, worker_mode)
        await self.add_cog(MemoryCog(self, self.llm_client, worker_mode=True))
        logger.info("WorkerBot: MemoryCog loaded in WORKER MODE.")

    async def on_ready(self):
        logger.info(f"WorkerBot Logged in as {self.user} (ID: {self.user.id})")
        logger.info("WorkerBot is ready to process memory tasks.")


async def main():
    # Load configuration
    try:
        config = Config.load()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    async with aiohttp.ClientSession() as session:
        bot = WorkerBot(config, session)
        async with bot:
            await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
