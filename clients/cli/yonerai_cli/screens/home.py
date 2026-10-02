from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from yonerai_cli import __version__
from yonerai_cli.auth_policy import build_google_auth_status
from yonerai_cli.screens.labels import (
    _approval_label,
    _file_access_label,
    _language_label,
    _provider_label,
    _safe,
)

_COMMAND_DISPLAY_EQUIVALENTS = {
    "/ログイン": "/login",
    "/認証": "/auth",
    "/アカウント": "/whoami",
    "/セッション": "/sessions",
    "/ログアウト": "/logout",
    "/取り消し": "/revoke",
    "/プロジェクト": "/projects",
    "/レート": "/rate-limit",
    "/疎通": "/ping",
    "/同期": "/sync",
    "/設定": "/settings",
    "/更新": "/update",
    "/ローカルLLM": "/local-llm",
    "/ローカルLLM 使う": "/local-llm use",
    "/提供元": "/providers",
    "/ヘルプ": "/help",
    "/終了": "/quit",
}


def format_home_screen(lines: Iterable[str]) -> str:
    return "\n".join(lines)


def build_home_policy_line(report: dict[str, Any] | None, *, lang: str) -> str:
    policies = report.get("policies") if isinstance(report, dict) and isinstance(report.get("policies"), dict) else {}
    provider = policies.get("provider") if isinstance(policies.get("provider"), dict) else {}
    permission = policies.get("permission") if isinstance(policies.get("permission"), dict) else {}
    memory = policies.get("memory_sync") if isinstance(policies.get("memory_sync"), dict) else {}
    tools = str(permission.get("tools_mode") or "dry_run")
    approval = str(permission.get("approval_mode") or "prompt")
    file_access = str(permission.get("file_access_mode") or "workspace_only")
    live_enabled = bool(provider.get("live_external_provider_enabled"))
    shell_enabled = bool(permission.get("arbitrary_shell_execution"))
    local_to_cloud_auto = bool(memory.get("local_private_auto_upload"))
    if lang == "ja":
        return " / ".join(
            (
                "ローカル優先",
                f"承認={_approval_label(approval, lang='ja')}",
                f"ファイル={_file_access_label(file_access, lang='ja')}",
                f"ツール={tools}",
                f"外部live={_bool_ja(live_enabled)}",
                f"任意shell={'有効' if shell_enabled else '無効'}",
                f"local→cloud={'自動同期あり' if local_to_cloud_auto else '自動同期なし'}",
            )
        )
    return " / ".join(
        (
            "local-first",
            f"approval={approval}",
            f"file_access={file_access}",
            f"tools={tools}",
            f"external_live={live_enabled}",
            f"arbitrary_shell={shell_enabled}",
            f"local_to_cloud_auto_sync={local_to_cloud_auto}",
        )
    )


def build_home_safety_line(report: dict[str, Any] | None, *, config: dict[str, object], lang: str) -> str:
    policies = report.get("policies") if isinstance(report, dict) and isinstance(report.get("policies"), dict) else {}
    permission = policies.get("permission") if isinstance(policies.get("permission"), dict) else {}
    provider = policies.get("provider") if isinstance(policies.get("provider"), dict) else {}
    approval = str(permission.get("approval_mode") or config.get("approval_mode") or "prompt")
    file_access = str(permission.get("file_access_mode") or config.get("file_access_mode") or "workspace_only")
    tools = str(permission.get("tools_mode") or config.get("tools_mode") or "dry_run")
    shell_enabled = bool(permission.get("arbitrary_shell_execution"))
    live_enabled = bool(provider.get("live_external_provider_enabled"))
    if lang == "ja":
        return " / ".join(
            (
                f"承認={_approval_label(approval, lang='ja')}",
                f"ファイル={_file_access_label(file_access, lang='ja')}",
                f"ツール={tools}",
                f"任意shell={'有効' if shell_enabled else '無効'}",
                f"外部live={_bool_ja(live_enabled)}",
            )
        )
    return " / ".join(
        (
            f"approval={approval}",
            f"file_access={file_access}",
            f"tools={tools}",
            f"arbitrary_shell={shell_enabled}",
            f"external_live={live_enabled}",
        )
    )


def build_home_safety_badge(
    report: dict[str, Any] | None,
    *,
    config: dict[str, object],
    lang: str,
) -> str:
    policies = report.get("policies") if isinstance(report, dict) and isinstance(report.get("policies"), dict) else {}
    permission = policies.get("permission") if isinstance(policies.get("permission"), dict) else {}
    provider = policies.get("provider") if isinstance(policies.get("provider"), dict) else {}
    approval = str(permission.get("approval_mode") or config.get("approval_mode") or "prompt")
    file_access = str(permission.get("file_access_mode") or config.get("file_access_mode") or "workspace_only")
    live_enabled = bool(provider.get("live_external_provider_enabled"))
    shell_enabled = bool(permission.get("arbitrary_shell_execution"))
    if lang == "ja":
        if shell_enabled:
            return "要確認 (任意shell有効)"
        if live_enabled:
            return "注意 (外部liveオン)"
        if approval == "deny" and file_access == "disabled":
            return "厳格"
        return "標準 (ワークスペースのみ / liveオフ)"
    if shell_enabled:
        return "review required (arbitrary shell on)"
    if live_enabled:
        return "caution (external live on)"
    if approval == "deny" and file_access == "disabled":
        return "strict"
    return "standard (workspace-only / live off)"


