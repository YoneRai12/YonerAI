from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
CLI_SRC = ROOT / "clients" / "cli"
INSTALL_SCRIPT = ROOT / "install.ps1"
SITE_ROOT = ROOT / "docs" / "site" / "yonerai.com"
INSTALL_PAGE = SITE_ROOT / "install.md"
LATEST_INSTALL_URL = "https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1"


def _prepare_paths() -> None:
    text = str(CLI_SRC)
    if text not in sys.path:
        sys.path.insert(0, text)


def test_install_page_is_command_only_and_never_local_pc_source() -> None:
    text = INSTALL_PAGE.read_text(encoding="utf-8")

    assert LATEST_INSTALL_URL in text
    assert "## Quick install" in text
    assert "## Verified install" in text
    assert "install.ps1.sha256" in text
    assert "sidecar SHA256 is invalid" in text
    assert "install.ps1 hash mismatch" in text
    assert "fails closed" in text
    assert "must not be an installer file source" in text
    assert "does not fetch ZIPs, manifests, or sidecar hashes from `yonerai.com`" in text
    assert "GitHub Release assets" in text
    assert "https://yonerai.com/install.ps1" not in text
    assert "https://yonerai.com/manifest" not in text
    assert "https://yonerai.com/releases/download" not in text


def test_yonerai_site_tree_contains_no_installable_local_files() -> None:
    forbidden_exact_names = {
        "install.ps1",
        "install.ps1.sha256",
        "manifest.json",
        "manifest.latest.json",
        "manifest.stable.json",
    }
    forbidden_suffixes = (".zip", ".ps1", ".ps1.sha256")
    forbidden_manifest = re.compile(r"^manifest\.v.+\.json$")

    offenders: list[str] = []
    for path in SITE_ROOT.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if name in forbidden_exact_names or name.endswith(forbidden_suffixes) or forbidden_manifest.match(name):
            offenders.append(path.relative_to(SITE_ROOT).as_posix())

    assert offenders == []


def test_install_script_rejects_local_custom_sources_and_requires_explicit_path_wrapper() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "Custom manifest/artifact inputs are not accepted" in script
    assert "Artifact filename must be the selected versioned asset" in script
    assert "latest, main, or source aliases" in script
    assert "Invoke-Expression" not in script
    assert "Invoke-GitHubApi" in script
    assert "Get-ReleaseFromApi" in script
    assert "[switch]$Repair" in script
    assert "[switch]$Force" in script
    assert "[switch]$CleanRetry" in script
    assert "[switch]$SetPath" in script
    assert "if (-not $SetPath -or $NoPath)" in script
    assert "SetEnvironmentVariable" in script
    assert re.search(r"\bsetx\b", script, flags=re.IGNORECASE) is None
    assert "irm https://install.yonerai.com | iex" in script
    assert "https://github.com/YoneRai12/YonerAI/releases/download" in script
    assert "https://api.github.com/repos/YoneRai12/YonerAI/releases" in script
    assert LATEST_INSTALL_URL in script
    assert "$releaseArtifact = Get-ManifestArtifact" in script
    assert "$artifact = Get-ManifestArtifact" not in script
    assert "old Python Scripts executable may shadow the wrapper" in script
    assert "v0.11.0-alpha.1" not in script


def test_install_script_execute_resolves_manifest_artifact_when_powershell_available(tmp_path: Path) -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    artifact = tmp_path / "YonerAI-0.6.4.zip"
    with ZipFile(artifact, "w", compression=ZIP_STORED) as archive:
        archive.writestr("repo/install-local.ps1", "Write-Host '[test] local bootstrap reached'\n")
        archive.writestr("repo/clients/cli/pyproject.toml", "[project]\nname='yonerai-cli'\n")

    import hashlib

    artifact_bytes = artifact.read_bytes()
    manifest = {
        "schema_version": "yonerai-installer-bootstrap-manifest/v1",
        "product": "YonerAI",
        "channel": "stable",
        "version": "0.6.4",
        "published_at": "2026-06-01T00:00:00Z",
        "production_ready": False,
        "release": {
            "tag": "v0.6.4",
            "github_release_url": "https://github.com/YoneRai12/YonerAI/releases/tag/v0.6.4",
            "manifest_status": "unsigned_example",
        },
        "minimum_requirements": {"python": ">=3.11", "network_required": True},
        "install_methods": ["powershell_github_release_bootstrap"],
        "warnings": ["test fixture"],
        "artifacts": [
            {
                "id": "yonerai-0.6.4-source-archive",
                "kind": "source_archive",
                "target": "source-any",
                "os": "any",
                "arch": "any",
                "url": "https://github.com/YoneRai12/YonerAI/releases/download/v0.6.4/YonerAI-0.6.4.zip",
                "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                "size_bytes": len(artifact_bytes),
                "signature": {"status": "placeholder_non_production"},
            }
        ],
    }
    manifest_path = tmp_path / "manifest.v0.6.4.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    script_text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    replacement = f"""function Invoke-GitHubDownload {{
    param(
        [string]$Url,
        [string]$OutFile,
        [string]$Label
    )
    if ($Label -eq "manifest") {{
        Copy-Item -LiteralPath {_ps_single_quote(manifest_path)} -Destination $OutFile
        return
    }}
    if ($Label -eq "artifact") {{
        Copy-Item -LiteralPath {_ps_single_quote(artifact)} -Destination $OutFile
        return
    }}
    throw "unexpected download label"
}}

