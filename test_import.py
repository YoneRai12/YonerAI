# ruff: noqa: E402, F401, B023, B007, B008
import os
import sys

# Set path to current dir
sys.path.append(os.getcwd())

print("Attempting to import src.utils.ui...")
try:
    from src.utils.ui import StatusManager
    print("Success: Imported StatusManager")
except ImportError as e:
    print(f"FAILED to import src.utils.ui: {e}")
except Exception as e:
    print(f"FAILED with unexpected error: {e}")
