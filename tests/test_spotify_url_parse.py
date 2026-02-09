from __future__ import annotations


def test_parse_spotify_url_http() -> None:
    from src.utils.spotify import parse_spotify_url

    assert parse_spotify_url("https://open.spotify.com/playlist/PL123?si=abc") == ("playlist", "PL123")
    assert parse_spotify_url("https://open.spotify.com/album/ALB456") == ("album", "ALB456")
    assert parse_spotify_url("https://open.spotify.com/track/TRK789") == ("track", "TRK789")
    assert parse_spotify_url("https://example.com/playlist/PL123") == (None, None)


def test_parse_spotify_url_uri() -> None:
    from src.utils.spotify import parse_spotify_url

    assert parse_spotify_url("spotify:playlist:PL123") == ("playlist", "PL123")
    assert parse_spotify_url("spotify:track:TRK789") == ("track", "TRK789")


def test_is_spotify_playlist_like() -> None:
    from src.utils.spotify import is_spotify_playlist_like

    assert is_spotify_playlist_like("https://open.spotify.com/playlist/PL123")
    assert is_spotify_playlist_like("https://open.spotify.com/album/ALB456")
    assert not is_spotify_playlist_like("https://open.spotify.com/track/TRK789")

