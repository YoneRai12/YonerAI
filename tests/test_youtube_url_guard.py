from __future__ import annotations

from typing import Any, Dict


def test_get_youtube_audio_rejects_non_youtube_url(monkeypatch) -> None:
    import src.utils.youtube as yt

    called: Dict[str, Any] = {"extract": 0}

    class _FakeYDL:
        def __init__(self, opts: dict):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, query: str, download: bool = False):
            called["extract"] += 1
            return {"url": "stream", "title": "x", "duration": 1}

    class _FakeMod:
        YoutubeDL = _FakeYDL

    monkeypatch.setattr(yt, "yt_dlp", _FakeMod())

    stream_url, title, duration = yt._get_youtube_audio_stream_url_sync("http://127.0.0.1:9")

    assert stream_url is None
    assert title is None
    assert duration is None
    assert called["extract"] == 0


def test_get_youtube_audio_allows_youtube_url(monkeypatch) -> None:
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
            return {"url": "stream", "title": "x", "duration": 1}

    class _FakeMod:
        YoutubeDL = _FakeYDL

    monkeypatch.setattr(yt, "yt_dlp", _FakeMod())

    stream_url, title, duration = yt._get_youtube_audio_stream_url_sync("https://www.youtube.com/watch?v=abc123")

    assert called["query"].startswith("https://www.youtube.com/watch")
    assert stream_url == "stream"
    assert title == "x"
    assert duration == 1
