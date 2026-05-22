from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from yonerai_cli.release_manifest import (
    ManifestError,
    expected_artifact_filename,
    load_manifest_file,
    verify_manifest,
)


INSTALL_PLAN_SCHEMA_VERSION = "yonerai-install-plan/v0.1"
WINDOWS_INSTALL_PLAN_SCHEMA_VERSION = "yonerai-windows-install-plan/v0.1"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def build_install_plan(manifest_path: str, *, target_category: str = "windows-user") -> dict[str, Any]:
    manifest = load_manifest_file(manifest_path)
    verification = verify_manifest(manifest)
    placeholder_non_production = verification["signature_state"] == "placeholder_non_production"
    return {
        "schema_version": INSTALL_PLAN_SCHEMA_VERSION,
        "ok": verification["contract_valid"],
        "dry_run": True,
        "platform": "windows",
        "target_category": target_category,
        "manifest": {
            "contract_valid": verification["contract_valid"],
            "install_ready": verification["install_ready"],
            "version": verification["version"],
            "release_tag": verification["release_tag"],
            "channel": verification["channel"],
            "manifest_status": verification["manifest_status"],
            "signature_state": verification["signature_state"],
            "signature_verified": verification["signature_verified"],
            "placeholder_non_production": placeholder_non_production,
            "verification_required_before_real_install": not verification["install_ready"],
            "artifact_count": verification["artifact_count"],
            "errors": verification["errors"],
        },
        "artifacts": _artifact_plan_rows(manifest),
        "steps": [
            "read local manifest file",
            "validate manifest schema and artifact metadata",
            "validate versioned artifact naming",
            "confirm sha256 field presence and format",
            "report signature state",
            "require production signature verification before real install",
            "plan install target category without printing a local absolute path",
            "prepare rollback plan placeholder",
            "stop before download, install, PATH mutation, registry mutation, service install, package install, or remote execution",
        ],
        "rollback_plan": [
            "record current installed version before a future real install",
            "preserve user data before mutation",
            "restore previous verified artifact if a future install fails",
        ],
        "non_actions": {
            "no_download": True,
            "no_execution": True,
            "no_path_mutation": True,
            "no_package_install": True,
            "no_registry_modification": True,
            "no_service_install": True,
            "no_remote_script_execution": True,
        },
        "download_performed": False,
        "remote_code_executed": False,
        "install_performed": False,
        "path_mutation": False,
        "package_install_performed": False,
        "registry_modified": False,
        "service_installed": False,
        "network_required": False,
        "powershell_pipe_execution_allowed": False,
    }


def build_windows_install_plan(manifest_path: str) -> dict[str, Any]:
    report = build_install_plan(manifest_path, target_category="windows-user")
    return {**report, "schema_version": WINDOWS_INSTALL_PLAN_SCHEMA_VERSION}


def build_windows_install_plan_from_default(repo_root: Path) -> dict[str, Any]:
    return build_windows_install_plan(str(repo_root / "releases" / "manifest.example.json"))


def build_install_plan_from_default(repo_root: Path) -> dict[str, Any]:
    return build_install_plan(str(repo_root / "releases" / "manifest.example.json"))


def _artifact_plan_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    version = manifest.get("version")
    artifacts = manifest.get("artifacts")
    if not isinstance(version, str) or not isinstance(artifacts, list):
        return []
    rows: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        sha256 = artifact.get("sha256")
        url = artifact.get("url")
        expected_name = expected_artifact_filename(artifact, version)
        actual_name = _artifact_filename(url)
        rows.append(
            {
                "artifact_id": artifact.get("id"),
                "kind": artifact.get("kind"),
                "target": artifact.get("target"),
                "sha256_present": isinstance(sha256, str) and bool(sha256),
                "sha256_format_valid": isinstance(sha256, str) and SHA256_RE.match(sha256) is not None,
                "expected_filename": expected_name,
                "actual_filename": actual_name,
                "filename_matches": expected_name is None or actual_name == expected_name,
            }
        )
    return rows


def _artifact_filename(url: object) -> str | None:
    if not isinstance(url, str):
        return None
    parsed = urlparse(url)
    name = Path(parsed.path).name
    return name or None


__all__ = [
    "INSTALL_PLAN_SCHEMA_VERSION",
    "WINDOWS_INSTALL_PLAN_SCHEMA_VERSION",
    "ManifestError",
    "build_install_plan",
    "build_install_plan_from_default",
    "build_windows_install_plan",
    "build_windows_install_plan_from_default",
]
