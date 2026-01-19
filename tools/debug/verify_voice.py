import ctypes.util
import os
import sys

import discord
import discord.opus
import nacl.secret

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
             # Check assets/libs first
             dll_path = os.path.abspath(os.path.join('assets', 'libs', 'libopus-0.dll'))
             if not os.path.exists(dll_path):
                 # Fallback to current directory if not found in assets/libs
                 dll_path = os.path.abspath('libopus-0.dll')
            
             if os.path.exists(dll_path):
                 try:
                    discord.opus.load_opus(dll_path)
                    print(f"Opus: Loaded local DLL ({dll_path})")
                 except Exception as e:
                    print(f"Opus: Load FAILED ({e})")
                    print(f"Debug: CWD={os.getcwd()}")
                    print(f"Debug: File Exists? {os.path.exists(dll_path)}")
    except Exception as e:
        print(f"Opus: Load FAILED ({e})")

print("----------------------------")
