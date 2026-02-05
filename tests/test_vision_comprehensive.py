import asyncio
import logging
import os
import sys
import json

# Add project root to path
sys.path.append(os.getcwd())

from src.utils.llm_client import LLMClient
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionComprehensiveTest")

async def test_comprehensive_vision():
    """
    Tests both direct attachments and tool-based image feedback.
    """
    logger.info("🚀 Starting Comprehensive Vision & Language Test...")

    # 1. Setup Client
    client = LLMClient(base_url="https://api.openai.com/v1", api_key=os.getenv("OPENAI_API_KEY", "EMPTY"), model="gpt-5-mini")

    dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

    # --- SCENARIO A: Direct Attachment ---
    logger.info("[Scenario A] Testing Direct Attachment...")
    messages_a = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "この画像は何？日本語で答えて。"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{dummy_b64}"}}
            ]
        }
    ]

    try:
        content, _, _ = await client.chat(messages_a, model="gpt-5-mini", max_tokens=50)
        logger.info(f"✅ Scenario A Success! AI Response: {content}")
    except Exception as e:
        logger.error(f"❌ Scenario A Failed: {e}")

    # --- SCENARIO B: Multimodal Tool Feedback (Screenshot Logic) ---
    logger.info("[Scenario B] Testing Multimodal Tool Feedback...")
    # Simulate the message list exactly as endpoints.py builds it
    messages_b = [
        {"role": "system", "content": "あなたは ORA です。日本語で答えてください。"},
        {"role": "user", "content": [{"type": "text", "text": "スクショを撮って解説して。"}]},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call_123", "type": "function", "function": {"name": "web_screenshot", "arguments": '{"url": "https://google.com"}'}}]}
    ]

    # Simulate result_data from bot
    raw_result = {
        "result": "Screenshot sent successfully to Discord.",
        "image_b64": dummy_b64
    }

    # Simulate processing logic in endpoints.py
    result_text = raw_result.get("result")
    b64 = raw_result["image_b64"]
    tool_attachment = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}

    messages_b.append({
        "role": "tool",
        "tool_call_id": "call_123",
        "name": "web_screenshot",
        "content": [
            {"type": "text", "text": result_text},
            tool_attachment
        ]
    })

    try:
        logger.info("Sending tool results to LLM for Scenario B...")
        content, _, _ = await client.chat(messages_b, model="gpt-5-mini", max_tokens=50)
        logger.info(f"✅ Scenario B Success! AI Response: {content}")
    except Exception as e:
        logger.error(f"❌ Scenario B Failed: {e}")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ OPENAI_API_KEY is missing. Skipping real API test.")
    else:
        asyncio.run(test_comprehensive_vision())
