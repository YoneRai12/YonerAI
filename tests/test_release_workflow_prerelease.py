from __future__ import annotations

from pathlib import Path


def test_release_workflow_marks_alpha_beta_rc_as_prereleases() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "Classify Release Channel" in workflow
    assert "*-alpha|*-alpha.*|*-alpha+*|*-beta|*-beta.*|*-beta+*|*-rc|*-rc.*|*-rc+*)" in workflow
    assert 'echo "ORA_PRERELEASE=true" >> "$GITHUB_ENV"' in workflow
    assert 'echo "ORA_PRERELEASE=false" >> "$GITHUB_ENV"' in workflow
    assert "prerelease: ${{ env.ORA_PRERELEASE }}" in workflow


def test_release_workflow_keeps_release_notes_and_version_guards() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert 'python scripts/verify_version.py --tag "${GITHUB_REF_NAME}"' in workflow
    assert 'test -f "docs/releases/${ORA_VERSION}.md"' in workflow
    assert "body_path: docs/releases/${{ env.ORA_VERSION }}.md" in workflow
    assert "generate_release_notes: false" in workflow
