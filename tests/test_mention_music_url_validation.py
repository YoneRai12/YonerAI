from __future__ import annotations


def test_is_trusted_youtube_url_accepts_real_youtube_hosts() -> None:
    from src.utils.youtube import is_trusted_youtube_url

    assert is_trusted_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert is_trusted_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    assert is_trusted_youtube_url("https://music.youtube.com/watch?v=dQw4w9WgXcQ")


def test_is_trusted_youtube_url_rejects_ssrf_style_bypass_urls() -> None:
    from src.utils.youtube import is_trusted_youtube_url

    assert not is_trusted_youtube_url("http://youtube.com@169.254.169.254/")
    assert not is_trusted_youtube_url("http://127.0.0.1/?q=youtube.com")
    assert not is_trusted_youtube_url("https://youtube.com.evil.example/watch?v=abc")
    assert not is_trusted_youtube_url("spotify:track:123")
