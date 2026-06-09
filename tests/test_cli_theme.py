"""CLI theme system tests.

Covers: config default/validation, theme palette selection, mono disables
truecolor, first-launch theme onboarding (interactive only), /theme slash
command, and that themes never alter JSON/behavior boundaries.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = REPO_ROOT / "clients" / "cli"
CORE_SRC = REPO_ROOT / "core" / "src"
for path in (CLIENTS_CLI, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from yonerai_cli.config import DEFAULT_CONFIG, ConfigError, THEMES, save_cli_config, validate_cli_config
from yonerai_cli.startup_home import render_startup_home_header
from yonerai_cli.tui.themes import normalize_theme, theme_palette, theme_uses_truecolor


class _TTYStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


class _PlainStringIO(io.StringIO):
    def isatty(self) -> bool:
        return False


# --- config ---


def test_default_theme_is_auto() -> None:
    assert DEFAULT_CONFIG["theme"] == "auto"


def test_valid_themes_accepted() -> None:
    for theme in THEMES:
        cfg = dict(DEFAULT_CONFIG)
        cfg["theme"] = theme
        cfg["language"] = "ja"
        assert validate_cli_config(cfg)["theme"] == theme


def test_invalid_theme_rejected() -> None:
    cfg = dict(DEFAULT_CONFIG)
    cfg["theme"] = "neon"
    with pytest.raises(ConfigError):
        validate_cli_config(cfg)


# --- palette / rendering ---


def test_normalize_theme_falls_back_to_auto() -> None:
    assert normalize_theme("nonsense") == "auto"
    assert normalize_theme(None) == "auto"
    assert normalize_theme("DARK") == "dark"


def test_mono_disables_truecolor() -> None:
    assert theme_uses_truecolor("mono") is False
    assert theme_uses_truecolor("dark") is True


def test_dark_and_light_have_distinct_palettes() -> None:
    assert theme_palette("dark", "title") != theme_palette("light", "title")


def test_header_mono_has_no_ansi_escape() -> None:
    out = render_startup_home_header(color="always", theme="mono", width=80)
    assert "\x1b[38;2;" not in out


def test_header_dark_has_ansi_escape_when_color_always() -> None:
    out = render_startup_home_header(color="always", theme="dark", width=140)
    assert "\x1b[38;2;" in out


def test_header_never_color_ignores_theme() -> None:
    out = render_startup_home_header(color="never", theme="dark", width=140)
    assert "\x1b[38;2;" not in out


# --- onboarding + slash command ---


def _interactive():
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    return InteractiveCallbacks, InteractiveOptions, run_interactive_cli


def _callbacks(InteractiveCallbacks: Any) -> Any:
    def ask_auto(task: str, provider: str, live: bool, ledger_path: str | None, lang: str) -> dict[str, Any]:
        return {
            "ok": True,
            "run": {"id": "r"},
            "response": {"output_text": f"ok {task}"},
            "auto": {"provider": provider, "route": "mock"},
            "live_call_performed": live,
            "ledger": {"path": ledger_path, "enabled": bool(ledger_path)},
        }

    return InteractiveCallbacks(
        providers=lambda: {"providers": []},
        ask_auto=ask_auto,
        runs_list=lambda *a: {"runs": []},
        runs_show=lambda *a: {"ok": False},
    )


def test_first_launch_theme_prompt_persists(tmp_path: Path) -> None:
    InteractiveCallbacks, InteractiveOptions, run_interactive_cli = _interactive()
    config_path = tmp_path / "c.json"
    # No config yet -> first launch asks language then theme.
    stdout = _TTYStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), color="never"),
        _callbacks(InteractiveCallbacks),
        stdin=_TTYStringIO("1\n2\n/quit\n"),  # 1=日本語, 2=dark
        stdout=stdout,
    )
    assert rc == 0
    out = stdout.getvalue()
    assert "表示テーマ" in out
    import json

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["theme"] == "dark"


def test_existing_config_skips_theme_prompt(tmp_path: Path) -> None:
    InteractiveCallbacks, InteractiveOptions, run_interactive_cli = _interactive()
    config_path = tmp_path / "c.json"
    cfg = dict(DEFAULT_CONFIG)
    cfg["language"] = "ja"
    cfg["theme"] = "light"
    save_cli_config(cfg, config_path)
    stdout = _TTYStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), color="never"),
        _callbacks(InteractiveCallbacks),
        stdin=_TTYStringIO("/quit\n"),
        stdout=stdout,
    )
    assert rc == 0
    assert "表示テーマ" not in stdout.getvalue()


def test_theme_slash_command_changes_and_persists(tmp_path: Path) -> None:
    InteractiveCallbacks, InteractiveOptions, run_interactive_cli = _interactive()
    config_path = tmp_path / "c.json"
    cfg = dict(DEFAULT_CONFIG)
    cfg["language"] = "ja"
    save_cli_config(cfg, config_path)
    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), provider="mock", script=True, color="never"),
        _callbacks(InteractiveCallbacks),
        stdin=_PlainStringIO("/テーマ light\n/quit\n"),
        stdout=stdout,
    )
    assert rc == 0
    assert "テーマを変更しました" in stdout.getvalue()
    import json

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["theme"] == "light"


def test_theme_slash_command_rejects_invalid(tmp_path: Path) -> None:
    InteractiveCallbacks, InteractiveOptions, run_interactive_cli = _interactive()
    config_path = tmp_path / "c.json"
    cfg = dict(DEFAULT_CONFIG)
    cfg["language"] = "ja"
    save_cli_config(cfg, config_path)
    stdout = _PlainStringIO()
    run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), provider="mock", script=True, color="never"),
        _callbacks(InteractiveCallbacks),
        stdin=_PlainStringIO("/テーマ neon\n/quit\n"),
        stdout=stdout,
    )
    assert "auto/dark/light/mono" in stdout.getvalue()