def _welcome(
    lang: str,
    *,
    provider: str,
    live: bool,
    config_exists: bool,
    config: dict[str, object],
    ledger_path: str | None,
    policy_report: dict[str, Any] | None = None,
    provider_report: dict[str, Any] | None = None,
    auth_report: dict[str, Any] | None = None,
) -> str:
    del live, config_exists, ledger_path, policy_report
    model = _safe(config.get("model_preference") or "auto")
    language = _language_label(config.get("language") or lang, lang=lang)
    memory_enabled = bool(config.get("memory_enabled"))
    update_notice_enabled = bool(config.get("update_notice_enabled"))
    auth_report = auth_report or build_google_auth_status(
        config,
        claim_path=str(config.get("_runtime_config_path") or "") or None,
    )
    auth_state_ja, auth_state_en, login_next_ja, login_next_en = _home_auth_summary(auth_report)
    local_llm_summary_ja, local_llm_summary_en = _local_llm_home_summary(
        provider_report,
        provider=provider,
        local_llm_enabled=bool(config.get("local_llm_enabled")),
    )
    next_action_ja, next_action_en = _home_primary_next_action(
        provider_report,
        login_next_ja=login_next_ja,
        login_next_en=login_next_en,
        provider=provider,
        local_llm_enabled=bool(config.get("local_llm_enabled")),
    )
    next_actions_ja, next_actions_en = _home_short_actions(
        provider_report,
        provider=provider,
        local_llm_enabled=bool(config.get("local_llm_enabled")),
        login_next_ja=login_next_ja,
        login_next_en=login_next_en,
    )
    version_ja, version_en = _home_version_line(__version__)
    command_display_mode = str(config.get("command_display_mode") or ("ja_with_en" if lang == "ja" else "en_with_ja"))
    shortcuts_ja = _home_shortcuts(next_action_ja, next_actions_ja)
    shortcuts_en = _home_shortcuts(next_action_en, next_actions_en)

    if lang == "ja":
        return format_home_screen(
            (
                f"YonerAI {version_ja}",
                "  会話: そのまま入力",
                "  コマンド: / で候補を開く",
                f"  言語: {language} / 接続: {_provider_label(provider, lang='ja')} / 認証: {auth_state_ja}",
                f"  モデル: {model} / ローカルLLM: {local_llm_summary_ja} / 記憶: {_bool_ja(memory_enabled)}",
                f"  更新: {'通知オン' if update_notice_enabled else '通知オフ'}",
                f"  次: {_display_command_alias(next_action_ja, lang=lang, mode=command_display_mode)}",
                "  近道: "
                + (
                    " ・ ".join(
                        _display_command_alias(command, lang=lang, mode=command_display_mode)
                        for command in shortcuts_ja
                    )
                    if shortcuts_ja
                    else "設定 (/設定 / settings)"
                ),
                "",
            )
        )
    return format_home_screen(
        (
            f"YonerAI {version_en}",
            "  chat: type normally",
            "  commands: use / for suggestions",
            f"  language: {language} / connection: {_provider_label(provider, lang='en')} / auth: {auth_state_en}",
            f"  model: {model} / local LLM: {local_llm_summary_en} / memory {'on' if memory_enabled else 'off'}",
            f"  update: {'notice on' if update_notice_enabled else 'notice off'}",
            f"  next: {_display_command_alias(next_action_en, lang=lang, mode=command_display_mode)}",
            "  shortcuts: "
            + (
                " ・ ".join(
                    _display_command_alias(command, lang=lang, mode=command_display_mode)
                    for command in shortcuts_en
                )
                if shortcuts_en
                else "settings (/settings / 設定)"
            ),
            "",
        )
    )


def _home_primary_next_action(
    provider_report: dict[str, Any] | None,
    *,
    login_next_ja: str,
    login_next_en: str,
    provider: str,
    local_llm_enabled: bool,
) -> tuple[str, str]:
    del provider_report, login_next_ja, login_next_en, provider, local_llm_enabled
    return "そのまま話す", "Type a normal message"


