from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from yonerai_cli.release_manifest import (
    ManifestError,
    SEMVER_RE,
    expected_artifact_filename,
    load_manifest_file,
    verify_manifest,
)


INSTALL_PLAN_SCHEMA_VERSION = "yonerai-install-plan/v0.1"
WINDOWS_INSTALL_PLAN_SCHEMA_VERSION = "yonerai-windows-install-plan/v0.1"
UPDATE_PLAN_SCHEMA_VERSION = "yonerai-update-plan/v0.1"
UPDATE_CHECK_SCHEMA_VERSION = "yonerai-update-check/v0.1"
INSTALL_STATUS_SCHEMA_VERSION = "yonerai-install-status/v0.1"
INSTALL_CHANNELS = ("stable", "alpha")
GITHUB_LATEST_INSTALL_PS1 = "https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1"
GITHUB_LATEST_INSTALL_BASE_URL = "https://github.com/YoneRai12/YonerAI/releases/latest/download"
LATEST_STABLE_VERSION = "0.7.0"
TRUSTED_INSTALL_RELEASE_TAG = f"v{LATEST_STABLE_VERSION}"
TRUSTED_INSTALL_SCRIPT_SHA256 = "3db7cdace412d2c2978c74d77e2a2fce664bee4e6ee710f79b2349c0e89f3874"
TRUSTED_INSTALL_SCRIPT_SHA256_BY_TAG = {
    TRUSTED_INSTALL_RELEASE_TAG: TRUSTED_INSTALL_SCRIPT_SHA256,
}
YONERAI_INSTALL_PAGE = "https://yonerai.com/install"
QUICK_INSTALL_COMMAND = "irm https://install.yonerai.com | iex"
GITHUB_INSTALL_FALLBACK_COMMAND = (
    'iex "& { $(irm https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1) } '
    '-Execute -Launch"'
)
VERIFIED_INSTALL_COMMAND = (
    "$ErrorActionPreference='Stop'; "
    "$base='https://github.com/YoneRai12/YonerAI/releases/latest/download'; "
    "$tmp=Join-Path ([System.IO.Path]::GetTempPath()) "
    "('yonerai-bootstrap-'+[System.Guid]::NewGuid().ToString('N')); "
    "New-Item -ItemType Directory -Path $tmp | Out-Null; "
    "try { "
    "$script=Join-Path $tmp 'install.ps1'; "
    "$sidecar=Join-Path $tmp 'install.ps1.sha256'; "
    'irm "$base/install.ps1" -OutFile $script; '
    'irm "$base/install.ps1.sha256" -OutFile $sidecar; '
    "$expected=((Get-Content -LiteralPath $sidecar -Raw) -split '\\s+')[0].ToLowerInvariant(); "
    "if ($expected -notmatch '^[a-f0-9]{64}$') { throw 'install.ps1 sidecar SHA256 is invalid' }; "
    "$actual=(Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant(); "
    "if ($actual -ne $expected) { throw 'install.ps1 hash mismatch' }; "
    "$scriptText=Get-Content -LiteralPath $script -Raw; "
    "if ($scriptText -notmatch 'Invoke-VerifiedLocalBootstrap' -or "
    "$scriptText -match 'install.ps1 is still plan-only') { "
    "throw 'install.ps1 is not an executable bootstrap. Refusing to launch.' "
    "}; "
    "& powershell -NoProfile -ExecutionPolicy Bypass -File $script -Execute -Launch "
    "} finally { "
    "if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force } "
    "}"
)
FORCED_UPDATE_ENABLED = False
AUTO_UPDATE_APPLY_ENABLED = False
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def build_install_update_status() -> dict[str, Any]:
    return {
        "latest_stable": LATEST_STABLE_VERSION,
        "stable_channel_default": True,
        "alpha_requires_explicit_channel": True,
        "quick_install_command": QUICK_INSTALL_COMMAND,
        "github_install_fallback_command": GITHUB_INSTALL_FALLBACK_COMMAND,
        "verified_install_command": VERIFIED_INSTALL_COMMAND,
        "verified_install_page": YONERAI_INSTALL_PAGE,
        "github_latest_install_base_url": GITHUB_LATEST_INSTALL_BASE_URL,
        "forced_update_enabled": FORCED_UPDATE_ENABLED,
        "auto_update_apply_enabled": AUTO_UPDATE_APPLY_ENABLED,
        "forced_update_policy": "disabled",
        "no_forced_update": not FORCED_UPDATE_ENABLED,
        "no_auto_update_apply": not AUTO_UPDATE_APPLY_ENABLED,
    }


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


