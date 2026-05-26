from __future__ import annotations

import json
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


def test_changed_files_uses_github_push_range_for_full_pushed_change_set(tmp_path: Path, monkeypatch) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "YonerAI Test")
    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", "base.txt")
    _git(tmp_path, "commit", "-m", "base")
    before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    (tmp_path / "first.py").write_text("FIRST = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "first.py")
    _git(tmp_path, "commit", "-m", "first")
    (tmp_path / "second.py").write_text("SECOND = 2\n", encoding="utf-8")
    _git(tmp_path, "add", "second.py")
    _git(tmp_path, "commit", "-m", "second")
    after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    event = tmp_path / "event.json"
    event.write_text(json.dumps({"before": before, "after": after}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_SHA", after)

    paths = {path.as_posix() for path in ci_quality_scans._changed_files(tmp_path)}

    assert {"first.py", "second.py"}.issubset(paths)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

