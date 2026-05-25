from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TextIO

from yonerai_cli.config import (
    APPROVAL_MODES,
    FILE_ACCESS_MODES,
    PROVIDER_PREFERENCES,
    build_config_report,
    default_config_path,
    load_cli_config,
    save_cli_config,
    set_cli_config_value,
)


INTERACTIVE_SCHEMA_VERSION = "yonerai-interactive-cli/v0.3"
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"(?i)(authorization|api[_-]?key|token|secret)\s*[:=]\s*[^,\s]+"),
)
PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^,\s]+", re.IGNORECASE),
    re.compile(r"/(?:home|Users|root)/[^,\s]+"),
)
COMMAND_ALIASES = {
    "/?": "/help",
    "/ヘルプ": "/help",
    "/help": "/help",
    "/設定": "/settings",
    "/settings": "/settings",
    "/安全": "/safety",
    "/safety": "/safety",
    "/提供元": "/providers",
    "/プロバイダー": "/providers",
    "/providers": "/providers",
    "/履歴": "/runs",
    "/runs": "/runs",
    "/表示": "/show",
    "/show": "/show",
    "/言語": "/language",
    "/language": "/language",
    "/提供元選択": "/provider",
    "/プロバイダー選択": "/provider",
    "/provider": "/provider",
    "/承認": "/approval",
    "/approval": "/approval",
    "/ファイル": "/file-access",
    "/ファイルアクセス": "/file-access",
    "/file-access": "/file-access",
    "/終了": "/quit",
    "/quit": "/quit",
    "/exit": "/quit",
    "/q": "/quit",
}
VALUE_ALIASES = {
    "日本語": "ja",
    "英語": "en",
    "自動": "auto",
    "モック": "mock",
    "ローカル": "local",
    "オープンai互換": "openai-compatible",
    "openai互換": "openai-compatible",
    "アンソロピック": "anthropic",
    "ジェミニ": "gemini",
    "確認": "prompt",
    "毎回確認": "prompt",
    "拒否": "deny",
    "ワークスペース内のみ": "workspace_only",
    "無効": "disabled",
}


@dataclass(frozen=True)
class InteractiveCallbacks:
    providers: Callable[[], dict[str, Any]]
    ask_auto: Callable[[str, str, bool, str | None, str], dict[str, Any]]
    runs_list: Callable[[str | None, int, str], dict[str, Any]]
    runs_show: Callable[[str, str | None, str], dict[str, Any]]


@dataclass(frozen=True)
class InteractiveOptions:
    config_path: str | None = None
    lang: str | None = None
    provider: str | None = None
    live: bool = False
    ledger_path: str | None = None
    script: bool = False
    color: str = "auto"


