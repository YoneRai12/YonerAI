import asyncio
import contextlib
import logging
import os
import re
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Constants (Ported from legacy)
DENY_META_CHARS = re.compile(r"[;&><`]")
ALLOWED_CMDS = {
    "cat", "diff", "find", "grep", "head", "lines", "ls", "rg", 
    "stat", "tree", "tail", "wc"
}

MAX_BYTES = 500_000 # Increased slightly
MAX_FILES_SCANNED = 5000
MAX_TOTAL_BYTES_SCANNED = 10_000_000
MAX_DEPTH = 8

ALLOWED_FLAGS: dict[str, set[str]] = {
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

FLAG_REQUIRES_VALUE: dict[str, set[str]] = {
    "find": {"-m"},
    "grep": {"-m", "-C", "-A", "-B"},
    "rg": {"-m", "-C", "-A", "-B"},
    "head": {"-n"},
    "lines": {"-s", "-e"},
    "tree": {"-L"},
    "tail": {"-n"},
}

PATTERN_ARG_COUNT: dict[str, int] = {"find": 1, "grep": 1, "rg": 1}

DENY_BASENAMES = {
    ".env", ".env.local", ".envrc", ".npmrc", ".pypirc", ".netrc", 
    ".git-credentials", "id_rsa", "id_rsa.pub", "credentials.json", 
    "secrets.json", "secrets.yaml", "secrets.yml", "secrets.env", 
    "secrets.txt", "private.key", "private.pem", "ora_bot.db"
}

class ScanLimitExceeded(Exception):
    pass

class SafeShell:
    """
    A read-only, confined shell executor for AI code analysis.
    Prevents escaping the root directory and reading sensitive files.
    """
    def __init__(self, root_dir: str | Path):
        self.root = Path(root_dir).resolve()
    
    def _parse_args(self, cmd: str, args: list[str]) -> tuple[set[str], dict[str, str], list[str]]:
        flags: set[str] = set()
        values: dict[str, str] = {}
        positionals: list[str] = []
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

    def _validate(self, cmd: str) -> str | None:
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
        path_args: list[str] = []

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
            
            # Allow common glob chars if needed, but legacy code blocked them. 
            # We will adhere to legacy strictness for now.
            if any(char in arg for char in ["*", "?", "{", "}"]):
                return "Denied: glob patterns are not allowed."
            
            if not self._is_safe_path(arg):
                return f"Denied: path '{arg}' is out of root."
            
            resolved_arg = (self.root / arg).resolve()
            if command == "cat":
                with contextlib.suppress(OSError):
                    if resolved_arg.stat().st_size > MAX_BYTES:
                         return f"Denied: file '{arg}' is too large (>{MAX_BYTES} bytes)."

            path_args.append(arg)
            saw_path = True
            idx += 1

        if command in {"rg", "grep", "find"}:
            if not saw_path:
                 return f"Denied: provide an explicit search path for {command}."
            if "-m" not in parts:
                 return f"Denied: include -m <limit> (e.g. -m 20) to bound {command} output."

        if command == "tree":
             if "-L" not in parts:
                  return "Denied: tree requires -L <depth> (e.g. -L 2) to limit traversal."
        
        return None

    def _run_builtin_sync(self, cmd: str) -> dict[str, Any]:
        parts = shlex.split(cmd)
        if not parts: return {"stdout":"", "stderr":"Empty command", "exit_code": 1}
        
        name = parts[0]
        args = parts[1:]

        files_scanned = 0
        bytes_scanned = 0

        def check_limits(path: Path):
            nonlocal files_scanned, bytes_scanned
            files_scanned += 1
            if files_scanned > MAX_FILES_SCANNED: raise ScanLimitExceeded("file_limit")
            try: bytes_scanned += path.stat().st_size
            except: pass
            if bytes_scanned > MAX_TOTAL_BYTES_SCANNED: raise ScanLimitExceeded("byte_limit")

        def resolve_path(arg: str) -> Path:
            if not arg or arg == ".": return self.root
            return (self.root / arg).resolve()

        def trunc(text: str) -> str:
            if len(text) <= MAX_BYTES: return text
            return text[:MAX_BYTES] + "...(truncated)"

        # --- Helper: Iter Files ---
        def iter_files(base: Path) -> list[Path]:
            out = []
            if base.is_file():
                 if base.name in DENY_BASENAMES: return []
                 check_limits(base)
                 return [base]
            
            if base.is_dir():
                 try: base_parts = len(base.resolve().parts)
                 except: return []
                 
                 for root_path, dirs, files in os.walk(base):
                      # Depth Check
                      try:
                          resolved_root = Path(root_path).resolve()
                          resolved_root.relative_to(self.root)
                          depth = len(resolved_root.parts) - base_parts
                          if depth >= MAX_DEPTH:
                              dirs[:] = []
                      except: continue

                      # Strict Filter
                      dirs[:] = [d for d in dirs if d not in DENY_BASENAMES and d != ".git"]
                      
                      for fname in sorted(files):
                           if fname in DENY_BASENAMES: continue
                           fpath = resolved_root / fname
                           if ".git" in fpath.parts: continue
                           check_limits(fpath)
                           out.append(fpath)
            return out

        # --- COMMANDS ---

        # 1. LS
        if name == "ls":
            flags, _, positionals = self._parse_args(name, args)
            show_all = any(f in flags for f in ("-a", "-al", "-la"))
            long = any(f in flags for f in ("-l", "-al", "-la", "-lh"))
            path_arg = positionals[-1] if positionals else "."
            base = resolve_path(path_arg)
            
            if not base.exists():
                return {"stdout":"", "stderr":f"ls: {path_arg} not found", "exit_code": 2}
            
            entries = [base] if base.is_file() else sorted(base.iterdir(), key=lambda p: p.name.lower())
            lines = []
            for entry in entries:
                if entry.name in DENY_BASENAMES: continue
                if not show_all and entry.name.startswith("."): continue
                
                if long:
                    kind = "d" if entry.is_dir() else "-"
                    size = entry.stat().st_size
                    date = datetime.fromtimestamp(entry.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    lines.append(f"{kind} {size:>8} {date} {entry.name}")
                else:
                    lines.append(entry.name)
            return {"stdout": "\n".join(lines), "stderr": "", "exit_code": 0}

        # 2. CAT / HEAD / TAIL / LINES
        if name in {"cat", "head", "tail", "lines"}:
            flags, values, positionals = self._parse_args(name, args)
            target = resolve_path(positionals[0])
            if not target.exists() or not target.is_file():
                return {"stdout":"", "stderr":f"{name}: file not found", "exit_code": 2}
            
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines(True)
                
                output = ""
                if name == "cat":
                    if "-n" in flags:
                        output = "".join(f"{i+1:4} | {l}" for i, l in enumerate(lines))
                    else:
                        output = content
                
                elif name == "head":
                    n = int(values.get("-n", "10"))
                    output = "".join(lines[:n])
                
                elif name == "tail":
                    n = int(values.get("-n", "10"))
                    output = "".join(lines[-n:])
                
                elif name == "lines":
                    s = int(values.get("-s", "1"))
                    e = int(values.get("-e", str(len(lines))))
                    # 1-based index
                    output = "".join(lines[s-1:e])

                return {"stdout": trunc(output), "stderr":"", "exit_code": 0}
            except Exception as e:
                return {"stdout":"", "stderr":str(e), "exit_code": 1}

        # 3. GREP / RG
        if name in {"grep", "rg"}:
            flags, values, positionals = self._parse_args(name, args)
            pattern = positionals[0]
            target = resolve_path(positionals[1])
            max_matches = int(values.get("-m", "50"))
            show_n = "-n" in flags
            ignore_case = "-i" in flags
            
            try:
                msg_regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
                results = []
                count = 0
                
                for fpath in iter_files(target):
                    try:
                        with fpath.open("r", encoding="utf-8", errors="replace") as fh:
                            for idx, line in enumerate(fh, 1):
                                if msg_regex.search(line):
                                    rel = str(fpath.relative_to(self.root)).replace("\\", "/")
                                    prefix = f"{rel}:{idx}:" if show_n else f"{rel}:"
                                    results.append(f"{prefix} {line.strip()}")
                                    count += 1
                                    if count >= max_matches: break
                    except: pass
                    if count >= max_matches: break
                
                return {"stdout": "\n".join(results), "stderr": "", "exit_code": 0}
            except Exception as e:
                return {"stdout": "", "stderr": str(e), "exit_code": 1}

        # 4. TREE
        if name == "tree":
            flags, values, positionals = self._parse_args(name, args)
            depth_limit = int(values.get("-L", str(MAX_DEPTH)))
            show_all = "-a" in flags
            root_target = resolve_path(positionals[0] if positionals else ".")
            
            tree_lines = []
            
            def build_tree(path: Path, prefix: str, current_depth: int):
                if current_depth >= depth_limit: return
                
                entries = sorted([e for e in path.iterdir() if e.name not in DENY_BASENAMES and (show_all or not e.name.startswith("."))], key=lambda x: x.name.lower())
                
                for i, entry in enumerate(entries):
                    connector = "└── " if i == len(entries) - 1 else "├── "
                    tree_lines.append(f"{prefix}{connector}{entry.name}")
                    if entry.is_dir():
                        ext = "    " if i == len(entries) - 1 else "│   "
                        build_tree(entry, prefix + ext, current_depth + 1)
            
            build_tree(root_target, "", 0)
            return {"stdout": "\n".join(tree_lines), "stderr": "", "exit_code": 0}

        # 5. FIND
        if name == "find":
             flags, values, positionals = self._parse_args(name, args)
             pattern = positionals[0]
             target = resolve_path(positionals[1])
             max_matches = int(values.get("-m", "50"))
             
             try:
                 regex = re.compile(pattern)
                 hits = []
                 for fpath in iter_files(target):
                     rel = str(fpath.relative_to(self.root)).replace("\\", "/")
                     if regex.search(rel):
                         hits.append(rel)
                         if len(hits) >= max_matches: break
                 return {"stdout": "\n".join(hits), "stderr": "", "exit_code": 0}
             except Exception as e:
                 return {"stdout": "", "stderr": str(e), "exit_code": 1}

        return {"stdout": "", "stderr": f"Command {name} implementation missing", "exit_code": 1}

    async def run(self, cmd: str) -> dict[str, Any]:
        """Async wrapper for the prompt handler."""
        # 1. Validate
        err = self._validate(cmd)
        if err: return {"stdout": "", "stderr": err, "exit_code": 1}
        
        # 2. Run in Thread (File I/O is blocking)
        try:
            return await asyncio.to_thread(self._run_builtin_sync, cmd)
        except Exception as e:
            logger.exception(f"Shell execution failed: {cmd}")
            return {"stdout": "", "stderr": f"Internal Error: {e}", "exit_code": 1}