def build_windows_install_plan_from_default(repo_root: Path, *, channel: str = "stable") -> dict[str, Any]:
    return build_windows_install_plan(str(default_channel_manifest_path(repo_root, channel=channel)))


def build_install_plan_from_default(repo_root: Path, *, channel: str = "stable") -> dict[str, Any]:
    return build_install_plan(str(default_channel_manifest_path(repo_root, channel=channel)))


def build_install_status(repo_root: Path, *, channel: str = "stable") -> dict[str, Any]:
    selected_channel = _normalize_channel(channel)
    manifest_path = default_channel_manifest_path(repo_root, channel=selected_channel)
    try:
        manifest = load_manifest_file(str(manifest_path))
        verification = verify_manifest(manifest)
    except ManifestError as exc:
        verification = {
            "contract_valid": False,
            "install_ready": False,
            "version": None,
            "release_tag": None,
            "channel": selected_channel,
            "signature_state": "unknown",
            "signature_verified": False,
            "errors": [str(exc)],
        }
        manifest = {}
    selected_artifact = _selected_artifact_row(_artifact_plan_rows(manifest))
    selected_version = str(verification.get("version") or _expected_channel_version(selected_channel))
    selected_tag = str(verification.get("release_tag") or f"v{selected_version}")
    return {
        "schema_version": INSTALL_STATUS_SCHEMA_VERSION,
        "ok": bool(verification.get("contract_valid")),
        "channel": selected_channel,
        "selected_version": selected_version,
        "selected_tag": selected_tag,
        "manifest": _display_manifest_path(str(manifest_path)),
        "selected_artifact": selected_artifact,
        "signature_status": {
            "state": verification.get("signature_state"),
            "verified": bool(verification.get("signature_verified")),
            "production_signature_available": False,
            "production_trust_store_included": False,
        },
        "source_policy": {
            "install_page": "https://yonerai.com/install",
            "install_script_source": "github_latest_release_asset_redirect",
            "manifest_source": "github_release_asset_only",
            "artifact_source": "github_release_asset_only",
            "yonerai_com_serves_install_script": False,
            "yonerai_com_serves_manifest_or_zip": False,
            "local_file_source_allowed": False,
            "custom_manifest_allowed_by_bootstrap": False,
            "alpha_requires_explicit_channel": True,
        },
        "recommended_commands": {
            "stable": QUICK_INSTALL_COMMAND,
            "alpha": f"& ([scriptblock]::Create((irm {GITHUB_LATEST_INSTALL_PS1}))) -Channel alpha -Execute -Launch",
            "github_fallback": GITHUB_INSTALL_FALLBACK_COMMAND,
            "verify_first": VERIFIED_INSTALL_COMMAND,
        },
        "non_actions": {
            "no_yonerai_com_installer_bytes": True,
            "no_local_custom_manifest": True,
            "no_custom_artifact": True,
            "no_path_mutation_by_default": True,
            "no_registry_modification": True,
            "no_service_install": True,
            "no_admin_request": True,
            "no_provider_key_storage": True,
        },
        "warnings": [
            "yonerai.com is an install guide only; GitHub Release assets are the install source",
            "production signing and production trust stores are not included in the public repo",
            "alpha installs require -Channel alpha",
        ],
        "errors": verification.get("errors", []),
    }


