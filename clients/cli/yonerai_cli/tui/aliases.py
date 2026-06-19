from __future__ import annotations


from difflib import SequenceMatcher


COMMAND_ALIASES = {
    "/?": "/help",
    "/状態": "/status",
    "/ホーム": "/status",
    "/status": "/status",
    "/home": "/status",
    "/ヘルプ": "/help",
    "/help": "/help",
    "/コマンド": "/palette",
    "/パレット": "/palette",
    "/palette": "/palette",
    "/commands": "/palette",
    "/入力": "/composer",
    "/入力欄": "/composer",
    "/composer": "/composer",
    "/input": "/composer",
    "/設定": "/settings",
    "/settings": "/settings",
    "/モデル": "/models",
    "/model": "/models",
    "/models": "/models",
    "/安全": "/safety",
    "/safety": "/safety",
    "/ポリシー": "/policy",
    "/方針": "/policy",
    "/policy": "/policy",
    "/提供元": "/providers",
    "/プロバイダー": "/providers",
    "/providers": "/providers",
    "/履歴": "/runs",
    "/runs": "/runs",
    "/進行": "/progress",
    "/progress": "/progress",
    "/タスク": "/tasks",
    "/tasks": "/tasks",
    "/表示": "/show",
    "/show": "/show",
    "/エージェント": "/agents",
    "/agents": "/agents",
    "/agent": "/agents",
    "/コンテキスト": "/context",
    "/参照": "/context",
    "/context": "/context",
    "/references": "/context",
    "/モード": "/mode",
    "/mode": "/mode",
    "/計画": "/plan",
    "/plan": "/plan",
    "/レビュー": "/review",
    "/review": "/review",
    "/権限": "/permissions",
    "/permissions": "/permissions",
    "/認証": "/auth",
    "/auth": "/auth",
    "/ログイン": "/login",
    "/login": "/login",
    "/アカウント": "/whoami",
    "/whoami": "/whoami",
    "/API": "/api",
    "/api": "/api",
    "/公式": "/api",
    "/レート": "/rate-limit",
    "/レート制限": "/rate-limit",
    "/rate-limit": "/rate-limit",
    "/ratelimit": "/rate-limit",
    "/疎通": "/ping",
    "/ping": "/ping",
    "/プロジェクト": "/project",
    "/projects": "/project",
    "/project": "/project",
    "/セッション": "/sessions",
    "/sessions": "/sessions",
    "/ログアウト": "/logout",
    "/logout": "/logout",
    "/取り消し": "/revoke",
    "/revoke": "/revoke",
    "/監査": "/audit",
    "/audit": "/audit",
    "/実行": "/run",
    "/run": "/run",
    "/Run": "/run",
    "/RUN": "/run",
    "/ワーカー": "/worker",
    "/worker": "/worker",
    "/Worker": "/worker",
    "/能力": "/capabilities",
    "/capability": "/capabilities",
    "/capabilities": "/capabilities",
    "/モジュール": "/modules",
    "/module": "/modules",
    "/modules": "/modules",
    "/同期": "/sync",
    "/クラウド": "/sync",
    "/会話": "/sync",
    "/conversation": "/sync",
    "/sync": "/sync",
    "/プライバシー": "/privacy",
    "/privacy": "/privacy",
    "/共有": "/privacy",
    "/共有トラフィック": "/privacy",
    "/provider-sharing": "/privacy",
    "/sharing": "/privacy",
    "/記憶": "/memory",
    "/メモリ": "/memory",
    "/memory": "/memory",
    "/自己進化": "/evolve",
    "/evolve": "/evolve",
    "/ローカルllm": "/local-llm",
    "/ローカルLLM": "/local-llm",
    "/local-llm": "/local-llm",
    "/llm": "/local-llm",
    "/更新": "/update",
    "/update": "/update",
    "/更新通知": "/update-notice",
    "/update-notice": "/update-notice",
    "/言語": "/language",
    "/language": "/language",
    "/表示方式": "/display",
    "/コマンド表示": "/display",
    "/display": "/display",
    "/display-mode": "/display",
    "/テーマ": "/theme",
    "/配色": "/theme",
    "/theme": "/theme",
    "/提供元選択": "/provider",
    "/プロバイダー選択": "/provider",
    "/provider": "/provider",
    "/承認": "/approval",
    "/approval": "/approval",
    "/ファイル": "/file-access",
    "/ファイルアクセス": "/file-access",
    "/file-access": "/file-access",
    "/履歴記録": "/ledger",
    "/ledger": "/ledger",
    "/ライブ": "/live-provider",
    "/ライブ接続": "/live-provider",
    "/live": "/live-provider",
    "/live-provider": "/live-provider",
    "/ネットワーク": "/network",
    "/network": "/network",
    "/選択": "/select",
    "/select": "/select",
    "/終了": "/quit",
    "/quit": "/quit",
    "/exit": "/quit",
    "/q": "/quit",
    "/ime": "/ime",
    "/IME": "/ime",
    "/変換": "/convert",
    "/convert": "/convert",
    "/確定": "/commit",
    "/commit": "/commit",
    "/戻す": "/revert",
    "/revert": "/revert",
    "/辞書": "/dict",
    "/dict": "/dict",
    "/文体": "/style",
    "/style": "/style",
}
VALUE_ALIASES = {
    "日本語": "ja",
    "英語": "en",
    "日本語だけ": "ja_only",
    "日本語+英語": "ja_with_en",
    "日本語＋英語": "ja_with_en",
    "英語+日本語": "en_with_ja",
    "英語＋日本語": "en_with_ja",
    "英語だけ": "en_only",
    "自動": "auto",
    "モック": "mock",
    "ローカル": "local",
    "OpenAI互換": "openai-compatible",
    "openai互換": "openai-compatible",
    "アンソロピック": "anthropic",
    "ジェミニ": "gemini",
    "確認": "prompt",
    "毎回確認": "prompt",
    "拒否": "deny",
    "計画": "plan_readonly",
    "読み取り": "plan_readonly",
    "読み取り専用": "plan_readonly",
    "plan": "plan_readonly",
    "plan-readonly": "plan_readonly",
    "安全実行": "build_safe",
    "ビルド": "build_safe",
    "構築": "build_safe",
    "build": "build_safe",
    "execute-safe": "build_safe",
    "レビュー": "review",
    "査読": "review",
    "記憶": "memory",
    "メモリ": "memory",
    "read-only": "read_only",
    "readonly": "read_only",
    "読み取りのみ": "read_only",
    "自動安全": "auto_safe",
    "auto-safe": "auto_safe",
    "危険時確認": "ask_before_risky",
    "ask-before-risky": "ask_before_risky",
    "ドライランのみ": "dry_run_only",
    "dry-run-only": "dry_run_only",
    "ワークスペース内のみ": "workspace_only",
    "ワークスペースのみ": "workspace_only",
    "無効": "disabled",
    "オン": "on",
    "有効": "on",
    "履歴オン": "on",
    "オフ": "off",
    "履歴オフ": "off",
}