def run_interactive_cli(
    options: InteractiveOptions,
    callbacks: InteractiveCallbacks,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    config = load_cli_config(options.config_path)
    config_exists = _config_exists(options.config_path)
    lang = _select_language(config, options, input_stream=input_stream, output_stream=output_stream)
    provider = options.provider or str(config.get("provider_preference") or "auto")
    if provider not in PROVIDER_PREFERENCES:
        provider = "auto"
    live = bool(options.live or config.get("live_provider_enabled") is True)

    if not options.script and not _is_interactive(input_stream):
        _write(output_stream, _non_tty_fallback(lang))
        return 0

    _write(output_stream, _welcome(lang, provider=provider, live=live, config_exists=config_exists))
    while True:
        if _is_interactive(input_stream):
            output_stream.write("yonerai> " if lang == "en" else "yonerai> ")
            output_stream.flush()
        line = input_stream.readline()
        if line == "":
            _write(output_stream, _bye(lang))
            return 0
        text = line.strip()
        if not text:
            continue
        if text.startswith("/"):
            command_result = _handle_slash_command(
                text,
                config=config,
                options=options,
                callbacks=callbacks,
                lang=lang,
                provider=provider,
                live=live,
                output_stream=output_stream,
            )
            provider = command_result.get("provider", provider)
            lang = command_result.get("lang", lang)
            live = bool(command_result.get("live", live))
            if command_result.get("exit"):
                _write(output_stream, _bye(lang))
                return 0
            continue

        report = callbacks.ask_auto(text, provider, live, options.ledger_path, lang)
        _write(output_stream, _format_chat_response(report, lang=lang))


def _select_language(
    config: dict[str, object],
    options: InteractiveOptions,
    *,
    input_stream: TextIO,
    output_stream: TextIO,
) -> str:
    if options.lang in {"ja", "en"}:
        config["language"] = options.lang
        save_cli_config(config, options.config_path)
        return options.lang
    language = config.get("language")
    if language in {"ja", "en"}:
        return str(language)
    if not options.script and _is_interactive(input_stream):
        output_stream.write("YonerAI language / 表示言語\n")
        output_stream.write("1) 日本語\n")
        output_stream.write("2) English\n")
        output_stream.write("> ")
        output_stream.flush()
        choice = input_stream.readline().strip().lower()
        language = "en" if choice in {"2", "en", "english"} else "ja"
        config["language"] = language
        save_cli_config(config, options.config_path)
        return str(language)
    return "ja"


def _handle_slash_command(
    text: str,
    *,
    config: dict[str, object],
    options: InteractiveOptions,
    callbacks: InteractiveCallbacks,
    lang: str,
    provider: str,
    live: bool,
    output_stream: TextIO,
) -> dict[str, object]:
    parts = text.split()
    command = _canonical_command(parts[0])
    args = parts[1:]
    if command == "/quit":
        return {"exit": True}
    if command == "/help":
        _write(output_stream, _help(lang))
        return {}
    if command == "/settings":
        _write(output_stream, _format_settings(config, provider=provider, live=live, lang=lang, provider_report=callbacks.providers()))
        return {}
    if command == "/safety":
        _write(output_stream, _format_safety(config, live=live, lang=lang))
        return {}
    if command == "/providers":
        _write(output_stream, _format_providers(callbacks.providers(), lang=lang))
        return {}
    if command == "/runs":
        _write(output_stream, _format_runs(callbacks.runs_list(options.ledger_path, 10, lang), lang=lang))
        return {}
    if command == "/show" and args:
        _write(output_stream, _format_run(callbacks.runs_show(args[0], options.ledger_path, lang), lang=lang))
        return {}
    if command == "/language" and args:
        value = _canonical_value(args[0])
        new_lang = _set_config(config, "language", value, options.config_path)
        _write(output_stream, _changed_message("language", new_lang["language"], lang=str(new_lang["language"])))
        return {"lang": str(new_lang["language"])}
    if command == "/provider" and args:
        value = _canonical_value(args[0])
        new_config = _set_config(config, "provider", value, options.config_path)
        new_provider = str(new_config["provider_preference"])
        _write(output_stream, _changed_message("provider", new_provider, lang=lang))
        return {"provider": new_provider}
    if command == "/approval" and args:
        value = _canonical_value(args[0])
        if value not in APPROVAL_MODES:
            _write(output_stream, _invalid(lang))
            return {}
        new_config = _set_config(config, "approval", value, options.config_path)
        _write(output_stream, _changed_message("approval", new_config["approval_mode"], lang=lang))
        return {}
    if command == "/file-access" and args:
        value = _canonical_value(args[0])
        if value not in FILE_ACCESS_MODES:
            _write(output_stream, _invalid(lang))
            return {}
        new_config = _set_config(config, "file_access", value, options.config_path)
        _write(output_stream, _changed_message("file_access", new_config["file_access_mode"], lang=lang))
        return {}
    _write(output_stream, _unknown(lang))
    return {}


def _set_config(config: dict[str, object], key: str, value: str, config_path: str | None) -> dict[str, object]:
    updated = set_cli_config_value(key, value, config_path)
    config.clear()
    config.update(updated)
    return updated


def _canonical_command(value: str) -> str:
    raw = value.strip()
    return COMMAND_ALIASES.get(raw, COMMAND_ALIASES.get(raw.lower(), raw.lower()))


def _canonical_value(value: str) -> str:
    raw = value.strip()
    return VALUE_ALIASES.get(raw, VALUE_ALIASES.get(raw.lower(), raw))


def _format_chat_response(report: dict[str, Any], *, lang: str) -> str:
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    auto = report.get("auto") if isinstance(report.get("auto"), dict) else {}
    provider = report.get("provider") if isinstance(report.get("provider"), dict) else {}
    response = report.get("response") if isinstance(report.get("response"), dict) else {}
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    output = response.get("output_text") or error.get("message") or "no output"
    if lang == "ja":
        return "\n".join(
            (
                "YonerAI 応答",
                f"  実行ID（run_id）: {_safe(run.get('run_id') or 'なし')}",
                f"  経路（処理方法）: {_route_label(auto.get('route'), lang='ja')}",
                f"  プロバイダー（AI接続先）: {_provider_label(provider.get('provider_id') or auto.get('provider_id'), lang='ja')}",
                f"  承認: {'必要' if auto.get('approval_required') else '不要'}",
                f"  出力: {_safe(output)}",
                "",
            )
        )
    return "\n".join(
        (
            "YonerAI response",
            f"  run_id: {_safe(run.get('run_id') or 'none')}",
            f"  route: {_safe(auto.get('route') or 'unknown')}",
            f"  provider: {_safe(provider.get('provider_id') or auto.get('provider_id') or 'unknown')}",
            f"  approval: {'required' if auto.get('approval_required') else 'not required'}",
            f"  output: {_safe(output)}",
            "",
        )
    )


def _format_settings(
    config: dict[str, object],
    *,
    provider: str,
    live: bool,
    lang: str,
    provider_report: dict[str, Any] | None = None,
) -> str:
    report = build_config_report(config, exists=True)
    values = report["config"]
    local_state = _provider_state(provider_report or {}, "local")
    if lang == "ja":
        return "\n".join(
            (
                "設定",
                f"  表示言語: {_language_label(values['language'] or 'ja', lang='ja')}",
                f"  プロバイダー（AI接続先）: {_provider_label(provider, lang='ja')}",
                f"  ローカルLLM（PC内モデル）: {_state_label(local_state, lang='ja')}",
                f"  承認（危険操作）: {_approval_label(values['approval_mode'], lang='ja')}",
                f"  ファイルアクセス（ファイル読み取り）: {_file_access_label(values['file_access_mode'], lang='ja')}",
                f"  ライブ接続（外部/ローカル実行）: {'オン（明示許可）' if live else 'オフ（初期値）'}",
                f"  ネットワーク（外部通信）: {'オン（明示許可）' if values['network_enabled'] else 'オフ（初期値）'}",
                "  秘密情報（APIキーなど）: 保存しません",
                "  ローカルパス（PC内の場所）: 出力しません",
                "",
            )
        )
    return "\n".join(
            (
                "Settings",
                f"  language: {values['language'] or 'ja'}",
                f"  provider: {provider}",
                f"  local_llm: {local_state}",
                f"  approval: {values['approval_mode']}",
                f"  file_access: {values['file_access_mode']}",
            f"  live_provider: {'on' if live else 'off'}",
            f"  network: {'on' if values['network_enabled'] else 'off'}",
            "  secrets: not stored",
            "  path: not printed",
            "",
        )
    )


def _provider_state(report: dict[str, Any], provider_id: str) -> str:
    providers = report.get("providers") if isinstance(report.get("providers"), list) else []
    for item in providers:
        if isinstance(item, dict) and item.get("provider_id") == provider_id:
            return _safe(item.get("plain_state") or item.get("setup_status") or "unknown")
    return "unknown"


def _format_safety(config: dict[str, object], *, live: bool, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    if lang == "ja":
        network_selected = "provider" if live else "off"
        file_selected = str(values["file_access_mode"])
        tools_selected = str(values["tools_mode"])
        return "\n".join(
            (
                "安全設定",
                "",
                "ネットワーク（外部通信）",
                f"{_selector('off', network_selected)} オフ（初期値）",
                f"{_selector('provider', network_selected)} プロバイダーだけ許可（明示した時だけ）",
                f"{_selector('search', network_selected)} 検索を許可（未実装）",
                "",
                "ファイルアクセス（ファイル読み取り）",
                f"{_selector('workspace_only', file_selected)} ワークスペース内のみ",
                f"{_selector('disabled', file_selected)} 無効",
                f"{_selector('ask', file_selected)} 毎回確認（未実装）",
                "",
                "ツール（操作機能）",
                f"{_selector('dry_run', tools_selected)} ドライランのみ（計画だけ）",
                f"{_selector('diagnostics', tools_selected)} 安全診断のみ許可（限定）",
                f"{_selector('disabled', tools_selected)} 無効",
                "",
                f"承認（危険操作）: {_approval_label(values['approval_mode'], lang='ja')}",
                "シェル実行（PC操作）: 任意コマンドは無効",
                "クラウド候補: private/local fileは送りません",
                "",
            )
        )
    return "\n".join(
        (
            "Safety",
            f"  network: {'explicitly enabled' if values['network_enabled'] else 'off'}",
            f"  live provider: {'explicitly enabled' if live else 'off'}",
            f"  tools: {values['tools_mode']}",
            f"  file access: {values['file_access_mode']}",
            f"  approval: {values['approval_mode']}",
            "  shell: arbitrary shell disabled",
            "  cloud: private/local files never sent to cloud candidates",
            "",
        )
    )


def _format_providers(report: dict[str, Any], *, lang: str) -> str:
    providers = report.get("providers") if isinstance(report.get("providers"), list) else []
    title = "プロバイダー" if lang == "ja" else "Providers"
    lines = [title]
    for item in providers:
        if not isinstance(item, dict):
            continue
        if lang == "ja":
            lines.append(
                f"  {_provider_label(item.get('provider_id'), lang='ja')}: "
                f"{_state_label(item.get('plain_state') or item.get('setup_status'), lang='ja')} "
                f"（設定={_yes_no(item.get('configured'), lang='ja')}）"
            )
        else:
            lines.append(
                f"  {item.get('provider_id')}: {item.get('plain_state') or item.get('setup_status')} "
                f"(configured={item.get('configured')})"
            )
    lines.append("  キー（秘密情報）: 表示しません" if lang == "ja" else "  keys: redacted / not printed")
    lines.append("")
    return "\n".join(_safe(line) for line in lines)


def _format_runs(report: dict[str, Any], *, lang: str) -> str:
    runs = report.get("runs") if isinstance(report.get("runs"), list) else []
    if not runs:
        return "実行履歴: まだありません\n" if lang == "ja" else "Runs: none yet\n"
    title = "実行履歴" if lang == "ja" else "Runs"
    lines = [title]
    for run in runs:
        if isinstance(run, dict):
            if lang == "ja":
                lines.append(
                    f"  実行ID（run_id）={run.get('run_id')}: {_run_status_label(run.get('status'), lang='ja')} {run.get('task_summary')}"
                )
            else:
                lines.append(f"  {run.get('run_id')}: {run.get('status')} {run.get('task_summary')}")
    lines.append("")
    return "\n".join(_safe(line) for line in lines)


def _format_run(report: dict[str, Any], *, lang: str) -> str:
    if not report.get("ok"):
        return ("実行が見つかりません\n" if lang == "ja" else "Run not found\n")
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    return "\n".join(
        (
            "実行" if lang == "ja" else "Run",
            (
                f"  実行ID（run_id）: {_safe(run.get('run_id') or 'なし')}"
                if lang == "ja"
                else f"  run_id: {_safe(run.get('run_id') or 'none')}"
            ),
            (
                f"  状態: {_run_status_label(run.get('status'), lang='ja')}"
                if lang == "ja"
                else f"  status: {_safe(run.get('status') or 'unknown')}"
            ),
            (
                f"  プロバイダー（AI接続先）: {_provider_label((run.get('provider_decision') or {}).get('provider_id') if isinstance(run.get('provider_decision'), dict) else 'unknown', lang='ja')}"
                if lang == "ja"
                else f"  provider: {_safe((run.get('provider_decision') or {}).get('provider_id') if isinstance(run.get('provider_decision'), dict) else 'unknown')}"
            ),
            "",
        )
    )


def _welcome(lang: str, *, provider: str, live: bool, config_exists: bool) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "YonerAI Interactive CLI v0.3 alpha",
                "日本語モード。/ヘルプ でコマンドを表示します。",
                f"プロバイダー（AI接続先）={_provider_label(provider, lang='ja')} ライブ接続={'オン' if live else 'オフ'} 設定={'既存' if config_exists else '初期値'}",
                "安全: ネットワークは初期値オフ / ツールはドライラン / ファイルはワークスペース内のみ",
                "",
            )
        )
    return "\n".join(
        (
            "YonerAI Interactive CLI v0.3 alpha",
            "English mode. Type /help for commands.",
            f"provider={provider} live={'on' if live else 'off'} config={'found' if config_exists else 'created/default'}",
            "Safety: network off / tools dry-run / workspace file only / live providers off by default",
            "",
        )
    )


