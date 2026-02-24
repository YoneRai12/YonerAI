from __future__ import annotations

from src.utils.redaction import redact_text


def test_redact_text_strips_query_from_urls() -> None:
    raw = "fetch https://example.com/api?token=abc123&user=alice now"
    out = redact_text(raw)
    assert "abc123" not in out
    assert "?token=" not in out
    assert "?[REDACTED_QUERY]" in out


def test_redact_text_keeps_url_without_query() -> None:
    raw = "https://example.com/path only"
    out = redact_text(raw)
    assert out == raw
