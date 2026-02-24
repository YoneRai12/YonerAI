from __future__ import annotations

import asyncio

import pytest

from src.skills.read_web_page import tool as read_page_tool


class _FakeStream:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    async def iter_chunked(self, _size: int):
        for chunk in self._chunks:
            yield chunk


class _FakeResponse:
    def __init__(self, chunks: list[bytes], *, content_length: int | None = None, charset: str = "utf-8") -> None:
        self.content = _FakeStream(chunks)
        self.content_length = content_length
        self.charset = charset


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://192.168.1.10/",
        "http://[::1]/",
    ],
)
def test_assert_safe_target_blocks_ssrf_hosts(url: str) -> None:
    with pytest.raises(read_page_tool.ReadPageSecurityError):
        asyncio.run(read_page_tool._assert_safe_target(url))


def test_redirect_target_blocked_when_hop_points_to_private_ip() -> None:
    with pytest.raises(read_page_tool.ReadPageSecurityError):
        asyncio.run(read_page_tool._resolve_redirect_target("https://example.com/path", "http://127.0.0.1/admin"))


def test_read_response_text_with_cap_interrupts_on_max_bytes() -> None:
    resp = _FakeResponse([b"abc", b"def", b"ghi"])
    with pytest.raises(read_page_tool.ContentTooLargeError):
        asyncio.run(read_page_tool._read_response_text_with_cap(resp, max_bytes=5))


def test_jina_fallback_default_off(monkeypatch) -> None:
    monkeypatch.delenv(read_page_tool._JINA_FALLBACK_ENV, raising=False)
    assert read_page_tool._is_jina_fallback_enabled() is False


def test_untrusted_boundary_wrapper_masks_query_in_source() -> None:
    out = read_page_tool._format_untrusted_result(
        source_url="https://example.com/path?q=sample_query",
        text="payload",
        via_reader=False,
    )
    assert "Policy: untrusted_web_content" in out
    assert "<untrusted_web_content>" in out
    assert "?q=" not in out