def _help(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "コマンド",
                "  /設定                 設定を見る",
                "  /提供元               プロバイダー（AI接続先）を見る",
                "  /安全                 安全境界を見る",
                "  /履歴                 実行履歴を見る",
                "  /表示 <実行ID>        1件の実行を見る",
                "  /言語 日本語|英語     表示言語を変更",
                "  /提供元選択 自動|モック|ローカル|オープンAI互換|アンソロピック|ジェミニ",
                "  /承認 確認|拒否       危険操作の扱いを変更",
                "  /ファイル ワークスペース内のみ|無効",
                "  /終了                 終了",
                "",
            )
        )
    return "\n".join(
        (
            "Commands",
            "  /settings        Show settings",
            "  /providers       Show provider status",
            "  /safety          Show safety boundaries",
            "  /runs            Show run history",
            "  /show <run_id>   Show one run",
            "  /language ja|en  Change language",
            "  /provider auto|mock|local|openai-compatible|anthropic|gemini",
            "  /quit            Exit",
            "",
        )
    )


def _non_tty_fallback(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "YonerAI Interactive CLI",
                "この入力はTTYではないため、対話画面は起動しません。",
                "対話で使う: yonerai chat",
                "スクリプトで使う: yonerai chat --script",
                "確認する: yonerai providers --pretty --lang ja",
                "",
            )
        )
    return "\n".join(
        (
            "YonerAI Interactive CLI",
            "stdin is not a TTY, so the interactive screen did not start.",
            "Interactive: yonerai chat",
            "Scripted: yonerai chat --script",
            "Check setup: yonerai providers --pretty --lang en",
            "",
        )
    )


