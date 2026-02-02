
import sys
import os
import asyncio
from typing import Optional

# Add project root to sys.path
sys.path.append(os.getcwd())

def check_module(name: str) -> bool:
    return name in sys.modules

async def verify_lazy_loading():
    print("--- 1. Initial State ---")
    print(f"Playwright loaded: {check_module('playwright')}")
    print(f"Web Tools loaded: {check_module('src.cogs.tools.web_tools')}")
    print(f"Media Tools loaded: {check_module('src.cogs.tools.media_tools')}")

    print("\n--- 2. Importing ToolHandler ---")
    from src.cogs.tools.tool_handler import ToolHandler
    
    print(f"ToolHandler imported.")
    print(f"Playwright loaded: {check_module('playwright')}")
    print(f"Web Tools loaded: {check_module('src.cogs.tools.web_tools')}")
    
    # Instantiate
    # Mock bot object minimal requirements
    class MockBot:
        def __init__(self):
            self.loop = asyncio.get_event_loop()
            self.config = None
    
    handler = ToolHandler(MockBot(), None)
    print("\n--- 3. Instantiated ToolHandler ---")
    print(f"Web Tools loaded: {check_module('src.cogs.tools.web_tools')}")

    print("\n--- 4. Executing Lazy Tool (web_download) ---")
    # We expect this to FAIL execution because args/bot are mocked/empty, 
    # BUT we are checking if it TRIGGERS the import first.
    
    try:
        # We need to simulate a valid registry lookup.
        # web_download is in registry.
        await handler.execute("web_download", {"url": "http://example.com"}, None, None)
    except Exception as e:
        print(f"Execution expectedly failed (Logic Error): {e}")
        # This is fine, we just want to see if it Imported.

    print(f"Web Tools loaded: {check_module('src.cogs.tools.web_tools')}")
    
    if check_module('src.cogs.tools.web_tools'):
        print("\n✅ SUCCESS: Module was lazily loaded upon execution.")
    else:
        print("\n❌ FAILURE: Module was NOT loaded (or name mismatch).")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(verify_lazy_loading())
