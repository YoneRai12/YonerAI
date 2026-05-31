from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE_MARKERS = tuple(chr(codepoint) for codepoint in (0xFFFD, 0x7E5D, 0x8B41, 0x96B1, 0x87FE, 0x9A3E, 0x87B3, 0x8B20))


def test_install_skeleton_defaults_to_v090_manifest_and_artifact() -> None:
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert 'releases\\manifest.v0.9.0-alpha.1.json' in script
    assert "YonerAI-0.9.0-alpha.1.zip" in script
    assert "manifest.v0.8.0-alpha.1.json" not in script
    assert "YonerAI-0.8.0-alpha.1.zip" not in script


def test_v090_site_content_exists_and_keeps_boundaries() -> None:
    release_page = (ROOT / "docs" / "site" / "yonerai.com" / "releases" / "v0.9.0-alpha.1.md").read_text(
        encoding="utf-8"
    )
    press_card = (ROOT / "docs" / "site" / "yonerai.com" / "press" / "v0.9.0-alpha.1-card.md").read_text(
        encoding="utf-8"
    )
    install_page = (ROOT / "docs" / "site" / "yonerai.com" / "install.md").read_text(encoding="utf-8")

    for text in (release_page, press_card, install_page):
        assert "v0.9.0-alpha.1" in text
        assert "production oracle" in text.lower()
        assert "production network installer" in text
        assert "OpenAI shared traffic" in text
        assert not any(marker in text for marker in MOJIBAKE_MARKERS)

    assert "releases\\manifest.v0.9.0-alpha.1.json" in release_page
    assert "YonerAI-0.9.0-alpha.1.zip" in install_page
    assert "/設定" in release_page
    assert "/状態" in release_page


def test_v090_release_note_and_index_section_are_readable() -> None:
    release_note = (ROOT / "docs" / "releases" / "0.9.0-alpha.1.md").read_text(encoding="utf-8")
    release_index = (ROOT / "docs" / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    v090_index_section = release_index.split("## v0.8.0-alpha.1", maxsplit=1)[0]

    for text in (release_note, v090_index_section):
        assert "v0.9.0-alpha.1" in text
        assert "/提供元選択" in text
        assert "/自己進化" in text
        assert "Quality Wall" in text
        assert not any(marker in text for marker in MOJIBAKE_MARKERS)

    assert "/設定" in v090_index_section
    assert "/状態" in v090_index_section
