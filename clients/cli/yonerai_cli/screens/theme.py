"""/theme slash-command handler.

Kept in a screen module (not interactive.py) so the interactive shell stays a
thin dispatcher. Changes only presentation; no trust-boundary or JSON change.
"""

from __future__ import annotations

from typing import TextIO

from yonerai_cli.config import ConfigError, save_cli_config
from yonerai_cli.screens.labels import _safe
from yonerai_cli.startup_home import render_startup_home_header
from yonerai_cli.tui.aliases import canonical_value as _canonical_value
from yonerai_cli.tui.themes import THEME_CHOICES_HELP, theme_from_input, theme_label


def _write(stream: TextIO, text: str) -> None:
    stream.write(text)
    stream.flush()


def _handle_theme_command(
    args: list[str],
    *,
    config: dict[str, object],
    config_path: str | None,
    color: str,
    lang: str,
    output_stream: TextIO,
) -> dict[str, object]:
    if not args:
        current = theme_label(str(config.get("theme") or "auto"), lang=lang)
        head = "現在のテーマ" if lang == "ja" else "current theme"
        _write(output_stream, f"{head}: {current}\n  {THEME_CHOICES_HELP}\n")
        return {}
    requested = theme_from_input(_canonical_value(args[0]))
    if requested is None:
        _write(
            output_stream,
            ("テーマは auto/dark/light/mono です。\n" if lang == "ja" else "theme must be auto/dark/light/mono.\n"),
        )
        return {}
    config["theme"] = requested
    try:
        save_cli_config(config, config_path)
    except ConfigError as exc:
        safe_error = _safe(exc)
        _write(
            output_stream,
            (
                f"設定を保存できませんでした:\n  理由: {safe_error}\n"
                if lang == "ja"
                else f"Could not save config:\n  reason: {safe_error}\n"
            ),
        )
        return {}
    label = theme_label(requested, lang=lang)
    _write(output_stream, (f"テーマを変更しました: {label}\n" if lang == "ja" else f"Changed theme: {label}\n"))
    _write(output_stream, render_startup_home_header(color=color, stream=output_stream, theme=requested) + "\n")
    return {}
