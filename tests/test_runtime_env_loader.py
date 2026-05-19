import sys
from pathlib import Path

CORE_SRC = Path(__file__).resolve().parents[1] / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from ora_core.env import resolve_env_path


def test_resolve_env_path_finds_repo_local_env(tmp_path):
    repo = tmp_path / "repo"
    nested = repo / "core" / "src" / "ora_core"
    nested.mkdir(parents=True)
    (repo / ".git").mkdir()
    env_path = repo / ".env"
    env_path.write_text("OPENAI_API_KEY=test\n", encoding="utf-8")

    resolved = resolve_env_path(nested / "main.py")

    assert resolved == env_path


def test_resolve_env_path_stops_at_repo_boundary(tmp_path):
    parent_env = tmp_path / ".env"
    parent_env.write_text("OPENAI_API_KEY=parent\n", encoding="utf-8")
    repo = tmp_path / "repo"
    nested = repo / "core" / "src" / "ora_core"
    nested.mkdir(parents=True)
    (repo / ".git").mkdir()

    resolved = resolve_env_path(nested / "main.py")

    assert resolved is None


def test_resolve_env_path_does_not_follow_worktree_gitdir(tmp_path):
    main_repo = tmp_path / "main"
    common_git = main_repo / ".git"
    common_git.mkdir(parents=True)
    (main_repo / ".env").write_text("OPENAI_API_KEY=private\n", encoding="utf-8")

    worktree = tmp_path / "worktree"
    nested = worktree / "core" / "src" / "ora_core"
    nested.mkdir(parents=True)
    gitdir = common_git / "worktrees" / "worktree"
    gitdir.mkdir(parents=True)
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")

    resolved = resolve_env_path(nested / "main.py")

    assert resolved is None


def test_resolve_env_path_honors_override(monkeypatch, tmp_path):
    env_path = tmp_path / ".env.custom"
    env_path.write_text("OPENAI_API_KEY=test\n", encoding="utf-8")
    monkeypatch.setenv("ORA_DOTENV_PATH", str(env_path))

    resolved = resolve_env_path(__file__)
    assert resolved == env_path
