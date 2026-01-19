# ruff: noqa: E402, F401, B023, B007, B008
import os
import sys

sys.path.append(os.getcwd())

print("Attempting to import src.cogs.handlers.chat_handler...")
try:
    import src.cogs.handlers.chat_handler as ch
    print("Success: Imported chat_handler")
except ImportError as e:
    print(f"FAILED to import chat_handler: {e}")
except Exception as e:
    print(f"FAILED with unexpected error: {e}")

print("Attempting to call handle_prompt (mock)...")
try:
    # Just check imports inside the function/file
    from src.utils.ui import StatusManager
    print("Success: Imported StatusManager from utils.ui")
except ImportError as e:
    print(f"FAILED to import StatusManager: {e}")
