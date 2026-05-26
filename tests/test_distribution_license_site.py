from __future__ import annotations

import json
import sys
import tomllib
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_SRC = ROOT / "clients" / "cli"
V050_MANIFEST = ROOT / "releases" / "manifest.v0.5.0.json"
V051_MANIFEST = ROOT / "releases" / "manifest.v0.5.1.json"


def _prepare_paths() -> None:
    text = str(CLI_SRC)
    if text not in sys.path:
        sys.path.insert(0, text)


def _load_v050_manifest() -> dict[str, object]:
    return json.loads(V050_MANIFEST.read_text(encoding="utf-8"))


def _load_v051_manifest() -> dict[str, object]:
    return json.loads(V051_MANIFEST.read_text(encoding="utf-8"))


def test_license_policy_is_source_available_noncommercial() -> None:
    root_license = (ROOT / "LICENSE").read_text(encoding="utf-8")
    policy = (ROOT / "docs" / "legal" / "LICENSE_POLICY.md").read_text(encoding="utf-8")
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    cli_pyproject = tomllib.loads((ROOT / "clients" / "cli" / "pyproject.toml").read_text(encoding="utf-8"))

    assert "PolyForm Noncommercial License 1.0.0" in root_license
    assert "source-available, not OSI open source" in root_license
    assert "Attribution-NonCommercial-NoDerivatives 4.0" in root_license
    assert "All Rights Reserved" in root_license
    assert "source-available and noncommercial" in policy
    assert "No trademark license" in policy
    assert "PolyForm Noncommercial License 1.0.0" in notice
    assert cli_pyproject["project"]["license"]["text"] == "PolyForm-Noncommercial-1.0.0"
    assert "License :: Other/Proprietary License" in cli_pyproject["project"]["classifiers"]


def test_v050_manifest_validates_and_records_release_asset() -> None:
    _prepare_paths()
    from yonerai_cli.release_manifest import load_manifest_file, verify_manifest

    report = verify_manifest(load_manifest_file(str(V050_MANIFEST)))

    assert report["contract_valid"] is True
    assert report["install_ready"] is False
    assert report["version"] == "0.5.0"
    assert report["release_tag"] == "v0.5.0"
    assert report["channel"] == "stable"
    assert report["signature_state"] == "placeholder_non_production"
    assert report["production_signature_verified"] is False
    assert report["install_methods"] == [
        "manual_zip_venv",
        "powershell_dry_run_plan",
        "manifest_verify_only",
    ]
    assert any("production signature verification" in warning for warning in report["warnings"])

    manifest = _load_v050_manifest()
    artifact = manifest["artifacts"][0]
    assert artifact["url"] == "https://github.com/YoneRai12/YonerAI/releases/download/v0.5.0/YonerAI-0.5.0.zip"
    assert artifact["sha256"] == "8a0a625c8cca899224e6fbead7bcc159c7010d58c16db941006341759263ab39"
    assert artifact["size_bytes"] == 9007426


def test_v051_manifest_validates_and_records_release_asset() -> None:
    _prepare_paths()
    from yonerai_cli.release_manifest import load_manifest_file, verify_manifest

    report = verify_manifest(load_manifest_file(str(V051_MANIFEST)))

    assert report["contract_valid"] is True
    assert report["install_ready"] is False
    assert report["version"] == "0.5.1"
    assert report["release_tag"] == "v0.5.1"
    assert report["channel"] == "stable"
    assert report["signature_state"] == "placeholder_non_production"
    assert report["production_signature_verified"] is False
    assert report["install_methods"] == [
        "manual_zip_venv",
        "powershell_dry_run_plan",
        "manifest_verify_only",
    ]
    assert any("production signature verification" in warning for warning in report["warnings"])
    assert any("install-local.ps1" in warning for warning in report["warnings"])

    manifest = _load_v051_manifest()
    artifact = manifest["artifacts"][0]
    assert artifact["id"] == "yonerai-0.5.1-source-archive"
    assert artifact["url"] == "https://github.com/YoneRai12/YonerAI/releases/download/v0.5.1/YonerAI-0.5.1.zip"
    assert len(str(artifact["sha256"])) == 64
    assert artifact["sha256"] != "0000000000000000000000000000000000000000000000000000000000000000"
    assert isinstance(artifact["size_bytes"], int) and artifact["size_bytes"] > 1


def test_v050_install_and_update_plans_are_dry_run_only() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_install_plan, build_update_plan

    install_plan = build_install_plan(str(V050_MANIFEST))
    update_plan = build_update_plan(str(V050_MANIFEST), current_version="0.5.0")

    assert install_plan["ok"] is True
    assert install_plan["manifest"]["version"] == "0.5.0"
    assert install_plan["artifacts"][0]["filename_matches"] is True
    assert install_plan["non_actions"]["no_download"] is True
    assert install_plan["non_actions"]["no_path_mutation"] is True
    assert install_plan["non_actions"]["no_remote_script_execution"] is True
    assert install_plan["download_performed"] is False
    assert install_plan["install_performed"] is False

    assert update_plan["ok"] is True
    assert update_plan["target_version"] == "0.5.0"
    assert update_plan["version_comparison"] == "same"
    assert update_plan["update_available"] is False
    assert update_plan["sha256_present"] is True
    assert "no download" in update_plan["actions_not_performed"]
    assert "no install" in update_plan["actions_not_performed"]
    assert "no PATH mutation" in update_plan["actions_not_performed"]
    assert "no remote execution" in update_plan["actions_not_performed"]
    assert update_plan["remote_code_executed"] is False


