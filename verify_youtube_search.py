
import asyncio
import logging
import sys
import os

# Setup path
sys.path.append(os.getcwd())

from src.utils.youtube import get_youtube_audio_stream_url

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    query = "Chaos Boogie"
    print(f"Testing search for: {query}")
    
    try:
        url, title, duration = await get_youtube_audio_stream_url(query)
        if url:
            print(f"SUCCESS: Found video '{title}'")
            print(f"URL: {url[:50]}...")
            print(f"Duration: {duration}s")
        else:
            print("FAILURE: No results found.")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
