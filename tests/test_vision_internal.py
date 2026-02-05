import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.utils.llm_client import LLMClient
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionTest")

async def test_vision_logic():
    """
    Tests if LLMClient generates the correct message schema for cloud models
    and if it can successfully route to OpenAI.
    """
    logger.info("🚀 Starting Internal Vision Logic Test...")

    # Check Environment
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ OPENAI_API_KEY is missing. Cannot perform cloud test.")
        return

    # Use a dummy base URL as we expect routing to OpenAI Cloud
    client = LLMClient(base_url="http://localhost:8008", api_key="EMPTY", model="gpt-5-mini")

    # Test Data: Simple Image Payload (Base64 placeholder)
    dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this image?"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{dummy_b64}"}}
            ]
        }
    ]

    logger.info("Testing LLMClient.chat with gpt-5-mini (Cloud Routing)...")
    try:
        # We perform a real (but tiny) call to verify it doesn't 400
        content, _, usage = await client.chat(messages, model="gpt-5-mini", max_tokens=10)
        logger.info(f"✅ Success! Response: {content}")
        logger.info(f"✅ Usage: {usage}")
    except Exception as e:
        logger.error(f"❌ Test Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_vision_logic())