def test_v051_install_and_update_plans_are_dry_run_only() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_install_plan, build_update_plan

    install_plan = build_install_plan(str(V051_MANIFEST))
    update_plan = build_update_plan(str(V051_MANIFEST), current_version="0.5.0")

    assert install_plan["ok"] is True
    assert install_plan["manifest"]["version"] == "0.5.1"
    assert install_plan["artifacts"][0]["filename_matches"] is True
    assert install_plan["non_actions"]["no_download"] is True
    assert install_plan["non_actions"]["no_path_mutation"] is True
    assert install_plan["non_actions"]["no_remote_script_execution"] is True
    assert install_plan["download_performed"] is False
    assert install_plan["install_performed"] is False

    assert update_plan["ok"] is True
    assert update_plan["current_version"] == "0.5.0"
    assert update_plan["target_version"] == "0.5.1"
    assert update_plan["version_comparison"] == "target_newer"
    assert update_plan["update_available"] is True
    assert update_plan["sha256_present"] is True
    assert "no download" in update_plan["actions_not_performed"]
    assert "no install" in update_plan["actions_not_performed"]
    assert "no PATH mutation" in update_plan["actions_not_performed"]
    assert "no remote execution" in update_plan["actions_not_performed"]
    assert update_plan["remote_code_executed"] is False


def test_v050_manifest_rejects_unversioned_artifact_and_missing_signature() -> None:
    _prepare_paths()
    from yonerai_cli.release_manifest import verify_manifest

    unversioned = _load_v050_manifest()
    artifact = deepcopy(unversioned["artifacts"][0])
    artifact["url"] = "https://github.com/YoneRai12/YonerAI/releases/download/v0.5.0/YonerAI-latest.zip"
    unversioned["artifacts"] = [artifact]

    unversioned_report = verify_manifest(unversioned)

    assert unversioned_report["contract_valid"] is False
    assert any("filename must be YonerAI-0.5.0.zip" in error for error in unversioned_report["errors"])

    missing_signature = _load_v050_manifest()
    artifact = deepcopy(missing_signature["artifacts"][0])
    artifact.pop("signature")
    missing_signature["artifacts"] = [artifact]

    missing_signature_report = verify_manifest(missing_signature)

    assert missing_signature_report["contract_valid"] is False
    assert any("signature" in error for error in missing_signature_report["errors"])


def test_manifest_rejects_unhashable_install_method_without_traceback() -> None:
    _prepare_paths()
    from yonerai_cli.release_manifest import verify_manifest

    manifest = _load_v050_manifest()
    manifest["install_methods"] = [["manual_zip_venv"]]

    report = verify_manifest(manifest)

    assert report["contract_valid"] is False
    assert "install_methods is invalid." in report["errors"]


def test_yonerai_site_install_content_is_copyable_and_non_executing() -> None:
    install_page = (ROOT / "docs" / "site" / "yonerai.com" / "install.md").read_text(encoding="utf-8")
    release_page = (ROOT / "docs" / "site" / "yonerai.com" / "releases" / "v0.5.1.md").read_text(
        encoding="utf-8"
    )
    press_card = (ROOT / "docs" / "site" / "yonerai.com" / "press" / "v0.5.1-card.md").read_text(
        encoding="utf-8"
    )

    for text in (install_page, release_page):
        lowered = text.lower()
        assert "YonerAI-0.5.1.zip" in text
        assert "yonerai manifest verify releases/manifest.v0.5.1.json --pretty" in text
        assert "yonerai install plan --manifest releases/manifest.v0.5.1.json --pretty" in text
        assert "irm ... | iex" in text
        assert "production signing keys" in lowered or "production signature" in lowered

    assert "https://yonerai.com/releases/v0.5.1" in press_card
    assert "Official Managed Cloud" in press_card


def test_readmes_point_to_v051_manifest_and_license_policy() -> None:
    for relative_path in ("README.md", "README_JP.md", "clients/cli/README.md"):
        text = (ROOT / relative_path).read_text(encoding="utf-8")

        assert "PolyForm Noncommercial" in text
        assert "releases/manifest.v0.5.1.json" in text


def test_release_archive_policy_is_hash_stable_for_manifest_recording() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    release_script = (ROOT / "scripts" / "create_release.py").read_text(encoding="utf-8")

    assert "releases/manifest.v*.json export-ignore" in attributes
    assert "HEAD^{tree}" in release_script