COMMAND_ALIASES_CASEFOLD = {alias.lower(): canonical for alias, canonical in COMMAND_ALIASES.items()}


def _best_fuzzy_command_alias(value: str) -> str | None:
    raw = value.strip()
    if not raw.startswith("/"):
        return None
    fragment = raw.lower().lstrip("/")
    if len(fragment) < 4:
        return None
    scored_matches: list[tuple[float, str]] = []
    for alias, canonical in sorted(COMMAND_ALIASES.items(), key=lambda item: item[0].casefold()):
        alias_lower = alias.lower()
        body = alias_lower.lstrip("/")
        if not body or body[0] != fragment[0]:
            continue
        score = SequenceMatcher(None, fragment, body).ratio()
        if body.startswith(fragment):
            score += 0.15
        if fragment.startswith(body):
            score += 0.05
        if score < 0.74:
            continue
        scored_matches.append((score, canonical))
    if not scored_matches:
        return None
    best_score = max(score for score, _canonical in scored_matches)
    canonical_matches = {canonical for score, canonical in scored_matches if best_score - score < 0.02}
    if len(canonical_matches) != 1:
        return None
    return sorted(canonical_matches)[0]

def canonical_command(value: str) -> str:
    raw = value.strip()
    exact = COMMAND_ALIASES.get(raw)
    if exact is None:
        exact = COMMAND_ALIASES_CASEFOLD.get(raw.lower(), raw.lower())
    if exact != raw.lower():
        return exact
    return _best_fuzzy_command_alias(raw) or exact


def canonical_value(value: str) -> str:
    raw = value.strip()
    return VALUE_ALIASES.get(raw, VALUE_ALIASES.get(raw.lower(), raw))


def canonical_agent_mode_value(value: str) -> str:
    normalized = canonical_value(value)
    return "plan_readonly" if normalized == "read_only" else normalized
