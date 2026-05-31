from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_SRC = ROOT / "clients" / "cli"
VERSION = "0.11.0-alpha.1"
PYPROJECT_VERSION = "0.11.0a1"


def _prepare_paths() -> None:
    text = str(CLI_SRC)
    if text not in sys.path:
        sys.path.insert(0, text)


def _load_manifest() -> dict[str, object]:
    return json.loads((ROOT / "releases" / f"manifest.v{VERSION}.json").read_text(encoding="utf-8"))


def test_v011_versions_and_installer_defaults_are_consistent() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = (ROOT / "clients" / "cli" / "pyproject.toml").read_text(encoding="utf-8")
    install_script = (ROOT / "install.ps1").read_text(encoding="utf-8")
    manifest = _load_manifest()

    assert version == VERSION
    assert f'version = "{PYPROJECT_VERSION}"' in pyproject
    assert manifest["version"] == VERSION
    assert manifest["release"]["tag"] == f"v{VERSION}"
    assert f"manifest.v{VERSION}.json" in install_script
    assert f"YonerAI-{VERSION}.zip" in install_script


def test_v011_manifest_validates_with_cli_contract() -> None:
    _prepare_paths()
    from yonerai_cli.release_manifest import verify_manifest

    report = verify_manifest(_load_manifest())

    assert report["ok"] is True
    assert report["contract_valid"] is True
    assert report["install_ready"] is False
    assert report["version"] == VERSION
    assert report["release_tag"] == f"v{VERSION}"
    assert report["signature_state"] == "placeholder_non_production"
    assert report["production_signature_verified"] is False
    assert report["production_trust_material"] is False
    assert report["network_required"] is False
    assert report["artifact_checks"] == []


def test_v011_release_docs_are_operation_manual_style() -> None:
    release_note = (ROOT / "docs" / "releases" / f"{VERSION}.md").read_text(encoding="utf-8")
    release_page = (
        ROOT / "docs" / "site" / "yonerai.com" / "releases" / f"v{VERSION}.md"
    ).read_text(encoding="utf-8")
    press_card = (
        ROOT / "docs" / "site" / "yonerai.com" / "press" / f"v{VERSION}-card.md"
    ).read_text(encoding="utf-8")
    install_page = (ROOT / "docs" / "site" / "yonerai.com" / "install.md").read_text(encoding="utf-8")
    release_index = (ROOT / "docs" / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    for text in (release_note, release_page, press_card, install_page, release_index, changelog):
        normalized = " ".join(text.lower().split())
        assert f"v{VERSION}" in text
        assert "production oracle" in normalized
        assert "official managed cloud" in normalized
        assert "openai shared traffic" in normalized
        assert "production google login" in normalized

    for command in (
        "/同期",
        "/認証",
        "/プライバシー",
        "yonerai sync status",
        "yonerai sync preview",
        "yonerai sync approve --dry-run",
        "yonerai sync api-contract",
        "yonerai sync rate-limit",
        f"manifest.v{VERSION}.json",
    ):
        assert command in release_note

    assert "#479" in release_note
    assert "Release gate PR for v0.11.0-alpha.1" in release_note


def test_v011_sync_manifest_install_and_update_commands_are_documented() -> None:
    release_note = (ROOT / "docs" / "releases" / f"{VERSION}.md").read_text(encoding="utf-8")
    install_page = (ROOT / "docs" / "site" / "yonerai.com" / "install.md").read_text(encoding="utf-8")

    for text in (release_note, install_page):
        assert f"manifest.v{VERSION}.json" in text
        assert "yonerai manifest verify" in text
        assert "yonerai install plan" in text
        assert "yonerai update check" in text
        assert "yonerai sync status" in text
        assert "yonerai sync preview" in text
