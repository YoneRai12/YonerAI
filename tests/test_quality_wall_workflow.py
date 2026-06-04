from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/quality-wall.yml")
REQUIRED_CHECKS = Path("docs/process/REQUIRED_CHECKS.md")


def test_quality_wall_workflow_splits_user_visible_gates() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for job_name in (
        "core-unit:",
        "cli-smoke:",
        "tui-smoke:",
        "provider-boundary:",
        "hybrid-zero-trust:",
        "installer-manifest:",
        "windows-cli-smoke:",
        "windows-installer-manifest:",
        "macos-cli-smoke:",
        "macos-installer-manifest:",
        "security-static:",
        "release-gate:",
    ):
        assert job_name in workflow

    assert "runs-on: windows-latest" in workflow
    assert "runs-on: macos-latest" in workflow
    assert 'branches: [main, "stable/**"]' in workflow
    assert "python scripts/ci_quality_scans.py --changed" in workflow
    assert "git diff --check" in workflow
    assert "ruff check" in workflow
    assert "python -m compileall" in workflow
    assert "tests/test_auth_privacy_policy.py" in workflow
    assert "tests/test_release_gate.py" in workflow


def test_release_gate_workflow_does_not_publish() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "softprops/action-gh-release" not in workflow
    assert "python scripts/release_gate.py" in workflow
    assert "--github-prerelease auto" in workflow


def test_required_checks_doc_lists_quality_wall_jobs() -> None:
    doc = REQUIRED_CHECKS.read_text(encoding="utf-8")

    for check_name in (
        "core-unit",
        "cli-smoke",
        "tui-smoke",
        "provider-boundary",
        "hybrid-zero-trust",
        "installer-manifest",
        "security-static",
        "release-gate",
        "windows-cli-smoke",
        "windows-installer-manifest",
        "macos-cli-smoke",
        "macos-installer-manifest",
    ):
        assert check_name in doc
