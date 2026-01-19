import contextlib
import logging
import os
import re
import shlex
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

DENY_META_CHARS = re.compile(r"[;&><`]")
ALLOWED_CMDS = {"cat", "diff", "find", "grep", "head", "lines", "ls", "rg", "stat", "tree", "tail", "wc"}

DENY_BASENAMES = {
    ".env",
    ".env.local",
    ".envrc",
    ".npmrc",
    ".pypirc",
    ".netrc",
    ".git-credentials",
    "id_rsa",
    "id_rsa.pub",
    "credentials.json",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "secrets.env",
    "secrets.txt",
    "private.key",
    "private.pem",
}

ALLOWED_FLAGS: Dict[str, Set[str]] = {
    "cat": {"-n"},
    "diff": {"-u"},
    "find": {"-m"},
    "grep": {"-n", "-i", "-m", "-C", "-A", "-B"},
    "head": {"-n"},
    "lines": {"-s", "-e"},
    "ls": {"-l", "-la", "-al", "-a", "-lh"},
    "rg": {"-n", "-i", "-m", "-C", "-A", "-B"},
    "stat": set(),
    "tree": {"-L", "-a"},
    "tail": {"-n"},
    "wc": {"-l", "-w", "-c"},
}

FLAG_REQUIRES_VALUE: Dict[str, Set[str]] = {
    "find": {"-m"},
    "grep": {"-m", "-C", "-A", "-B"},
    "rg": {"-m", "-C", "-A", "-B"},
    "head": {"-n"},
    "lines": {"-s", "-e"},
    "tree": {"-L"},
    "tail": {"-n"},
}

PATTERN_ARG_COUNT: Dict[str, int] = {"find": 1, "grep": 1, "rg": 1}


@dataclass
class ShellPolicy:
    root_dir: Path
    hard_timeout_sec: float = 10.0
    max_bytes: int = 200_000
    max_commands: int = 1
    max_files_scanned: int = 5_000
    max_total_bytes_scanned: int = 5_000_000
    max_depth: int = 6


