import asyncio
import logging
import os
from dotenv import load_dotenv
from src.utils.search_client import SearchClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_search():
    load_dotenv()
    api_key = os.getenv("SEARCH_API_KEY")
    engine = os.getenv("SEARCH_ENGINE", "google")
    
    print(f"API Key present: {bool(api_key)}")
    print(f"Engine: {engine}")
    
    client = SearchClient(api_key, engine)
    
    if not client.enabled:
        print("SearchClient is NOT enabled. Check SEARCH_API_KEY.")
        return

    query = "YoneRai12"
    print(f"Searching for: {query}")
    
    try:
        results = await client.search(query, limit=3)
        print(f"Found {len(results)} results:")
        for title, link in results:
            print(f"- {title}: {link}")
    except Exception as e:
        print(f"Search failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())
