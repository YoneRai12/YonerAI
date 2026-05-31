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
    value_group: str | None = None


@dataclass(frozen=True)
class SlashValueSpec:
    value: str
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
    SlashCommandSpec("/提供元", "/providers", "AI接続元の状態", "Provider status", ("/providers",)),
    SlashCommandSpec("/安全", "/safety", "安全境界を見る", "Safety boundaries", ("/safety",)),
    SlashCommandSpec("/履歴", "/runs", "実行履歴を見る", "Run history", ("/runs",)),
    SlashCommandSpec("/表示", "/show", "実行IDを表示", "Show one run", ("/show",)),
    SlashCommandSpec("/タスク", "/tasks", "タスク進行を見る", "Task progress", ("/tasks",)),
    SlashCommandSpec("/エージェント", "/agents", "担当計画を見る", "Agent/reviewer plan", ("/agents",)),
    SlashCommandSpec("/認証", "/auth", "Google認証のdry-run状態", "Auth dry-run status", ("/auth",)),
    SlashCommandSpec("/プライバシー", "/privacy", "共有とプライバシー境界を見る", "Privacy status", ("/privacy",)),
    SlashCommandSpec(
        "/自己進化",
        "/evolve",
        "proposal-only自己進化キュー",
        "Self-evolution proposal queue",
        ("/evolve",),
    ),
    SlashCommandSpec("/更新", "/update", "更新確認", "Update check", ("/update",)),
    SlashCommandSpec("/更新通知", "/update-notice", "更新通知設定", "Update notice setting", ("/update-notice",), "toggle"),
    SlashCommandSpec("/言語", "/language", "表示言語を変える", "Change language", ("/language",), "language"),
    SlashCommandSpec(
        "/提供元選択",
        "/provider",
        "AI接続元を選ぶ",
        "Choose provider",
        ("/provider",),
        "provider",
    ),
    SlashCommandSpec("/承認", "/approval", "危険操作の扱いを変える", "Change approval mode", ("/approval",), "approval"),
    SlashCommandSpec(
        "/ファイルアクセス",
        "/file-access",
        "ファイル読み取り境界を変える",
        "Change file access mode",
        ("/file-access",),
        "file_access",
    ),
    SlashCommandSpec("/履歴記録", "/ledger", "ローカル履歴を切り替える", "Toggle ledger", ("/ledger",), "toggle"),
    SlashCommandSpec("/ライブ", "/live-provider", "明示live接続を切り替える", "Toggle live provider", ("/live", "/live-provider"), "toggle"),
    SlashCommandSpec("/ネットワーク", "/network", "外部通信許可を切り替える", "Toggle network", ("/network",), "toggle"),
    SlashCommandSpec("/ローカルLLM", "/local-llm", "PC内モデルの接続案内", "Local LLM setup", ("/local-llm", "/llm")),
    SlashCommandSpec("/選択", "/select", "番号で設定を変える", "Select numbered setting", ("/select",), "setting_number"),
    SlashCommandSpec("/ヘルプ", "/help", "コマンド一覧", "Help", ("/help", "/?")),
    SlashCommandSpec("/終了", "/quit", "終了", "Quit", ("/quit", "/exit", "/q")),
)


JAPANESE_SLASH_ALIASES: dict[str, tuple[str, ...]] = {
    "/settings": ("/設定",),
    "/models": ("/モデル",),
    "/providers": ("/提供元", "/プロバイダー"),
    "/safety": ("/安全",),
    "/runs": ("/履歴",),
    "/show": ("/表示",),
    "/tasks": ("/タスク",),
    "/agents": ("/エージェント",),
    "/auth": ("/認証",),
    "/privacy": ("/プライバシー",),
    "/evolve": ("/自己進化",),
    "/update": ("/更新",),
    "/update-notice": ("/更新通知",),
    "/language": ("/言語",),
    "/provider": ("/提供元選択", "/プロバイダー選択"),
    "/approval": ("/承認",),
    "/file-access": ("/ファイルアクセス", "/ファイル"),
    "/ledger": ("/履歴記録",),
    "/live-provider": ("/ライブ", "/ライブ接続"),
    "/network": ("/ネットワーク",),
    "/local-llm": ("/ローカルLLM", "/ローカルllm"),
    "/select": ("/選択",),
    "/help": ("/ヘルプ",),
    "/quit": ("/終了",),
}


