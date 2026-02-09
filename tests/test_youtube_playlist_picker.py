from __future__ import annotations

from typing import Any, Dict, List, Tuple


def test_is_youtube_playlist_url() -> None:
    import src.utils.youtube as yt

    assert yt.is_youtube_playlist_url("https://www.youtube.com/playlist?list=PL1234567890")
    assert yt.is_youtube_playlist_url("https://www.youtube.com/watch?v=abc123&list=PL1234567890&index=2")
    assert not yt.is_youtube_playlist_url("https://www.youtube.com/watch?v=abc123")
    assert not yt.is_youtube_playlist_url("https://example.com/?list=PL1234567890")


def test_get_youtube_playlist_entries_sync(monkeypatch) -> None:
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
            # Minimal playlist shape
            return {
                "title": "My Playlist",
                "entries": [
                    {"id": "aaa111", "title": "T1", "duration": 61, "webpage_url": "https://www.youtube.com/watch?v=aaa111&list=PLx"},
                    {"id": "bbb222", "title": "T2", "duration": 120, "webpage_url": "https://www.youtube.com/watch?v=bbb222&list=PLx"},
                ],
            }

    class _FakeMod:
        YoutubeDL = _FakeYDL

    monkeypatch.setattr(yt, "yt_dlp", _FakeMod())

    title, entries = yt._get_youtube_playlist_entries_sync("https://www.youtube.com/playlist?list=PLx", limit=1, proxy=None)
    assert title == "My Playlist"
    assert called["download"] is False
    assert len(entries) == 1
    # Ensure we strip playlist params from the picked entry URL (watch-only URL).
    assert entries[0]["webpage_url"] == "https://www.youtube.com/watch?v=aaa111"

