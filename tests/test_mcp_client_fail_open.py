from __future__ import annotations

import io

import pytest

from src.utils.mcp_client import MCPStdioClient


class _FakeProc:
    def __init__(self, stderr_bytes: bytes):
        self.stderr = io.BytesIO(stderr_bytes)
        self._terminated = 0
        self._poll = None

    def poll(self):
        return self._poll

    def terminate(self):
        self._terminated += 1
        self._poll = 0


def test_stderr_win32sysloader_disables_server_fail_open():
    client = MCPStdioClient(name="artist", command="python -m whatever")
    proc = _FakeProc(b"ImportError: cannot import name _win32sysloader\r\n")
    client._proc = proc  # test hook

    client._stderr_loop()

    assert client._disabled is True
    assert client._disabled_reason == "mcp_import_error_win32sysloader"
    assert proc._terminated == 1


@pytest.mark.asyncio
async def test_list_tools_breaks_early_when_disabled(monkeypatch):
    client = MCPStdioClient(name="artist", command="python -m whatever")
    client._disabled = True
    client._disabled_reason = "mcp_import_error_win32sysloader"
    calls = {"count": 0}

    async def _fake_request(method, params=None, timeout=60):
        calls["count"] += 1
        raise RuntimeError("disabled")

    monkeypatch.setattr(client, "request", _fake_request)

    tools = await client.list_tools()
    assert tools == []
    assert calls["count"] == 1
