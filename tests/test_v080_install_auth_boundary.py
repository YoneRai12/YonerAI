from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SKELETON = ROOT / "install.ps1"
V070_MANIFEST = ROOT / "releases" / "manifest.v0.7.0-alpha.1.json"


def test_v080_boundary_docs_exist_and_keep_public_private_split() -> None:
    plan = (ROOT / "docs" / "tasks" / "V0_8_OFFICIAL_INSTALL_AUTH_EVOLUTION_PLAN.md").read_text(
        encoding="utf-8"
    )
    boundary = (ROOT / "docs" / "contracts" / "OFFICIAL_SELF_EVOLUTION_BOUNDARY.md").read_text(
        encoding="utf-8"
    )
    handoff = (ROOT / "docs" / "private_handoff" / "YONERAI_ORACLE_SELF_EVOLUTION_HANDOFF.md").read_text(
        encoding="utf-8"
    )

    for text in (plan, boundary, handoff):
        assert "production Oracle" in text
        assert "production Google login" in text or "production auth" in text or "account linking" in text
        assert "proposal-only" in text
        assert "raw prompt" in text or "raw prompts" in text
        assert "provider key" in text or "production tokens" in text

    assert "Private/official lane only" in plan
    assert "Public Repository Must Not Include" in boundary
    assert "This public repository does not implement the production system" in handoff


def test_v080_site_content_is_candidate_not_deployed_or_production_claim() -> None:
    release_page = (ROOT / "docs" / "site" / "yonerai.com" / "releases" / "v0.8.0-alpha.1.md").read_text(
        encoding="utf-8"
    )
    press_card = (ROOT / "docs" / "site" / "yonerai.com" / "press" / "v0.8.0-alpha.1-card.md").read_text(
        encoding="utf-8"
    )
    install_page = (ROOT / "docs" / "site" / "yonerai.com" / "install.md").read_text(encoding="utf-8")

    for text in (release_page, press_card, install_page):
        assert "v0.8.0-alpha.1" in text
        assert "not" in text.lower()
        assert "production network installer" in text
        assert "OpenAI shared traffic" in text
        assert "production Google login" in text

    assert "not a live download promise" in install_page
    assert "does not download, install, mutate" in install_page
    assert "/自己進化" in release_page


def test_install_skeleton_reads_local_manifest_plan_without_actions_when_powershell_available() -> None:
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
            "-Manifest",
            str(V070_MANIFEST.relative_to(ROOT)),
            "-Artifact",
            "YonerAI-0.7.0-alpha.1.zip",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, _subprocess_failure(result)
    assert "Plan only. Nothing was installed." in output
    assert "manifest version: 0.7.0-alpha.1" in output
    assert "artifact name: YonerAI-0.7.0-alpha.1.zip" in output
    assert "sha256 format valid: True" in output
    assert "production trust: not present in public repo" in output
    assert "not performed: network download" in output
    assert "PATH mutation" in output
    assert "remote script execution" in output


def test_install_skeleton_rejects_absolute_manifest_path_when_powershell_available() -> None:
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
            "-Manifest",
            str(V070_MANIFEST),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "Manifest must be a relative local path" in (result.stdout + result.stderr)


def test_install_skeleton_does_not_contain_remote_execute_or_path_mutation_primitives() -> None:
    script = INSTALL_SKELETON.read_text(encoding="utf-8")

    assert "Invoke-Expression" not in script
    assert re.search(r"\biex\b", script, flags=re.IGNORECASE) is None
    assert "Invoke-WebRequest" not in script
    assert re.search(r"\biwr\b", script, flags=re.IGNORECASE) is None
    assert re.search(r"\birm\b", script, flags=re.IGNORECASE) is None
    assert "SetEnvironmentVariable" not in script
    assert re.search(r"\bsetx\b", script, flags=re.IGNORECASE) is None


def _powershell_executable() -> Path | None:
    from shutil import which

    for candidate in ("pwsh", "powershell"):
        found = which(candidate)
        if found:
            return Path(found)
    return None


def _subprocess_failure(result: subprocess.CompletedProcess[str]) -> str:
    stdout = result.stdout.replace(str(ROOT), "<repo>")
    stderr = result.stderr.replace(str(ROOT), "<repo>")
    return f"Subprocess failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
