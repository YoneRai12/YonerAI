from __future__ import annotations

from typing import Callable, TextIO, TypeVar

from yonerai_cli.tui.keymap import build_prompt_completer


T = TypeVar("T")


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
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.styles import Style

    completer = build_prompt_completer(lang)
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "completion-menu.completion": "bg:#202020 #dddddd",
            "completion-menu.completion.current": "bg:#005f87 #ffffff bold",
            "bottom-toolbar": "bg:#1f2937 #e5e7eb",
        }
    )
    toolbar_text = bottom_toolbar or (
        "Tab/矢印で候補を選択: /設定 /モデル /提供元 /安全 /履歴 /認証 /同期 /自己進化 /更新"
        if lang == "ja"
        else "Use Tab/arrows for suggestions: /settings /models /providers /safety /runs /auth /sync /evolve /update"
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
    except Exception:
        return False
    force_terminal = None if color == "auto" else color != "never"
    console = Console(file=stream, force_terminal=force_terminal, color_system="auto")
    console.print(Panel(text, title=title, border_style="cyan"))
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
        "japanese_alias_completion": True,
        "japanese_value_completion": True,
        "context_value_completion": prompt_ready,
        "completion_descriptions": prompt_ready,
        "tab_completion": prompt_ready,
        "arrow_selection": prompt_ready,
        "status_screen": True,
        "memory_screen": True,
        "rich_panels": rich_ready,
        "rich_status_spinner": rich_ready,
        "plain_fallback": True,
        "json_ansi_output": False,
    }
