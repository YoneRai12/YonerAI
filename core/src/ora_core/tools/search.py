import asyncio
import logging
import time
import hashlib
import os
from typing import List, Dict, Any, Optional
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# Global In-Memory Cache for Search Results
# Key: user_id:provider:query_hash
# Value: {"sources": [...], "expires_at": float}
_search_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SEC = 300  # 5 minutes

# Environment validation flag
_search_enabled = True
_search_disabled_reason = ""

def _check_search_env():
    """Graceful validation: disable search if keys are missing, but don't crash."""
    global _search_enabled, _search_disabled_reason
    api_key = os.getenv("SEARCH_API_KEY")
    cx = os.getenv("GOOGLE_SEARCH_CX")
    engine = os.getenv("SEARCH_ENGINE", "google")
    if engine == "google" and (not api_key or not cx):
        _search_enabled = False
        _search_disabled_reason = "SEARCH_API_KEY or GOOGLE_SEARCH_CX not set. Using DDG fallback."
        logger.warning(_search_disabled_reason)
    elif engine == "ddg":
        pass # DDG doesn't need keys
    else:
        _search_enabled = True

_check_search_env()

class SearchProvider:
    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        raise NotImplementedError

class DDGSearchProvider(SearchProvider):
    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        try:
            results = DDGS().text(query, max_results=num_results)
            if not results:
                return []
            
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"DDG Search failed: {e}")
            return []

class GoogleSearchProvider(SearchProvider):
    def __init__(self, api_key: str, cx: Optional[str] = None):
        self.api_key = api_key
        self.cx = cx

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("Google Search API Key missing. Falling back to DDG.")
            return await DDGSearchProvider().search(query, num_results)
        
        # Note: Implementation for Google Custom Search API
        # Needs 'aiohttp' or similar, using loop.run_in_executor for simple sync blocking if needed
        # For ORA, we expect aiohttp.
        import aiohttp
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cx or "", # CX is often required for Google Custom Search
            "q": query,
            "num": num_results
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("items", [])
                        return [
                            {
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "snippet": item.get("snippet", "")
                            }
                            for item in items
                        ]
                    else:
                        err_text = await resp.text()
                        logger.error(f"Google Search error ({resp.status}): {err_text}")
                        return []
        except Exception as e:
            logger.error(f"Google Search failed: {e}")
            return []

async def execute_search(user_id: str, query: str, provider_name: str = "google") -> Dict[str, Any]:
    """
    Executes search with caching and summarization.
    """
    import json
    start_time = time.time()
    
    # 1. Normalize Query and Generate Strict Cache Key
    query_norm = " ".join(query.strip().lower().split()) # Compress whitespace
    params = {"num": 5, "provider": provider_name}
    params_str = json.dumps(params, sort_keys=True)
    hash_input = f"{user_id}:{provider_name}:{query_norm}:{params_str}"
    query_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    cache_key = query_hash
    
    cached = _search_cache.get(cache_key)
    if cached and cached["expires_at"] > time.time():
        logger.info(f"Search cache hit for: {query_norm}")
        return {
            "ok": True,
            "content": _format_mcp_content(cached["sources"]),
            "structuredContent": {"sources": cached["sources"]},
            "metrics": {
                "latency_ms": int((time.time() - start_time) * 1000),
                "cache_hit": True
            }
        }

    # 2. Select Provider (Fallback to DDG if env not set)
    effective_provider = provider_name
    if provider_name == "google" and not _search_enabled:
        effective_provider = "ddg" # Graceful fallback

    if effective_provider == "google":
        api_key = os.getenv("SEARCH_API_KEY")
        cx = os.getenv("GOOGLE_SEARCH_CX") 
        provider = GoogleSearchProvider(api_key, cx)
    else:
        provider = DDGSearchProvider()

    # 3. Execute
    results = await provider.search(query_norm, num_results=5)
    
    # 4. Structure Sources with rank and provider
    sources = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("snippet", ""),
            "rank": i + 1,
            "provider": effective_provider
        }
        for i, r in enumerate(results)
    ]
    
    # 5. Save to Cache
    _search_cache[cache_key] = {
        "sources": sources,
        "expires_at": time.time() + CACHE_TTL_SEC
    }
    
    latency = int((time.time() - start_time) * 1000)
    
    if not sources:
        return {
            "ok": True,
            "content": [{"type": "text", "text": "No search results found."}],
            "structuredContent": {"sources": []},
            "error": None,
            "metrics": {"latency_ms": latency, "cache_hit": False}
        }

    return {
        "ok": True,
        "content": _format_mcp_content(sources),
        "structuredContent": {"sources": sources},
        "error": None,
        "metrics": {
            "latency_ms": latency,
            "cache_hit": False
        }
    }

def _format_mcp_content(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format sources into MCP standard content atoms."""
    content = []
    for s in sources:
        item_text = f"[{s.get('rank', '?')}] {s['title']}\nURL: {s['url']}\nSnippet: {s['snippet']}\n"
        content.append({"type": "text", "text": item_text})
    return content
