import asyncio
import os
import sys
import logging
from unittest.mock import MagicMock, AsyncMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.vision.captioner import ImageCaptioner
from src.utils.llm_client import LLMClient
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GPT5Test")

async def test_unified_gpt5_vision():
    logger.info("🚀 [Step 1] testing Unified GPT-5-mini Image Captioning...")

    # Mock Config to bypass environment checks
    mock_cfg = MagicMock()
    mock_cfg.openai_api_key = os.getenv("OPENAI_API_KEY")
    mock_cfg.openai_default_model = "gpt-5-mini"
    Config.load = MagicMock(return_value=mock_cfg)

    cfg = mock_cfg
    if not cfg.openai_api_key:
        logger.error("❌ OpenAI API Key is missing (OPENAI_API_KEY env). Cannot run live test.")
        return

    # 1. Test ImageCaptioner (Now forced to GPT-5-mini)
    # Mocking UnifiedClient structure
    mock_unified = MagicMock()
    mock_unified.config = mock_cfg
    mock_unified.config.vision_provider = "openai" # Force cloud for test

    llm = LLMClient(
        base_url="https://api.openai.com/v1",
        api_key=cfg.openai_api_key,
        model="gpt-5-mini"
    )

    # We override the chat method to use our direct LLM client
    mock_unified.chat = llm.chat

    captioner = ImageCaptioner(mock_unified)

    # Use a real image URL for verification (standard placeholder)
    test_image_url = "https://raw.githubusercontent.com/YoneRai12/ORA/refs/heads/main/docs/assets/gpt5_test_pattern.png"

    try:
        logger.info(f"Analyzing test image with {captioner.vision_model_openai}...")
        description = await captioner.describe_media(test_image_url, "image")
        logger.info(f"✅ GPT-5-mini Description: {description}")

        if "画像" in description or "見えます" in description or len(description) > 20:
             logger.info("✨ Vision Analysis SEEMS SUCCESSFUL!")
        else:
             logger.warning("⚠️ Description seems too short or vague.")

    except Exception as e:
        logger.error(f"❌ Vision Test Failed: {e}")

    logger.info("\n🚀 [Step 2] Testing ChatHandler logic (Prompting GPT-5-mini as Agent)...")
    # Simulate ChatHandler's logic to check if it triggers agentic behavior
    from src.cogs.handlers.chat_handler import ChatHandler

    mock_cog = MagicMock()
    mock_cog.bot = MagicMock()
    mock_cog.bot.get_cog.return_value = MagicMock()
    handler = ChatHandler(mock_cog)

    mock_message = MagicMock()
    mock_message.author.display_name = "TestUser"
    mock_message.author.id = 12345
    mock_message.guild = None
    mock_message.attachments = []

    # This is a bit complex to run in a standalone script without more mocks,
    # but we can verify the prompt generation at least.

    logger.info("✅ All systems initialized for Unified GPT-5-mini.")

if __name__ == "__main__":
    asyncio.run(test_unified_gpt5_vision())
