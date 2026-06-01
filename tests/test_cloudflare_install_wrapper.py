from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER_ROOT = ROOT / "cloudflare" / "install-wrapper"


def test_cloudflare_install_wrapper_is_hash_verified_github_bootstrap() -> None:
    worker = (WRAPPER_ROOT / "src" / "worker.js").read_text(encoding="utf-8")

    assert "https://github.com/YoneRai12/YonerAI/releases/latest/download" in worker
    assert "install.ps1" in worker
    assert "install.ps1.sha256" in worker
    assert "Get-FileHash" in worker
    assert "[System.IO.Path]::GetTempPath()" in worker
    assert ".Split()" not in worker
    assert "-split" in worker
    assert "install.ps1 hash mismatch" in worker
    assert "Invoke-VerifiedLocalBootstrap" in worker
    assert "not an executable bootstrap" in worker
    assert "-Execute -Launch" in worker
    assert "cache-control" in worker
    assert "no-store" in worker
    assert "x-content-type-options" in worker
    assert "nosniff" in worker


def test_cloudflare_install_wrapper_does_not_serve_local_pc_or_release_assets() -> None:
    worker = (WRAPPER_ROOT / "src" / "worker.js").read_text(encoding="utf-8")
    readme = (WRAPPER_ROOT / "README.md").read_text(encoding="utf-8")
    combined = worker + "\n" + readme

    forbidden_patterns = (
        r"C:\\Users\\",
        r"/Users/",
        r"127\.0\.0\.1",
        r"localhost",
        r"cloudflared",
        r"YonerAI-0\.6\.3\.zip",
        r"manifest\.v0\.6\.3\.json",
    )
    for pattern in forbidden_patterns:
        assert re.search(pattern, combined, flags=re.IGNORECASE) is None
    assert "Installer assets are served by GitHub Releases" in worker
    assert 'url.pathname === "/"' in worker
    assert 'url.pathname === "/install.ps1"' not in worker
    assert "Do not replace this with" in readme
    assert "Cloudflare Tunnel" in readme


def test_cloudflare_install_wrapper_route_targets_install_yonerai_com() -> None:
    wrangler = (WRAPPER_ROOT / "wrangler.toml").read_text(encoding="utf-8")

    assert 'name = "yonerai-install-wrapper"' in wrangler
    assert 'main = "src/worker.js"' in wrangler
    assert "workers_dev = false" in wrangler
    assert 'pattern = "install.yonerai.com"' in wrangler
    assert "custom_domain = true" in wrangler