SLASH_VALUE_GROUPS: dict[str, tuple[SlashValueSpec, ...]] = {
    "language": (
        SlashValueSpec("日本語", "日本語UIにする", "Japanese UI", ("ja",)),
        SlashValueSpec("英語", "English UIにする", "English UI", ("en",)),
    ),
    "provider": (
        SlashValueSpec("自動", "安全に自動選択", "Auto route", ("auto",)),
        SlashValueSpec("モック", "既定のテスト用提供元", "Mock provider", ("mock",)),
        SlashValueSpec("ローカル", "PC内のloopback LLM", "Local loopback LLM", ("local",)),
        SlashValueSpec("OpenAI互換", "明示許可時だけ使うOpenAI互換API", "OpenAI-compatible", ("openai-compatible",)),
        SlashValueSpec("アンソロピック", "明示許可時だけ使うAnthropic", "Anthropic", ("anthropic", "Anthropic")),
        SlashValueSpec("ジェミニ", "明示許可時だけ使うGemini", "Gemini", ("gemini", "Gemini")),
    ),
    "approval": (
        SlashValueSpec("毎回確認", "危険操作は確認待ち", "Ask before risky actions", ("prompt", "確認")),
        SlashValueSpec("拒否", "危険操作を拒否", "Deny risky actions", ("deny",)),
    ),
    "file_access": (
        SlashValueSpec("ワークスペース内のみ", "許可した作業場所だけ読む", "Workspace only", ("workspace_only",)),
        SlashValueSpec("無効", "ファイル読み取りを使わない", "Disabled", ("disabled",)),
    ),
    "toggle": (
        SlashValueSpec("オン", "明示的に有効化", "On", ("on", "true", "yes", "1")),
        SlashValueSpec("オフ", "無効化または初期値へ戻す", "Off", ("off", "false", "no", "0")),
    ),
    "setting_number": (
        SlashValueSpec("1", "表示言語", "Language"),
        SlashValueSpec("2", "提供元", "Provider"),
        SlashValueSpec("3", "承認", "Approval"),
        SlashValueSpec("4", "ファイルアクセス", "File access"),
        SlashValueSpec("5", "履歴記録", "Ledger"),
        SlashValueSpec("6", "ライブ接続", "Live provider"),
        SlashValueSpec("7", "ネットワーク", "Network"),
        SlashValueSpec("8", "モデル", "Model"),
        SlashValueSpec("9", "更新通知", "Update notice"),
    ),
}


NUMBERED_VALUE_GROUPS: dict[str, str] = {
    "1": "language",
    "2": "provider",
    "3": "approval",
    "4": "file_access",
    "5": "toggle",
    "6": "toggle",
    "7": "toggle",
    "9": "toggle",
}


def _build_command_alias_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for spec in SLASH_COMMANDS:
        mapping[spec.command] = spec.canonical
        mapping[spec.canonical] = spec.canonical
        for alias in spec.aliases:
            mapping[alias] = spec.canonical
        for alias in JAPANESE_SLASH_ALIASES.get(spec.canonical, ()):
            mapping[alias] = spec.canonical
    return mapping


_COMMAND_ALIAS_MAP = _build_command_alias_map()


def slash_command_words(lang: str) -> list[str]:
    words: list[str] = []
    for spec in SLASH_COMMANDS:
        if lang == "ja":
            words.append(spec.command)
        else:
            words.extend(spec.aliases)
            words.append(spec.command)
    if lang == "ja":
        for spec in SLASH_COMMANDS:
            words.extend(JAPANESE_SLASH_ALIASES.get(spec.canonical, ()))
    return _dedupe(words)