def _changed_message(key: str, value: object, *, lang: str) -> str:
    if lang == "ja":
        return f"設定を変更しました: {_setting_label(key, lang='ja')}={_value_label(value, lang='ja')}\n"
    return f"Changed setting: {key}={value}\n"


def _invalid(lang: str) -> str:
    return "値が不正です\n" if lang == "ja" else "Invalid value\n"


def _unknown(lang: str) -> str:
    return "不明なコマンドです。/help を見てください\n" if lang == "ja" else "Unknown command. Type /help\n"


def _bye(lang: str) -> str:
    return "終了します\n" if lang == "ja" else "Goodbye\n"


def _safe(value: object) -> str:
    text = " ".join(str(value).split())
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    for pattern in PATH_PATTERNS:
        text = pattern.sub("[LOCAL_PATH]", text)
    return text[:500]


def _selector(option: str, selected: str) -> str:
    return ">" if option == selected else " "


def _language_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {"ja": "日本語", "en": "英語"}.get(str(value), _safe(value))


def _provider_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "unknown")
    labels = {
        "auto": "自動（安全に選択）",
        "mock": "モック（テスト用）",
        "local": "ローカル（PC内モデル）",
        "openai-compatible": "オープンAI互換（外部API）",
        "anthropic": "アンソロピック（外部API）",
        "gemini": "ジェミニ（外部API）",
        "unknown": "不明",
        None: "不明",
    }
    return labels.get(value, _safe(value or "不明"))


