from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
    "reference_clawdbot",
}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"(?i)\b(?:authorization|proxy-authorization)\s*[:=]\s*bearer\s+[A-Za-z0-9_.+/=-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|discord[_-]?token|client[_-]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9_.:/+=-]{16,}"),
)
LOCAL_PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:[\\/]Users[\\/][A-Za-z0-9_.-]+[\\/]"),
    re.compile(r"/(?:home|Users|root)/[A-Za-z0-9_.-]+/"),
)
MOJIBAKE_PATTERNS = (
    re.compile("\ufffd"),
    re.compile(r"(繝|縺|荳|譁|蜿|螳|險|豁ｴ|邂)"),
)
HIDDEN_UNICODE = tuple(chr(codepoint) for codepoint in (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF))
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
TERMINAL_ESCAPE_PATTERNS = (
    re.compile(r"(?i)(?:\\x1b|\\u001b|\\u009b|\\033|\\e)\[[0-?]*[ -/]*[@-~]"),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run public-safe text scans for YonerAI CI.")
    parser.add_argument("--changed", action="store_true", help="Scan changed text files only.")
    parser.add_argument("--all", action="store_true", help="Scan all tracked text files.")
    args = parser.parse_args(argv)
    repo_root = Path.cwd()
    paths = _changed_files(repo_root) if args.changed or not args.all else _tracked_files(repo_root)
    errors = scan_paths(repo_root, paths)
    if errors:
        print("[FAIL] ci quality scans found issues:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"[OK] ci quality scans passed for {len(paths)} file(s).")
    return 0


def scan_paths(repo_root: Path, paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if not _should_scan(path):
            continue
        full_path = repo_root / path
        try:
            text = full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.as_posix()
        for index, line in enumerate(text.splitlines(), 1):
            _scan_line(rel, index, line, errors)
    return errors


def _scan_line(rel: str, index: int, line: str, errors: list[str]) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(line):
            errors.append(f"{rel}:{index}: possible secret or token literal")
            break
    for pattern in LOCAL_PATH_PATTERNS:
        if pattern.search(line) and not _is_allowed_local_path_fixture(rel, line):
            errors.append(f"{rel}:{index}: possible local absolute path leak")
            break
    for pattern in MOJIBAKE_PATTERNS:
        if pattern.search(line) and not _is_allowed_mojibake_fixture(rel, line):
            errors.append(f"{rel}:{index}: possible mojibake")
            break
    if any(char in line for char in HIDDEN_UNICODE):
        errors.append(f"{rel}:{index}: hidden unicode marker")
    if CONTROL_CHAR_RE.search(line):
        errors.append(f"{rel}:{index}: raw terminal control character")
    for pattern in TERMINAL_ESCAPE_PATTERNS:
        if pattern.search(line) and not _is_allowed_terminal_escape_fixture(rel, line):
            errors.append(f"{rel}:{index}: terminal escape sequence literal")
            break


def _changed_files(repo_root: Path) -> list[Path]:
    pushed_paths = _github_push_changed_files(repo_root)
    if pushed_paths:
        return pushed_paths
    refs = (
        ("git", "diff", "--name-only", "--diff-filter=ACMRT", "origin/main...HEAD"),
        ("git", "diff", "--name-only", "--diff-filter=ACMRT"),
        ("git", "diff", "--name-only", "--diff-filter=ACMRT", "HEAD~1...HEAD"),
    )
    for command in refs:
        result = _run_git(command, repo_root)
        if result.returncode == 0 and result.stdout.strip():
            return _with_untracked(repo_root, [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()])
    return _tracked_files(repo_root)


def _github_push_changed_files(repo_root: Path) -> list[Path]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return []
    before, after = _github_push_range()
    if not before or not after or before == after or set(before) == {"0"}:
        return []
    result = _run_git(("git", "diff", "--name-only", "--diff-filter=ACMRT", f"{before}..{after}"), repo_root)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return _with_untracked(repo_root, [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()])


def _github_push_range() -> tuple[str | None, str | None]:
    before = os.environ.get("GITHUB_EVENT_BEFORE")
    after = os.environ.get("GITHUB_SHA")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        try:
            payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict):
            before = str(payload.get("before") or before or "")
            after = str(payload.get("after") or after or "")
    return before, after


def _tracked_files(repo_root: Path) -> list[Path]:
    result = _run_git(("git", "ls-files"), repo_root)
    if result.returncode != 0:
        return []
    return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]


def _with_untracked(repo_root: Path, paths: list[Path]) -> list[Path]:
    result = _run_git(("git", "ls-files", "--others", "--exclude-standard"), repo_root)
    if result.returncode != 0:
        return paths
    combined = {path.as_posix(): path for path in paths}
    for line in result.stdout.splitlines():
        if line.strip():
            path = Path(line.strip())
            combined.setdefault(path.as_posix(), path)
    return list(combined.values())


def _should_scan(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    parts = set(path.parts)
    return not bool(parts & EXCLUDED_PARTS)


def _is_allowed_local_path_fixture(rel: str, line: str) -> bool:
    if rel.startswith("tests/") and any(path in line for path in ("C:\\Users", "C:/Users", "/Users/", "/home/", "/root/")):
        return True
    return "LOCAL_PATH_PATTERNS" in line or "PRIVATE_MARKERS" in line


def _run_git(command: tuple[str, ...], repo_root: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return subprocess.CompletedProcess(command, returncode=127, stdout="", stderr="")


def _is_allowed_mojibake_fixture(rel: str, line: str) -> bool:
    return rel.endswith("ci_quality_scans.py")


def _is_allowed_terminal_escape_fixture(rel: str, line: str) -> bool:
    return rel.endswith("ci_quality_scans.py") or rel.startswith("tests/")


if __name__ == "__main__":
    raise SystemExit(main())
