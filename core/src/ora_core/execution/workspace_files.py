from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_MAX_FILE_BYTES = 64 * 1024
MAX_PROMPT_CHARS = 6000
WORKSPACE_FILE_ACCESS_CAPABILITY = "workspace_file_access"
WORKSPACE_FILE_ACCESS_COMPAT_ALIASES = ("file_summary",)
TEXT_EXTENSIONS = {
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".log",
    ".md",
    ".py",
    ".rst",
    ".text",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}


class WorkspaceFileError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def to_public_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class WorkspaceFileContext:
    file_name: str
    extension: str
    size_bytes: int
    sha256_prefix: str
    preview_text: str
    truncated: bool

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("preview_text", None)
        payload["capability"] = WORKSPACE_FILE_ACCESS_CAPABILITY
        payload["raw_content_persisted"] = False
        return payload


def read_workspace_text_file(
    file_path: str | Path,
    *,
    workspace: str | Path,
    max_bytes: int = DEFAULT_MAX_FILE_BYTES,
    include_hidden: bool = False,
) -> WorkspaceFileContext:
    root = _resolve_existing_directory(workspace)
    target = Path(file_path)
    if not target.is_absolute():
        target = root / target
    try:
        resolved_target = target.resolve(strict=True)
    except OSError as exc:
        raise WorkspaceFileError("file_not_found", "file was not found inside the selected workspace.") from exc
    if not _is_within(resolved_target, root):
        raise WorkspaceFileError("outside_workspace", "file must stay inside the selected workspace.")
    if not resolved_target.is_file():
        raise WorkspaceFileError("not_a_file", "selected path must be a regular file.")
    relative = resolved_target.relative_to(root)
    if not include_hidden and any(part.startswith(".") for part in relative.parts):
        raise WorkspaceFileError("hidden_file_rejected", "hidden files require an explicit future policy.")
    max_bytes = _normalize_max_bytes(max_bytes)
    size = resolved_target.stat().st_size
    if size <= 0:
        raise WorkspaceFileError("empty_file", "file is empty.")
    if size > max_bytes:
        raise WorkspaceFileError("file_too_large", "file exceeds the configured workspace file access limit.")
    suffix = resolved_target.suffix.lower()
    data = resolved_target.read_bytes()
    if _looks_binary(data, suffix=suffix):
        raise WorkspaceFileError("binary_file_rejected", "binary files are not supported by the workspace file access guard.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkspaceFileError("unsupported_encoding", "file must be UTF-8 text.") from exc
    preview = " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())
    truncated = len(preview) > MAX_PROMPT_CHARS
    if truncated:
        preview = preview[:MAX_PROMPT_CHARS]
    return WorkspaceFileContext(
        file_name=resolved_target.name,
        extension=suffix or "",
        size_bytes=size,
        sha256_prefix=_sha256_prefix(data),
        preview_text=preview,
        truncated=truncated,
    )


def build_workspace_file_prompt(task_text: str, context: WorkspaceFileContext) -> str:
    return (
        f"{task_text}\n\n"
        "Workspace file access guard context follows. This is one explicitly selected UTF-8 text file, "
        "not PDF/image parsing, folder crawling, arbitrary filesystem access, or a completed summarizer. "
        "Do not infer local absolute paths or private runtime details.\n"
        f"file_name: {context.file_name}\n"
        f"extension: {context.extension or 'none'}\n"
        f"size_bytes: {context.size_bytes}\n"
        f"sha256_prefix: {context.sha256_prefix}\n"
        f"truncated: {str(context.truncated).lower()}\n"
        "content_preview:\n"
        f"{context.preview_text}"
    )


def _resolve_existing_directory(path: str | Path) -> Path:
    try:
        resolved = Path(path).resolve(strict=True)
    except OSError as exc:
        raise WorkspaceFileError("workspace_not_found", "workspace was not found.") from exc
    if not resolved.is_dir():
        raise WorkspaceFileError("workspace_not_directory", "workspace must be a directory.")
    return resolved


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _normalize_max_bytes(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MAX_FILE_BYTES
    if parsed <= 0:
        return DEFAULT_MAX_FILE_BYTES
    return min(parsed, DEFAULT_MAX_FILE_BYTES)


def _looks_binary(data: bytes, *, suffix: str) -> bool:
    if suffix and suffix not in TEXT_EXTENSIONS:
        return True
    if b"\x00" in data:
        return True
    sample = data[:2048]
    if not sample:
        return False
    control = sum(1 for byte in sample if byte < 9 or (13 < byte < 32))
    return control / len(sample) > 0.05


def _sha256_prefix(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()[:16]
