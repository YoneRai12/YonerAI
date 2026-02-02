import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Attempting to import src.utils.browser...")
try:
    from src.utils.browser import browser_manager
    print("✅ Success: browser_manager imported.")
except ImportError as e:
    print(f"❌ ImportError: {e}")
except Exception as e:
    print(f"❌ Exception: {e}")

print("Attempting to import src.cogs.tools.tool_handler...")
try:
    from src.cogs.tools.tool_handler import ToolHandler
    print("✅ Success: ToolHandler imported.")
except Exception as e:
    print(f"❌ ToolHandler Import Failed: {e}")
