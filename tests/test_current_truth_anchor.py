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
    assert "status_snapshot_schema: yonerai.status.v1" in text
    assert "official_api_contract_policy: yonerai-official-api-contract/v0.14" in text
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
        assert "- status_snapshot_schema: yonerai.status.v1" in text
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


def _published(tag: str, at: str, *, prerelease: bool = True, draft: bool = False):
    return {
        "tag_name": tag,
        "published_at": at,
        "prerelease": prerelease,
        "draft": draft,
        "assets": [{"name": f"YonerAI-{tag[1:]}.zip", "state": "uploaded"}],
    }


def test_release_check_uses_published_cli_artifacts_without_writing(tmp_path):
    import json

    module = _load_current_truth_module()
    stable = _published("v0.8.1", "2026-06-13T15:45:03Z", prerelease=False)
    old = _published("v0.22.0-alpha.1", "2026-06-18T19:35:43Z")
    latest = _published("v0.23.0-alpha.1", "2026-06-30T23:32:55Z")
    draft = _published("v0.99.0-alpha.1", "2026-11-01T00:00:00Z", draft=True)
    legacy = _published("v2026.11.1-alpha", "2026-11-01T00:00:00Z")
    no_zip = dict(_published("v0.26.0-alpha.1", "2026-11-01T00:00:00Z"), assets=[])
    stable_path, pages_path = tmp_path / "stable.json", tmp_path / "pages.json"
    stable_path.write_text(json.dumps(stable))
    pages_path.write_text(json.dumps([[draft, no_zip, legacy, old], [latest]]))
    anchor = tmp_path / "anchor.md"
    current = "- latest_stable_tag: v0.8.1\n- latest_prerelease_tag: v0.22.0-alpha.1\n"
    anchor.write_text(current)
    args = ["--output", str(anchor), "--check-published", str(stable_path), str(pages_path)]
    assert module.main(args) == 1
    assert anchor.read_text() == current
    anchor.write_text(current.replace(old["tag_name"], latest["tag_name"]))
    assert module.main(args) == 0
    pages_path.write_text("{}")
    assert module.main(args) == 2
    assert latest["tag_name"] in anchor.read_text()