def _route_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "unknown")
    labels = {
        "instant_local": "ローカルで即時実行",
        "local_llm": "ローカルLLM（PC内モデル）",
        "hybrid_node": "ハイブリッド（ローカル優先）",
        "cloud_contract_candidate": "クラウド候補（local-dev stub）",
        "deny": "拒否",
    }
    return labels.get(value, _safe(value or "不明"))


def _approval_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {"prompt": "毎回確認", "deny": "拒否"}.get(str(value), _safe(value))


def _file_access_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {"workspace_only": "ワークスペース内のみ", "disabled": "無効"}.get(str(value), _safe(value))


def _run_status_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {"completed": "完了", "failed": "失敗", "in_progress": "実行中"}.get(str(value), _safe(value or "不明"))


def _state_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    labels = {
        "ready_now": "今すぐ利用可能",
        "ready_for_explicit_local_live": "明示許可でローカル利用可能",
        "configured_for_explicit_live": "明示許可で利用可能",
        "not_configured": "未設定",
        "missing_configuration": "設定不足",
        "disabled": "無効",
        "blocked_by_loopback_policy": "loopback以外のため拒否",
        "invalid_configuration": "設定が不正",
        "unknown": "不明",
    }
    return labels.get(str(value), _safe(value))


def _setting_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    labels = {
        "language": "表示言語",
        "provider": "プロバイダー（AI接続先）",
        "approval": "承認（危険操作）",
        "file_access": "ファイルアクセス（ファイル読み取り）",
    }
    return labels.get(str(value), _safe(value))


def _value_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    if value in {"ja", "en"}:
        return _language_label(value, lang=lang)
    if value in PROVIDER_PREFERENCES:
        return _provider_label(value, lang=lang)
    if value in APPROVAL_MODES:
        return _approval_label(value, lang=lang)
    if value in FILE_ACCESS_MODES:
        return _file_access_label(value, lang=lang)
    return _safe(value)


def _yes_no(value: object, *, lang: str) -> str:
    if lang != "ja":
        return "true" if value else "false"
    return "はい" if value else "いいえ"


def _write(stream: TextIO, text: str) -> None:
    stream.write(text if text.endswith("\n") else text + "\n")
    stream.flush()


def _is_interactive(stream: TextIO) -> bool:
    return bool(getattr(stream, "isatty", lambda: False)())


def _config_exists(path: str | None) -> bool:
    try:
        config_path = default_config_path() if path is None else Path(path).expanduser()
        return config_path.exists()
    except Exception:
        return False


__all__ = [
    "INTERACTIVE_SCHEMA_VERSION",
    "InteractiveCallbacks",
    "InteractiveOptions",
    "run_interactive_cli",
]