def build_update_plan(manifest_path: str, *, current_version: str) -> dict[str, Any]:
    manifest = load_manifest_file(manifest_path)
    verification = verify_manifest(manifest)
    target_version = verification["version"] if isinstance(verification["version"], str) else None
    comparison = _compare_versions(current_version, target_version)
    artifact_rows = _artifact_plan_rows(manifest)
    selected_artifact = _selected_artifact_row(artifact_rows)
    sha256_present = bool(
        selected_artifact
        and selected_artifact["sha256_present"]
        and selected_artifact["sha256_format_valid"]
    )
    placeholder_non_production = verification["signature_state"] == "placeholder_non_production"
    warnings = _update_plan_warnings(
        comparison=comparison,
        placeholder_non_production=placeholder_non_production,
        contract_valid=verification["contract_valid"],
    )
    return {
        "schema_version": UPDATE_PLAN_SCHEMA_VERSION,
        "ok": verification["contract_valid"] and comparison != "unknown",
        "dry_run": True,
        "command": "yonerai update plan",
        "current_version": current_version,
        "target_version": target_version,
        "latest_stable": LATEST_STABLE_VERSION,
        "channel": verification["channel"],
        "update_available": comparison == "target_newer",
        "version_comparison": comparison,
        "selected_artifact": selected_artifact,
        "sha256_present": sha256_present,
        "signature_status": {
            "state": verification["signature_state"],
            "verified": verification["signature_verified"],
            "placeholder_non_production": placeholder_non_production,
            "verification_required_before_real_update": not verification["install_ready"],
        },
        "rollback_plan_available": False,
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
            "verification_required_before_real_update": not verification["install_ready"],
            "artifact_count": verification["artifact_count"],
            "errors": verification["errors"],
        },
        "artifacts": artifact_rows,
        "actions_that_would_run": [
            "read local VERSION",
            "read local manifest file",
            "validate manifest schema and artifact metadata",
            "validate versioned artifact naming",
            "confirm sha256 field presence and format",
            "report signature and trust status",
            "compare current VERSION to manifest version",
            "select update artifact",
            "report rollback readiness",
        ],
        "actions_not_performed": [
            "no download",
            "no install",
            "no PATH mutation",
            "no remote execution",
            "no package install",
            "no registry modification",
            "no service install",
            "no admin request",
            "no forced update",
            "no auto-apply update",
        ],
        "rollback_plan": [
            "record current installed version before a future real update",
            "preserve user data before mutation",
            "restore previous verified artifact if a future update fails",
        ],
        "non_actions": {
            "no_download": True,
            "no_install": True,
            "no_path_mutation": True,
            "no_remote_execution": True,
            "no_package_install": True,
            "no_registry_modification": True,
            "no_service_install": True,
        },
        "download_performed": False,
        "install_performed": False,
        "path_mutation": False,
        "package_install_performed": False,
        "registry_modified": False,
        "service_installed": False,
        "remote_code_executed": False,
        "network_required": False,
        "admin_required": False,
        "quick_install_command": QUICK_INSTALL_COMMAND,
        "github_install_fallback_command": GITHUB_INSTALL_FALLBACK_COMMAND,
        "verified_install_command": VERIFIED_INSTALL_COMMAND,
        "verified_install_page": YONERAI_INSTALL_PAGE,
        "forced_update_enabled": FORCED_UPDATE_ENABLED,
        "auto_update_apply_enabled": AUTO_UPDATE_APPLY_ENABLED,
        "forced_update_policy": "disabled",
        "warnings": warnings,
    }


def build_update_plan_from_default(repo_root: Path, *, current_version: str, channel: str = "stable") -> dict[str, Any]:
    return build_update_plan(str(default_channel_manifest_path(repo_root, channel=channel)), current_version=current_version)