class ReadOnlyShellExecutor:
    """Safe, read-only shell emulator for inspecting the codebase."""

    def __init__(self, policy: ShellPolicy) -> None:
        self.p = policy
        self.root = policy.root_dir.resolve()

    def _parse_args(self, cmd: str, args: List[str]) -> Tuple[Set[str], Dict[str, str], List[str]]:
        flags: Set[str] = set()
        values: Dict[str, str] = {}
        positionals: List[str] = []
        requires = FLAG_REQUIRES_VALUE.get(cmd, set())

        idx = 0
        while idx < len(args):
            token = args[idx]
            if token.startswith("-"):
                flags.add(token)
                if token in requires:
                    if idx + 1 >= len(args):
                        raise ValueError(f"{cmd}: flag '{token}' requires a value")
                    values[token] = args[idx + 1]
                    idx += 2
                    continue
                idx += 1
                continue

            positionals.append(token)
            idx += 1

        return flags, values, positionals

    def _is_safe_path(self, candidate: str) -> bool:
        if candidate.startswith(("/", "\\")) or ":" in candidate:
            return False
        parts = Path(candidate).parts
        if ".." in parts:
            return False
        if any(part == ".git" for part in parts):
            return False
        resolved = (self.root / candidate).resolve()
        try:
            rel = resolved.relative_to(self.root)
        except Exception:
            return False
        if any(part == ".git" for part in rel.parts):
            return False
        if resolved.name in DENY_BASENAMES:
            return False
        return True

    def validate(self, cmd: str) -> str | None:
        if DENY_META_CHARS.search(cmd):
            return "Denied: meta characters are not allowed."

        parts = shlex.split(cmd)
        if not parts:
            return "Denied: empty command."

        command = parts[0]
        if command not in ALLOWED_CMDS:
            return f"Denied: command '{command}' is not allowed."

        allowed_flags = ALLOWED_FLAGS.get(command, set())
        flags_require_value = FLAG_REQUIRES_VALUE.get(command, set())
        pattern_budget = PATTERN_ARG_COUNT.get(command, 0)
        saw_path = False
        path_args: List[str] = []

        idx = 1
        while idx < len(parts):
            arg = parts[idx]
            if arg.startswith("-"):
                if arg not in allowed_flags:
                    return f"Denied: flag '{arg}' is not allowed for {command}."
                if arg in flags_require_value:
                    if idx + 1 >= len(parts):
                        return f"Denied: flag '{arg}' requires a value."
                    value = parts[idx + 1]
                    if not value.isdigit():
                        return f"Denied: flag '{arg}' value must be a non-negative integer."
                    idx += 2
                    continue
                idx += 1
                continue

            if pattern_budget > 0:
                pattern_budget -= 1
                idx += 1
                continue

            if arg in DENY_BASENAMES or Path(arg).name in DENY_BASENAMES:
                return f"Denied: access to '{arg}' is not allowed."
            if any(char in arg for char in ["*", "?", "{", "}"]):
                return "Denied: glob patterns are not allowed."
            if not self._is_safe_path(arg):
                return f"Denied: path '{arg}' is out of root."
            resolved_arg = (self.root / arg).resolve()
            if command == "cat":
                with contextlib.suppress(OSError):
                    if resolved_arg.exists() and resolved_arg.stat().st_size > self.p.max_bytes:
                        return f"Denied: file '{arg}' is too large ({self.p.max_bytes} bytes max)."

            path_args.append(arg)
            saw_path = True
            idx += 1

        if command in {"rg", "grep"}:
            if not saw_path:
                return "Denied: provide an explicit search path for grep/rg."
            if "-m" not in parts:
                return "Denied: include -m <limit> to bound grep/rg output."

        if command == "tree":
            # implicit dot is allowed for tree if no path
            pass

        if command == "diff":
            if len(path_args) != 2:
                return "Denied: diff expects exactly two file paths."

        if command == "find":
            if pattern_budget > 0:
                return "Denied: provide a search pattern for find."
            if not saw_path:
                return "Denied: provide an explicit search path for find."
            if "-m" not in parts:
                return "Denied: include -m <limit> to bound find output."

        if command == "lines":
            if "-s" not in parts or "-e" not in parts:
                return "Denied: lines requires -s <start> and -e <end>."
            if not path_args:
                return "Denied: provide a file path for lines."

        return None

    def run(self, cmd: str) -> Dict[str, Any]:
        """Execute a validated read-only command."""
        parts = shlex.split(cmd)
        if not parts:
            return {"stdout": "", "stderr": "Empty command", "outcome": {"exit_code": 1}}

        name = parts[0]
        args = parts[1:]

        def trunc(text: str) -> str:
            data = text.encode("utf-8", errors="replace")
            if len(data) <= self.p.max_bytes:
                return text
            return data[: self.p.max_bytes].decode("utf-8", errors="ignore")

        class ScanLimitExceeded(Exception):
            pass

        files_scanned = 0
        bytes_scanned = 0

        def resolve_path(arg: str) -> Path:
            if not arg:
                return self.root
            return (self.root / arg).resolve()

        def check_limits(path: Path) -> None:
            nonlocal files_scanned, bytes_scanned
            files_scanned += 1
            if files_scanned > self.p.max_files_scanned:
                raise ScanLimitExceeded("file_limit")
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            bytes_scanned += size
            if bytes_scanned > self.p.max_total_bytes_scanned:
                raise ScanLimitExceeded("byte_limit")

        def iter_files(base: Path) -> List[Path]:
            if base.is_file():
                try:
                    resolved_file = base.resolve()
                    resolved_file.relative_to(self.root)
                    if resolved_file.name in DENY_BASENAMES or ".git" in resolved_file.parts:
                        return []
                    check_limits(resolved_file)
                    return [resolved_file]
                except Exception:
                    return []

            if base.is_dir():
                out: List[Path] = []
                try:
                    for root_path, dirs, files in os.walk(base):
                        resolved_root = Path(root_path).resolve()
                        if ".git" in resolved_root.parts:
                            dirs[:] = []
                            continue

                        # Prune hidden dirs (optional, but good for cleanliness)
                        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in DENY_BASENAMES]

                        for file_name in sorted(files):
                            if file_name in DENY_BASENAMES:
                                continue
                            fpath = resolved_root / file_name
                            check_limits(fpath)
                            out.append(fpath)
                except ScanLimitExceeded:
                    raise
                except Exception:
                    pass
                return out
            return []

        # --- COMMAND IMPLEMENTATIONS (Simulated) ---

        if name == "ls":
            flags, _, positionals = self._parse_args(name, args)
            show_all = any(flag in flags for flag in ("-a", "-al", "-la"))
            long = any(flag in flags for flag in ("-l", "-al", "-la", "-lh"))
            human = "-lh" in flags
            shown = positionals[-1] if positionals else "."
            base = resolve_path(shown)

            if not base.exists():
                return {"stdout": "", "stderr": "No such file or directory", "outcome": {"exit_code": 2}}

            entries = [base] if base.is_file() else sorted(base.iterdir(), key=lambda p: p.name.lower())
            lines = []
            for entry in entries:
                if entry.name in DENY_BASENAMES:
                    continue
                if not show_all and entry.name.startswith("."):
                    continue

                if long:
                    try:
                        st = entry.stat()
                        kind = "d" if entry.is_dir() else "-"
                        size = f"{st.st_size / 1024:.1f}K" if human else str(st.st_size)
                        mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                        lines.append(f"{kind} {size:>8} {mtime} {entry.name}")
                    except:
                        pass
                else:
                    lines.append(entry.name)

            return {"stdout": trunc("\n".join(lines)), "stderr": "", "outcome": {"exit_code": 0}}

        if name == "cat":
            _, _, targets = self._parse_args(name, args)
            target = resolve_path(targets[0])
            if not target.is_file():
                return {"stdout": "", "stderr": "Not a file", "outcome": {"exit_code": 1}}
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
                return {"stdout": trunc(content), "stderr": "", "outcome": {"exit_code": 0}}
            except Exception as e:
                return {"stdout": "", "stderr": str(e), "outcome": {"exit_code": 1}}

        if name == "grep" or name == "rg":
            flags, values, positionals = self._parse_args(name, args)
            pattern = positionals[0]
            target_path = resolve_path(positionals[1])
            ignore_case = "-i" in flags
            try:
                regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
            except re.error as e:
                return {"stdout": "", "stderr": f"Invalid regex: {e}", "outcome": {"exit_code": 2}}

            hits = []
            try:
                # Simplified walk for grep
                def walk_grep(path):
                    if path.is_file():
                        try:
                            with path.open("r", encoding="utf-8", errors="replace") as f:
                                for i, line in enumerate(f):
                                    if regex.search(line):
                                        rel = path.relative_to(self.root)
                                        hits.append(f"{rel}:{i + 1}:{line.strip()}")
                        except:
                            pass
                    elif path.is_dir():
                        for child in path.iterdir():
                            if child.name not in DENY_BASENAMES and not child.name.startswith("."):
                                walk_grep(child)

                walk_grep(target_path)
            except Exception as e:
                return {"stdout": "", "stderr": str(e), "outcome": {"exit_code": 1}}

            return {
                "stdout": trunc("\n".join(hits[: int(values.get("-m", 200))])),
                "stderr": "",
                "outcome": {"exit_code": 0},
            }

        # Fallback for others not fully implemented in this port yet
        return {"stdout": "", "stderr": "Command not fully implemented in ORA port yet.", "outcome": {"exit_code": 0}}
