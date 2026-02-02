import os
import re
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Any
from datetime import datetime
import difflib

logger = logging.getLogger(__name__)

# Configuration defaults
MAX_BYTES = 500_000  # 500KB limit for read
MAX_DEPTH = 5
MAX_MATCHES = 200
DENY_BASENAMES = {".git", "__pycache__", ".env", "node_modules", ".DS_Store"}

class FilesystemTools:
    def __init__(self, root_dir: str = os.getcwd()):
        self.root = Path(root_dir).resolve()

    def resolve_path(self, path_str: str) -> Path:
        """Resolve path and ensure it's within root."""
        try:
            target = (self.root / path_str).resolve()
            # Security check: must be relative to root
            target.relative_to(self.root)
            return target
        except ValueError:
            raise PermissionError(f"Access denied: Path '{path_str}' is outside root.")

    def _truncate(self, text: str, limit: int = 2000) -> str:
        if len(text) <= limit:
            return text
        return text[:limit-3] + "..."

    def _iter_files(self, path: Path) -> Any:
        # Simple recursive iterator respecting deny list
        try:
            for entry in path.iterdir():
                if entry.name in DENY_BASENAMES:
                    continue
                if entry.is_dir():
                    yield from self._iter_files(entry)
                else:
                    yield entry
        except OSError:
            pass

    def ls(self, path_str: str = ".", recursive: bool = False, limit: int = 50) -> str:
        """List directory contents."""
        try:
            target = self.resolve_path(path_str)
            if not target.exists():
                return f"ls: cannot access '{path_str}': No such file or directory"
            
            lines = []
            if target.is_file():
                st = target.stat()
                lines.append(f"{st.st_size:>8} {datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M} {target.name}")
            else:
                entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                for i, entry in enumerate(entries):
                    if i >= limit:
                        lines.append("... (truncated)")
                        break
                    kind = "DIR " if entry.is_dir() else "FILE"
                    size = ""
                    if entry.is_file():
                        size = f"{entry.stat().st_size:>8}"
                    else:
                        size = " " * 8
                    
                    mtime = datetime.fromtimestamp(entry.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    lines.append(f"{kind} {size} {mtime} {entry.name}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"ls error: {e}"

    def cat(self, path_str: str, max_bytes: int = MAX_BYTES, line_numbers: bool = False) -> str:
        """Read file content."""
        try:
            target = self.resolve_path(path_str)
            if not target.exists() or not target.is_file():
                return f"cat: '{path_str}': No such file"
            
            if target.stat().st_size > max_bytes:
                return f"Error: File too large ({target.stat().st_size} bytes). Limit is {max_bytes}."
            
            content = target.read_text(encoding="utf-8", errors="replace")
            if line_numbers:
                lines = content.splitlines()
                content = "\n".join(f"{i+1}\t{line}" for i, line in enumerate(lines))
            
            return self._truncate(content, limit=4000) # Returns truncated if too long for one message, caller should handle artifacts if huge
        except Exception as e:
            return f"cat error: {e}"

    def grep(self, pattern: str, path_str: str = ".", recursive: bool = True, ignore_case: bool = False, max_matches: int = MAX_MATCHES) -> str:
        """Search for pattern in files."""
        try:
            target = self.resolve_path(path_str)
            regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
            
            results = []
            count = 0
            
            files_to_search = []
            if target.is_file():
                files_to_search = [target]
            else:
                files_to_search = self._iter_files(target)

            for file_path in files_to_search:
                try:
                    rel_path = file_path.relative_to(self.root).as_posix()
                    with file_path.open("r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(f"{rel_path}:{i}: {line.strip()}")
                                count += 1
                                if count >= max_matches:
                                    break
                except Exception:
                    continue
                if count >= max_matches:
                    break
            
            if not results:
                return "No matches found."
            return "\n".join(results)
        except Exception as e:
            return f"grep error: {e}"

    def tree(self, path_str: str = ".", max_depth: int = MAX_DEPTH) -> str:
        """Visual tree of directory."""
        try:
            target = self.resolve_path(path_str)
            if not target.is_dir():
                return f"tree: '{path_str}' is not a directory"

            lines = [target.name if path_str == "." else str(path_str)]
            
            def walk(path: Path, prefix: str, current_depth: int):
                if current_depth >= max_depth:
                    return
                try:
                    entries = sorted(path.iterdir(), key=lambda p: p.name.lower())
                    filtered = [e for e in entries if e.name not in DENY_BASENAMES and not e.name.startswith(".")]
                    
                    for i, entry in enumerate(filtered):
                        is_last = (i == len(filtered) - 1)
                        connector = "└── " if is_last else "├── "
                        lines.append(f"{prefix}{connector}{entry.name}")
                        
                        if entry.is_dir():
                            child_prefix = prefix + ("    " if is_last else "│   ")
                            walk(entry, child_prefix, current_depth + 1)
                except Exception:
                    pass

            walk(target, "", 0)
            return "\n".join(lines)
        except Exception as e:
            return f"tree error: {e}"
    
    def diff(self, file1: str, file2: str) -> str:
        """Show diff between two files."""
        try:
            p1 = self.resolve_path(file1)
            p2 = self.resolve_path(file2)
            
            if not p1.exists() or not p2.exists():
                return "diff: One or both files not found."
            
            t1 = p1.read_text(encoding="utf-8", errors="replace").splitlines()
            t2 = p2.read_text(encoding="utf-8", errors="replace").splitlines()
            
            diff = difflib.unified_diff(t1, t2, fromfile=file1, tofile=file2, lineterm="")
            return "\n".join(diff)
        except Exception as e:
            return f"diff error: {e}"

# Global instance
fs_tools = FilesystemTools()
