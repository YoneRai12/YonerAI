from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from yonerai_cli.tui.keymap import JAPANESE_SLASH_ALIASES, SLASH_COMMANDS, SlashCommandSpec


@dataclass(frozen=True)
class CommandPaletteCategory:
    title_ja: str
    title_en: str
    commands: tuple[str, ...]


COMMAND_PALETTE_CATEGORIES: tuple[CommandPaletteCategory, ...] = (
    CommandPaletteCategory("ホーム", "Home", ("/status", "/palette", "/help", "/quit")),
    CommandPaletteCategory("設定", "Settings", ("/settings", "/models", "/providers", "/mode", "/permissions")),
    CommandPaletteCategory("安全", "Safety", ("/safety", "/policy", "/file-access", "/network", "/live-provider")),
    CommandPaletteCategory("作業", "Work", ("/plan", "/review", "/tasks", "/agents", "/context")),
    CommandPaletteCategory("履歴と記憶", "History and memory", ("/runs", "/show", "/memory", "/ledger")),
    CommandPaletteCategory("公式境界", "Official boundary", ("/auth", "/api", "/sync", "/privacy", "/evolve", "/update")),
)


def format_command_palette(lang: str) -> str:
    if lang == "ja":
        lines = [
            "コマンドパレット",
            "  / を入力すると候補が出ます。Tab/矢印が使えない端末では、この一覧と /選択 を使います。",
            "  日本語コマンドを優先表示します。英語の互換コマンドも入力できます。",
            "  参照は @planner / @reviewer / @researcher と、/コンテキスト の公開安全な候補だけです。",
            "",
        ]
    else:
        lines = [
            "Command palette",
            "  Type / for suggestions. If Tab/arrows are unavailable, use this list and /select numbered fallback.",
            "  English aliases remain available. Japanese mode shows Japanese commands first.",
            "  Context references are limited to public-safe @planner/@reviewer/@researcher and /context guidance.",
            "",
        ]
    specs = _spec_by_canonical()
    for category in COMMAND_PALETTE_CATEGORIES:
        title = category.title_ja if lang == "ja" else category.title_en
        lines.append(title)
        for canonical in category.commands:
            spec = specs.get(canonical)
            if spec is None:
                continue
            lines.append(_format_palette_command(spec, lang=lang))
        lines.append("")
    lines.append("全コマンド" if lang == "ja" else "All commands")
    lines.append(slash_command_summary(lang).rstrip())
    lines.append("")
    return "\n".join(lines)


def slash_command_summary(lang: str) -> str:
    lines = ["候補:" if lang == "ja" else "Suggestions:"]
    for spec in SLASH_COMMANDS:
        if lang == "ja":
            aliases = ", ".join(alias for alias in JAPANESE_SLASH_ALIASES.get(spec.canonical, ()) if alias != spec.command)
            alias_text = f" / {aliases}" if aliases else ""
            lines.append(f"  {spec.command:<10} {spec.description_ja}{alias_text}")
        else:
            primary = spec.aliases[0] if spec.aliases else spec.command
            lines.append(f"  {primary:<10} {spec.description_en}")
    lines.append("")
    return "\n".join(lines)


def _spec_by_canonical() -> dict[str, SlashCommandSpec]:
    return {spec.canonical: spec for spec in SLASH_COMMANDS}


def _format_palette_command(spec: SlashCommandSpec, *, lang: str) -> str:
    if lang == "ja":
        aliases = [alias for alias in JAPANESE_SLASH_ALIASES.get(spec.canonical, ()) if alias != spec.command]
        alias_text = f"  別名: {', '.join(aliases)}" if aliases else ""
        return f"  {_pad_display_width(spec.command, 14)} {spec.description_ja}{alias_text}"
    primary = spec.aliases[0] if spec.aliases else spec.command
    return f"  {primary:<16} {spec.description_en}"


def _pad_display_width(value: str, width: int) -> str:
    display_width = sum(_char_display_width(ch) for ch in value)
    return value + (" " * max(width - display_width, 1))


def _char_display_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1
