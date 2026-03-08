from __future__ import annotations

import importlib


def _reload_agent_trace(monkeypatch, value: str | None):
    if value is None:
        monkeypatch.delenv("ORA_TRACE_ENABLED", raising=False)
    else:
        monkeypatch.setenv("ORA_TRACE_ENABLED", value)
    import src.utils.agent_trace as agent_trace

    return importlib.reload(agent_trace)


def test_trace_disabled_by_default(monkeypatch) -> None:
    agent_trace = _reload_agent_trace(monkeypatch, None)
    assert agent_trace._is_enabled() is False


def test_sanitize_text_redacts_url_and_inline_secret(monkeypatch) -> None:
    agent_trace = _reload_agent_trace(monkeypatch, "1")
    payload = {
        "prompt": "db=https://example.com?api_key=LEAKME and token=abc123",
        "args": {"url": "https://x.test/path?password=hunter2"},
    }

    sanitized = agent_trace._sanitize(payload)

    assert sanitized["prompt"].count("[REDACTED]") >= 2
    assert "LEAKME" not in sanitized["prompt"]
    assert "abc123" not in sanitized["prompt"]
    assert "hunter2" not in sanitized["args"]["url"]
