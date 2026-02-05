import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.utils.llm_client import LLMClient
from src.cogs.handlers.chat_handler import ChatHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PlanningTest")

async def test_planning_behavior():
    """
    Tests if the AI generates a plan in Japanese and if our detection logic works.
    """
    logger.info("🚀 Starting Autonomous Planning Test...")

    # 1. Setup Client
    client = LLMClient(base_url="https://api.openai.com/v1", api_key=os.getenv("OPENAI_API_KEY", "EMPTY"), model="gpt-5-mini")

    # Simulate the system context we just updated in chat_handler.py
    system_context = """
[エージェントプロトコル: 実行計画の可視化]
ユーザーの要求が複雑、多段階、または困難な場合：
1. まず最初に、「📋 **実行計画**:」としてこれから行う手順をリストアップしてください。
2. その後、同じレスポンス内で対応するツール呼び出しを生成してください。
"""

    prompt = "Googleのスクショを撮って、そのあとロゴの色を詳しく教えて。最後にその画像を保存して。"

    messages = [
        {"role": "system", "content": system_context},
        {"role": "user", "content": prompt}
    ]

    logger.info("Sending complex request to gpt-5-mini...")
    try:
        content, tool_calls, _ = await client.chat(messages, model="gpt-5-mini", max_tokens=500)

        logger.info(f"--- AI Response Output ---\n{content}\n-------------------------")

        # 2. Check Detection Logic (Manual simulation of chat_handler.py logic)
        has_plan_header = "Execution Plan" in content or "実行計画" in content
        has_list = "1." in content

        if has_plan_header and has_list:
            logger.info("✅ Detection Logic: Success! Plan detected.")

            # Extract lines
            msg_lines = content.split("\n")
            plan_lines = [line.strip() for line in msg_lines if line.strip().startswith("1.") or line.strip().startswith("2.") or line.strip().startswith("-")]
            logger.info(f"✅ Extracted Plan: {plan_lines}")
        else:
            logger.warning("❌ Plan not detected in the format expected.")

        if tool_calls:
            logger.info(f"✅ Success! Tool calls generated: {[tc['function']['name'] for tc in tool_calls]}")
        else:
            logger.warning("⚠️ No tool calls generated. (GPT-5 might be just talking)")

    except Exception as e:
        logger.error(f"❌ Test Failed: {e}")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ OPENAI_API_KEY is missing. Skipping real API test.")
    else:
        asyncio.run(test_planning_behavior())
