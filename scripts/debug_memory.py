import asyncio
import sys
from pathlib import Path

# Add core to path
root = Path(__file__).parent.parent
sys.path.append(str(root / "core" / "src"))

async def test_memory_store_direct():
    print("Testing MemoryStore directly...")
    from ora_core.brain.memory import memory_store
    
    test_id = "test_verification_id"
    profile = await memory_store.get_or_create_profile(test_id, "Test Runner")
    print(f"Profile created: {profile['name']}")
    
    # Verify file
    path = Path(r"L:\ORA_Memory\users") / f"{test_id}.json"
    if path.exists():
        print(f"✅ SUCCESS: File exists at {path}")
    else:
        print(f"❌ FAILED: File NOT found at {path}")
        print(f"Current Directory: {Path.cwd()}")
    
if __name__ == "__main__":
    asyncio.run(test_memory_store_direct())
