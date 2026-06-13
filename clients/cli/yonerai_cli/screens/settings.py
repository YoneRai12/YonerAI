from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from yonerai_cli.config import build_config_report
from yonerai_cli.screens.labels import (
    _agent_mode_label,
    _approval_label,
    _file_access_label,
    _language_label,
    _provider_label,
    _safe,
    _selector,
    _setting_label,
    _state_label,
    _value_label,
)


def format_settings_screen(lines: Iterable[str]) -> str:
    """Render settings screens from precomputed display lines."""

    return "\n".join(lines)


SETTINGS_CATEGORY_ALIASES = {
    "言語": "language",
    "language": "language",
    "lang": "language",
    "提供元": "providers",
    "提供元選択": "providers",
    "プロバイダー": "providers",
    "providers": "providers",
    "provider": "providers",
    "モデル": "models",
    "model": "models",
    "models": "models",
    "表示": "display",
    "display": "display",
    "安全": "safety",
    "safety": "safety",
    "ポリシー": "policy",
    "方針": "policy",
    "policy": "policy",
    "モード": "mode",
    "mode": "mode",
    "記憶": "memory",
    "メモリ": "memory",
    "memory": "memory",
    "更新": "update",
    "update": "update",
    "認証": "auth",
    "auth": "auth",
    "プライバシー": "privacy",
    "privacy": "privacy",
    "戻る": "back",
    "back": "back",
}


def _command_display_label(mode: object, *, lang: str) -> str:
    raw = str(mode or ("ja_only" if lang == "ja" else "en_only"))
    if lang == "ja":
        return {
            "ja_only": "日本語だけ",
            "ja_with_en": "日本語 + 英語",
            "en_with_ja": "英語 + 日本語",
            "en_only": "英語だけ",
        }.get(raw, raw)
    return raw


def _format_settings(
    config: dict[str, object],
    *,
    provider: str,
    live: bool,
    lang: str,
    provider_report: dict[str, Any] | None = None,
) -> str:
    values = build_config_report(config, exists=True)["config"]
    local_state = _provider_state(provider_report or {}, "local")
    ledger = "on" if values.get("ledger_enabled") else "off"
    update_notice = "on" if values.get("update_notice_enabled") else "off"
    if lang == "ja":
        return format_settings_screen(
            (
                "設定",
                "  現在: "
                + _language_label(values["language"] or "ja", lang="ja")
                + " / "
                + _provider_label(provider, lang="ja")
                + " / "
                + _safe(values.get("model_preference") or "auto")
                + " / "
                + _agent_mode_label(values.get("agent_mode"), lang="ja"),
                "  補助: 表示="
                + _command_display_label(values.get("command_display_mode"), lang="ja")
                + " / ローカルLLM="
                + _state_label(local_state, lang="ja")
                + " / 更新通知="
                + update_notice,
                "  安全: 承認="
                + _approval_label(values["approval_mode"], lang="ja")
                + " / ファイル="
                + _file_access_label(values["file_access_mode"], lang="ja")
                + " / 履歴="
                + ledger
                + " / live="
                + ("オン" if live else "オフ"),
                "  開く: 1 言語  2 提供元  3 モデル  4 安全  5 記憶",
                "        6 表示  7 更新    8 認証    9 プライバシー  10 ポリシー",
                "  次: /設定 <項目名>  または  /選択 <番号>",
                "",
            )
        )
    return format_settings_screen(
        (
            "Settings",
            "  current: "
            + f"language={values['language'] or 'ja'}"
            + f" / provider={provider}"
            + f" / model={values.get('model_preference') or 'auto'}"
            + f" / agent_mode={values.get('agent_mode')}",
            "  assist: "
            + f"display={values.get('command_display_mode') or 'en_only'}"
            + f" / local_llm={local_state}"
            + f" / update_notice={update_notice}",
            "  safety: "
            + f"approval={values['approval_mode']}"
            + f" / file_access={values['file_access_mode']}"
            + f" / ledger={ledger}"
            + f" / live={'on' if live else 'off'}",
            "  open: 1 language  2 providers  3 models  4 safety  5 memory",
            "        6 display   7 update     8 auth    9 privacy 10 policy",
            "  next: /settings <category>  or  /select <number>",
            "",
        )
    )

def _settings_category_from_args(args: list[str]) -> str | None:
    if not args:
        return None
    first = args[0].strip()
    raw = " ".join(args).strip()
    return (
        SETTINGS_CATEGORY_ALIASES.get(raw)
        or SETTINGS_CATEGORY_ALIASES.get(raw.lower())
        or SETTINGS_CATEGORY_ALIASES.get(first)
        or SETTINGS_CATEGORY_ALIASES.get(first.lower())
    )

