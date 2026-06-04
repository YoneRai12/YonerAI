from __future__ import annotations

from shutil import get_terminal_size
from typing import Literal, TextIO


ColorMode = Literal["auto", "never", "always"]
ESC = chr(27)
RESET = f"{ESC}[0m"
SUBTITLE = "CLI • build / sync / evolve"

ASCII_YONERAI = r"""
██╗   ██╗ ██████╗ ███╗   ██╗███████╗██████╗  █████╗ ██╗
╚██╗ ██╔╝██╔═══██╗████╗  ██║██╔════╝██╔══██╗██╔══██╗██║
 ╚████╔╝ ██║   ██║██╔██╗ ██║█████╗  ██████╔╝███████║██║
  ╚██╔╝  ██║   ██║██║╚██╗██║██╔══╝  ██╔══██╗██╔══██║██║
   ██║   ╚██████╔╝██║ ╚████║███████╗██║  ██║██║  ██║██║
   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝
""".strip("\n")


def render_startup_home_header(
    *,
    color: ColorMode = "auto",
    stream: TextIO | None = None,
    width: int | None = None,
) -> str:
    title_palette = ["#8BE9FD", "#5A8CFF", "#9B6DFF", "#67F3B0"]
    line_palette = ["#89F7FE", "#66A6FF"]
    subtitle_palette = ["#8BE9FD", "#67F3B0"]
    terminal_width = width or get_terminal_size((120, 30)).columns

    title = center_block(ASCII_YONERAI, width=terminal_width)
    divider = center_block("─" * 40, width=terminal_width)
    subtitle = center_block(SUBTITLE, width=terminal_width)

    if not _color_enabled(color, stream=stream):
        return "\n".join((title, divider, subtitle))
    return "\n".join(
        (
            colorize(title, title_palette),
            colorize(divider, line_palette),
            colorize(subtitle, subtitle_palette),
        )
    )


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def rgb_escape(red: int, green: int, blue: int) -> str:
    return f"{ESC}[38;2;{red};{green};{blue}m"


def interpolate(
    first: tuple[int, int, int],
    second: tuple[int, int, int],
    position: float,
) -> tuple[int, int, int]:
    return (
        round(first[0] + (second[0] - first[0]) * position),
        round(first[1] + (second[1] - first[1]) * position),
        round(first[2] + (second[2] - first[2]) * position),
    )


def gradient_colors(steps: int, palette: list[str]) -> list[tuple[int, int, int]]:
    if steps <= 1:
        return [hex_to_rgb(palette[0])]

    rgb_palette = [hex_to_rgb(color) for color in palette]
    segments = len(rgb_palette) - 1
    colors: list[tuple[int, int, int]] = []

    for index in range(steps):
        position = index / (steps - 1)
        segment_position = position * segments
        segment_index = min(int(segment_position), segments - 1)
        local_position = segment_position - segment_index
        colors.append(interpolate(rgb_palette[segment_index], rgb_palette[segment_index + 1], local_position))

    return colors


def colorize(text: str, palette: list[str]) -> str:
    visible = [character for character in text if character not in "\n\r"]
    colors = gradient_colors(max(len(visible), 1), palette)

    output: list[str] = []
    color_index = 0
    for character in text:
        if character in "\n\r":
            output.append(character)
            continue
        red, green, blue = colors[color_index]
        output.append(f"{rgb_escape(red, green, blue)}{character}")
        color_index += 1

    output.append(RESET)
    return "".join(output)


def center_block(text: str, *, width: int | None = None) -> str:
    terminal_width = width or get_terminal_size((120, 30)).columns
    return "\n".join(line.center(terminal_width) for line in text.splitlines())


def _color_enabled(mode: ColorMode, *, stream: TextIO | None = None) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return bool(stream is not None and getattr(stream, "isatty", lambda: False)())
