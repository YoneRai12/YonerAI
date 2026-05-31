from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


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
    assert "Quick install command" in text
    assert "Verified install command" in text
    assert "install.ps1.sha256" in text
    assert "sidecar SHA256 is invalid" in text
    assert "install.ps1 hash mismatch" in text
    assert "fails closed" in text
    assert "must not be an installer file source" in text
    assert "It does not read installer bytes from `yonerai.com`" in text
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


def test_install_script_rejects_local_custom_sources_and_has_no_iex() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "Local or custom manifest/artifact inputs are not accepted" in script
    assert "Artifact filename must be the pinned versioned asset" in script
    assert "latest, main, or source aliases" in script
    assert "Invoke-Expression" not in script
    assert re.search(r"\biex\b", script, flags=re.IGNORECASE) is None
    assert "SetEnvironmentVariable" not in script
    assert re.search(r"\bsetx\b", script, flags=re.IGNORECASE) is None
    assert "https://yonerai.com" not in script
    assert "https://github.com/YoneRai12/YonerAI/releases/download" in script
    assert LATEST_INSTALL_URL in script


def test_install_status_reports_github_release_only_source_policy() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_install_status

    report = build_install_status(ROOT, channel="stable")

    assert report["schema_version"] == "yonerai-install-status/v0.1"
    assert report["channel"] == "stable"
    assert report["selected_version"] == "0.6.3"
    assert report["selected_tag"] == "v0.6.3"
    assert report["selected_artifact"]["actual_filename"] == "YonerAI-0.6.3.zip"
    assert "alpha" not in report["selected_artifact"]["actual_filename"]
    assert report["source_policy"]["install_script_source"] == "github_latest_release_asset_redirect"
    assert report["source_policy"]["artifact_source"] == "github_release_asset_only"
    assert report["source_policy"]["yonerai_com_serves_install_script"] is False
    assert report["source_policy"]["yonerai_com_serves_manifest_or_zip"] is False
    assert report["source_policy"]["local_file_source_allowed"] is False
    assert report["recommended_commands"]["stable"].startswith("& ([scriptblock]::Create((irm ")
    assert LATEST_INSTALL_URL in report["recommended_commands"]["stable"]
    assert "-Channel alpha" in report["recommended_commands"]["alpha"]
    assert "install.ps1.sha256" in report["recommended_commands"]["verify_first"]
    assert "sidecar SHA256 is invalid" in report["recommended_commands"]["verify_first"]
    assert "install.ps1 hash mismatch" in report["recommended_commands"]["verify_first"]


def test_alpha_install_status_matches_current_public_alpha_manifest() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_install_status

    report = build_install_status(ROOT, channel="alpha")

    assert report["ok"] is True
    assert report["channel"] == "alpha"
    assert report["selected_version"] == "0.11.0-alpha.1"
    assert report["selected_tag"] == "v0.11.0-alpha.1"
    assert report["selected_artifact"]["actual_filename"] == "YonerAI-0.11.0-alpha.1.zip"
    assert report["source_policy"]["alpha_requires_explicit_channel"] is True


def test_install_status_cli_json_is_stable_and_redacted() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from yonerai_cli.cli import main; main()",
            "install",
            "status",
            "--json",
        ],
        cwd=CLI_SRC,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["schema_version"] == "yonerai-install-status/v0.1"
    assert report["source_policy"]["install_page"] == "https://yonerai.com/install"
    assert str(ROOT) not in result.stdout
    assert "provider key" not in result.stdout.lower()


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