function Assert-FileSha256"""
    script_text = re.sub(
        r"function Invoke-GitHubDownload \{.*?\r?\n\}\r?\n\r?\nfunction Assert-FileSha256",
        lambda _match: replacement,
        script_text,
        flags=re.S,
    )
    test_script = tmp_path / "install.ps1"
    test_script.write_text(script_text, encoding="utf-8")

    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(test_script),
            "-Execute",
            "-Version",
            "0.6.4",
            "-InstallDir",
            str(tmp_path / "target"),
        ],
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, _subprocess_failure(result)
    assert "artifact sha256 verified: true" in result.stdout
    assert "[test] local bootstrap reached" in result.stdout
    assert "Install flow completed from verified GitHub Release assets." in result.stdout
    assert "property 'url' cannot be found" not in (result.stdout + result.stderr).lower()


def test_install_status_reports_github_release_only_source_policy() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_install_update_status

    report = build_install_update_status()

    assert report["latest_stable"] == "0.6.5"
    assert report["stable_channel_default"] is True
    assert report["alpha_requires_explicit_channel"] is True
    assert report["quick_install_command"] == "irm https://install.yonerai.com | iex"
    assert LATEST_INSTALL_URL in report["github_install_fallback_command"]
    assert "install.ps1.sha256" in report["verified_install_command"]
    assert "sidecar SHA256 is invalid" in report["verified_install_command"]
    assert "install.ps1 hash mismatch" in report["verified_install_command"]
    assert report["forced_update_enabled"] is False
    assert report["auto_update_apply_enabled"] is False


def test_install_status_cli_json_is_stable_and_redacted() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from yonerai_cli.cli import main; main()",
            "doctor",
            "--json",
        ],
        cwd=CLI_SRC,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["install_update"]["quick_install_command"] == "irm https://install.yonerai.com | iex"
    assert report["install_update"]["verified_install_page"] == "https://yonerai.com/install"
    assert str(ROOT) not in result.stdout
    assert "sk-" not in result.stdout.lower()


def test_verified_bootstrap_hash_mismatch_fails_closed_when_powershell_available(tmp_path: Path) -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    script = tmp_path / "install.ps1"
    sidecar = tmp_path / "install.ps1.sha256"
    script.write_text("Write-Host should-not-run", encoding="utf-8")
    sidecar.write_text("0" * 64, encoding="utf-8")

    result = _run_verify_snippet(powershell, script, sidecar)

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "install.ps1 hash mismatch" in combined
    assert "should-not-run" not in combined


def test_verified_bootstrap_missing_sidecar_fails_closed_when_powershell_available(tmp_path: Path) -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    script = tmp_path / "install.ps1"
    sidecar = tmp_path / "install.ps1.sha256"
    script.write_text("Write-Host should-not-run", encoding="utf-8")

    result = _run_verify_snippet(powershell, script, sidecar)

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "should-not-run" not in combined


def _run_verify_snippet(powershell: Path, script: Path, sidecar: Path) -> subprocess.CompletedProcess[str]:
    script_literal = _ps_single_quote(script)
    sidecar_literal = _ps_single_quote(sidecar)
    snippet = (
        "$ErrorActionPreference='Stop'; "
        f"$script={script_literal}; "
        f"$sidecar={sidecar_literal}; "
        "$expected=((Get-Content -LiteralPath $sidecar -Raw).Split()[0]).ToLowerInvariant(); "
        "if ($expected -notmatch '^[a-f0-9]{64}$') { throw 'install.ps1 sidecar SHA256 is invalid' }; "
        "$actual=(Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant(); "
        "if ($actual -ne $expected) { throw 'install.ps1 hash mismatch' }; "
        "& powershell -NoProfile -ExecutionPolicy Bypass -File $script"
    )
    return subprocess.run(
        [str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", snippet],
        text=True,
        capture_output=True,
        timeout=30,
    )


def _ps_single_quote(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _powershell_executable() -> Path | None:
    from shutil import which

    for candidate in ("pwsh", "powershell"):
        found = which(candidate)
        if found is not None:
            return Path(found)
    return None


def _subprocess_failure(result: subprocess.CompletedProcess[str]) -> str:
    stdout = result.stdout.replace(str(ROOT), "<repo>").replace(str(Path.home()), "<home>")
    stderr = result.stderr.replace(str(ROOT), "<repo>").replace(str(Path.home()), "<home>")
    return f"Subprocess failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
