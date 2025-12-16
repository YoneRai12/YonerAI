
import asyncio
import os
import sys
# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

async def verify_all_tools():
    print("=== ORA Bot Tool Verification ===")
    
    # 1. Search Client (Fixed)
    print("\n[1] Checking Search (Google/DDG)...")
    try:
        from src.utils.search_client import SearchClient
        s = SearchClient(os.getenv("SERPAPI_API_KEY"), "google")
        print(f"   -> Enabled: {s.enabled}")
        if s.enabled:
            res = await s.search("What requires VRAM?", limit=1)
            if res:
                print(f"   -> Result: {res[0].get('title')} ({len(res)} results)")
            else:
                print("   -> Result: [] (Empty list)")
        else:
            print("   -> Result: DISABLED (Failed check)")
    except Exception as e:
        print(f"   -> Error: {e}")

    # 2. Vision API (Import Check)
    print("\n[2] Checking Vision API...")
    try:
        # Just check import
        from src.utils.image_tools import analyze_image_v2
        print("   -> Module `image_tools`: OK")
    except ImportError:
        print("   -> Module `image_tools`: FAILED (ImportError)")
    except Exception as e:
        print(f"   -> Error: {e}")

    # 3. Media/Voice
    print("\n[3] Checking Voice Dependencies...")
    op_path = "libopus-0.dll" # default check
    exists = any(os.path.exists(p) for p in [op_path, f"C:\\Windows\\System32\\{op_path}"]) 
    print(f"   -> libopus-0.dll: {'Found' if exists else 'Not found locally (might be in PATH)'}")

    # 4. ComfyUI Connection
    print("\n[4] Checking ComfyUI (Port 8188)...")
    try:
        _, writer = await asyncio.open_connection('127.0.0.1', 8188)
        writer.close()
        await writer.wait_closed()
        print("   -> Port 8188: OPEN (ComfyUI Running)")
    except (ConnectionRefusedError, OSError):
        print("   -> Port 8188: CLOSED (ComfyUI Not Running)")

    # 5. vLLM Connection
    print("\n[5] Checking vLLM (Port 8001)...")
    try:
        _, writer = await asyncio.open_connection('127.0.0.1', 8001)
        writer.close()
        await writer.wait_closed()
        print("   -> Port 8001: OPEN (vLLM Running)")
    except (ConnectionRefusedError, OSError):
        print("   -> Port 8001: CLOSED (vLLM Not Running)")

if __name__ == "__main__":
    asyncio.run(verify_all_tools())
