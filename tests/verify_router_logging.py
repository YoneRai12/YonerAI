
import sys
import os
import asyncio
import logging
import json
from unittest.mock import MagicMock, AsyncMock

# Add project root
sys.path.append(os.getcwd())

from src.cogs.handlers.tool_selector import ToolSelector

# Mock Logging to capture output
class MockLogger(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
    
    def emit(self, record):
        self.records.append(record)

async def verify_s6_features():
    print("--- S6 Verification: Structured Logging & Prefix Stabilization ---")
    
    # 1. Setup Mock Bot & Logger
    mock_bot = MagicMock()
    mock_bot.config.openai_api_key = "sk-fake-key"
    mock_bot.config.openai_base_url = "https://api.openai.com/v1"
    
    # Capture logs
    logger = logging.getLogger("src.cogs.handlers.tool_selector")
    logger.setLevel(logging.INFO)
    mock_handler = MockLogger()
    logger.addHandler(mock_handler)
    
    selector = ToolSelector(mock_bot)
    
    # Mock LLM Client to return valid JSON
    selector.llm_client.chat = AsyncMock(return_value=('["WEB_READ", "SYSTEM_UTIL"]', {}, {}))
    
    # 2. Run Selection
    print("\nRunning Tool Selection...")
    tools = await selector.select_tools("Navigate to google.com and save screenshot")
    
    # 3. Verify Structured Log
    print("\n--- Verifying Structured Log ---")
    found_log = False
    for record in mock_handler.records:
        if record.msg == "🧩 Router Decision":
            found_log = True
            extra = getattr(record, "router_event", None)
            if extra:
                print("✅ Found Structured Log Payload:")
                print(json.dumps(extra, indent=2))
                
                # Check fields
                assert "request_id" in extra
                assert "router_roundtrip_ms" in extra
                assert "router_local_ms" in extra
                assert "prefix_hash" in extra
                assert "tools_bundle_id" in extra
                assert extra["selected_categories"] == ["WEB_READ", "SYSTEM_UTIL"]
                assert extra["retry_count"] == 0
                assert extra["fallback_triggered"] is False
                
                print(f"✅ Prefix Hash: {extra['prefix_hash']}")
                print(f"✅ Tools Bundle ID: {extra['tools_bundle_id']}")
                print(f"✅ Timing: Roundtrip={extra['router_roundtrip_ms']}ms, Local={extra['router_local_ms']}ms")
            else:
                print("❌ Log message found but 'router_event' extra missing.")
                
    if not found_log:
        print("❌ '🧩 Router Decision' log not found.")

    # 4. Verify Prefix Stabilization (Compare two runs)
    print("\n--- Verifying Hash Stability ---")
    # Run again identical input
    await selector.select_tools("Navigate to google.com and save screenshot")
    
    hashes = []
    ids = []
    
    for record in mock_handler.records[-2:]: # Last 2 records (1 from previous run, 1 from this)
        if hasattr(record, "router_event"):
            hashes.append(record.router_event["prefix_hash"])
            ids.append(record.router_event["tools_bundle_id"])
            
    if len(hashes) >= 2:
        if hashes[-1] == hashes[-2]:
             print("✅ Prefix Hash is STABLE across calls.")
        else:
             print(f"❌ Prefix Hash CHANGED: {hashes[-2]} -> {hashes[-1]}")
             
        if ids[-1] == ids[-2]:
             print("✅ Tools Bundle ID is STABLE across calls.")
        else:
             print(f"❌ Tools Bundle ID CHANGED: {ids[-2]} -> {ids[-1]}")
    else:
        print("❌ Could not compare hashes (logs missing).")

    print("\n✅ Verification Complete.")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(verify_s6_features())
