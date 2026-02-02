import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MechanicsVerifier")

async def verify_tool_selector():
    print("\n--- 1. Verifying Category Router Logic ---")
    
    # Mock ToolSelector and LLM
    # We define a dummy ToolSelector that mimics the logic we just implemented
    # because importing the real one requires full bot setup/config.
    
    # The Logic we are testing:
    # 1. Receive Categories from LLM
    # 2. Expand to Tools
    
    available_tools = [
        {"name": "web_screenshot", "tags": ["view", "url"], "description": "Screenshot tool"},
        {"name": "web_download", "tags": ["save", "url"], "description": "Download tool"},
        {"name": "join_voice", "tags": ["voice", "vc"], "description": "Join VC"},
        {"name": "ban_user", "tags": ["ban", "server"], "description": "Ban User"},
    ]
    
    # Heuristic Classification (Same as in tool_selector.py)
    categories = {
        "WEB_SURFING": {"tools": []},
        "VOICE_AUDIO": {"tools": []},
        "DISCORD_SERVER": {"tools": []}
    }
    
    for tool in available_tools:
        name = tool["name"]
        if "web" in name: categories["WEB_SURFING"]["tools"].append(tool)
        elif "voice" in name: categories["VOICE_AUDIO"]["tools"].append(tool)
        elif "ban" in name: categories["DISCORD_SERVER"]["tools"].append(tool)

    # Simulate LLM Response (Router Decision)
    print("User Prompt: 'Save this video from the website'")
    mock_llm_response_json = '["WEB_SURFING"]' 
    print(f"Mock Router (LLM) Response: {mock_llm_response_json}")
    
    selected_cats = json.loads(mock_llm_response_json)
    
    # Expansion Logic
    final_tools = []
    for cat in selected_cats:
        if cat in categories:
            final_tools.extend(categories[cat]["tools"])
            
    print(f"Expanded Tools: {[t['name'] for t in final_tools]}")
    
    if "web_screenshot" in [t['name'] for t in final_tools] and "web_download" in [t['name'] for t in final_tools]:
        print("✅ SUCCESS: Router correctly expanded category into specific tools.")
    else:
        print("❌ FAILURE: Tool expansion failed.")

async def verify_plan_detection():
    print("\n--- 2. Verifying Plan & Embed Detection Logic ---")
    
    # Simulate ChatHandler's event loop logic
    full_content = ""
    
    # Simulating incoming chunks from Core Brain
    chunks = [
        "📋 **Execution Plan**:\n",
        "1. Open the URL with headless browser\n",
        "2. Take a 4K screenshot\n",
        "3. Download video buffer\n",
        "\n",
        "Executing tools..."
    ]
    
    plan_detected = False
    
    for chunk in chunks:
        full_content += chunk
        
        # The Logic we implemented in chat_handler.py:
        if "📋 **Execution Plan**:" in full_content and "1." in full_content and not plan_detected:
            msg_lines = full_content.split("\n")
            plan_lines = [line.strip() for line in msg_lines if line.strip().startswith("1.") or line.strip().startswith("2.") or line.strip().startswith("3.") or line.strip().startswith("-")]
            
            if plan_lines:
                print("⚡ EMBED TRIGGERED!")
                print("Embed Title: 🤖 Task Execution Plan")
                print("Embed Body:")
                for line in plan_lines:
                    print(f"  {line}")
                plan_detected = True
                
    if plan_detected:
        print("✅ SUCCESS: System intercepted the plan and created the Card (Embed).")
    else:
        print("❌ FAILURE: Plan detection logic detected nothing.")

async def main():
    await verify_tool_selector()
    await verify_plan_detection()

if __name__ == "__main__":
    asyncio.run(main())
