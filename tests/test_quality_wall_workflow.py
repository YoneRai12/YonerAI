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
    assert "python scripts/ci_quality_scans.py --changed" in workflow
    assert "git diff --check" in workflow
    assert "ruff check" in workflow
    assert "python -m compileall" in workflow
    assert "tests/test_auth_privacy_policy.py" in workflow
    assert "tests/test_release_gate.py" in workflow
    assert "tests/test_v080_install_auth_boundary.py" in workflow


def test_release_gate_workflow_does_not_publish() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "softprops/action-gh-release" not in workflow
    assert "python scripts/release_gate.py" in workflow
    assert "--github-prerelease auto" in workflow
    assert "fetch-depth: 0" in workflow
    assert "PUSH_BEFORE=\"${{ github.event.before }}\"" in workflow
    assert "RELEASE_DIFF_RANGE=\"${PUSH_BEFORE}..HEAD\"" in workflow
    assert "RELEASE_DIFF_RANGE=\"origin/${BASE_REF}...HEAD\"" in workflow
    assert "python scripts/create_release.py \"${VERSION}\"" in workflow
    assert '--artifact "${PRODUCT_NAME}-${VERSION}.zip"' in workflow
    assert "git diff --name-only \"${RELEASE_DIFF_RANGE}\"" in workflow
    assert (
        "grep -E '^(VERSION|PRODUCT_NAME|releases/manifest\\.v[^/]+\\.json|docs/releases/[^/]+\\.md)$'"
        in workflow
    )
    assert "releases/manifest|docs/releases/" not in workflow


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
