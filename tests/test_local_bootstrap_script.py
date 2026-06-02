from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "install-local.ps1"
INSTALL_SKELETON = ROOT / "install.ps1"


def test_local_bootstrap_script_is_plan_first_and_non_remote_execution() -> None:
    script = BOOTSTRAP.read_text(encoding="utf-8")

    assert "param(" in script
    assert "[switch]$Execute" in script
    assert "[switch]$Launch" in script
    assert "Plan only. Nothing was installed." in script
    assert "remote script execution, PATH mutation, registry change, service install, admin request" in script
    assert "Invoke-Expression" not in script
    assert re.search(r"\biex\b", script, flags=re.IGNORECASE) is None
    assert "Invoke-WebRequest" not in script
    assert re.search(r"\biwr\b", script, flags=re.IGNORECASE) is None
    assert re.search(r"\birm\b", script, flags=re.IGNORECASE) is None
    assert "SetEnvironmentVariable" not in script
    assert re.search(r"\bsetx\b", script, flags=re.IGNORECASE) is None


def test_install_bootstrap_uses_github_release_only_and_rejects_custom_sources() -> None:
    script = INSTALL_SKELETON.read_text(encoding="utf-8")

    assert "GitHub Release installer" in script
    assert "Plan only. Nothing was installed." in script
    assert "Custom manifest/artifact inputs are not accepted" in script
    assert "https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1" in script
    assert "https://github.com/YoneRai12/YonerAI/releases/download" in script
    assert "https://api.github.com/repos/YoneRai12/YonerAI/releases" in script
    assert "irm https://install.yonerai.com | iex" in script
    assert "Invoke-Expression" not in script
    assert "Invoke-GitHubApi" in script
    assert "[switch]$Repair" in script
    assert "[switch]$Force" in script
    assert "[switch]$CleanRetry" in script
    assert "[switch]$SetPath" in script
    assert "Get-Command \"yonerai\" -All" in script
    assert "old Python Scripts executable may shadow the wrapper" in script
    assert "if (-not $SetPath -or $NoPath)" in script
    assert "SetEnvironmentVariable" in script
    assert re.search(r"\bsetx\b", script, flags=re.IGNORECASE) is None
    assert "v0.11.0-alpha.1" not in script


def test_local_bootstrap_script_rejects_absolute_venv_target_when_powershell_available() -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BOOTSTRAP),
            "-Venv",
            str(ROOT),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "Refusing absolute target path" in (result.stderr + result.stdout)


def test_local_bootstrap_script_rejects_repo_root_venv_when_powershell_available() -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BOOTSTRAP),
            "-Venv",
            ".",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "Refusing to use the repository root" in (result.stderr + result.stdout)


def test_local_bootstrap_script_rejects_path_traversal_venv_when_powershell_available() -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BOOTSTRAP),
            "-Venv",
            "..\\yonerai-outside-venv",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "Refusing target path outside" in (result.stderr + result.stdout)


def test_local_bootstrap_plan_mode_does_not_install_when_powershell_available() -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BOOTSTRAP),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, _subprocess_failure(result)
    assert "Plan only. Nothing was installed." in result.stdout
    assert ".\\install-local.ps1 -Execute" in result.stdout
    assert "PATH mutation" in result.stdout


def test_install_skeleton_plan_mode_does_not_install_when_powershell_available() -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALL_SKELETON),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, _subprocess_failure(result)
    assert "Plan only. Nothing was installed." in result.stdout
    assert "GitHub Release assets" in result.stdout
    assert "PATH mutation" in result.stdout
    assert "current yonerai command" in result.stdout


def test_install_bootstrap_rejects_existing_target_before_download_when_powershell_available(tmp_path: Path) -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    install_dir = tmp_path / "existing-install"
    source_dir = install_dir / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "partial.txt").write_text("partial", encoding="utf-8")

    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALL_SKELETON),
            "-Execute",
            "-Version",
            "0.6.4",
            "-InstallDir",
            str(install_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "-Repair" in combined
    assert "-Force" in combined
    assert "-CleanRetry" in combined
    assert "Downloading manifest" not in combined
    assert "Downloading artifact" not in combined
    assert str(tmp_path) not in _subprocess_failure(result)


def _powershell_executable() -> Path | None:
    candidates = ("pwsh", "powershell")
    for candidate in candidates:
        path = _which(candidate)
        if path is not None:
            return path
    return None


def _which(command: str) -> Path | None:
    from shutil import which

    found = which(command)
    return Path(found) if found else None


def _subprocess_failure(result: subprocess.CompletedProcess[str]) -> str:
    stdout = result.stdout.replace(str(ROOT), "<tmp>")
    stderr = result.stderr.replace(str(ROOT), "<tmp>")
    return f"Subprocess failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
