from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from yonerai_cli.config import COMMAND_DISPLAY_MODES
from yonerai_cli.output import ColorMode
from yonerai_cli.tui.keymap import (
    JAPANESE_SLASH_ALIASES,
    SLASH_COMMANDS,
    TOP_LEVEL_COMMANDS,
    SlashCommandSpec,
    _best_insert_text,
)


CommandDisplayMode = str
ESC = chr(27)
DIM = f"{ESC}[2m"
RESET = f"{ESC}[0m"


@dataclass(frozen=True)
class CommandPaletteCategory:
    title_ja: str
    title_en: str
    commands: tuple[str, ...]


COMMAND_PALETTE_CATEGORIES: tuple[CommandPaletteCategory, ...] = (
    CommandPaletteCategory("すぐ始める", "Get started", ("/login", "/local-llm", "/update")),
    CommandPaletteCategory("アカウントとAPI", "Account and API", ("/whoami", "/sessions", "/projects", "/ping", "/rate-limit")),
    CommandPaletteCategory("設定と同期", "Settings and sync", ("/settings", "/sync", "/auth")),
)


def normalize_command_display_mode(value: object, *, lang: str) -> CommandDisplayMode:
    raw = str(value or "").strip()
    if raw in COMMAND_DISPLAY_MODES:
        return raw
    return "ja_with_en" if lang == "ja" else "en_with_ja"


def format_command_palette(
    lang: str,
    *,
    display_mode: CommandDisplayMode | None = None,
    color: ColorMode = "auto",
) -> str:
    mode = normalize_command_display_mode(display_mode, lang=lang)
    if mode.startswith("ja"):
        lines = [
            "コマンドパレット",
            "  / で候補を開きます。/l や /p のように打つと、その場で絞り込みます。",
            "  Enter で実行、Esc で閉じます。",
            "  まずはよく使う短いコマンドだけを前に出します。",
            "",
        ]
    else:
        lines = [
            "Command palette",
            "  / opens suggestions. Type fragments like /l or /p to filter in place.",
            "  Enter runs the selection. Esc closes it.",
            "  Common short commands are shown first.",
            "",
        ]
    specs = _spec_by_canonical()
    for category in COMMAND_PALETTE_CATEGORIES:
        title = category.title_ja if mode.startswith("ja") else category.title_en
        lines.append(title)
        for canonical in category.commands:
            spec = specs.get(canonical)
            if spec is None:
                continue
            lines.append(_format_palette_command(spec, mode=mode, color=color))
        lines.append("")
    return "\n".join(lines)


def format_command_palette_query(
    lang: str,
    query: str,
    *,
    display_mode: CommandDisplayMode | None = None,
    color: ColorMode = "auto",
) -> str:
    mode = normalize_command_display_mode(display_mode, lang=lang)
    items = command_palette_dialog_items(lang, display_mode=mode, query=query)
    lines = [f"絞り込み: {query}" if mode.startswith("ja") else f"Matches: {query}"]
    if not items:
        lines.append("  一致するコマンドはありません。" if mode.startswith("ja") else "  No matching commands.")
        lines.append("")
        return "\n".join(lines)
    for _value, label in items[:8]:
        lines.append(f"  {label}")
    lines.append("")
    return "\n".join(lines)


def slash_command_summary(
    lang: str,
    *,
    display_mode: CommandDisplayMode | None = None,
    color: ColorMode = "auto",
) -> str:
    mode = normalize_command_display_mode(display_mode, lang=lang)
    lines = ["候補:" if mode.startswith("ja") else "Suggestions:"]
    for spec in SLASH_COMMANDS:
        lines.append(_format_summary_command(spec, mode=mode, color=color))
    lines.append("")
    return "\n".join(lines)


