# ruff: noqa: E402, F401, B023, B007, B008
import asyncio
import os

from dotenv import load_dotenv

# Load env
load_dotenv()


async def check_search():
    print("--- Checking Search Client ---")
    try:
        from src.utils.search_client import SearchClient

        api_key = os.getenv("SERPAPI_API_KEY")
        print(f"API Key present: {bool(api_key)}")
        if api_key:
            print(f"API Key length: {len(api_key)}")

        client = SearchClient(api_key, "google")
        print(f"Client Enabled: {client.enabled}")

        if not client.enabled:
            print("REASON: Client is disabled (Missing Key or Module)")
            try:
                from serpapi import GoogleSearch

                print("serpapi module: Loaded")
            except ImportError:
                print("serpapi module: MISSING (ImportError)")
            return

        print("Attempting Search...")
        results = await client.search("test")
        print(f"Results: {len(results)}")
        if results:
            print(f"First result: {results[0]}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(check_search())
