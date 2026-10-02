from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path


TEXT_SUFFIXES = {
    ".cfg",
    ".cjs",
    ".css",
    ".cmd",
    ".html",
    ".ini",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".ts",
    ".tsx",
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
QUESTION_MARK_MOJIBAKE_RE = re.compile(r"\?{4,}")
HIDDEN_UNICODE = tuple(
    chr(codepoint)
    for codepoint in (
        0x200B,
        0x200C,
        0x200D,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2060,
        0x2066,
        0x2067,
        0x2068,
        0x2069,
        0xFEFF,
    )
)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
TERMINAL_ESCAPE_PATTERNS = (
    re.compile(r"(?i)(?:\\x1b|\\u001b|\\u009b|\\033|\\e)\[[0-?]*[ -/]*[@-~]"),
)
FULL_COMMIT_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
CI_DIFF_MODES = {
    "two-dot": "..",
    "three-dot": "...",
}


class ChangedFileSelectionError(RuntimeError):
    """Raised when CI cannot prove the exact changed-file range."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run public-safe text scans for YonerAI CI.")
    parser.add_argument("--changed", action="store_true", help="Scan changed text files only.")
    parser.add_argument("--all", action="store_true", help="Scan all tracked text files.")
    args = parser.parse_args(argv)
    repo_root = Path.cwd()
    try:
        paths = _changed_files(repo_root) if args.changed or not args.all else _tracked_files(repo_root)
    except ChangedFileSelectionError as error:
        print(f"[FAIL] ci quality changed-file selection failed: {error}")
        return 1
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
            text = full_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.as_posix()
        for index, line in enumerate(text.splitlines(), 1):
            _scan_line(rel, index, line, errors)
    return errors


def _scan_line(rel: str, index: int, line: str, errors: list[str]) -> None:
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(line):
            if not _is_allowed_secret_reference(rel, line, match):
                errors.append(f"{rel}:{index}: possible secret or token literal")
                break
        else:
            continue
        break
    for pattern in LOCAL_PATH_PATTERNS:
        if pattern.search(line) and not _is_allowed_local_path_fixture(rel, line):
            errors.append(f"{rel}:{index}: possible local absolute path leak")
            break
    for pattern in MOJIBAKE_PATTERNS:
        if pattern.search(line) and not _is_allowed_mojibake_fixture(rel, line):
            errors.append(f"{rel}:{index}: possible mojibake")
            break
    if _has_question_mark_mojibake(line) and not _is_allowed_mojibake_fixture(rel, line):
        errors.append(f"{rel}:{index}: possible mojibake")
    if any(char in line for char in HIDDEN_UNICODE):
        errors.append(f"{rel}:{index}: hidden unicode marker")
    if CONTROL_CHAR_RE.search(line):
        errors.append(f"{rel}:{index}: raw terminal control character")
    for pattern in TERMINAL_ESCAPE_PATTERNS:
        if pattern.search(line) and not _is_allowed_terminal_escape_fixture(rel, line):
            errors.append(f"{rel}:{index}: terminal escape sequence literal")
            break


def _changed_files(repo_root: Path) -> list[Path]:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return _github_actions_changed_files(repo_root)
    return _local_changed_files(repo_root)


def _github_actions_changed_files(repo_root: Path) -> list[Path]:
    base = _validated_ci_sha("YONERAI_DIFF_BASE_SHA")
    head = _validated_ci_sha("YONERAI_DIFF_HEAD_SHA")
    mode = os.environ.get("YONERAI_DIFF_MODE", "")
    separator = CI_DIFF_MODES.get(mode)
    if separator is None:
        raise ChangedFileSelectionError("YONERAI_DIFF_MODE must be 'two-dot' or 'three-dot'")

    _require_commit(repo_root, base, "base")
    _require_commit(repo_root, head, "head")
    range_spec = f"{base}{separator}{head}"
    result = _run_git(
        ("git", "diff", "--name-only", "--diff-filter=ACMRT", "-z", range_spec),
        repo_root,
    )
    if result.returncode != 0:
        raise ChangedFileSelectionError("git diff failed for the validated CI range")

    paths = [Path(name) for name in result.stdout.split("\0") if name]
    print(f"[INFO] ci quality diff mode={mode} range={range_spec} path_count={len(paths)}")
    return paths


def _validated_ci_sha(env_name: str) -> str:
    value = os.environ.get(env_name, "")
    if FULL_COMMIT_SHA_RE.fullmatch(value) is None:
        raise ChangedFileSelectionError(f"{env_name} must be a full 40-character commit SHA")
    return value.lower()


def _require_commit(repo_root: Path, sha: str, role: str) -> None:
    result = _run_git(("git", "cat-file", "-e", f"{sha}^{{commit}}"), repo_root)
    if result.returncode != 0:
        raise ChangedFileSelectionError(f"validated {role} commit is unavailable in the checkout")


def _local_changed_files(repo_root: Path) -> list[Path]:
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


def _is_allowed_secret_reference(rel: str, line: str, match: re.Match[str]) -> bool:
    if rel.startswith("tests/"):
        return False
    matched_text = match.group(0)
    if re.search(r"\b(?:sk-|gh[pousr]_|github_pat_|xox[baprs]-|AKIA|ASIA|AIza)", matched_text):
        return False
    if re.search(r"(?i)\bbearer\s+[A-Za-z0-9_.+/=-]{20,}", matched_text):
        return False
    if "PRIVATE KEY" in matched_text:
        return False
    if _is_safe_env_reference(line, match):
        return True
    if _is_safe_access_token_reference(line, match):
        return True
    return False


def _is_safe_access_token_reference(line: str, match: re.Match[str]) -> bool:
    access_token_match = re.search(
        r"\b(?:token|session)\.(accessToken\s*=\s*(?:account\.access_token|token\.accessToken|session\.accessToken))\b",
        line,
    )
    if not (
        access_token_match
        and access_token_match.start(1) == match.start()
        and access_token_match.end(1) == match.end()
    ):
        return False
    tail_before_terminator = re.split(r";|//", line[access_token_match.end(1) :], maxsplit=1)[0]
    return bool(
        tail_before_terminator.strip() == ""
    )


def _is_safe_env_reference(line: str, match: re.Match[str]) -> bool:
    env_match = re.search(r"\bprocess\.env\.[A-Z0-9_]+\b", match.group(0))
    if not env_match:
        return False
    value_tail = re.split(r"[,;]", line[match.end() :], maxsplit=1)[0]
    if "||" in value_tail or "??" in value_tail or "'" in value_tail or '"' in value_tail:
        return False
    return True


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


def _has_question_mark_mojibake(line: str) -> bool:
    if not QUESTION_MARK_MOJIBAKE_RE.search(line):
        return False
    return any(ord(char) > 127 for char in line)


def _is_allowed_terminal_escape_fixture(rel: str, line: str) -> bool:
    if rel.endswith("ci_quality_scans.py") or rel.startswith("tests/"):
        return True
    if rel == "start.sh" and re.match(r"^[A-Z_]+='\\033\[[0-9;]*m'", line):
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