def command_palette_dialog_items(
    lang: str,
    *,
    display_mode: CommandDisplayMode | None = None,
    query: str | None = None,
) -> list[tuple[str, str]]:
    mode = normalize_command_display_mode(display_mode, lang=lang)
    specs = _spec_by_canonical()
    query_text = str(query or "").strip().casefold()
    items: list[tuple[str, str]] = []
    for canonical in TOP_LEVEL_COMMANDS:
        spec = specs.get(canonical)
        if spec is None:
            continue
        primary, description, secondary = _command_parts(
            spec,
            mode=mode,
            query=query_text,
        )
        secondary = _candidate_secondary_alias(
            spec,
            lang=lang,
            primary=primary,
            secondary=secondary,
        )
        command_terms = " ".join(
            part
            for part in (
                canonical,
                spec.command,
                " ".join(spec.aliases),
                " ".join(JAPANESE_SLASH_ALIASES.get(spec.canonical, ())),
                primary,
                secondary,
            )
            if part
        ).casefold()
        full_terms = " ".join(part for part in (command_terms, description) if part).casefold()
        haystack = command_terms if query_text.startswith("/") else full_terms
        fuzzy_command = bool(query_text.startswith("/") and _best_insert_text(spec, fragment=query_text))
        if query_text and query_text not in haystack and not fuzzy_command:
            continue
        label = f"{_pad_display_width(primary, 16)} {description}"
        if secondary:
            label = f"{label}  {secondary}"
        items.append((canonical, label))
    return items


def _spec_by_canonical() -> dict[str, SlashCommandSpec]:
    return {spec.canonical: spec for spec in SLASH_COMMANDS}


def _format_palette_command(spec: SlashCommandSpec, *, mode: CommandDisplayMode, color: ColorMode) -> str:
    primary, description, secondary = _command_parts(spec, mode=mode)
    secondary_text = f"  {_dim(secondary, color=color)}" if secondary else ""
    return f"  {_pad_display_width(primary, 16)} {description}{secondary_text}"


def _format_summary_command(spec: SlashCommandSpec, *, mode: CommandDisplayMode, color: ColorMode) -> str:
    primary, description, secondary = _command_parts(spec, mode=mode)
    secondary_text = f" {_dim(secondary, color=color)}" if secondary else ""
    return f"  {_pad_display_width(primary, 12)} {description}{secondary_text}"


def _ascii_command_query(query: str) -> bool:
    if not query.startswith("/"):
        return False
    body = query[1:]
    return bool(body) and all(ord(ch) < 128 for ch in body)


def _japanese_command_query(query: str) -> bool:
    if not query.startswith("/"):
        return False
    body = query[1:]
    return any(ord(ch) >= 128 for ch in body)


def _command_parts(
    spec: SlashCommandSpec,
    *,
    mode: CommandDisplayMode,
    query: str | None = None,
) -> tuple[str, str, str]:
    english = spec.canonical
    japanese_aliases = tuple(alias for alias in JAPANESE_SLASH_ALIASES.get(spec.canonical, ()) if alias != spec.command)
    query_text = str(query or "")
    if mode.startswith("ja") and _ascii_command_query(query_text):
        return english, spec.description_ja, spec.command
    if mode.startswith("en") and _japanese_command_query(query_text):
        return spec.command, spec.description_en, english
    if mode == "ja_only":
        return spec.command, spec.description_ja, " ".join(japanese_aliases)
    if mode == "ja_with_en":
        return spec.command, spec.description_ja, english
    if mode == "en_with_ja":
        return english, spec.description_en, spec.command
    return english, spec.description_en, ""


def _candidate_secondary_alias(
    spec: SlashCommandSpec,
    *,
    lang: str,
    primary: str,
    secondary: str,
) -> str:
    parts = [part for part in str(secondary).split() if part]
    preferred = spec.canonical if lang == "ja" else spec.command
    if preferred and preferred != primary and preferred not in parts:
        parts.append(preferred)
    return " ".join(parts)


def _dim(value: str, *, color: ColorMode) -> str:
    if color != "never":
        return f"{DIM}{value}{RESET}"
    return value


def _pad_display_width(value: str, width: int) -> str:
    display_width = sum(_char_display_width(ch) for ch in value)
    return value + (" " * max(width - display_width, 1))


def _char_display_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1
