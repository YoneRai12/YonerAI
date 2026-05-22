from __future__ import annotations

from src.utils.redaction import redact_text


def test_redact_text_strips_query_from_urls() -> None:
    raw = "fetch https://example.com/api?q=abc123&user=alice now"
    out = redact_text(raw)
    assert "abc123" not in out
    assert "?q=" not in out
    assert "?[REDACTED_QUERY]" in out


def test_redact_text_keeps_url_without_query() -> None:
    raw = "https://example.com/path only"
    out = redact_text(raw)
    assert out == raw


def test_redact_text_redacts_discord_webhooks() -> None:
    webhook_id = "1234567890"
    webhook_secret = "abcdefghijklmnopqrstuvwxyz"
    raw = f"send https://discord.com/api/webhooks/{webhook_id}/{webhook_secret} now"
    out = redact_text(raw)
    assert "discord.com/api/webhooks" not in out
    assert "1234567890" not in out
    assert out == "send [REDACTED] now"
