from __future__ import annotations

from dataclasses import dataclass


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
    SlashCommandSpec("/状態", "/status", "状態ヘッダーを再表示", "Show mission-control status", ("/status", "/home")),
    SlashCommandSpec("/設定", "/settings", "設定カテゴリを開く", "Open settings categories", ("/settings",), "settings_category"),
    SlashCommandSpec(
        "/コマンド",
        "/palette",
        "コマンドパレットを表示",
        "Show command palette",
        ("/palette", "/commands"),
    ),
    SlashCommandSpec(
        "/モデル",
        "/models",
        "モデルとローカルLLM設定",
        "Model and local LLM setup",
        ("/models", "/model", "/local-llm"),
        "model",
    ),
    SlashCommandSpec("/提供元", "/providers", "AI接続元の状態", "Provider status", ("/providers",)),
    SlashCommandSpec("/安全", "/safety", "安全境界を見る", "Safety boundaries", ("/safety",)),
    SlashCommandSpec("/ポリシー", "/policy", "提供元・権限・更新・記憶の方針を見る", "Policy status", ("/policy",)),
    SlashCommandSpec("/履歴", "/runs", "実行履歴を見る", "Run history", ("/runs",)),
    SlashCommandSpec("/表示", "/show", "実行IDを表示", "Show one run", ("/show",)),
    SlashCommandSpec("/タスク", "/tasks", "タスク進行を見る", "Task progress", ("/tasks",)),
    SlashCommandSpec("/エージェント", "/agents", "担当計画を見る", "Agent/reviewer plan", ("/agents",)),
    SlashCommandSpec("/モード", "/mode", "作業モードを選ぶ", "Choose agent mode", ("/mode",), "agent_mode"),
    SlashCommandSpec("/計画", "/plan", "読み取り専用の計画モード", "Switch to read-only planning mode", ("/plan",)),
    SlashCommandSpec("/レビュー", "/review", "レビュー担当モード", "Switch to review mode", ("/review",)),
    SlashCommandSpec("/権限", "/permissions", "承認と権限の状態を見る", "Show approval and permission policy", ("/permissions",), "permission_profile"),
    SlashCommandSpec("/認証", "/auth", "Google認証のdry-run状態", "Auth dry-run status", ("/auth",)),
    SlashCommandSpec("/API", "/api", "公式API契約とStatus API連携を表示", "Official API and status bridge", ("/api", "/公式")),
    SlashCommandSpec("/同期", "/sync", "cloud/local同期境界", "Cloud/local sync boundary", ("/sync",)),
    SlashCommandSpec("/プライバシー", "/privacy", "共有とプライバシー境界を見る", "Privacy status", ("/privacy",)),
    SlashCommandSpec("/記憶", "/memory", "ローカル記憶と同期境界を見る", "Memory boundary status", ("/memory", "/メモリ")),
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
    "/status": ("/状態", "/ホーム"),
    "/settings": ("/設定",),
    "/models": ("/モデル",),
    "/providers": ("/提供元", "/プロバイダー"),
    "/safety": ("/安全",),
    "/policy": ("/ポリシー", "/方針"),
    "/runs": ("/履歴",),
    "/show": ("/表示",),
    "/tasks": ("/タスク",),
    "/agents": ("/エージェント",),
    "/mode": ("/モード",),
    "/plan": ("/計画",),
    "/review": ("/レビュー",),
    "/permissions": ("/権限",),
    "/palette": ("/コマンド", "/パレット"),
    "/auth": ("/認証",),
    "/api": ("/API", "/公式"),
    "/sync": ("/同期",),
    "/privacy": ("/プライバシー",),
    "/memory": ("/記憶", "/メモリ"),
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
    "model": (
        SlashValueSpec("自動", "設定済みの提供元に任せる", "Auto model", ("auto",)),
        SlashValueSpec("llama3.1", "ローカルLLMでよく使う例", "Common local LLM example"),
        SlashValueSpec("qwen2.5-coder", "ローカル coding model の例", "Local coding model example"),
    ),
    "approval": (
        SlashValueSpec("毎回確認", "危険操作は確認待ち", "Ask before risky actions", ("prompt", "確認")),
        SlashValueSpec("拒否", "危険操作を拒否", "Deny risky actions", ("deny",)),
    ),
    "agent_mode": (
        SlashValueSpec("計画", "読み取り専用で計画する", "Plan/read-only mode", ("plan_readonly", "plan", "read-only")),
        SlashValueSpec("安全実行", "安全な範囲だけ実行候補にする", "Build/execute-safe mode", ("build_safe", "build", "execute-safe")),
        SlashValueSpec("レビュー", "レビューと検証を優先する", "Review mode", ("review",)),
        SlashValueSpec("記憶", "記憶の確認と整理を優先する", "Memory mode", ("memory",)),
    ),
    "permission_profile": (
        SlashValueSpec("読み取り専用", "変更を行わず計画だけにする", "Read-only planning", ("read_only", "read-only")),
        SlashValueSpec("自動安全", "安全なdry-runだけ自動で扱う", "Auto-safe dry-run", ("auto_safe", "auto-safe")),
        SlashValueSpec("危険時確認", "危険操作は確認待ちにする", "Ask before risky", ("ask_before_risky", "ask-before-risky")),
        SlashValueSpec("ドライランのみ", "実行ではなく計画だけにする", "Dry-run only", ("dry_run_only", "dry-run-only")),
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
        SlashValueSpec("10", "作業モード", "Agent mode"),
    ),
    "settings_category": (
        SlashValueSpec("言語", "表示言語", "Language", ("language",)),
        SlashValueSpec("提供元", "AI接続元", "Providers", ("providers", "provider")),
        SlashValueSpec("モデル", "AIモデル", "Models", ("models", "model")),
        SlashValueSpec("モード", "作業モード", "Agent mode", ("mode",)),
        SlashValueSpec("安全", "安全境界", "Safety", ("safety",)),
        SlashValueSpec("ポリシー", "提供元・権限・更新・記憶の方針", "Policy", ("policy",)),
        SlashValueSpec("記憶", "ローカル記憶と同期境界", "Memory", ("memory", "メモリ")),
        SlashValueSpec("更新", "更新通知とdry-run確認", "Update", ("update",)),
        SlashValueSpec("認証", "Google OAuth dry-run状態", "Auth", ("auth",)),
        SlashValueSpec("プライバシー", "共有と非公開データ境界", "Privacy", ("privacy",)),
        SlashValueSpec("戻る", "カテゴリ一覧へ戻る", "Back", ("back",)),
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
    "8": "model",
    "9": "toggle",
    "10": "agent_mode",
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


COMMAND_ALIAS_MAP = _build_command_alias_map()


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
    canonical = COMMAND_ALIAS_MAP.get(parts[0], parts[0].lower())
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


def build_prompt_completer(lang: str):
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
