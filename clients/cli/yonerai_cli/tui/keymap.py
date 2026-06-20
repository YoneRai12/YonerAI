from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


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
    SlashCommandSpec("/状態", "/status", "ホーム画面と現在の状態を表示", "Show the home screen and current status", ("/status", "/home")),
    SlashCommandSpec("/設定", "/settings", "設定画面を開く", "Open settings", ("/settings",), "settings_category"),
    SlashCommandSpec("/コマンド", "/palette", "コマンドパレットを開く", "Open the command palette", ("/palette", "/commands")),
    SlashCommandSpec("/入力", "/composer", "入力欄の使い方を表示", "Show composer help", ("/composer", "/input")),
    SlashCommandSpec("/ログイン", "/login", "staging Google ログインを開始", "Start staging Google login", ("/login",)),
    SlashCommandSpec("/認証", "/auth", "認証とアカウント状態を表示", "Show auth and account status", ("/auth",)),
    SlashCommandSpec("/アカウント", "/whoami", "現在の staging アカウントを表示", "Show the current staging account", ("/whoami",)),
    SlashCommandSpec("/セッション", "/sessions", "staging セッション一覧を表示", "List staging sessions", ("/sessions",)),
    SlashCommandSpec("/ログアウト", "/logout", "ローカルの staging セッションを消す", "Clear the local staging session", ("/logout",)),
    SlashCommandSpec("/取り消し", "/revoke", "指定した staging セッションを取り消す", "Revoke one staging session by id", ("/revoke",)),
    SlashCommandSpec("/プロジェクト", "/projects", "現在の staging プロジェクトを表示", "Show the current staging project", ("/projects", "/project")),
    SlashCommandSpec("/疎通", "/ping", "staging API の疎通確認", "Ping the staging API", ("/ping",)),
    SlashCommandSpec("/監査", "/audit", "監査イベントを表示", "Show audit events", ("/audit",)),
    SlashCommandSpec("/実行", "/run", "Native Run の送信/状態/結果を見る", "Show Native Run submit/status/result help", ("/run", "/Run"), "native_run"),
    SlashCommandSpec("/ワーカー", "/worker", "Official Execution Worker の状態を見る", "Show Official Execution Worker status", ("/worker", "/Worker")),
    SlashCommandSpec("/能力", "/capabilities", "Native Run の能力一覧を見る", "Show Native Run capability list", ("/capability", "/capabilities")),
    SlashCommandSpec("/モジュール", "/modules", "Native Run のモジュール一覧を見る", "Show Native Run module list", ("/module", "/modules")),
    SlashCommandSpec("/API", "/api", "Control Spine と API の状態を表示", "Show Control Spine and API status", ("/api", "/公式")),
    SlashCommandSpec("/レート", "/rate-limit", "API レート制限を表示", "Show the API rate limit", ("/rate-limit", "/ratelimit")),
    SlashCommandSpec("/同期", "/sync", "クラウド同期の境界を表示", "Show the cloud sync boundary", ("/sync", "/cloud")),
    SlashCommandSpec("/プライバシー", "/privacy", "プライバシー境界を表示", "Show privacy boundaries", ("/privacy",)),
    SlashCommandSpec("/自己進化", "/evolve", "proposal-only 自己進化キューを表示", "Show the proposal-only self-evolution queue", ("/evolve",)),
    SlashCommandSpec("/記憶", "/memory", "ローカル記憶の状態を表示", "Show local memory status", ("/memory", "/メモリ")),
    SlashCommandSpec("/モデル", "/models", "モデルとローカル LLM の設定", "Model and local LLM setup", ("/models", "/model"), "model"),
    SlashCommandSpec("/ローカルLLM", "/local-llm", "ローカル LLM の自動検出と設定", "Detect and configure a local LLM", ("/local-llm", "/llm")),
    SlashCommandSpec("/提供元", "/providers", "AI 提供元の状態を表示", "Show AI provider status", ("/providers",)),
    SlashCommandSpec("/提供元選択", "/provider", "AI 提供元を選ぶ", "Choose a provider", ("/provider",), "provider"),
    SlashCommandSpec("/安全", "/safety", "安全境界を表示", "Show safety boundaries", ("/safety",)),
    SlashCommandSpec("/権限", "/permissions", "権限と承認モードを表示", "Show permission and approval policy", ("/permissions",), "permission_profile"),
    SlashCommandSpec("/承認", "/approval", "承認モードを変更", "Change approval mode", ("/approval",), "approval"),
    SlashCommandSpec("/ファイル", "/file-access", "ファイルアクセス範囲を変更", "Change file access mode", ("/file-access",), "file_access"),
    SlashCommandSpec("/ライブ", "/live-provider", "外部 live 接続を切り替える", "Toggle external live provider", ("/live", "/live-provider"), "toggle"),
    SlashCommandSpec("/ネットワーク", "/network", "外部ネットワーク接続を切り替える", "Toggle external network access", ("/network",), "toggle"),
    SlashCommandSpec("/モード", "/mode", "エージェント動作モードを変更", "Change the agent mode", ("/mode",), "agent_mode"),
    SlashCommandSpec("/計画", "/plan", "計画モードに切り替える", "Switch to plan mode", ("/plan",)),
    SlashCommandSpec("/レビュー", "/review", "レビューモードに切り替える", "Switch to review mode", ("/review",)),
    SlashCommandSpec("/ポリシー", "/policy", "固定/可変ポリシーを表示", "Show fixed and configurable policies", ("/policy", "/方針")),
    SlashCommandSpec("/履歴", "/runs", "実行履歴を表示", "Show run history", ("/runs",)),
    SlashCommandSpec("/表示", "/show", "run_id を指定して詳細を表示", "Show one run by run_id", ("/show",)),
    SlashCommandSpec("/進行", "/progress", "現在の進行状況を表示", "Show current progress", ("/progress",)),
    SlashCommandSpec("/タスク", "/tasks", "タスク進行一覧を表示", "Show task progress", ("/tasks",)),
    SlashCommandSpec("/エージェント", "/agents", "エージェント計画を表示", "Show the agent plan", ("/agents", "/agent")),
    SlashCommandSpec("/コンテキスト", "/context", "安全な参照コンテキストを表示", "Show safe context references", ("/context", "/references")),
    SlashCommandSpec("/更新", "/update", "安定版/ベータ版の更新を確認", "Check stable and beta updates", ("/update",)),
    SlashCommandSpec("/更新通知", "/update-notice", "更新通知のオン/オフ", "Toggle update notices", ("/update-notice",), "toggle"),
    SlashCommandSpec("/言語", "/language", "表示言語を変更", "Change the display language", ("/language",), "language"),
    SlashCommandSpec("/表示方式", "/display", "日本語/英語コマンドの見せ方を変更", "Change command display mode", ("/display", "/display-mode"), "command_display"),
    SlashCommandSpec("/テーマ", "/theme", "表示テーマを変更", "Change the display theme", ("/theme",), "theme"),
    SlashCommandSpec("/履歴記録", "/ledger", "履歴記録のオン/オフ", "Toggle the local run ledger", ("/ledger",), "toggle"),
    SlashCommandSpec("/ヘルプ", "/help", "ヘルプを表示", "Show help", ("/help", "/?")),
    SlashCommandSpec("/終了", "/quit", "終了する", "Quit the app", ("/quit", "/exit", "/q")),
)


