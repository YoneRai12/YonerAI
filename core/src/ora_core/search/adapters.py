from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SearchRequest:
    query: str
    mode: str = "mock"


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = "mock"

    def to_public_dict(self) -> dict[str, str]:
        return asdict(self)


@runtime_checkable
class SearchAdapter(Protocol):
    adapter_id: str

    def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        ...


class MockSearchAdapter:
    adapter_id = "mock"

    def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        query = " ".join(str(request.query or "").split())[:120] or "yonerai"
        return (
            SearchResult(
                title="YonerAI public runtime fixture",
                url="https://example.invalid/yonerai/public-runtime",
                snippet=f"Deterministic mock search result for: {query}",
            ),
            SearchResult(
                title="YonerAI alpha safety fixture",
                url="https://example.invalid/yonerai/alpha-safety",
                snippet="Mock fixture only. No network request was performed.",
            ),
        )


LIVE_SEARCH_ACTIONS_NOT_PERFORMED = (
    "no network request",
    "no external search provider call",
    "no result scraping",
    "no credential lookup",
)


def build_live_search_disabled_boundary(query: str) -> dict[str, object]:
    return {
        "status": "disabled",
        "reason": "live_search_not_implemented",
        "message": "Live search is disabled in this public alpha slice; no network request was performed.",
        "query": " ".join(str(query or "").split()),
        "requires_explicit_live_provider": True,
        "default_mode": "mock",
        "network_performed": False,
        "actions_not_performed": list(LIVE_SEARCH_ACTIONS_NOT_PERFORMED),
    }
