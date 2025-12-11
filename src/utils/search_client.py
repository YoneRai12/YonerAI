"""Wrapper around SerpApi (or similar) web search APIs."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional, Sequence, Tuple

try:
    from serpapi import GoogleSearch
except ImportError:  # pragma: no cover - optional dependency
    GoogleSearch = None  # type: ignore

logger = logging.getLogger(__name__)

SearchResult = Tuple[str, str]

# Global semaphore for rate limiting
_SEM = asyncio.Semaphore(10)

class SearchClient:
    """Perform web searches using SerpApi when configured."""

    def __init__(self, api_key: Optional[str], engine: Optional[str]) -> None:
        self._api_key = api_key
        self._engine = engine or "google"

    @property
    def enabled(self) -> bool:
        return bool(self._api_key and GoogleSearch is not None)

    async def search(self, query: str, *, limit: int = 5, engine: Optional[str] = None, gl: str = "jp", hl: str = "ja") -> Sequence[SearchResult]:
        start_time = time.monotonic()
        deadline = start_time + 30.0 # Total budget 30s

        async with _SEM:
            # Try SerpApi first if enabled
            if self.enabled:
                for attempt in range(1, 4): # Max 3 attempts
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        logger.warning("Search budget exceeded before SerpApi call.")
                        break
                    
                    try:
                        params = {
                            "q": query,
                            "api_key": self._api_key,
                            "engine": engine or self._engine,
                            "gl": gl,
                            "hl": hl,
                        }

                        def _request() -> List[SearchResult]:
                            search = GoogleSearch(params)
                            response = search.get_dict()
                            results: List[SearchResult] = []
                            
                            # Handle Shopping Results
                            if params["engine"] == "google_shopping":
                                for item in response.get("shopping_results", [])[:limit]:
                                    title = item.get("title") or "(no title)"
                                    price = item.get("price") or ""
                                    link = item.get("link") or ""
                                    results.append((f"{title} ({price})", link))
                            else:
                                # Handle Organic Results
                                for item in response.get("organic_results", [])[:limit]:
                                    title = item.get("title") or "(no title)"
                                    link = item.get("link") or ""
                                    results.append((title, link))
                            return results

                        # Enforce per-attempt timeout (min 10s or remaining)
                        timeout = min(10.0, remaining)
                        return await asyncio.wait_for(asyncio.to_thread(_request), timeout=timeout)
                        
                    except asyncio.TimeoutError:
                        logger.warning(f"SerpApi attempt {attempt} timed out.")
                    except Exception as e:
                        logger.warning(f"SerpApi attempt {attempt} failed: {e}")
                        await asyncio.sleep(1) # Simple backoff

            # Fallback to DuckDuckGo
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                 logger.warning("Search budget exceeded, skipping DuckDuckGo fallback.")
                 return []

            try:
                from duckduckgo_search import DDGS
                
                def _ddg_request() -> List[SearchResult]:
                    results: List[SearchResult] = []
                    with DDGS() as ddgs:
                        # region="jp-jp" for Japan
                        ddg_results = list(ddgs.text(query, region="jp-jp", max_results=limit))
                        for item in ddg_results:
                            title = item.get("title") or "(no title)"
                            link = item.get("href") or ""
                            results.append((title, link))
                    return results

                timeout = min(10.0, remaining)
                return await asyncio.wait_for(asyncio.to_thread(_ddg_request), timeout=timeout)
                
            except ImportError:
                logger.error("duckduckgo-search not installed.")
                if not self.enabled:
                    raise RuntimeError("検索APIが設定されておらず、DuckDuckGoもインストールされていません。")
                return []
            except asyncio.TimeoutError:
                logger.error("DuckDuckGo search timed out.")
                return []
            except Exception as e:
                logger.error(f"DuckDuckGo search failed: {e}")
                return []