def build_update_check(manifest_path: str, *, current_version: str) -> dict[str, Any]:
    plan = build_update_plan(manifest_path, current_version=current_version)
    artifact = plan.get("selected_artifact") if isinstance(plan.get("selected_artifact"), dict) else {}
    manifest_display = _display_manifest_path(manifest_path)
    next_safe_command_shell = _detect_cli_shell()
    next_safe_commands = _next_safe_update_commands(manifest_display)
    next_safe_command = next_safe_commands[next_safe_command_shell]
    return {
        "schema_version": UPDATE_CHECK_SCHEMA_VERSION,
        "ok": plan["ok"],
        "dry_run": True,
        "command": "yonerai update check",
        "manifest": manifest_display,
        "current_version": plan["current_version"],
        "latest_manifest_version": plan["target_version"],
        "latest_stable": LATEST_STABLE_VERSION,
        "channel": plan["channel"],
        "update_available": plan["update_available"],
        "version_comparison": plan["version_comparison"],
        "artifact_status": {
            "selected_artifact": artifact.get("artifact_id"),
            "filename_matches": artifact.get("filename_matches"),
            "sha256_present": plan["sha256_present"],
            "expected_filename": artifact.get("expected_filename"),
            "actual_filename": artifact.get("actual_filename"),
        },
        "signature_status": plan["signature_status"],
        "rollback_plan_available": bool(plan.get("rollback_plan_available")),
        "next_safe_command": next_safe_command,
        "next_safe_command_shell": next_safe_command_shell,
        "next_safe_commands": next_safe_commands,
        "actions_not_performed": plan["actions_not_performed"],
        "download_performed": False,
        "install_performed": False,
        "path_mutation": False,
        "remote_code_executed": False,
        "network_required": False,
        "quick_install_command": QUICK_INSTALL_COMMAND,
        "github_install_fallback_command": GITHUB_INSTALL_FALLBACK_COMMAND,
        "verified_install_command": VERIFIED_INSTALL_COMMAND,
        "verified_install_page": YONERAI_INSTALL_PAGE,
        "forced_update_enabled": FORCED_UPDATE_ENABLED,
        "auto_update_apply_enabled": AUTO_UPDATE_APPLY_ENABLED,
        "forced_update_policy": "disabled",
        "warnings": plan["warnings"],
    }


def build_update_check_from_default(repo_root: Path, *, current_version: str, channel: str = "stable") -> dict[str, Any]:
    return build_update_check(str(default_channel_manifest_path(repo_root, channel=channel)), current_version=current_version)


def default_channel_manifest_path(repo_root: Path, *, channel: str = "stable") -> Path:
    selected_channel = _normalize_channel(channel)
    candidates: list[Path] = []
    releases = repo_root / "releases"
    for path in releases.glob("manifest.v*.json"):
        version = _version_from_manifest_filename(path)
        if version is None:
            continue
        if _manifest_filename_channel(version) == selected_channel:
            candidates.append(path)
    if candidates:
        return max(candidates, key=lambda path: _version_key(_version_from_manifest_filename(path)) or (0, 0, 0, ()))
    fallback = _expected_channel_version(selected_channel)
    return releases / f"manifest.v{fallback}.json"


def default_update_manifest_path(repo_root: Path) -> Path:
    releases = repo_root / "releases"
    candidates = [
        path
        for path in releases.glob("manifest.v*.json")
        if _version_from_manifest_filename(path) is not None
    ]
    if not candidates:
        return releases / "manifest.example.json"
    return max(candidates, key=lambda path: _version_key(_version_from_manifest_filename(path)) or (0, 0, 0, ()))


def _normalize_channel(channel: str) -> str:
    if channel not in INSTALL_CHANNELS:
        raise ManifestError("install channel must be stable or alpha.")
    return channel


def _manifest_filename_channel(version: str) -> str:
    return "alpha" if "-alpha." in version else "stable"


def _expected_channel_version(channel: str) -> str:
    return "0.11.0-alpha.1" if channel == "alpha" else LATEST_STABLE_VERSION


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


def _selected_artifact_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        if row.get("kind") == "windows_zip" and row.get("target") == "windows-x64":
            return row
    for row in rows:
        if row.get("kind") == "source_archive":
            return row
    return rows[0] if rows else None


def _update_plan_warnings(*, comparison: str, placeholder_non_production: bool, contract_valid: bool) -> list[str]:
    warnings: list[str] = []
    if placeholder_non_production:
        warnings.append("non-production placeholder signature; production trust verification is not available in the public repo")
    if comparison == "target_older":
        warnings.append("manifest target version is older than local VERSION")
    if comparison == "unknown":
        warnings.append("version comparison could not be completed")
    if not contract_valid:
        warnings.append("manifest contract validation failed")
    return warnings


def _compare_versions(current_version: str | None, target_version: str | None) -> str:
    current_key = _version_key(current_version)
    target_key = _version_key(target_version)
    if current_key is None or target_key is None:
        return "unknown"
    if target_key > current_key:
        return "target_newer"
    if target_key < current_key:
        return "target_older"
    return "same"


