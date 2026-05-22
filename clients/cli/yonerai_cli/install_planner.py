from __future__ import annotations

from pathlib import Path
from typing import Any

from yonerai_cli.release_manifest import ManifestError, load_manifest_file, verify_manifest


INSTALL_PLAN_SCHEMA_VERSION = "yonerai-windows-install-plan/v0.1"


def build_windows_install_plan(manifest_path: str) -> dict[str, Any]:
    manifest = load_manifest_file(manifest_path)
    verification = verify_manifest(manifest)
    return {
        "schema_version": INSTALL_PLAN_SCHEMA_VERSION,
        "ok": verification["contract_valid"],
        "dry_run": True,
        "platform": "windows",
        "manifest": {
            "contract_valid": verification["contract_valid"],
            "install_ready": verification["install_ready"],
            "version": verification["version"],
            "release_tag": verification["release_tag"],
            "signature_state": verification["signature_state"],
            "artifact_count": verification["artifact_count"],
            "errors": verification["errors"],
        },
        "steps": [
            "read local manifest file",
            "validate manifest schema and artifact metadata",
            "report required hashes and signatures",
            "stop before download, install, PATH mutation, or remote execution",
        ],
        "download_performed": False,
        "remote_code_executed": False,
        "install_performed": False,
        "path_mutation": False,
        "network_required": False,
        "powershell_pipe_execution_allowed": False,
    }


def build_windows_install_plan_from_default(repo_root: Path) -> dict[str, Any]:
    return build_windows_install_plan(str(repo_root / "releases" / "manifest.example.json"))


__all__ = [
    "INSTALL_PLAN_SCHEMA_VERSION",
    "ManifestError",
    "build_windows_install_plan",
    "build_windows_install_plan_from_default",
]
