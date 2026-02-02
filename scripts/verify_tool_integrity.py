
import sys
import os
import asyncio

# Setup path to src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("Step 1: Verifying src.utils.youtube...")
try:
    from src.utils import youtube
    print("✅ src.utils.youtube imported successfully.")
except Exception as e:
    print(f"❌ Failed to import src.utils.youtube: {e}")
    sys.exit(1)

print("Step 2: Verifying src.cogs.tools.tool_handler...")
try:
    # We need to mock discord module if it's not installed in this env, but usually it is.
    # If this runs in the user's env, discord.py should be there.
    from src.cogs.tools import tool_handler
    print("✅ src.cogs.tools.tool_handler imported successfully.")
    
    # Inspect class attributes if possible?
    # Inspect key method existence
    if hasattr(tool_handler.ToolHandler, "_handle_web_screenshot"):
        print("✅ _handle_web_screenshot method exists.")
    else:
        print("❌ _handle_web_screenshot method MISSING.")
        sys.exit(1)

except Exception as e:
    print(f"❌ Failed to import src.cogs.tools.tool_handler: {e}")
    # Check for common mistakes
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Step 3: Verifying src.cogs.ora schema...")
try:
    from src.cogs import ora
    print("✅ src.cogs.ora imported successfully.")
except Exception as e:
    print(f"❌ Failed to import src.cogs.ora: {e}")
    sys.exit(1)

print("\n🎉 INTEGRITY CHECK PASSED: All modified modules import without error.")
