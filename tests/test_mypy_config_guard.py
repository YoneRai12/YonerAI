from __future__ import annotations

import tomllib
from pathlib import Path


def test_mypy_does_not_disable_syntax_errors() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)

    mypy_config = data["tool"]["mypy"]
    disabled = set(mypy_config.get("disable_error_code", []))
    assert "syntax" not in disabled

    for override in mypy_config.get("overrides", []):
        override_disabled = set(override.get("disable_error_code", []))
        assert "syntax" not in override_disabled