TOP_LEVEL_COMMANDS: tuple[str, ...] = (
    "/login",
    "/run",
    "/sync",
    "/memory",
    "/update",
    "/settings",
    "/whoami",
    "/projects",
    "/sessions",
    "/local-llm",
)

MAX_TOP_LEVEL_COMPLETIONS = 10
MAX_COMMAND_COMPLETIONS = 10


JAPANESE_SLASH_ALIASES: dict[str, tuple[str, ...]] = {
    "/status": ("/ホーム",),
    "/palette": ("/パレット",),
    "/composer": ("/入力欄",),
    "/api": ("/公式",),
    "/run": ("/実行",),
    "/worker": ("/ワーカー",),
    "/capabilities": ("/能力",),
    "/modules": ("/モジュール",),
    "/sync": ("/クラウド",),
    "/memory": ("/メモリ",),
    "/policy": ("/方針",),
    "/context": ("/参照",),
    "/providers": ("/プロバイダー",),
    "/provider": ("/プロバイダー選択",),
    "/file-access": ("/ファイルアクセス",),
    "/live-provider": ("/ライブ接続",),
    "/display": ("/コマンド表示",),
    "/theme": ("/配色",),
}


SLASH_VALUE_GROUPS: dict[str, tuple[SlashValueSpec, ...]] = {
    "language": (
        SlashValueSpec("日本語", "日本語 UI にする", "Japanese UI", ("ja",)),
        SlashValueSpec("英語", "English UI にする", "English UI", ("en",)),
    ),
    "command_display": (
        SlashValueSpec("日本語だけ", "英語コマンドは隠す", "Japanese only", ("ja_only", "ja-only")),
        SlashValueSpec("日本語+英語", "英語コマンドを薄く併記する", "Japanese with dim English", ("ja_with_en", "ja-with-en")),
        SlashValueSpec("英語+日本語", "日本語コマンドを薄く併記する", "English with dim Japanese", ("en_with_ja", "en-with-ja")),
        SlashValueSpec("英語だけ", "日本語コマンドは隠す", "English only", ("en_only", "en-only")),
    ),
    "theme": (
        SlashValueSpec("自動", "端末に合わせる", "Auto", ("auto",)),
        SlashValueSpec("ダーク", "暗い見た目", "Dark", ("dark",)),
        SlashValueSpec("ライト", "明るい見た目", "Light", ("light",)),
        SlashValueSpec("モノ", "低色数・読み上げ向け", "Mono", ("mono",)),
    ),
    "provider": (
        SlashValueSpec("自動", "安全な自動選択", "Auto route", ("auto",)),
        SlashValueSpec("モック", "既定のテスト用提供元", "Mock provider", ("mock",)),
        SlashValueSpec("ローカル", "PC 内の loopback LLM", "Local loopback LLM", ("local",)),
        SlashValueSpec("OpenAI互換", "OpenAI 互換 API", "OpenAI-compatible", ("openai-compatible",)),
        SlashValueSpec("アンソロピック", "Anthropic", "Anthropic", ("anthropic", "Anthropic")),
        SlashValueSpec("ジェミニ", "Gemini", "Gemini", ("gemini", "Gemini")),
    ),
    "native_run": (
        SlashValueSpec("送信", "短い文を staging Native Run に送る", "Submit a short staging Native Run", ("submit",)),
        SlashValueSpec("状態", "run_id の状態を見る", "Show status by run_id", ("status",)),
        SlashValueSpec("イベント", "run_id のイベントを見る", "Show events by run_id", ("events",)),
        SlashValueSpec("結果", "run_id の結果概要を見る", "Show result by run_id", ("result",)),
        SlashValueSpec("キャンセル", "queued/claimed の実行をキャンセルする", "Cancel a queued/claimed run", ("cancel",)),
    ),
    "model": (
        SlashValueSpec("自動", "提供元に合わせて自動選択", "Auto model", ("auto",)),
        SlashValueSpec("llama3.1", "ローカル LLM の例", "Common local LLM example"),
        SlashValueSpec("qwen2.5-coder", "ローカル coding model の例", "Local coding model example"),
    ),
    "approval": (
        SlashValueSpec("毎回確認", "危険操作の前に確認する", "Ask before risky actions", ("prompt", "確認")),
        SlashValueSpec("拒否", "危険操作を実行しない", "Deny risky actions", ("deny",)),
    ),
    "agent_mode": (
        SlashValueSpec("計画", "読み取り専用の計画モード", "Plan/read-only mode", ("plan_readonly", "plan", "read-only")),
        SlashValueSpec("安全実行", "安全な範囲で実行する", "Build/execute-safe mode", ("build_safe", "build", "execute-safe")),
        SlashValueSpec("レビュー", "レビューモード", "Review mode", ("review",)),
        SlashValueSpec("記憶", "記憶操作の確認モード", "Memory mode", ("memory",)),
    ),
    "permission_profile": (
        SlashValueSpec("読み取り専用", "計画のみ / 実行なし", "Read-only planning", ("read_only", "read-only")),
        SlashValueSpec("自動安全", "安全な操作のみ許可", "Auto-safe", ("auto_safe", "auto-safe")),
        SlashValueSpec("危険時確認", "危険時だけ確認する", "Ask before risky", ("ask_before_risky", "ask-before-risky")),
        SlashValueSpec("ドライランのみ", "常にドライランにする", "Dry-run only", ("dry_run_only", "dry-run-only")),
    ),
    "file_access": (
        SlashValueSpec("ワークスペース内のみ", "ワークスペース内だけ読む", "Workspace only", ("workspace_only",)),
        SlashValueSpec("無効", "ファイルを読まない", "Disabled", ("disabled",)),
    ),
    "toggle": (
        SlashValueSpec("オン", "有効にする", "On", ("on", "true", "yes", "1")),
        SlashValueSpec("オフ", "無効にする", "Off", ("off", "false", "no", "0")),
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
        SlashValueSpec("10", "モード", "Agent mode"),
    ),
    "settings_category": (
        SlashValueSpec("言語", "表示言語", "Language", ("language",)),
        SlashValueSpec("表示方式", "日本語と英語の見せ方", "Display", ("display",)),
        SlashValueSpec("提供元", "AI 提供元", "Providers", ("providers", "provider")),
        SlashValueSpec("モデル", "AI モデル", "Models", ("models", "model")),
        SlashValueSpec("モード", "エージェント動作", "Agent mode", ("mode",)),
        SlashValueSpec("安全", "安全境界", "Safety", ("safety",)),
        SlashValueSpec("記憶", "ローカル記憶", "Memory", ("memory", "メモリ")),
        SlashValueSpec("更新", "更新通知と適用", "Update", ("update",)),
        SlashValueSpec("認証", "staging 認証", "Auth", ("auth",)),
        SlashValueSpec("プライバシー", "プライバシー境界", "Privacy", ("privacy",)),
        SlashValueSpec("ポリシー", "固定/可変ポリシー", "Policy", ("policy",)),
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
        mapping[spec.command.lower()] = spec.canonical
        mapping[spec.canonical] = spec.canonical
        mapping[spec.canonical.lower()] = spec.canonical
        for alias in spec.aliases:
            mapping[alias] = spec.canonical
            mapping[alias.lower()] = spec.canonical
        for alias in JAPANESE_SLASH_ALIASES.get(spec.canonical, ()):
            mapping[alias] = spec.canonical
            mapping[alias.lower()] = spec.canonical
    mapping["/選択"] = "/select"
    mapping["/select"] = "/select"
    return mapping


COMMAND_ALIAS_MAP = _build_command_alias_map()


def resolve_submitted_slash_command(command_line: str) -> str | None:
    stripped = command_line.strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split(maxsplit=1)
    head = parts[0]
    tail = parts[1] if len(parts) > 1 else ""

    exact = COMMAND_ALIAS_MAP.get(head) or COMMAND_ALIAS_MAP.get(head.lower())
    if exact is not None:
        return f"{exact} {tail}".rstrip()

    fragment = head
    if len(_command_body(fragment)) < 3:
        return None

    matches: list[tuple[tuple[int, int, float, int], str]] = []
    for spec in _canonical_command_specs():
        match = _best_command_match(spec, fragment=fragment)
        if match is None:
            continue
        _insert_text, rank = match
        matches.append((rank, spec.canonical))
    if not matches:
        return None

    best_kind = min(rank[0] for rank, _canonical in matches)
    best_canonicals = {canonical for rank, canonical in matches if rank[0] == best_kind}
    if len(best_canonicals) != 1:
        return None

    canonical = next(iter(best_canonicals))
    return f"{canonical} {tail}".rstrip()


def slash_command_words(lang: str) -> list[str]:
    words: list[str] = []
    if lang == "ja":
        for spec in SLASH_COMMANDS:
            words.append(spec.command)
            words.extend(JAPANESE_SLASH_ALIASES.get(spec.canonical, ()))
        for spec in SLASH_COMMANDS:
            words.append(spec.canonical)
            words.extend(spec.aliases)
    else:
        for spec in SLASH_COMMANDS:
            words.append(spec.canonical)
            words.extend(spec.aliases)
    return _dedupe(words)


def slash_command_meta(lang: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for spec in SLASH_COMMANDS:
        description = spec.description_ja if lang == "ja" else spec.description_en
        keys = [spec.command] if lang == "ja" else [spec.canonical, *spec.aliases]
        if lang == "ja":
            keys.extend(JAPANESE_SLASH_ALIASES.get(spec.canonical, ()))
            keys.extend((spec.canonical, *spec.aliases))
        for key in keys:
            meta[key] = description
    return meta


def slash_command_value_group(command_line: str) -> str | None:
    stripped = command_line.lstrip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split()
    if not parts:
        return None
    canonical = COMMAND_ALIAS_MAP.get(parts[0], COMMAND_ALIAS_MAP.get(parts[0].lower(), parts[0].lower()))
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
        primary = _primary_value_word(spec, lang=lang)
        words.append(primary)
        if lang != "ja":
            if spec.value != primary:
                words.append(spec.value)
            words.extend(alias for alias in spec.aliases if alias != primary and alias != spec.value)
    return _dedupe(words)


def slash_value_meta(command_line: str, lang: str) -> dict[str, str]:
    group = slash_command_value_group(command_line)
    if group is None:
        return {}
    meta: dict[str, str] = {}
    for spec in SLASH_VALUE_GROUPS.get(group, ()):
        description = spec.description_ja if lang == "ja" else spec.description_en
        if lang == "ja":
            keys = [spec.value]
        else:
            primary = _primary_value_word(spec, lang=lang)
            keys = [primary]
            if spec.value != primary:
                keys.append(spec.value)
            keys.extend(alias for alias in spec.aliases if alias != primary and alias != spec.value)
        for key in keys:
            meta[key] = description
    return meta


def _dedupe(words: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for word in words:
        if word not in seen:
            seen.add(word)
            deduped.append(word)
    return deduped


def _primary_value_word(spec: SlashValueSpec, *, lang: str) -> str:
    if lang == "ja":
        return spec.value
    if _is_ascii_token(spec.value):
        return spec.value
    for alias in spec.aliases:
        if _is_ascii_token(alias):
            return alias
    return spec.value


def _is_ascii_token(value: str) -> bool:
    return bool(value) and all(ord(ch) < 128 for ch in value)


def _normalize_display_mode(display_mode: object, *, lang: str) -> str:
    raw = str(display_mode or "").strip()
    if raw in {"ja_only", "ja_with_en", "en_with_ja", "en_only"}:
        return raw
    return "ja_with_en" if lang == "ja" else "en_with_ja"


def _canonical_command_specs() -> list[SlashCommandSpec]:
    seen: set[str] = set()
    specs: list[SlashCommandSpec] = []
    for spec in SLASH_COMMANDS:
        if spec.canonical in seen:
            continue
        seen.add(spec.canonical)
        specs.append(spec)
    return specs


def _command_inputs(spec: SlashCommandSpec) -> list[str]:
    return _dedupe(
        [
            spec.command,
            spec.canonical,
            *spec.aliases,
            *JAPANESE_SLASH_ALIASES.get(spec.canonical, ()),
        ]
    )


def _command_display_columns(spec: SlashCommandSpec, *, mode: str) -> tuple[str, str | None]:
    japanese = spec.command
    english = spec.canonical
    if mode == "ja_with_en":
        return japanese, english if english != japanese else None
    if mode == "en_with_ja":
        return english, japanese if japanese != english else None
    if mode == "en_only":
        return english, None
    return japanese, None


def _ascii_command_query(fragment: str) -> bool:
    if not fragment.startswith("/"):
        return False
    body = fragment[1:]
    return bool(body) and all(ord(ch) < 128 for ch in body)


def _japanese_command_query(fragment: str) -> bool:
    if not fragment.startswith("/"):
        return False
    body = fragment[1:]
    return any(ord(ch) >= 128 for ch in body)


def _query_display_columns(
    spec: SlashCommandSpec,
    *,
    mode: str,
    fragment: str,
    insert_text: str,
) -> tuple[str, str | None]:
    primary, secondary = _command_display_columns(spec, mode=mode)
    if mode.startswith("ja") and _ascii_command_query(fragment) and insert_text == spec.canonical:
        return spec.canonical, spec.command if spec.command != spec.canonical else None
    if mode.startswith("en") and _japanese_command_query(fragment) and insert_text == spec.command:
        return spec.command, spec.canonical if spec.command != spec.canonical else None
    return primary, secondary


def _command_body(value: str) -> str:
    return value[1:] if value.startswith("/") else value


def _command_candidate_priority(spec: SlashCommandSpec, candidate: str, fragment: str) -> int:
    if _ascii_command_query(fragment):
        if candidate == spec.canonical:
            return 0
        if candidate in spec.aliases:
            return 1
        if candidate == spec.command:
            return 2
        return 3
    if _japanese_command_query(fragment):
        if candidate == spec.command:
            return 0
        if candidate in JAPANESE_SLASH_ALIASES.get(spec.canonical, ()):
            return 1
        if candidate == spec.canonical:
            return 2
        return 3
    if candidate == spec.command:
        return 0
    if candidate == spec.canonical:
        return 1
    return 2


def _command_match_rank(
    spec: SlashCommandSpec,
    candidate: str,
    fragment: str,
) -> tuple[int, int, float, int] | None:
    lower_candidate = candidate.lower()
    lower_fragment = fragment.lower()
    candidate_priority = _command_candidate_priority(spec, candidate, fragment)
    if lower_candidate.startswith(lower_fragment):
        return (0, candidate_priority, float(len(lower_candidate) - len(lower_fragment)), len(lower_candidate))
    if lower_fragment in lower_candidate:
        return (1, candidate_priority, float(lower_candidate.index(lower_fragment)), len(lower_candidate))
    fragment_body = _command_body(lower_fragment)
    candidate_body = _command_body(lower_candidate)
    if len(fragment_body) < 3 or not candidate_body:
        return None
    ratio = SequenceMatcher(None, fragment_body, candidate_body).ratio()
    if ratio < 0.72:
        return None
    return (2, candidate_priority, -ratio, len(candidate_body))


def _best_command_match(spec: SlashCommandSpec, *, fragment: str) -> tuple[str, tuple[int, int, float, int]] | None:
    candidates = _command_inputs(spec)
    if not fragment:
        return spec.command, (0, 0, 0.0, len(spec.command))
    ranked: list[tuple[tuple[int, int, float, int], str]] = []
    for word in candidates:
        rank = _command_match_rank(spec, word, fragment)
        if rank is None:
            continue
        ranked.append((rank, word))
    if ranked:
        rank, word = min(ranked, key=lambda item: (item[0], len(item[1])))
        return word, rank
    return None


def _best_insert_text(spec: SlashCommandSpec, *, fragment: str) -> str | None:
    match = _best_command_match(spec, fragment=fragment)
    return None if match is None else match[0]


def build_prompt_completer(lang: str, display_mode: str | None = None):
    from prompt_toolkit.completion import Completer, Completion

    mode = _normalize_display_mode(display_mode, lang=lang)
    spec_map = {spec.canonical: spec for spec in _canonical_command_specs()}
    top_specs = [spec_map[command] for command in TOP_LEVEL_COMMANDS if command in spec_map]

    def _command_display(spec: SlashCommandSpec, *, insert_text: str, fragment: str):
        primary, secondary = _query_display_columns(
            spec,
            mode=mode,
            fragment=fragment,
            insert_text=insert_text,
        )
        extras: list[str] = []
        if secondary and secondary != primary:
            extras.append(secondary)
        bilingual_alias = spec.canonical if lang == "ja" else spec.command
        if bilingual_alias and bilingual_alias not in {primary, secondary}:
            extras.append(bilingual_alias)
        if insert_text not in {primary, secondary, *extras}:
            extras.append(insert_text)
        display = [("", primary)]
        for extra in _dedupe(extras):
            display.append(("class:completion.alias", f"  {extra}"))
        return display

    def _yield_command_completions(fragment: str, *, specs: list[SlashCommandSpec]):
        start_position = -len(fragment)
        emitted = 0
        ranked_specs: list[tuple[tuple[int, int, float, int], int, str, SlashCommandSpec]] = []
        for spec_index, spec in enumerate(specs):
            match = _best_command_match(spec, fragment=fragment)
            if match is None:
                continue
            insert_text, rank = match
            ranked_specs.append((rank, spec_index, insert_text, spec))
        for _rank, _spec_index, insert_text, spec in sorted(ranked_specs, key=lambda item: (item[0], item[1], len(item[2]))):
            yield Completion(
                insert_text,
                start_position=start_position,
                display=_command_display(spec, insert_text=insert_text, fragment=fragment),
                display_meta=spec.description_ja if lang == "ja" else spec.description_en,
            )
            emitted += 1
            if emitted >= MAX_COMMAND_COMPLETIONS:
                break

    class YonerAISlashCompleter(Completer):
        def get_completions(self, document, complete_event):  # type: ignore[no-untyped-def]
            text = document.text_before_cursor
            stripped = text.lstrip()
            if not stripped.startswith("/"):
                return
            parts = stripped.split()
            completing_command = len(parts) <= 1 and not stripped.endswith(" ")
            if completing_command:
                if stripped == "/":
                    start_position = 0
                    for index, spec in enumerate(top_specs):
                        if index >= MAX_TOP_LEVEL_COMPLETIONS:
                            break
                        insert_text = spec.command if mode.startswith("ja") else spec.canonical
                        yield Completion(
                            insert_text,
                            start_position=start_position,
                            display=_command_display(spec, insert_text=insert_text, fragment=""),
                            display_meta="",
                        )
                    return
                fragment = stripped
                prioritized_specs = [spec for spec in top_specs if _best_insert_text(spec, fragment=fragment) is not None]
                if prioritized_specs:
                    extra_specs = [
                        spec
                        for spec in _canonical_command_specs()
                        if spec.canonical not in {item.canonical for item in prioritized_specs}
                        and _best_insert_text(spec, fragment=fragment) is not None
                    ]
                    yield from _yield_command_completions(
                        fragment,
                        specs=[*prioritized_specs, *extra_specs],
                    )
                    return
                yield from _yield_command_completions(fragment, specs=_canonical_command_specs())
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
