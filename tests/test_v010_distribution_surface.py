from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE_MARKERS = tuple(chr(codepoint) for codepoint in (0xFFFD, 0x7E5D, 0x8B41, 0x96B1, 0x87FE, 0x9A3E, 0x87B3, 0x8B20))


def test_install_skeleton_no_longer_points_to_older_v09_defaults() -> None:
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "manifest.v0.9.0-alpha.1.json" not in script
    assert "YonerAI-0.9.0-alpha.1.zip" not in script


def test_v010_manifest_keeps_historical_version_and_artifact() -> None:
    manifest = (ROOT / "releases" / "manifest.v0.10.0-alpha.1.json").read_text(encoding="utf-8")

    assert '"version": "0.10.0-alpha.1"' in manifest
    assert "YonerAI-0.10.0-alpha.1.zip" in manifest


def test_v010_release_and_site_content_keep_boundaries() -> None:
    release_note = (ROOT / "docs" / "releases" / "0.10.0-alpha.1.md").read_text(encoding="utf-8")
    release_page = (ROOT / "docs" / "site" / "yonerai.com" / "releases" / "v0.10.0-alpha.1.md").read_text(
        encoding="utf-8"
    )
    press_card = (ROOT / "docs" / "site" / "yonerai.com" / "press" / "v0.10.0-alpha.1-card.md").read_text(
        encoding="utf-8"
    )
    install_page = (ROOT / "docs" / "site" / "yonerai.com" / "install.md").read_text(encoding="utf-8")
    release_index = (ROOT / "docs" / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    for text in (release_note, release_page, press_card, install_page, release_index, changelog):
        normalized = " ".join(text.lower().split())
        assert "v0.10.0-alpha.1" in text
        assert "production oracle" in normalized
        assert "network installer" in normalized
        assert "openai shared traffic" in normalized
        assert not any(marker in text for marker in MOJIBAKE_MARKERS)

    for command in ("/ホーム", "/状態", "/設定", "/モデル", "/提供元選択", "/認証", "/プライバシー", "/自己進化"):
        assert command in release_note
        assert command in release_page

    for pr in ("#474", "#475", "#476", "#477"):
        assert pr in release_note


def test_v010_manifest_commands_are_documented() -> None:
    release_note = (ROOT / "docs" / "releases" / "0.10.0-alpha.1.md").read_text(encoding="utf-8")
    install_page = (ROOT / "docs" / "site" / "yonerai.com" / "install.md").read_text(encoding="utf-8")

    for text in (release_note, install_page):
        assert "manifest.v0.10.0-alpha.1.json" in text
        assert "yonerai manifest verify" in text
        assert "yonerai install plan" in text
        assert "yonerai update check" in text
