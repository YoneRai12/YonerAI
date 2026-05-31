from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_SRC = ROOT / "clients" / "cli"
V070_MANIFEST = ROOT / "releases" / "manifest.v0.7.0-alpha.1.json"


def _prepare_paths() -> None:
    text = str(CLI_SRC)
    if text not in sys.path:
        sys.path.insert(0, text)


def _load_v070_manifest() -> dict[str, object]:
    return json.loads(V070_MANIFEST.read_text(encoding="utf-8"))


def test_v070_manifest_validates_as_alpha_bridge_manifest() -> None:
    _prepare_paths()
    from yonerai_cli.release_manifest import load_manifest_file, verify_manifest

    report = verify_manifest(load_manifest_file(str(V070_MANIFEST)))

    assert report["contract_valid"] is True
    assert report["install_ready"] is False
    assert report["version"] == "0.7.0-alpha.1"
    assert report["release_tag"] == "v0.7.0-alpha.1"
    assert report["channel"] == "alpha"
    assert report["signature_state"] == "placeholder_non_production"
    assert report["production_signature_verified"] is False
    assert report["install_methods"] == [
        "manual_zip_venv",
        "powershell_dry_run_plan",
        "manifest_verify_only",
    ]
    assert any("Google OAuth remains dry-run" in warning for warning in report["warnings"])
    assert any("OpenAI shared traffic remains disabled" in warning for warning in report["warnings"])

    manifest = _load_v070_manifest()
    artifact = manifest["artifacts"][0]
    assert artifact["id"] == "yonerai-0.7.0-alpha.1-source-archive"
    assert artifact["url"] == (
        "https://github.com/YoneRai12/YonerAI/releases/download/"
        "v0.7.0-alpha.1/YonerAI-0.7.0-alpha.1.zip"
    )
    assert len(str(artifact["sha256"])) == 64
    assert isinstance(artifact["size_bytes"], int) and artifact["size_bytes"] > 0


def test_v070_install_and_update_plans_are_dry_run_only() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_install_plan, build_update_plan

    install_plan = build_install_plan(str(V070_MANIFEST))
    update_plan = build_update_plan(str(V070_MANIFEST), current_version="0.6.0")

    assert install_plan["ok"] is True
    assert install_plan["manifest"]["version"] == "0.7.0-alpha.1"
    assert install_plan["artifacts"][0]["filename_matches"] is True
    assert install_plan["non_actions"]["no_download"] is True
    assert install_plan["non_actions"]["no_path_mutation"] is True
    assert install_plan["non_actions"]["no_remote_script_execution"] is True
    assert install_plan["download_performed"] is False
    assert install_plan["install_performed"] is False

    assert update_plan["ok"] is True
    assert update_plan["current_version"] == "0.6.0"
    assert update_plan["target_version"] == "0.7.0-alpha.1"
    assert update_plan["version_comparison"] == "target_newer"
    assert update_plan["update_available"] is True
    assert update_plan["sha256_present"] is True
    assert "no download" in update_plan["actions_not_performed"]
    assert "no install" in update_plan["actions_not_performed"]
    assert "no PATH mutation" in update_plan["actions_not_performed"]
    assert "no remote execution" in update_plan["actions_not_performed"]
    assert update_plan["remote_code_executed"] is False


def test_v070_site_and_release_docs_explain_bridge_boundaries() -> None:
    release_note = (ROOT / "docs" / "releases" / "0.7.0-alpha.1.md").read_text(encoding="utf-8")
    site_release = (ROOT / "docs" / "site" / "yonerai.com" / "releases" / "v0.7.0-alpha.1.md").read_text(
        encoding="utf-8"
    )
    press_card = (ROOT / "docs" / "site" / "yonerai.com" / "press" / "v0.7.0-alpha.1-card.md").read_text(
        encoding="utf-8"
    )
    install_page = (ROOT / "docs" / "site" / "yonerai.com" / "install.md").read_text(encoding="utf-8")

    for text in (release_note, site_release, press_card):
        assert "Official Bridge Foundation" in text
        assert "production Google login" in text
        assert "OpenAI shared traffic" in text
        assert "production network installer" in text
        assert "live Discord" in text
        assert "production Oracle" in text
        assert "Official Managed Cloud" in text
        assert "/自己進化" in text or "yonerai evolve" in text

    assert "manifest.v0.7.0-alpha.1.json" in install_page
    assert "Use v0.6.0 for the current stable CLI Local Runtime" in install_page
    assert "no remote script execution" in install_page
