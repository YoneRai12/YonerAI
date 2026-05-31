from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SKELETON = ROOT / "install.ps1"
V070_MANIFEST = ROOT / "releases" / "manifest.v0.7.0-alpha.1.json"
V080_MANIFEST = ROOT / "releases" / "manifest.v0.8.0-alpha.1.json"
MOJIBAKE_MARKERS = ("\ufffd", "\u7e5d", "\u87fe", "\u8b8c", "\u87f9")


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

    for page_text in (release_page, press_card, install_page):
        assert "v0.8.0-alpha.1" in page_text
        assert "not" in page_text.lower()
        assert "production network installer" in page_text
        assert "OpenAI shared traffic" in page_text
        assert "production Google login" in page_text
        assert not any(marker in page_text for marker in MOJIBAKE_MARKERS)

    assert "not a live download promise" in install_page
    assert "does not download, install, mutate" in install_page
    assert "/\u81ea\u5df1\u9032\u5316" in release_page
    assert "/\u81ea\u5df1\u9032\u5316 stays proposal-only" in press_card


def test_v080_manifest_validates_as_non_production_alpha_manifest() -> None:
    import sys

    cli_src = ROOT / "clients" / "cli"
    if str(cli_src) not in sys.path:
        sys.path.insert(0, str(cli_src))
    from yonerai_cli.release_manifest import load_manifest_file, verify_manifest

    report = verify_manifest(load_manifest_file(str(V080_MANIFEST)))

    assert report["contract_valid"] is True
    assert report["install_ready"] is False
    assert report["version"] == "0.8.0-alpha.1"
    assert report["release_tag"] == "v0.8.0-alpha.1"
    assert report["channel"] == "alpha"
    assert report["signature_state"] == "placeholder_non_production"
    assert report["production_signature_verified"] is False
    assert report["production_trust_material"] is False


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
    assert "artifact name matches manifest: True" in output
    assert "local artifact status: not found; hash not checked" in output
    assert "production trust: not present in public repo" in output
    assert "not performed: network download" in output
    assert "PATH mutation" in output
    assert "remote script execution" in output


def test_install_skeleton_rejects_tampered_local_artifact_when_powershell_available() -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    artifact_dir = ROOT / ".installer-tamper-test"
    artifact_path = artifact_dir / "YonerAI-0.7.0-alpha.1.zip"
    artifact_dir.mkdir(exist_ok=True)
    artifact_path.write_bytes(b"tampered artifact")
    try:
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
                str(artifact_path.relative_to(ROOT)),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )
    finally:
        artifact_path.unlink(missing_ok=True)
        try:
            artifact_dir.rmdir()
        except OSError:
            pass

    output = result.stdout + result.stderr
    assert result.returncode != 0, _subprocess_failure(result)
    assert "local artifact sha256 matches manifest: False" in output
    assert "Artifact SHA256 mismatch" in output
    assert "Plan only. Nothing was installed." not in output


def test_install_skeleton_selects_matching_artifact_when_manifest_has_multiple_entries() -> None:
    powershell = _powershell_executable()
    if powershell is None:
        return

    artifact_dir = ROOT / ".installer-multi-artifact-test"
    manifest_path = artifact_dir / "manifest.json"
    artifact_path = artifact_dir / "YonerAI-0.7.0-alpha.1-windows-x64.zip"
    artifact_bytes = b"fixture windows artifact"
    artifact_dir.mkdir(exist_ok=True)
    artifact_path.write_bytes(artifact_bytes)
    manifest = json.loads(V070_MANIFEST.read_text(encoding="utf-8"))
    manifest["artifacts"].append(
        {
            "id": "yonerai-0.7.0-alpha.1-windows-x64",
            "kind": "windows_zip",
            "target": "windows-x64",
            "os": "windows",
            "arch": "x64",
            "url": (
                "https://github.com/YoneRai12/YonerAI/releases/download/"
                "v0.7.0-alpha.1/YonerAI-0.7.0-alpha.1-windows-x64.zip"
            ),
            "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
            "size_bytes": len(artifact_bytes),
            "signature": {"status": "placeholder_non_production"},
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    try:
        result = subprocess.run(
            [
                str(powershell),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(INSTALL_SKELETON),
                "-Manifest",
                str(manifest_path.relative_to(ROOT)),
                "-Artifact",
                str(artifact_path.relative_to(ROOT)),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )
    finally:
        artifact_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        try:
            artifact_dir.rmdir()
        except OSError:
            pass

    output = result.stdout + result.stderr
    assert result.returncode == 0, _subprocess_failure(result)
    assert "artifact name: YonerAI-0.7.0-alpha.1-windows-x64.zip" in output
    assert "artifact name matches manifest: True" in output
    assert "local artifact sha256 matches manifest: True" in output
    assert "local artifact size matches manifest: True" in output
    assert "Plan only. Nothing was installed." in output


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

    assert result.returncode != 0, _subprocess_failure(result)
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
    stdout = _redact_subprocess_output(result.stdout)
    stderr = _redact_subprocess_output(result.stderr)
    return f"Subprocess failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"


def _redact_subprocess_output(text: str) -> str:
    redacted = text.replace(str(ROOT), "<repo>")
    redacted = re.sub(
        r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+[\\/]+AppData[\\/]+Local[\\/]+Temp[\\/]+[^,\s]+",
        "<tmp>",
        redacted,
    )
    return redacted
