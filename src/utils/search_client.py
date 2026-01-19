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
        # Check SerpApi first
        if self._api_key and GoogleSearch is not None:
            return True
        # Check DuckDuckGo
        try:
            from duckduckgo_search import DDGS

            return True
        except ImportError:
            return False

    async def search(
        self, query: str, *, limit: int = 5, engine: Optional[str] = None, gl: str = "jp", hl: str = "ja"
    ) -> Sequence[dict]:
        start_time = time.monotonic()
        deadline = start_time + 30.0  # Total budget 30s

        async with _SEM:
            # Try SerpApi first if enabled
            if self.enabled:
                for attempt in range(1, 4):  # Max 3 attempts
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

                        def _request() -> List[dict]:
                            search = GoogleSearch(params)
                            response = search.get_dict()
                            results: List[dict] = []

                            # Handle Shopping Results
                            if params["engine"] == "google_shopping":
                                for item in response.get("shopping_results", [])[:limit]:
                                    title = item.get("title") or "(no title)"
                                    price = item.get("price") or ""
                                    link = item.get("link") or ""
                                    thumb = item.get("thumbnail") or ""
                                    results.append(
                                        {
                                            "title": f"{title} ({price})",
                                            "link": link,
                                            "snippet": price,  # Use price as snippet for shopping
                                            "thumbnail": thumb,
                                        }
                                    )
                            else:
                                # Handle Organic Results
                                for item in response.get("organic_results", [])[:limit]:
                                    title = item.get("title") or "(no title)"
                                    link = item.get("link") or ""
                                    snippet = item.get("snippet") or ""
                                    thumb = item.get("thumbnail") or ""
                                    # Fallback for thumbnail if not direct
                                    if not thumb and "pagemap" in item and "cse_image" in item["pagemap"]:
                                        try:
                                            thumb = item["pagemap"]["cse_image"][0]["src"]
                                        except (IndexError, KeyError):
                                            pass

                                    results.append(
                                        {"title": title, "link": link, "snippet": snippet, "thumbnail": thumb}
                                    )
                            return results

                        # Enforce per-attempt timeout (min 10s or remaining)
                        timeout = min(10.0, remaining)
                        return await asyncio.wait_for(asyncio.to_thread(_request), timeout=timeout)

                    except asyncio.TimeoutError:
                        logger.warning(f"SerpApi attempt {attempt} timed out.")
                    except Exception as e:
                        logger.warning(f"SerpApi attempt {attempt} failed: {e}")
                        await asyncio.sleep(1)  # Simple backoff

            # Fallback to DuckDuckGo
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning("Search budget exceeded, skipping DuckDuckGo fallback.")
                return []

            try:
                from duckduckgo_search import DDGS

                def _ddg_request() -> List[dict]:
                    results: List[dict] = []
                    with DDGS() as ddgs:
                        # region="jp-jp" for Japan
                        ddg_results = list(ddgs.text(query, region="jp-jp", max_results=limit))
                        for item in ddg_results:
                            title = item.get("title") or "(no title)"
                            link = item.get("href") or ""
                            snippet = item.get("body") or ""
                            results.append(
                                {
                                    "title": title,
                                    "link": link,
                                    "snippet": snippet,
                                    "thumbnail": "",  # DDG text search doesn't easily give thumbnails
                                }
                            )
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
