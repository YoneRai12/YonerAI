from __future__ import annotations

import tomllib
from pathlib import Path


def test_mypy_does_not_disable_syntax_errors() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    disabled = set(data["tool"]["mypy"].get("disable_error_code", []))

    assert "syntax" not in disabled
