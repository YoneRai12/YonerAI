from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import ci_quality_scans


def test_ci_quality_scan_allows_linux_path_fixtures_under_tests(tmp_path: Path) -> None:
    fixture = tmp_path / "tests" / "path_fixture.py"
    fixture.parent.mkdir()
    fixture.write_text(
        'HOME_FIXTURE = "/home/runner/project"\nROOT_FIXTURE = "/root/project"\n',
        encoding="utf-8",
    )

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("tests/path_fixture.py")])

    assert errors == []


def test_ci_quality_scan_blocks_linux_path_leak_outside_tests(tmp_path: Path) -> None:
    source = tmp_path / "src" / "leak.py"
    source.parent.mkdir()
    source.write_text('LEAK = "/home/runner/project"\n', encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("src/leak.py")])

    assert any("possible local absolute path leak" in error for error in errors)


def test_ci_quality_scan_git_fallback_handles_missing_git(tmp_path: Path, monkeypatch) -> None:
    def raise_os_error(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr(ci_quality_scans.subprocess, "run", raise_os_error)

    assert ci_quality_scans._changed_files(tmp_path) == []
    assert ci_quality_scans._tracked_files(tmp_path) == []