def _home_short_actions(
    provider_report: dict[str, Any] | None,
    *,
    provider: str,
    local_llm_enabled: bool,
    login_next_ja: str,
    login_next_en: str,
) -> tuple[tuple[str, str, str], tuple[str, str, str]]:
    local_llm = provider_report.get("local_llm") if isinstance(provider_report, dict) and isinstance(provider_report.get("local_llm"), dict) else {}
    installed_labels = _installed_local_llm_labels(local_llm)
    login_shortcut_ja = login_next_ja if login_next_ja == "/ログイン" else "/更新"
    login_shortcut_en = login_next_en if login_next_en == "/login" else "/update"
    if provider == "local" and local_llm_enabled:
        return (
            ("そのまま話す", login_shortcut_ja, "/設定" if login_shortcut_ja == "/更新" else "/更新"),
            ("Type a normal message", login_shortcut_en, "/settings" if login_shortcut_en == "/update" else "/update"),
        )
    if str(local_llm.get("status") or "") == "detected" or installed_labels:
        return (
            ("そのまま話す", "/ローカルLLM", login_shortcut_ja),
            ("Type a normal message", "/local-llm", login_shortcut_en),
        )
    if login_next_ja == "/ログイン":
        return (
            ("そのまま話す", "/ログイン", "/更新"),
            ("Type a normal message", "/login", "/update"),
        )
    return (
        ("そのまま話す", "/設定", "/更新"),
        ("Type a normal message", "/settings", "/update"),
    )


def _home_shortcuts(primary_action: str, actions: tuple[str, str, str]) -> tuple[str, ...]:
    shortcuts: list[str] = []
    for action in actions:
        if not action.startswith("/") or action == primary_action or action in shortcuts:
            continue
        shortcuts.append(action)
    return tuple(shortcuts[:2])


def _local_llm_home_summary(
    provider_report: dict[str, Any] | None,
    *,
    provider: str,
    local_llm_enabled: bool,
) -> tuple[str, str]:
    local_llm = provider_report.get("local_llm") if isinstance(provider_report, dict) and isinstance(provider_report.get("local_llm"), dict) else {}
    status = str(local_llm.get("status") or "unknown")
    detected_label = _safe(local_llm.get("detected_label") or local_llm.get("endpoint_label") or "not-detected")
    installed_labels = _installed_local_llm_labels(local_llm)
    if provider == "local" and local_llm_enabled:
        return f"使用中 ({detected_label})", f"active ({detected_label})"
    if status == "detected":
        return f"検出済み ({detected_label})", f"detected ({detected_label})"
    if status == "blocked":
        return "拒否: 非loopback URL", "blocked: non-loopback URL"
    if installed_labels:
        joined = ", ".join(installed_labels)
        return f"アプリあり / 未起動 ({joined})", f"app found / not running ({joined})"
    return "未検出", "not detected"


def _home_auth_summary(report: dict[str, Any]) -> tuple[str, str, str, str]:
    staging = report.get("staging") if isinstance(report.get("staging"), dict) else {}
    state = str(report.get("staging_auth_state") or "unauthenticated")
    if state == "linked":
        return "staging セッションあり", "staging session saved", "/認証", "/auth"
    if state == "expired":
        return "期限切れ (α/staging)", "expired (alpha/staging)", "/ログイン", "/login"
    if state == "revoked":
        return "取り消し済み (α/staging)", "revoked (alpha/staging)", "/ログイン", "/login"
    if state == "pending":
        return "ログイン待ち (α/staging)", "login pending (alpha/staging)", "/ログイン", "/login"
    if bool(staging.get("configured")):
        return "未ログイン (α/staging)", "not linked (alpha/staging)", "/ログイン", "/login"
    return "ローカルだけ", "local only", "/認証", "/auth"


def _home_version_line(version: str) -> tuple[str, str]:
    normalized = _safe(version or "unknown")
    if "-alpha." in normalized:
        return f"{normalized} / α-staging", f"{normalized} / alpha staging"
    if "-beta." in normalized:
        return f"{normalized} / ベータ", f"{normalized} / beta"
    return f"{normalized} / 安定版", f"{normalized} / stable"


def _installed_local_llm_labels(local_llm: dict[str, Any]) -> list[str]:
    installed_apps = local_llm.get("installed_apps") if isinstance(local_llm.get("installed_apps"), list) else []
    labels: list[str] = []
    for app in installed_apps:
        if not isinstance(app, dict) or app.get("installed") is not True:
            continue
        label = _safe(app.get("label") or "")
        if label:
            labels.append(label)
    return labels[:2]


def _bool_ja(value: object) -> str:
    return "オン" if bool(value) else "オフ"


def _display_command_alias(command: str, *, lang: str, mode: str) -> str:
    if not command.startswith("/"):
        return command
    english = _COMMAND_DISPLAY_EQUIVALENTS.get(command, command)
    japanese = next((ja for ja, en in _COMMAND_DISPLAY_EQUIVALENTS.items() if en == command), command)
    bare_english = english.lstrip("/")
    bare_japanese = japanese.lstrip("/")
    if lang == "ja":
        if mode == "ja_only":
            return f"{bare_japanese} ({japanese})"
        return f"{bare_japanese} ({japanese} / {bare_english})"
    if mode == "en_only":
        return f"{bare_english} ({english})"
    return f"{bare_english} ({english} / {bare_japanese})"
