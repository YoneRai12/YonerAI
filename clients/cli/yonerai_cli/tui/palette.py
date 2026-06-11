from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from yonerai_cli.config import COMMAND_DISPLAY_MODES
from yonerai_cli.output import ColorMode
from yonerai_cli.tui.keymap import JAPANESE_SLASH_ALIASES, SLASH_COMMANDS, SlashCommandSpec


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
    CommandPaletteCategory("ホーム", "Home", ("/status", "/palette", "/composer", "/help", "/quit")),
    CommandPaletteCategory("設定", "Settings", ("/settings", "/models", "/providers", "/mode", "/permissions")),
    CommandPaletteCategory("安全", "Safety", ("/safety", "/policy", "/file-access", "/network", "/live-provider")),
    CommandPaletteCategory("作業", "Work", ("/plan", "/review", "/progress", "/tasks", "/agents", "/context")),
    CommandPaletteCategory("履歴と記憶", "History and memory", ("/runs", "/show", "/memory", "/ledger")),
    CommandPaletteCategory("公式境界", "Official boundary", ("/auth", "/api", "/sync", "/privacy", "/evolve", "/update")),
)


def normalize_command_display_mode(value: object, *, lang: str) -> CommandDisplayMode:
    raw = str(value or "").strip()
    if raw in COMMAND_DISPLAY_MODES:
        return raw
    return "ja_only" if lang == "ja" else "en_only"


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
            "  / を入力すると候補が出ます。Tab/矢印が使えない端末では、この一覧と /選択 を使います。",
            "  普通は短い日本語コマンドだけで使えます。英語コマンドは互換用の別名です。",
            "  参照は @planner / @reviewer / @researcher と、/コンテキスト の公開安全な候補だけです。",
            "  検索: / の後に文字を続けると候補を絞ります。長い一覧はカテゴリごとに見ます。",
            "  番号fallback: /設定 で番号を確認し、/選択 <番号> <値> で変更します。",
            "  表示設定: config set command_display ja_only|ja_with_en|en_with_ja|en_only",
            "  ページ: 端末が狭い場合はカテゴリ単位でスクロールしてください。",
            "",
        ]
    else:
        lines = [
            "Command palette",
            "  Type / for suggestions. If Tab/arrows are unavailable, use this list and /select numbered fallback.",
            "  English aliases remain available. Japanese mode shows Japanese commands first.",
            "  Context references are limited to public-safe @planner/@reviewer/@researcher and /context guidance.",
            "  Search: keep typing after / to filter candidates. Long lists are grouped by category.",
            "  Numbered fallback: use /settings to inspect numbers, then /select <number> <value>.",
            "  Paging: scroll by category on narrow terminals.",
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
    lines.append("全コマンド" if mode.startswith("ja") else "All commands")
    lines.append(slash_command_summary(lang, display_mode=mode, color=color).rstrip())
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


def _spec_by_canonical() -> dict[str, SlashCommandSpec]:
    return {spec.canonical: spec for spec in SLASH_COMMANDS}


def _format_palette_command(spec: SlashCommandSpec, *, mode: CommandDisplayMode, color: ColorMode) -> str:
    primary, description, secondary = _command_parts(spec, mode=mode)
    secondary_text = f"  {_dim(secondary, color=color)}" if secondary else ""
    if mode.startswith("ja"):
        return f"  {_pad_display_width(primary, 14)} {description}{secondary_text}"
    return f"  {primary:<16} {description}{secondary_text}"


def _format_summary_command(spec: SlashCommandSpec, *, mode: CommandDisplayMode, color: ColorMode) -> str:
    primary, description, secondary = _command_parts(spec, mode=mode)
    secondary_text = f" {_dim(secondary, color=color)}" if secondary else ""
    if mode.startswith("ja"):
        return f"  {_pad_display_width(primary, 10)} {description}{secondary_text}"
    return f"  {primary:<10} {description}{secondary_text}"


def _command_parts(spec: SlashCommandSpec, *, mode: CommandDisplayMode) -> tuple[str, str, str]:
    english = spec.aliases[0] if spec.aliases else spec.canonical
    japanese_aliases = tuple(alias for alias in JAPANESE_SLASH_ALIASES.get(spec.canonical, ()) if alias != spec.command)
    if mode == "ja_only":
        return spec.command, spec.description_ja, " ".join(japanese_aliases)
    if mode == "ja_with_en":
        return spec.command, spec.description_ja, f"({english})"
    if mode == "en_with_ja":
        fallback = spec.command if spec.command.startswith("/") else ""
        japanese = fallback or (japanese_aliases[0] if japanese_aliases else "")
        return english, spec.description_en, f"({japanese})" if japanese else ""
    return english, spec.description_en, ""


def _dim(value: str, *, color: ColorMode) -> str:
    if color == "always":
        return f"{DIM}{value}{RESET}"
    return value


def _pad_display_width(value: str, width: int) -> str:
    display_width = sum(_char_display_width(ch) for ch in value)
    return value + (" " * max(width - display_width, 1))


def _char_display_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1
