from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_current_truth_has_public_safe_anchor_fields() -> None:
    text = (ROOT / "CURRENT_TRUTH.md").read_text(encoding="utf-8")

    assert re.search(r"latest_stable_tag: v\d+\.\d+\.\d+", text)
    assert re.search(r"latest_prerelease_tag: v\d+\.\d+\.\d+-[0-9A-Za-z.-]+", text)
    assert re.search(r"main_head_short: [0-9a-f]{7,12}", text)
    assert "staging_api_base_host: api-staging.yonerai.com" in text
    assert "Production Google login is not enabled" in text
    assert "agent:run" in text
    assert "admin:*" in text
    assert "http://" not in text
    assert "https://" not in text
    assert "C:\\Users" not in text
    assert "/home/" not in text
    assert "access_token" not in text
    assert "refresh_token" not in text
    assert "client_secret" not in text


def test_current_truth_generator_is_deterministic_for_known_date() -> None:
    output = subprocess.run(
        [sys.executable, "scripts/generate_current_truth.py", "--output", "CURRENT_TRUTH.test.md", "--date", "2026-06-11"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    generated = ROOT / "CURRENT_TRUTH.test.md"
    try:
        assert "CURRENT_TRUTH.test.md" in output.stdout
        text = generated.read_text(encoding="utf-8")
        assert "- generated_date_utc: 2026-06-11" in text
        assert "- staging_api_base_host: api-staging.yonerai.com" in text
    finally:
        generated.unlink(missing_ok=True)
