import sys
from pathlib import Path

CORE_SRC = Path(__file__).resolve().parents[1] / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from ora_core.env import resolve_env_path


def test_resolve_env_path_finds_canonical_repo_env():
    resolved = resolve_env_path(__file__)
    assert resolved is not None
    assert resolved.name == ".env"
    assert resolved.parent.name == "ORADiscordBOT-main3"


def test_resolve_env_path_honors_override(monkeypatch, tmp_path):
    env_path = tmp_path / ".env.custom"
    env_path.write_text("OPENAI_API_KEY=test\n", encoding="utf-8")
    monkeypatch.setenv("ORA_DOTENV_PATH", str(env_path))

    resolved = resolve_env_path(__file__)
    assert resolved == env_path