def _version_key(version: str | None) -> tuple[int, int, int, tuple[tuple[int, int | str], ...]] | None:
    if not isinstance(version, str):
        return None
    match = SEMVER_RE.match(version)
    if match is None:
        return None
    try:
        major, minor, patch = (int(match.group(index)) for index in (1, 2, 3))
    except ValueError:
        return None
    prerelease = match.group(4)
    if prerelease is None:
        return major, minor, patch, ((2, ""),)
    return major, minor, patch, tuple(_prerelease_token(token) for token in prerelease.split("."))


def _prerelease_token(token: str) -> tuple[int, int | str]:
    if token.isdigit():
        try:
            return 0, int(token)
        except ValueError:
            return 1, token
    return 1, token


def _artifact_filename(url: object) -> str | None:
    if not isinstance(url, str):
        return None
    parsed = urlparse(url)
    name = Path(parsed.path).name
    return name or None


def _version_from_manifest_filename(path: Path) -> str | None:
    name = path.name
    if not name.startswith("manifest.v") or not name.endswith(".json"):
        return None
    version = name.removeprefix("manifest.v").removesuffix(".json")
    return version if SEMVER_RE.match(version) else None


def _display_manifest_path(path: str) -> str:
    normalized = Path(path)
    resolved = normalized.resolve()
    cwd = Path.cwd().resolve()
    try:
        relative = resolved.relative_to(cwd)
        return relative.as_posix()
    except Exception:
        repo_root = _source_repo_root()
        if repo_root is not None:
            try:
                resolved.relative_to(repo_root)
                return Path(os.path.relpath(resolved, cwd)).as_posix()
            except Exception:
                pass
        return normalized.name or "<local-manifest>"


def _source_repo_root() -> Path | None:
    candidates = [Path(__file__).resolve().parents[3], Path.cwd().resolve()]
    for candidate in candidates:
        try:
            if (candidate / "releases").is_dir() and (candidate / "VERSION").is_file():
                return candidate
        except Exception:
            continue
    return None


def _next_safe_update_commands(manifest_display: str) -> dict[str, str]:
    return {
        shell: f"yonerai update plan --manifest {_quote_cli_path(manifest_display, shell=shell)} --pretty"
        for shell in ("powershell", "cmd", "posix")
    }


def _detect_cli_shell(*, platform: str | None = None, env: dict[str, str] | None = None) -> str:
    platform_name = platform or os.name
    if platform_name != "nt":
        return "posix"
    values = env if env is not None else os.environ
    explicit = (values.get("YONERAI_CLI_SHELL") or "").lower()
    if explicit in {"powershell", "pwsh"}:
        return "powershell"
    if explicit in {"cmd", "cmd.exe", "command_prompt"}:
        return "cmd"
    prompt_hint = values.get("PROMPT")
    comspec_hint = (values.get("COMSPEC") or "").lower()
    if prompt_hint and "cmd.exe" in comspec_hint:
        return "cmd"
    return "powershell"


def _quote_cli_path(path: str, *, platform: str | None = None, shell: str | None = None) -> str:
    if not path:
        return "''"
    shell_name = shell or _detect_cli_shell(platform=platform)
    if shell_name == "powershell":
        return _quote_powershell_path(path)
    if shell_name == "cmd":
        return _quote_cmd_path(path)
    return shlex.quote(path)


def _quote_powershell_path(path: str) -> str:
    if re.search(r"[\s;&|<>()`$'\"\[\]{}]", path) is None:
        return path
    return "'" + path.replace("'", "''") + "'"


def _quote_cmd_path(path: str) -> str:
    if re.search(r'[\s&|<>()^%!"]', path) is None:
        return path
    escaped = path.replace("^", "^^").replace("%", "^%").replace("!", "^!").replace('"', '""')
    return f'"{escaped}"'


__all__ = [
    "INSTALL_PLAN_SCHEMA_VERSION",
    "INSTALL_STATUS_SCHEMA_VERSION",
    "UPDATE_PLAN_SCHEMA_VERSION",
    "UPDATE_CHECK_SCHEMA_VERSION",
    "WINDOWS_INSTALL_PLAN_SCHEMA_VERSION",
    "ManifestError",
    "build_install_plan",
    "build_install_plan_from_default",
    "build_install_status",
    "build_update_check",
    "build_update_check_from_default",
    "build_update_plan",
    "build_update_plan_from_default",
    "build_windows_install_plan",
    "build_windows_install_plan_from_default",
]
