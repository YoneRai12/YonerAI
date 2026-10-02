from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def resolve_env_path(start: Path | str | None = None) -> Path | None:
    override = (os.getenv("ORA_DOTENV_PATH") or "").strip()
    if override:
        override_path = Path(override).expanduser()
        if not override_path.is_absolute():
            override_path = (Path.cwd() / override_path).resolve()
        return override_path

    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        direct_env = candidate / ".env"
        if direct_env.exists():
            return direct_env

        # Stop at the checked-out repository boundary. In a git worktree, .git is
        # a pointer into the common git directory; following it can accidentally
        # load a sibling checkout's private .env instead of this public clone.
        if (candidate / ".git").exists():
            return None

    return None


def load_runtime_env(start: Path | str | None = None, *, override: bool = False) -> Path | None:
    env_path = resolve_env_path(start)
    if env_path and env_path.exists():
        load_dotenv(env_path, override=override)
        return env_path
    return None