def _format_settings_language(config: dict[str, object], *, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    if lang == "ja":
        return "\n".join(
            (
                "設定: 言語",
                f"  現在: {_language_label(values['language'] or 'ja', lang='ja')}",
                "  選択肢:",
                f"{_selector('ja', str(values['language'] or 'ja'))} 日本語",
                f"{_selector('en', str(values['language'] or 'ja'))} 英語",
                "  変更: /言語 日本語 または /選択 1 日本語",
                "  戻る: /設定",
                "",
            )
        )
    return "\n".join(
        (
            "Settings: language",
            f"  current: {values['language'] or 'ja'}",
            "  choices: ja, en",
            "  change: /language en or /select 1 en",
            "  back: /settings",
            "",
        )
    )

def _format_settings_update(config: dict[str, object], *, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    enabled = bool(values.get("update_notice_enabled"))
    if lang == "ja":
        return "\n".join(
            (
                "設定: 更新",
                f"  更新通知: {'オン' if enabled else 'オフ'}",
                "  通常: 通知だけ。作業中は割り込まない",
                "  セキュリティ: 警告だけ。自動適用しない",
                "  クリティカル: 次回起動時に先に表示。基本のローカルmockチャットは止めない",
                "  自動更新: なし",
                "  強制サイレント更新: なし",
                "  変更: /更新通知 オン|オフ  または  /選択 9 オン|オフ",
                "  確認: /更新 → 安定版 / ベータ版 を選ぶ",
                "  戻る: /設定",
                "",
            )
        )
    return "\n".join(
        (
            "Settings: update",
            f"  update_notice: {'on' if enabled else 'off'}",
            "  normal: notice only",
            "  security: warning only, no interruption during active task",
            "  critical: show first on next startup, basic local mock chat remains available",
            "  auto_apply: off",
            "  forced_silent_update: off",
            "  change: /update-notice on|off or /select 9 on|off",
            "  check: /update",
            "  back: /settings",
            "",
        )
    )


def _format_settings_display(config: dict[str, object], *, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    current = str(values.get("command_display_mode") or ("ja_only" if lang == "ja" else "en_only"))
    if lang == "ja":
        return "\n".join(
            (
                "設定: 表示方式",
                f"  現在: {_command_display_label(current, lang='ja')}",
                "  選択肢:",
                f"{_selector('ja_only', current)} 日本語だけ",
                f"{_selector('ja_with_en', current)} 日本語+英語",
                f"{_selector('en_with_ja', current)} 英語+日本語",
                f"{_selector('en_only', current)} 英語だけ",
                "  変更: /表示方式 日本語だけ",
                "  変更: /表示方式 日本語+英語",
                "  戻る: /設定",
                "",
            )
        )
    return "\n".join(
        (
            "Settings: display",
            f"  current: {current}",
            "  choices: ja_only, ja_with_en, en_with_ja, en_only",
            "  change: /display ja_with_en",
            "  back: /settings",
            "",
        )
    )

def _format_settings_memory(config: dict[str, object], status_report: dict[str, Any] | None, *, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    status = status_report or {}
    enabled = bool(values.get("memory_enabled"))
    scope = str(values.get("memory_default_scope") or "local_private")
    count = status.get("record_count", 0)
    if lang == "ja":
        lines = [
            "設定: 記憶",
            f"  記憶: {'オン' if enabled else 'オフ'} / default={_safe(scope)} / 件数={_safe(count)}",
            f"  cloud→local preview: {'オン' if values.get('memory_cloud_to_local_preview_enabled') else 'オフ'}",
            "  local→cloud: 承認必須 / 自動同期なし",
            f"  self-evolution signal: {'オン' if values.get('memory_self_evolution_signal_enabled') else 'オフ'}",
            "  操作: /記憶 list /記憶 add <内容> /記憶 forget <id>",
            "  同期確認: /記憶 sync preview cloud-to-local / local-to-cloud",
            "  private 記憶は cloud へ送りません。secret と local path は redact します。",
        ]
        lines.append("")
        return "\n".join(lines)
    lines = [
        "Settings: memory",
        f"  memory_enabled: {enabled}",
        f"  default_scope: {_safe(scope)}",
        f"  active_records: {_safe(count)}",
        f"  cloud_to_local_preview_enabled: {bool(values.get('memory_cloud_to_local_preview_enabled'))}",
        f"  local_to_cloud_approval_required: {bool(values.get('memory_local_to_cloud_approval_required'))}",
        f"  self_evolution_signal_memory: {bool(values.get('memory_self_evolution_signal_enabled'))}",
        "  shared_traffic: off",
        "  change: /settings memory on|off",
        "  change: /settings memory scope local_private|procedural|shared_preference|project|session",
        "  change: /settings memory cloud-preview on|off",
        "  change: /settings memory self-evolution on|off",
        "  actions: /memory add <text>, /memory list, /memory forget <memory_id>, /memory sync preview local-to-cloud",
        "  local_private memory never syncs automatically.",
    ]
    lines.append("")
    return "\n".join(lines)

def _settings_memory_help(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "記憶設定の指定が分かりません。",
                "例: /設定 記憶 オン",
                "例: /設定 記憶 scope procedural",
                "例: /設定 記憶 cloud-preview オフ",
                "例: /設定 記憶 self-evolution オン",
                "",
            )
        )
    return (
        "Unknown memory setting. Examples: /settings memory on, /settings memory scope procedural, "
        "/settings memory cloud-preview off, /settings memory self-evolution on\n"
    )

def _provider_state(report: dict[str, Any], provider_id: str) -> str:
    providers = report.get("providers") if isinstance(report.get("providers"), list) else []
    for item in providers:
        if isinstance(item, dict) and item.get("provider_id") == provider_id:
            return _safe(item.get("plain_state") or item.get("setup_status") or "unknown")
    return "unknown"


def _changed_message(key: str, value: object, *, lang: str) -> str:
    if lang == "ja":
        return f"設定を変更しました: {_setting_label(key, lang='ja')}={_value_label(value, lang='ja')}\n"
    return f"Changed setting: {key}={value}\n"


def _invalid(lang: str) -> str:
    return "値が正しくありません\n" if lang == "ja" else "Invalid value\n"


def _settings_selection_help(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "番号設定の形式が正しくありません。",
                "例: /選択 1 日本語",
                "例: /選択 2 モック",
                "例: /選択 8 llama3.1",
                "例: /選択 5 オン",
                "例: /選択 6 オフ",
                "例: /選択 7 オフ",
                "例: /選択 10 レビュー",
                "",
            )
        )
    return "Invalid numbered setting. Examples: /select 1 en, /select 2 mock, /select 8 llama3.1, /select 5 on\n"