def _dedupe(words: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for word in words:
        if word not in seen:
            seen.add(word)
            deduped.append(word)
    return deduped


def slash_command_meta(lang: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for spec in SLASH_COMMANDS:
        description = spec.description_ja if lang == "ja" else spec.description_en
        if lang == "ja":
            meta[spec.command] = description
            for alias in JAPANESE_SLASH_ALIASES.get(spec.canonical, ()):
                meta[alias] = description
        else:
            meta[spec.command] = description
            for alias in spec.aliases:
                meta[alias] = description
    return meta


def slash_command_value_group(command_line: str) -> str | None:
    stripped = command_line.lstrip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split()
    if not parts:
        return None
    canonical = _COMMAND_ALIAS_MAP.get(parts[0], parts[0].lower())
    if canonical == "/select":
        if len(parts) == 1:
            return "setting_number"
        if len(parts) == 2 and not stripped.endswith(" "):
            return "setting_number"
        return NUMBERED_VALUE_GROUPS.get(parts[1])
    for spec in SLASH_COMMANDS:
        if spec.canonical == canonical:
            return spec.value_group
    return None


def slash_value_words(command_line: str, lang: str) -> list[str]:
    group = slash_command_value_group(command_line)
    if group is None:
        return []
    words: list[str] = []
    for spec in SLASH_VALUE_GROUPS.get(group, ()):
        if lang == "ja":
            words.append(spec.value)
        else:
            words.extend(spec.aliases)
            words.append(spec.value)
    return _dedupe(words)


def slash_value_meta(command_line: str, lang: str) -> dict[str, str]:
    group = slash_command_value_group(command_line)
    if group is None:
        return {}
    meta: dict[str, str] = {}
    for spec in SLASH_VALUE_GROUPS.get(group, ()):
        description = spec.description_ja if lang == "ja" else spec.description_en
        if lang == "ja":
            meta[spec.value] = description
        else:
            meta[spec.value] = description
            for alias in spec.aliases:
                meta[alias] = description
    return meta


def slash_command_summary(lang: str) -> str:
    lines = ["候補:" if lang == "ja" else "Suggestions:"]
    for spec in SLASH_COMMANDS:
        if lang == "ja":
            aliases = ", ".join(
                alias for alias in JAPANESE_SLASH_ALIASES.get(spec.canonical, ()) if alias != spec.command
            )
            alias_text = f" / {aliases}" if aliases else ""
            lines.append(f"  {spec.command:<10} {spec.description_ja}{alias_text}")
        else:
            primary = spec.aliases[0] if spec.aliases else spec.command
            lines.append(f"  {primary:<10} {spec.description_en}")
    lines.append("")
    return "\n".join(lines)


def _build_prompt_completer(lang: str):
    from prompt_toolkit.completion import Completer, Completion, WordCompleter

    command_completer = WordCompleter(
        slash_command_words(lang),
        ignore_case=True,
        meta_dict=slash_command_meta(lang),
        match_middle=True,
        sentence=True,
    )

    class YonerAISlashCompleter(Completer):
        def get_completions(self, document, complete_event):  # type: ignore[no-untyped-def]
            text = document.text_before_cursor
            stripped = text.lstrip()
            if not stripped.startswith("/"):
                return
            parts = stripped.split()
            completing_command = len(parts) <= 1 and not stripped.endswith(" ")
            if completing_command:
                yield from command_completer.get_completions(document, complete_event)
                return

            words = slash_value_words(stripped, lang)
            if not words:
                return
            meta = slash_value_meta(stripped, lang)
            fragment = "" if stripped.endswith(" ") else parts[-1]
            start_position = -len(fragment)
            lower_fragment = fragment.lower()
            for word in words:
                if not lower_fragment or word.lower().startswith(lower_fragment):
                    yield Completion(word, start_position=start_position, display_meta=meta.get(word, ""))

    return YonerAISlashCompleter()


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

    completer = _build_prompt_completer(lang)
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "completion-menu.completion": "bg:#202020 #dddddd",
            "completion-menu.completion.current": "bg:#005f87 #ffffff bold",
            "bottom-toolbar": "bg:#1f2937 #e5e7eb",
        }
    )
    toolbar_text = bottom_toolbar or (
        "Tab/矢印で候補を選択: /設定 /モデル /提供元 /安全 /履歴 /認証 /自己進化 /更新"
        if lang == "ja"
        else "Use Tab/arrows for suggestions: /settings /models /providers /safety /runs /auth /evolve /update"
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
        "rich_panels": rich_ready,
        "rich_status_spinner": rich_ready,
        "plain_fallback": True,
        "json_ansi_output": False,
    }
