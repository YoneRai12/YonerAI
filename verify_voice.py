import discord
import discord.opus
import nacl.secret
import sys
import ctypes.util

print("--- Voice Dependency Check ---")
print(f"Python: {sys.version}")

try:
    print(f"PyNaCl: {nacl.__version__} (Imported successfully)")
except Exception as e:
    print(f"PyNaCl: FAILED ({e})")

if discord.opus.is_loaded():
    print("Opus: LOADED")
else:
    print("Opus: NOT LOADED. Attempting load...")
    try:
        # Try common paths
        lib = ctypes.util.find_library('opus')
        if lib:
            discord.opus.load_opus(lib)
            print(f"Opus: Loaded from {lib}")
        else:
             print("Opus: Could not find library via ctypes.")
             # Try local
             discord.opus.load_opus('libopus-0.x64.dll')
             print("Opus: Loaded local DLL")
    except Exception as e:
        print(f"Opus: Load FAILED ({e})")

print("----------------------------")
