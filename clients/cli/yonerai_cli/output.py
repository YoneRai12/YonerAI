from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, Iterable, Literal, TextIO


Status = Literal["ok", "warn", "fail", "skipped"]
ColorMode = Literal["auto", "never", "always"]

STATUS_MARKERS: dict[Status, str] = {
    "ok": "[OK]",
    "warn": "[WARN]",
    "fail": "[FAIL]",
    "skipped": "[SKIP]",
}
STATUS_COLORS: dict[Status, str] = {
    "ok": "\033[32m",
    "warn": "\033[33m",
    "fail": "\033[31m",
    "skipped": "\033[36m",
}
RESET = "\033[0m"


@dataclass(frozen=True)
class CliRow:
    label: str
    value: object
    status: Status | None = None
    note: str | None = None


@dataclass(frozen=True)
class CliSection:
    title: str
    rows: tuple[CliRow, ...]


def render_report(
    title: str,
    sections: Iterable[CliSection],
    *,
    color: ColorMode = "auto",
    stream: TextIO | None = None,
) -> str:
    color_enabled = _color_enabled(color, stream=stream)
    lines = [title]
    for section in sections:
        rows = tuple(section.rows)
        if not rows:
            continue
        lines.append("")
        lines.append(section.title)
        label_width = max(len(row.label) for row in rows)
        for row in rows:
            prefix = _status_marker(row.status, color_enabled=color_enabled) if row.status else "  "
            value = _format_value(row.value)
            note = f" ({row.note})" if row.note else ""
            lines.append(f"{prefix} {row.label.ljust(label_width)}: {value}{note}")
    return "\n".join(lines)


def render_status(status: Status, *, color: ColorMode = "auto", stream: TextIO | None = None) -> str:
    return _status_marker(status, color_enabled=_color_enabled(color, stream=stream))


def _format_value(value: object) -> str:
    if value is True:
        rendered = "true"
    elif value is False:
        rendered = "false"
    elif value is None:
        rendered = "none"
    else:
        rendered = str(value)
    return _escape_control_characters(rendered)


def _escape_control_characters(value: str) -> str:
    return "".join(_escape_char(char) for char in value)


def _escape_char(char: str) -> str:
    codepoint = ord(char)
    if codepoint < 0x20 or codepoint == 0x7F:
        return f"\\x{codepoint:02x}"
    return char


def _status_marker(status: Status, *, color_enabled: bool) -> str:
    marker = STATUS_MARKERS[status]
    if not color_enabled:
        return marker
    return f"{STATUS_COLORS[status]}{marker}{RESET}"


def _color_enabled(
    mode: ColorMode,
    *,
    stream: TextIO | None = None,
    rich_probe: Callable[[], bool] | None = None,
) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    probe = rich_probe or _rich_available
    target = stream or sys.stdout
    is_tty = bool(getattr(target, "isatty", lambda: False)())
    return is_tty and probe()


def _rich_available() -> bool:
    try:
        __import__("rich.console")
    except Exception:
        return False
    return True
