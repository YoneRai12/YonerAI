
import asyncio
import os
import sys

# Add src to path
# tools/debug/script.py -> tools/debug -> tools -> root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils.gtts_client import GTTSClient


async def test_gtts():
    print("Testing GTTSClient...")
    client = GTTSClient()
    try:
        text = "This is a test."
        audio = await client.synthesize(text)
        print(f"GTTS Success: Generated {len(audio)} bytes.")
        
        with open("test_gtts.mp3", "wb") as f:
            f.write(audio)
        print("Saved to test_gtts.mp3")
        
    except Exception as e:
        print(f"GTTS Failed: {e}")

if __name__ == "__main__":
    # asyncio.run(test_edge_tts())
    asyncio.run(test_gtts())
