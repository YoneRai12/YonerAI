from __future__ import annotations

from shutil import get_terminal_size
from typing import Literal, TextIO


ColorMode = Literal["auto", "never", "always"]
SUBTITLE = "CLI | build / sync / evolve"
COMPACT_YONERAI = "YonerAI"


def render_startup_home_header(
    *,
    color: ColorMode = "auto",
    stream: TextIO | None = None,
    width: int | None = None,
    theme: str | None = "auto",
    compact: bool = False,
) -> str:
    terminal_width = width or get_terminal_size((120, 30)).columns

    if compact:
        return center_block(COMPACT_YONERAI, width=terminal_width)

    divider_width = 18 if compact else 24
    title = center_block(COMPACT_YONERAI, width=terminal_width)
    divider = center_block("-" * divider_width, width=terminal_width)
    subtitle = center_block(SUBTITLE, width=terminal_width)

    # Startup and theme previews stay plain-text on purpose.
    # Windows terminals plus nested TUI/panel rendering have proven brittle
    # enough that truecolor header escapes can leak visibly. A stable, compact
    # header is more important than decorative gradients here.
    return "\n".join((title, divider, subtitle))


def center_block(text: str, *, width: int | None = None) -> str:
    terminal_width = width or get_terminal_size((120, 30)).columns
    return "\n".join(line.center(terminal_width) for line in text.splitlines())
