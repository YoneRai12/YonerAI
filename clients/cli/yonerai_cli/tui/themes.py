"""Theme palettes for the YonerAI CLI startup header.

Themes only change presentation (gradient colors / truecolor vs ANSI). They do
not change JSON output, command behavior, or any trust boundary. The "mono"
theme disables truecolor gradients for low-color or screen-reader terminals.
"""

from __future__ import annotations

from typing import Literal

ThemeName = Literal["auto", "dark", "light", "mono"]

# Ordered choices used by the onboarding picker (number -> theme name).
THEME_CHOICES: tuple[str, ...] = ("auto", "dark", "light", "mono")
THEME_CHOICES_HELP = "1) auto  2) dark  3) light  4) mono"
_THEME_INPUT_ALIASES: dict[str, ThemeName] = {
    "1": "auto",
    "auto": "auto",
    "自動": "auto",
    "オート": "auto",
    "2": "dark",
    "dark": "dark",
    "ダーク": "dark",
    "3": "light",
    "light": "light",
    "ライト": "light",
    "4": "mono",
    "mono": "mono",
    "モノ": "mono",
    "モノクロ": "mono",
}


# Each theme maps a logical role to a hex gradient palette used by
# startup_home.colorize(). "mono" carries no palette (truecolor disabled).
_THEME_PALETTES: dict[str, dict[str, list[str]]] = {
    "auto": {
        "title": ["#8BE9FD", "#5A8CFF", "#9B6DFF", "#67F3B0"],
        "line": ["#89F7FE", "#66A6FF"],
        "subtitle": ["#8BE9FD", "#67F3B0"],
    },
    "dark": {
        "title": ["#7AA2F7", "#9D7CD8", "#7DCFFF", "#73DACA"],
        "line": ["#3B4261", "#7AA2F7"],
        "subtitle": ["#7AA2F7", "#73DACA"],
    },
    "light": {
        "title": ["#2563EB", "#7C3AED", "#0EA5E9", "#0F766E"],
        "line": ["#2563EB", "#0EA5E9"],
        "subtitle": ["#2563EB", "#0F766E"],
    },
}


def theme_from_input(theme: str | None) -> ThemeName | None:
    value = (theme or "").strip().lower()
    return _THEME_INPUT_ALIASES.get(value)


def normalize_theme(theme: str | None) -> ThemeName:
    return theme_from_input(theme) or "auto"


def theme_uses_truecolor(theme: str | None) -> bool:
    """False for 'mono' (and unknown values fall back to truecolor 'auto')."""
    return normalize_theme(theme) != "mono"


def theme_palette(theme: str | None, role: str) -> list[str]:
    """Return the hex gradient palette for a header role under a theme."""
    name = normalize_theme(theme)
    if name == "mono":
        name = "auto"
    return _THEME_PALETTES.get(name, _THEME_PALETTES["auto"]).get(
        role, _THEME_PALETTES["auto"]["title"]
    )


def theme_label(theme: str | None, *, lang: str) -> str:
    name = normalize_theme(theme)
    if lang == "ja":
        return {
            "auto": "自動（端末に合わせる）",
            "dark": "ダーク",
            "light": "ライト",
            "mono": "モノクロ（低色/読み上げ向け）",
        }[name]
    return {
        "auto": "auto (match terminal)",
        "dark": "dark",
        "light": "light",
        "mono": "mono (low-color / screen-reader)",
    }[name]
