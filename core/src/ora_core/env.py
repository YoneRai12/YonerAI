from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _resolve_git_common_dir(git_marker: Path) -> Path | None:
    if git_marker.is_dir():
        return git_marker.resolve()

    if not git_marker.is_file():
        return None

    text = git_marker.read_text(encoding="utf-8").strip()
    if not text.startswith("gitdir:"):
        return None

    git_dir = Path(text.split(":", 1)[1].strip())
    if not git_dir.is_absolute():
        git_dir = (git_marker.parent / git_dir).resolve()
    return git_dir.parent.parent.resolve()


def resolve_env_path(start: Path | str | None = None) -> Path | None:
    override = (os.getenv("ORA_DOTENV_PATH") or "").strip()
    if override:
        override_path = Path(override).expanduser()
        if not override_path.is_absolute():
            override_path = (Path.cwd() / override_path).resolve()
        return override_path

    current = Path(start or __file__).resolve()
    candidates = [current, *current.parents]

    for candidate in candidates:
        direct_env = candidate / ".env"
        if direct_env.exists():
            return direct_env

        git_common_dir = _resolve_git_common_dir(candidate / ".git")
        if git_common_dir:
            repo_root_env = git_common_dir.parent / ".env"
            if repo_root_env.exists():
                return repo_root_env

    return None


def load_runtime_env(start: Path | str | None = None, *, override: bool = False) -> Path | None:
    env_path = resolve_env_path(start)
    if env_path and env_path.exists():
        load_dotenv(env_path, override=override)
        return env_path
    return None
