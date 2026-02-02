import asyncio
import os
import sys

# Mocking the path to import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.cogs.handlers.tool_selector import ToolSelector

class MockBot:
    def __init__(self):
        self.config = type('Config', (), {'openai_api_key': os.getenv("OPENAI_API_KEY")})()

async def verify_cross_lingual():
    bot = MockBot()
    selector = ToolSelector(bot)
    
    # Test cases: Japanese prompts that require 'Concept' mapping
    test_cases = [
        "このサイトを開いて",   # Open this site -> WEB_SURFING
        "これを保存して",       # Save this -> WEB_SURFING (Download)
        "画面を見せて",         # Show screen -> WEB_SURFING (Screenshot)
        "通話に入って",         # Join call -> VOICE_AUDIO
    ]
    
    # Mock tools (simplified)
    tools = [
        {"name": "web_navigate", "tags": ["open"]},
        {"name": "web_download", "tags": ["save"]},
        {"name": "web_screenshot", "tags": ["screen"]},
        {"name": "join_voice", "tags": ["vc"]}
    ]

    print("--- Cross-Lingual Router Verification ---")
    for prompt in test_cases:
        print(f"\nPrompt: {prompt}")
        cats = await selector.select_tools(prompt, tools)
        
        # We want to see if the LLM selected the category BEFORE fallback
        # Note: The real select_tools has fallback baked in. 
        # But if the log shows "Router returned empty" then LLM failed.
        # We can't see internal logs easily here without configuring logging, 
        # but the result is what matters.
        
        print(f"Selected: {[t['name'] for t in cats]}")

if __name__ == "__main__":
    asyncio.run(verify_cross_lingual())
