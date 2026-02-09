from __future__ import annotations

from typing import Any, Dict, List


def test_search_youtube_prefix(monkeypatch) -> None:
    import src.utils.youtube as yt

    called: Dict[str, Any] = {}

    class _FakeYDL:
        def __init__(self, opts: dict):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, query: str, download: bool = False):
            called["query"] = query
            called["download"] = download
            # Minimal "search results" shape
            return {
                "entries": [
                    {"id": "abc123", "title": "A", "duration": 120, "webpage_url": "https://www.youtube.com/watch?v=abc123"},
                    {"id": "def456", "title": "B", "duration": 90, "webpage_url": "https://www.youtube.com/watch?v=def456"},
                ]
            }

    class _FakeMod:
        YoutubeDL = _FakeYDL

    monkeypatch.setattr(yt, "yt_dlp", _FakeMod())

    res: List[Dict[str, Any]] = yt._search_youtube_sync("hello world", limit=3, proxy=None)
    assert called["query"].startswith("ytsearch3:")
    assert "hello world" in called["query"]
    assert len(res) == 2
    assert res[0]["webpage_url"].startswith("https://")

