import discord
import discord.opus
import nacl.secret
import sys
import ctypes.util
import os

print("--- Voice Dependency Check ---")
print(f"Python: {sys.version}")

try:
    print(f"PyNaCl: {nacl.__version__} (Imported successfully)")
except Exception as e:
    print(f"PyNaCl: FAILED ({e})")

if discord.opus.is_loaded():
    print("Opus: LOADED")
else:
    print("Opus: NOT LOADED via default loader. Attempting manual load...")
    try:
        # Try finding via ctypes
        lib = ctypes.util.find_library('opus')
        if lib:
            discord.opus.load_opus(lib)
            print(f"Opus: Loaded from {lib}")
        else:
             print("Opus: Could not find library via ctypes.")
             # Try local .x64
             try:
                 dll_path = os.path.abspath('libopus-0.x64.dll')
                 discord.opus.load_opus(dll_path)
                 print(f"Opus: Loaded local DLL ({dll_path})")
             except:
                 # Try local standard
                 try:
                    dll_path = os.path.abspath('libopus-0.dll')
                    discord.opus.load_opus(dll_path)
                    print(f"Opus: Loaded local DLL ({dll_path})")
                 except Exception as e:
                    print(f"Opus: Load FAILED ({e})")
                    print(f"Debug: CWD={os.getcwd()}")
                    print(f"Debug: File Exists? {os.path.exists(dll_path)}")
    except Exception as e:
        print(f"Opus: Load FAILED ({e})")

print("----------------------------")
