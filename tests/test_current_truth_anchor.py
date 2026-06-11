from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_current_truth_module():
    module_path = ROOT / "scripts" / "generate_current_truth.py"
    spec = importlib.util.spec_from_file_location("generate_current_truth", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_current_truth_generator_ignores_legacy_release_tag_families(monkeypatch) -> None:
    module = _load_current_truth_module()

    def fake_run_git(args: list[str]) -> str:
        if args[:3] == ["tag", "--list", "v*"]:
            return "\n".join(
                [
                    "v0.7.0",
                    "v0.20.0-alpha.1",
                    "v0.21.0-alpha.1",
                    "v1.0.0",
                    "v1.1.0-alpha.1",
                    "v5.1.14",
                    "v2026.5.21",
                    "v2026.3.8-security",
                ]
            )
        if args[:2] == ["rev-parse", "--short"]:
            return "abcdef0"
        return ""

    monkeypatch.setattr(module, "_run_git", fake_run_git)

    text = module.build_current_truth(generated_date="2026-06-11")

    assert "- latest_stable_tag: v1.0.0" in text
    assert "- latest_prerelease_tag: v1.1.0-alpha.1" in text
    assert "v2026." not in text
    assert "v5.1." not in text


def test_current_truth_prefers_origin_main_over_stale_public_remote(monkeypatch) -> None:
    module = _load_current_truth_module()

    def fake_run_git(args: list[str]) -> str:
        if args[:3] == ["tag", "--list", "v*"]:
            return "\n".join(["v0.7.0", "v0.21.0-alpha.2"])
        if args == ["rev-parse", "--short", "origin/main"]:
            return "57eee92a"
        if args == ["rev-parse", "--short", "public/main"]:
            return "69fb9768"
        if args[:2] == ["rev-parse", "--short"]:
            return "abcdef0"
        return ""

    monkeypatch.setattr(module, "_run_git", fake_run_git)

    text = module.build_current_truth(generated_date="2026-06-11")

    assert "- main_head_short: 57eee92a" in text
    assert "69fb9768" not in text
