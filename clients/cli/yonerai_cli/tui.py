from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TextIO, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class SlashCommandSpec:
    command: str
    canonical: str
    description_ja: str
    description_en: str
    aliases: tuple[str, ...] = ()


SLASH_COMMANDS: tuple[SlashCommandSpec, ...] = (
    SlashCommandSpec("/設定", "/settings", "設定を開く", "Open settings", ("/settings",)),
    SlashCommandSpec(
        "/モデル",
        "/models",
        "モデルとローカルLLM設定",
        "Model and local LLM setup",
        ("/models", "/model", "/local-llm"),
    ),
    SlashCommandSpec("/提供元", "/providers", "AI接続先の状態", "Provider status", ("/providers",)),
    SlashCommandSpec("/安全", "/safety", "安全境界を見る", "Safety boundaries", ("/safety",)),
    SlashCommandSpec("/履歴", "/runs", "実行履歴を見る", "Run history", ("/runs",)),
    SlashCommandSpec("/表示", "/show", "実行IDを表示", "Show one run", ("/show",)),
    SlashCommandSpec("/タスク", "/tasks", "タスク進行を見る", "Task progress", ("/tasks",)),
    SlashCommandSpec("/エージェント", "/agents", "担当計画を見る", "Agent/reviewer plan", ("/agents",)),
    SlashCommandSpec("/認証", "/auth", "Google認証のdry-run状態", "Auth dry-run status", ("/auth",)),
    SlashCommandSpec("/プライバシー", "/privacy", "共有と秘匿境界を見る", "Privacy status", ("/privacy",)),
    SlashCommandSpec("/更新", "/update", "更新確認", "Update check", ("/update",)),
    SlashCommandSpec("/更新通知", "/update-notice", "更新通知設定", "Update notice setting", ("/update-notice",)),
    SlashCommandSpec("/ヘルプ", "/help", "コマンド一覧", "Help", ("/help", "/?")),
    SlashCommandSpec("/終了", "/quit", "終了", "Quit", ("/quit", "/exit", "/q")),
)


def slash_command_words(lang: str) -> list[str]:
    words: list[str] = []
    for spec in SLASH_COMMANDS:
        if lang == "ja":
            words.append(spec.command)
        else:
            words.extend(spec.aliases)
            words.append(spec.command)
    seen: set[str] = set()
    deduped: list[str] = []
    for word in words:
        if word not in seen:
            seen.add(word)
            deduped.append(word)
    return deduped


def slash_command_summary(lang: str) -> str:
    lines = ["候補:" if lang == "ja" else "Suggestions:"]
    for spec in SLASH_COMMANDS:
        if lang == "ja":
            lines.append(f"  {spec.command:<10} {spec.description_ja}")
        else:
            primary = spec.aliases[0] if spec.aliases else spec.command
            lines.append(f"  {primary:<10} {spec.description_en}")
    lines.append("")
    return "\n".join(lines)


def prompt_toolkit_available() -> bool:
    try:
        import prompt_toolkit  # noqa: F401
    except Exception:
        return False
    return True


def rich_available() -> bool:
    try:
        import rich  # noqa: F401
    except Exception:
        return False
    return True


def prompt_line(*, lang: str, bottom_toolbar: str | None = None) -> str:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.styles import Style

    completer = WordCompleter(
        slash_command_words(lang),
        ignore_case=True,
        match_middle=True,
        sentence=True,
    )
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "completion-menu.completion": "bg:#202020 #dddddd",
            "completion-menu.completion.current": "bg:#005f87 #ffffff bold",
            "bottom-toolbar": "bg:#1f2937 #e5e7eb",
        }
    )
    toolbar_text = bottom_toolbar or (
        "Tab/矢印で候補を選択: /設定 /モデル /提供元 /安全 /履歴 /認証 /更新"
        if lang == "ja"
        else "Use Tab/arrows for suggestions: /settings /models /providers /safety /runs /auth /update"
    )
    prompt = HTML("<prompt>yonerai</prompt> > ")
    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        complete_in_thread=True,
        reserve_space_for_menu=8,
        bottom_toolbar=toolbar_text,
        style=style,
    )
    try:
        return str(session.prompt(prompt)).strip()
    except (EOFError, KeyboardInterrupt):
        return "/終了" if lang == "ja" else "/quit"


def render_panel(text: str, *, title: str, stream: TextIO, color: str = "auto") -> bool:
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
    except Exception:
        return False
    force_terminal = None if color == "auto" else color != "never"
    console = Console(file=stream, force_terminal=force_terminal, color_system="auto")
    console.print(Panel(Text.from_ansi(text), title=title, border_style="cyan"))
    return True


def run_with_status(message: str, func: Callable[[], T], *, stream: TextIO, color: str = "auto") -> T:
    try:
        from rich.console import Console
    except Exception:
        return func()
    force_terminal = None if color == "auto" else color != "never"
    console = Console(file=stream, force_terminal=force_terminal, color_system="auto")
    with console.status(message, spinner="dots"):
        return func()


def tui_capability_report() -> dict[str, object]:
    prompt_ready = prompt_toolkit_available()
    rich_ready = rich_available()
    return {
        "schema_version": "yonerai-tui-runtime/v0.6",
        "prompt_toolkit_available": prompt_ready,
        "rich_available": rich_ready,
        "slash_completion": prompt_ready,
        "tab_completion": prompt_ready,
        "arrow_selection": prompt_ready,
        "rich_panels": rich_ready,
        "rich_status_spinner": rich_ready,
        "plain_fallback": True,
        "json_ansi_output": False,
    }
