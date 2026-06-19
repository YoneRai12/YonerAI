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


def test_install_script_is_plan_first_verified_github_release_bootstrap() -> None:
    script = INSTALL_SKELETON.read_text(encoding="utf-8")

    assert "GitHub Release installer" in script
    assert "Plan only. Nothing was installed." in script
    assert "not performed unless -Execute" in script
    assert "Invoke-VerifiedLocalBootstrap" in script
    assert "Custom manifest/artifact inputs are not accepted by install.ps1" in script
    assert "Invoke-Expression" not in script
    assert "PATH mutation: disabled unless -SetPath" in script
    assert "user wrapper: refreshed on install at %LOCALAPPDATA%\\YonerAI\\bin\\yonerai.cmd" in script
    assert "[switch]$SetPath" in script
    assert "[switch]$Shortcut" in script
    assert "optional shortcuts: disabled unless -Shortcut" in script
    assert "CreateShortcut" in script
    assert "New-YonerAIShortcut" in script
    assert "Write-YonerAIUserWrapper" in script
    assert "Write-Warning \"Failed to create shortcuts; continuing without them.\"" in script
    assert "SetEnvironmentVariable" in script
    assert re.search(r"\bsetx\b", script, flags=re.IGNORECASE) is None


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


def test_install_script_plan_mode_does_not_install_when_powershell_available() -> None:
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
    assert "install.yonerai.com" in result.stdout
    assert "-Execute" in result.stdout
    assert "PATH mutation" in result.stdout
    assert "user wrapper: refreshed on install" in result.stdout
    assert "-Shortcut" in result.stdout
    assert "Optional shortcuts" in result.stdout


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
