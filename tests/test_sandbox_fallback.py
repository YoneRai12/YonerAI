import os
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_sandbox_download_repo_falls_back_when_download_fails(monkeypatch):
    # Import inside test so monkeypatching works on module globals.
    import src.cogs.tools.sandbox_tools as sbx

    monkeypatch.setenv("ORA_SANDBOX_FALLBACK_ON_DOWNLOAD_FAIL", "1")

    async def _boom(*args, **kwargs):
        raise RuntimeError("download_failed:status=500")

    async def _fake_meta(session, rr):
        return {"ok": True, "stargazers_count": 1, "forks_count": 2, "language": "Python", "default_branch": "main"}

    async def _fake_root(session, rr, *, ref: str, max_entries: int):
        return {"ok": True, "items": [{"name": "README.md"}, {"name": "src"}]}

    async def _fake_readme(session, rr, *, ref: str, max_bytes: int):
        return {"ok": True, "text": "# Hello\nline2\n"}

    monkeypatch.setattr(sbx, "_download_to_file", _boom)
    monkeypatch.setattr(sbx, "_github_repo_metadata", _fake_meta)
    monkeypatch.setattr(sbx, "_github_root_listing", _fake_root)
    monkeypatch.setattr(sbx, "_github_readme", _fake_readme)

    # Bot/session isn't used because we hit fallback.
    out = await sbx.download_repo(
        {"url": "https://github.com/example/repo"},
        message=SimpleNamespace(),
        status_manager=None,
        bot=None,
    )
    assert out.get("fallback_used") is True
    assert "Sandbox Fallback" in (out.get("result") or "")

