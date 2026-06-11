from __future__ import annotations

from pathlib import Path


def test_release_workflow_marks_any_semver_prerelease_as_prerelease() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "Classify Release Channel" in workflow
    assert 'core = version.split("+", 1)[0]' in workflow
    assert 'print("true" if "-" in core else "false")' in workflow
    assert "ORA_PRERELEASE=$ORA_PRERELEASE" in workflow
    assert "prerelease: ${{ env.ORA_PRERELEASE }}" in workflow


def test_release_workflow_keeps_release_notes_and_version_guards() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert 'python scripts/verify_version.py --tag "${GITHUB_REF_NAME}"' in workflow
    assert 'test -f "docs/releases/${ORA_VERSION}.md"' in workflow
    assert "Read Release Title" in workflow
    assert "RELEASE_TITLE" in workflow
    assert "name: ${{ env.RELEASE_TITLE }}" in workflow
    assert "body_path: docs/releases/${{ env.ORA_VERSION }}.md" in workflow
    assert "generate_release_notes: false" in workflow
    assert "Run Release Gate" in workflow
    assert 'python scripts/release_gate.py \\' in workflow
    assert '--tag "${GITHUB_REF_NAME}"' in workflow
    assert '--artifact "${PRODUCT_NAME}-${ORA_VERSION}.zip"' in workflow
    assert '--github-prerelease "${ORA_PRERELEASE}"' in workflow


def test_release_workflow_fetches_tags_before_current_truth_archive() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "fetch-depth: 0" in workflow
    assert "Regenerate CURRENT_TRUTH.md for release archive" in workflow
