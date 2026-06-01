from __future__ import annotations

import re
import sys
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TextIO

from yonerai_cli.auth_policy import build_google_auth_status, build_privacy_status
from yonerai_cli.config import (
    AGENT_MODES,
    APPROVAL_MODES,
    ConfigError,
    FILE_ACCESS_MODES,
    MEMORY_DEFAULT_SCOPES,
    MODEL_RE,
    PROVIDER_PREFERENCES,
    build_config_report,
    default_config_path,
    load_cli_config,
    save_cli_config,
    set_cli_config_value,
)
from yonerai_cli.tui import (
    prompt_line,
    prompt_toolkit_available,
    render_panel,
    run_with_status,
    slash_command_summary,
    tui_capability_report,
)


INTERACTIVE_SCHEMA_VERSION = "yonerai-interactive-cli/v0.8"
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
CONTROL_CHARACTER_TRANSLATION: dict[int, str] = {codepoint: f"\\x{codepoint:02x}" for codepoint in range(32)}
CONTROL_CHARACTER_TRANSLATION[0x7F] = "\\x7f"
for codepoint in range(0x80, 0xA0):
    CONTROL_CHARACTER_TRANSLATION[codepoint] = f"\\x{codepoint:02x}"

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
    "/設定": "/settings",
    "/settings": "/settings",
    "/モデル": "/models",
    "/model": "/models",
    "/models": "/models",
    "/安全": "/safety",
    "/safety": "/safety",
    "/提供元": "/providers",
    "/プロバイダー": "/providers",
    "/providers": "/providers",
    "/履歴": "/runs",
    "/runs": "/runs",
    "/タスク": "/tasks",
    "/tasks": "/tasks",
    "/表示": "/show",
    "/show": "/show",
    "/エージェント": "/agents",
    "/agents": "/agents",
    "/agent": "/agents",
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
    "/同期": "/sync",
    "/sync": "/sync",
    "/プライバシー": "/privacy",
    "/privacy": "/privacy",
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
}
VALUE_ALIASES = {
    "日本語": "ja",
    "英語": "en",
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
    "安全": "safety",
    "safety": "safety",
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


@dataclass(frozen=True)
class InteractiveCallbacks:
    providers: Callable[[], dict[str, Any]]
    ask_auto: Callable[..., dict[str, Any]]
    runs_list: Callable[[str | None, int, str], dict[str, Any]]
    runs_show: Callable[[str, str | None, str], dict[str, Any]]
    update_check: Callable[[str | None, str], dict[str, Any]] | None = None
    evolve_status: Callable[[str], dict[str, Any]] | None = None
    sync_status: Callable[[str], dict[str, Any]] | None = None
    memory_status: Callable[[str], dict[str, Any]] | None = None
    memory_action: Callable[[str, list[str], str, str | None], dict[str, Any]] | None = None


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
    ledger_path = _resolve_ledger_path(config, options)

    if not options.script and not _is_interactive(input_stream):
        _write(output_stream, _non_tty_fallback(lang))
        return 0

    last_report: dict[str, Any] | None = None
    use_tui_prompt = _can_use_prompt_toolkit(options, input_stream=input_stream, output_stream=output_stream)
    welcome = _welcome(
        lang,
        provider=provider,
        live=_effective_live(live, config),
        config_exists=config_exists,
        config=config,
        ledger_path=ledger_path,
    )
    if not (use_tui_prompt and render_panel(welcome, title="YonerAI", stream=output_stream, color=options.color)):
        _write(output_stream, welcome)
    update_notice_report = _read_update_notice_report(config, callbacks, lang)
    startup_update_notice = _format_update_notice(update_notice_report, lang, phase="startup")
    if startup_update_notice:
        _write(output_stream, startup_update_notice)

    while True:
        if use_tui_prompt:
            line = prompt_line(
                lang=lang,
                bottom_toolbar=_bottom_toolbar(lang, provider=provider, live=_effective_live(live, config), config=config),
            )
        elif _is_interactive(input_stream):
            output_stream.write("yonerai> ")
            output_stream.flush()
            line = input_stream.readline()
        else:
            line = input_stream.readline()
        if line == "":
            if use_tui_prompt:
                continue
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
                ledger_path=ledger_path,
                last_report=last_report,
                output_stream=output_stream,
            )
            provider = str(command_result.get("provider", provider))
            lang = str(command_result.get("lang", lang))
            live = bool(command_result.get("live", live))
            ledger_path = command_result.get("ledger_path", ledger_path)  # type: ignore[assignment]
            if command_result.get("update_notice_changed"):
                update_notice_report = _read_update_notice_report(config, callbacks, lang)
            if command_result.get("exit"):
                _write(output_stream, _bye(lang))
                return 0
            continue
        agent_preview = _format_agent_mention_preview(text, config=config, lang=lang)
        if agent_preview is not None:
            _write(output_stream, agent_preview)
            continue

        effective_live = _effective_live(live, config)
        memory_store_path = _resolve_memory_store_path(config)
        if use_tui_prompt:
            report = run_with_status(
                "考え中..." if lang == "ja" else "Thinking...",
                lambda: _invoke_ask_auto(callbacks.ask_auto, text, provider, effective_live, ledger_path, lang, memory_store_path),
                stream=output_stream,
                color=options.color,
            )
        else:
            report = _invoke_ask_auto(callbacks.ask_auto, text, provider, effective_live, ledger_path, lang, memory_store_path)
        last_report = report
        _write(output_stream, _format_chat_response(report, lang=lang))
        report_for_notice = update_notice_report if config.get("update_notice_enabled") is True else None
        after_task_notice = _format_update_notice(report_for_notice, lang, phase="after_task")
        if after_task_notice:
            _write(output_stream, after_task_notice)


def _invoke_ask_auto(
    callback: Callable[..., dict[str, Any]],
    task: str,
    provider: str,
    live: bool,
    ledger_path: str | None,
    lang: str,
    memory_store_path: str | None,
) -> dict[str, Any]:
    if _callback_accepts_memory_store(callback):
        return callback(task, provider, live, ledger_path, lang, memory_store_path)
    return callback(task, provider, live, ledger_path, lang)


def _callback_accepts_memory_store(callback: Callable[..., dict[str, Any]]) -> bool:
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return False
    parameters = tuple(signature.parameters.values())
    if any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters):
        return True
    positional = [
        parameter
        for parameter in parameters
        if parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
    ]
    return len(positional) >= 6


def _can_use_prompt_toolkit(options: InteractiveOptions, *, input_stream: TextIO, output_stream: TextIO) -> bool:
    if options.script or options.color == "never":
        return False
    if input_stream is not sys.stdin or output_stream is not sys.stdout:
        return False
    return _is_interactive(input_stream) and _is_interactive(output_stream) and prompt_toolkit_available()


def _effective_live(live: bool, config: dict[str, object]) -> bool:
    return bool(live and config.get("network_enabled") is not False)


def _bottom_toolbar(lang: str, *, provider: str, live: bool, config: dict[str, object]) -> str:
    model = _safe(config.get("model_preference") or "auto")
    agent_mode = _agent_mode_label(config.get("agent_mode") or "plan_readonly", lang=lang)
    if lang == "ja":
        live_text = "ライブ接続オン" if live else "ライブ接続オフ"
        ledger = "履歴オン" if config.get("ledger_enabled") is True else "履歴オフ"
        return f"Tab/矢印で候補を選択 | 提供元={_provider_label(provider, lang='ja')} | モデル={model} | モード={agent_mode} | {live_text} | {ledger}"
    return f"Tab/arrows complete | provider={provider} | model={model} | mode={agent_mode} | live={'on' if live else 'off'} | ledger={'on' if config.get('ledger_enabled') else 'off'}"


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
    ledger_path: str | None,
    last_report: dict[str, Any] | None,
    output_stream: TextIO,
) -> dict[str, object]:
    parts = text.split()
    if parts[0] == "/":
        _write(output_stream, slash_command_summary(lang))
        return {}
    command = _canonical_command(parts[0])
    args = parts[1:]
    if command == "/quit":
        return {"exit": True}
    if command == "/status":
        _write(
            output_stream,
            _welcome(
                lang,
                provider=provider,
                live=_effective_live(live, config),
                config_exists=_config_exists(options.config_path),
                config=config,
                ledger_path=ledger_path,
            ),
        )
        return {}
    if command == "/help":
        _write(output_stream, _help(lang))
        return {}
    if command == "/palette":
        _write(output_stream, _format_command_palette(lang))
        return {}
    if command == "/settings":
        provider_report = callbacks.providers()
        category = _settings_category_from_args(args)
        if category is None:
            _write(
                output_stream,
                _format_settings(
                    config,
                    provider=provider,
                    live=live,
                    lang=lang,
                    provider_report=provider_report,
                ),
            )
            return {}
        if category == "memory":
            if len(args) > 1:
                return _handle_memory_setting(args[1:], config=config, options=options, lang=lang, output_stream=output_stream)
            status_report = callbacks.memory_status(lang) if callbacks.memory_status is not None else None
            _write(output_stream, _format_settings_memory(config, status_report, lang=lang))
            return {}
        if category == "update" and callbacks.update_check is not None:
            _write(output_stream, _format_settings_update(config, lang=lang))
            return {}
        _write(
            output_stream,
            _format_settings_category(
                category,
                config,
                provider=provider,
                live=live,
                lang=lang,
                provider_report=provider_report,
            ),
        )
        return {}
    if command == "/models":
        if args:
            value = _canonical_value(args[0])
            if not MODEL_RE.fullmatch(value) or "://" in value or "\\" in value:
                _write(output_stream, _invalid(lang))
                return {}
            success, result = _set_and_report("model", value, config, options, lang, output_stream)
            if not success:
                return {}
            return result
        _write(output_stream, _format_models(config, callbacks.providers(), lang=lang))
        return {}
    if command == "/safety":
        _write(output_stream, _format_safety(config, live=live, lang=lang))
        return {}
    if command == "/providers":
        _write(output_stream, _format_providers(callbacks.providers(), lang=lang))
        return {}
    if command == "/runs":
        _write(output_stream, _format_runs(callbacks.runs_list(ledger_path, 10, lang), lang=lang))
        return {}
    if command == "/tasks":
        _write(output_stream, _format_tasks(last_report, callbacks.runs_list(ledger_path, 5, lang), lang=lang))
        return {}
    if command == "/show" and args:
        _write(output_stream, _format_run(callbacks.runs_show(args[0], ledger_path, lang), lang=lang))
        return {}
    if command == "/agents":
        _write(output_stream, _format_agents(last_report, lang=lang))
        return {}
    if command == "/mode":
        if args:
            value = _canonical_agent_mode_value(args[0])
            if value not in AGENT_MODES:
                _write(output_stream, _invalid(lang))
                return {}
            success, result = _set_and_report("agent_mode", value, config, options, lang, output_stream)
            if not success:
                return {}
            _write(output_stream, _format_mode_state(config, lang=lang))
            return result
        _write(output_stream, _format_mode_state(config, lang=lang))
        return {}
    if command == "/plan":
        success, result = _set_and_report("agent_mode", "plan_readonly", config, options, lang, output_stream)
        if not success:
            return {}
        _write(output_stream, _format_mode_state(config, lang=lang))
        if args:
            preview = _format_agent_mention_preview("@planner " + " ".join(args), config=config, lang=lang)
            if preview is not None:
                _write(output_stream, preview)
        return result
    if command == "/review":
        success, result = _set_and_report("agent_mode", "review", config, options, lang, output_stream)
        if not success:
            return {}
        _write(output_stream, _format_mode_state(config, lang=lang))
        if args:
            preview = _format_agent_mention_preview("@reviewer " + " ".join(args), config=config, lang=lang)
            if preview is not None:
                _write(output_stream, preview)
        return result
    if command == "/permissions":
        if args:
            return _handle_permission_profile(args, config=config, options=options, lang=lang, output_stream=output_stream)
        _write(output_stream, _format_permissions(config, live=live, lang=lang))
        return {}
    if command == "/auth":
        _write(output_stream, _format_auth_status(config, lang=lang))
        return {}
    if command == "/privacy":
        _write(output_stream, _format_privacy_status(config, lang=lang))
        return {}
    if command == "/memory":
        if callbacks.memory_status is None:
            _write(output_stream, _format_memory_unavailable(lang))
            return {}
        if args:
            _write(
                output_stream,
                _handle_memory_action(
                    args,
                    callbacks=callbacks,
                    config=config,
                    lang=lang,
                ),
            )
            return {}
        _write(output_stream, _format_memory_status(callbacks.memory_status(lang), lang=lang))
        return {}
    if command == "/sync":
        if callbacks.sync_status is None:
            _write(output_stream, _format_sync_unavailable(lang))
            return {}
        _write(output_stream, _format_sync_status(callbacks.sync_status(lang), lang=lang))
        return {}
    if command == "/evolve":
        if callbacks.evolve_status is None:
            _write(output_stream, _format_evolve_unavailable(lang))
            return {}
        _write(output_stream, _format_evolve_status(callbacks.evolve_status(lang), lang=lang))
        return {}
    if command == "/local-llm":
        _write(output_stream, _format_local_llm_setup(callbacks.providers(), lang=lang))
        return {}
    if command == "/update":
        if callbacks.update_check is None:
            _write(output_stream, _update_unavailable(lang))
            return {}
        try:
            report = callbacks.update_check(_joined_arg_after_command(text, parts[0]), lang)
        except Exception as exc:
            _write(output_stream, _format_update_error(exc, lang=lang))
            return {}
        _write(output_stream, _format_update_check(report, lang=lang))
        return {}
    if command == "/select" and args:
        return _handle_numbered_selection(
            args,
            config=config,
            options=options,
            lang=lang,
            provider=provider,
            live=live,
            output_stream=output_stream,
        )
    if command == "/language" and args:
        value = _canonical_value(args[0])
        if value not in {"ja", "en"}:
            _write(output_stream, _invalid(lang))
            return {}
        try:
            new_config = _set_config(config, "language", value, options.config_path)
        except ConfigError as exc:
            _write(output_stream, _config_error(lang, exc))
            return {}
        _write(output_stream, _changed_message("language", new_config["language"], lang=str(new_config["language"])))
        return {"lang": str(new_config["language"])}
    if command == "/provider" and args:
        value = _canonical_value(args[0])
        if value not in PROVIDER_PREFERENCES:
            _write(output_stream, _invalid(lang))
            return {}
        success, result = _set_and_report("provider", value, config, options, lang, output_stream)
        return result if success else {}
    if command == "/approval" and args:
        value = _canonical_value(args[0])
        if value not in APPROVAL_MODES:
            _write(output_stream, _invalid(lang))
            return {}
        success, result = _set_and_report("approval", value, config, options, lang, output_stream)
        if not success:
            return {}
        return result
    if command == "/file-access" and args:
        value = _canonical_value(args[0])
        if value not in FILE_ACCESS_MODES:
            _write(output_stream, _invalid(lang))
            return {}
        success, result = _set_and_report("file_access", value, config, options, lang, output_stream)
        if not success:
            return {}
        return result
    if command == "/ledger" and args:
        value = _canonical_value(args[0])
        if value not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
            _write(output_stream, _invalid(lang))
            return {}
        success, result = _set_and_report("ledger", value, config, options, lang, output_stream)
        if not success:
            return {}
        result["ledger_path"] = _resolve_ledger_path(config, options)
        return result
    if command == "/live-provider" and args:
        value = _canonical_value(args[0])
        if value not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
            _write(output_stream, _invalid(lang))
            return {}
        success, result = _set_and_report("live_provider", value, config, options, lang, output_stream)
        if not success:
            return {}
        result["live"] = bool(config["live_provider_enabled"])
        return result
    if command == "/network" and args:
        value = _canonical_value(args[0])
        if value not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
            _write(output_stream, _invalid(lang))
            return {}
        success, result = _set_and_report("network", value, config, options, lang, output_stream)
        if not success:
            return {}
        return result
    if command == "/update-notice" and args:
        value = _canonical_value(args[0])
        if value not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
            _write(output_stream, _invalid(lang))
            return {}
        success, result = _set_and_report("update_notice", value, config, options, lang, output_stream)
        if not success:
            return {}
        result["update_notice_changed"] = True
        return result
    _write(output_stream, _unknown(lang))
    return {}


def _set_and_report(
    key: str,
    value: str,
    config: dict[str, object],
    options: InteractiveOptions,
    lang: str,
    output_stream: TextIO,
) -> tuple[bool, dict[str, object]]:
    try:
        new_config = _set_config(config, key, value, options.config_path)
    except ConfigError as exc:
        _write(output_stream, _config_error(lang, exc))
        return False, {}
    setting_key = {
        "provider": "provider_preference",
        "model": "model_preference",
        "agent_mode": "agent_mode",
        "approval": "approval_mode",
        "file_access": "file_access_mode",
        "ledger": "ledger_enabled",
        "live_provider": "live_provider_enabled",
        "network": "network_enabled",
        "update_notice": "update_notice_enabled",
    }.get(key, key)
    _write(output_stream, _changed_message(key, new_config[setting_key], lang=lang))
    if key == "provider":
        return True, {"provider": str(new_config["provider_preference"])}
    return True, {}


def _set_config(config: dict[str, object], key: str, value: str, config_path: str | None) -> dict[str, object]:
    updated = set_cli_config_value(key, value, config_path)
    config.clear()
    config.update(updated)
    return updated


def _set_config_values(
    config: dict[str, object],
    values: dict[str, object],
    config_path: str | None,
) -> dict[str, object]:
    updated = load_cli_config(config_path)
    updated.update(values)
    saved = save_cli_config(updated, config_path)
    config.clear()
    config.update(saved)
    return saved


def _handle_memory_setting(
    args: list[str],
    *,
    config: dict[str, object],
    options: InteractiveOptions,
    lang: str,
    output_stream: TextIO,
) -> dict[str, object]:
    if not args:
        return {}
    head = _canonical_value(args[0])
    value = _canonical_value(args[1]) if len(args) > 1 else None
    key: str | None = None
    selected: str | None = None
    if head in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
        key = "memory"
        selected = head
    elif head in {"scope", "default_scope", "default-scope"} and value is not None:
        key = "memory_scope"
        selected = value
    elif head in {"cloud-preview", "cloud_preview", "cloud-to-local", "cloud_to_local"} and value is not None:
        key = "memory_cloud_preview"
        selected = value
    elif head in {"self-evolution", "self_evolution", "signal", "signals"} and value is not None:
        key = "memory_self_evolution_signal"
        selected = value
    elif head in {"local-to-cloud", "local_to_cloud", "approval"}:
        _write(
            output_stream,
            (
                "local -> cloud 記憶同期は public runtime では承認必須のままです。無効化できません。\n"
                if lang == "ja"
                else "local-to-cloud memory sync approval is mandatory in the public runtime and cannot be disabled.\n"
            ),
        )
        return {}
    if key is None or selected is None:
        _write(output_stream, _settings_memory_help(lang))
        return {}
    try:
        new_config = _set_config(config, key, selected, options.config_path)
    except ConfigError as exc:
        _write(output_stream, _config_error(lang, exc))
        return {}
    normalized = {
        "memory": "memory_enabled",
        "memory_scope": "memory_default_scope",
        "memory_cloud_preview": "memory_cloud_to_local_preview_enabled",
        "memory_self_evolution_signal": "memory_self_evolution_signal_enabled",
    }[key]
    _write(output_stream, _changed_message(normalized, new_config[normalized], lang=lang))
    return {}


def _handle_memory_action(
    args: list[str],
    *,
    callbacks: InteractiveCallbacks,
    config: dict[str, object],
    lang: str,
) -> str:
    if callbacks.memory_action is None:
        return _format_memory_unavailable(lang)
    action = _canonical_memory_action(args[0])
    remaining = args[1:]
    default_scope = str(config.get("memory_default_scope") or "local_private")
    if action == "status":
        return _format_memory_status(callbacks.memory_status(lang) if callbacks.memory_status else {}, lang=lang)
    if action == "add":
        if config.get("memory_enabled") is not True:
            return _memory_write_disabled(lang)
        if not remaining:
            return _memory_action_help(lang)
        report = callbacks.memory_action("add", [" ".join(remaining)], lang, default_scope)
        return _format_memory_action_report(report, lang=lang)
    if action == "list":
        report = callbacks.memory_action("list", remaining, lang, default_scope)
        return _format_memory_action_report(report, lang=lang)
    if action == "forget":
        if not remaining:
            return _memory_action_help(lang)
        report = callbacks.memory_action("forget", [remaining[0]], lang, default_scope)
        return _format_memory_action_report(report, lang=lang)
    if action == "sync":
        sync_args = list(remaining)
        if sync_args and _canonical_memory_action(sync_args[0]) == "preview":
            sync_args = sync_args[1:]
        direction = sync_args[0] if sync_args else "cloud-to-local"
        if _cloud_to_local_memory_preview_disabled(direction, config):
            return _memory_cloud_preview_disabled(lang)
        report = callbacks.memory_action("sync-preview", [direction], lang, default_scope)
        return _format_memory_action_report(report, lang=lang)
    if action == "preview":
        direction = remaining[0] if remaining else "cloud-to-local"
        if _cloud_to_local_memory_preview_disabled(direction, config):
            return _memory_cloud_preview_disabled(lang)
        report = callbacks.memory_action("sync-preview", [direction], lang, default_scope)
        return _format_memory_action_report(report, lang=lang)
    return _memory_action_help(lang)


def _canonical_memory_action(value: str) -> str:
    raw = value.strip()
    normalized = raw.lower()
    aliases = {
        "追加": "add",
        "add": "add",
        "一覧": "list",
        "list": "list",
        "ls": "list",
        "忘れる": "forget",
        "forget": "forget",
        "remove": "forget",
        "同期": "sync",
        "sync": "sync",
        "preview": "preview",
        "プレビュー": "preview",
        "status": "status",
    }
    return aliases.get(raw, aliases.get(normalized, normalized))


def _cloud_to_local_memory_preview_disabled(direction: str, config: dict[str, object]) -> bool:
    normalized = str(direction or "").strip().lower().replace("_", "-")
    return normalized == "cloud-to-local" and config.get("memory_cloud_to_local_preview_enabled") is not True


def _handle_numbered_selection(
    args: list[str],
    *,
    config: dict[str, object],
    options: InteractiveOptions,
    lang: str,
    provider: str,
    live: bool,
    output_stream: TextIO,
) -> dict[str, object]:
    number = args[0]
    value = _canonical_value(args[1]) if len(args) > 1 else None
    try:
        if number == "1" and value in {"ja", "en"}:
            new_config = _set_config(config, "language", value, options.config_path)
            _write(output_stream, _changed_message("language", new_config["language"], lang=str(new_config["language"])))
            return {"lang": str(new_config["language"])}
        if number == "2" and value in PROVIDER_PREFERENCES:
            new_config = _set_config(config, "provider", value, options.config_path)
            new_provider = str(new_config["provider_preference"])
            _write(output_stream, _changed_message("provider", new_provider, lang=lang))
            return {"provider": new_provider}
        if number == "3" and value in APPROVAL_MODES:
            new_config = _set_config(config, "approval", value, options.config_path)
            _write(output_stream, _changed_message("approval", new_config["approval_mode"], lang=lang))
            return {}
        if number == "4" and value in FILE_ACCESS_MODES:
            new_config = _set_config(config, "file_access", value, options.config_path)
            _write(output_stream, _changed_message("file_access", new_config["file_access_mode"], lang=lang))
            return {}
        if number == "5":
            selected = value or ("off" if config.get("ledger_enabled") is True else "on")
            new_config = _set_config(config, "ledger", selected, options.config_path)
            _write(output_stream, _changed_message("ledger", new_config["ledger_enabled"], lang=lang))
            return {"ledger_path": _resolve_ledger_path(new_config, options)}
        if number == "6":
            selected = value or ("off" if config.get("live_provider_enabled") is True else "on")
            new_config = _set_config(config, "live_provider", selected, options.config_path)
            new_live = bool(new_config["live_provider_enabled"])
            _write(output_stream, _changed_message("live_provider", new_live, lang=lang))
            return {"live": new_live}
        if number == "7":
            selected = value or ("off" if config.get("network_enabled") is True else "on")
            new_config = _set_config(config, "network", selected, options.config_path)
            _write(output_stream, _changed_message("network", new_config["network_enabled"], lang=lang))
            return {}
        if number == "8" and value and MODEL_RE.fullmatch(value) and "://" not in value and "\\" not in value:
            new_config = _set_config(config, "model", value, options.config_path)
            _write(output_stream, _changed_message("model", new_config["model_preference"], lang=lang))
            return {}
        if number == "9":
            selected = value or ("off" if config.get("update_notice_enabled") is True else "on")
            new_config = _set_config(config, "update_notice", selected, options.config_path)
            _write(output_stream, _changed_message("update_notice", new_config["update_notice_enabled"], lang=lang))
            return {"update_notice_changed": True}
        if number == "10":
            normalized_value = _canonical_agent_mode_value(args[1]) if len(args) > 1 else None
            if normalized_value in AGENT_MODES:
                new_config = _set_config(config, "agent_mode", normalized_value, options.config_path)
                _write(output_stream, _changed_message("agent_mode", new_config["agent_mode"], lang=lang))
                return {}
            _write(output_stream, _settings_selection_help(lang))
            return {}
    except ConfigError as exc:
        _write(output_stream, _config_error(lang, exc))
        return {}
    _write(output_stream, _settings_selection_help(lang))
    return {"provider": provider, "live": live}


def _handle_permission_profile(
    args: list[str],
    *,
    config: dict[str, object],
    options: InteractiveOptions,
    lang: str,
    output_stream: TextIO,
) -> dict[str, object]:
    profile = _canonical_value(args[0]) if args else ""
    force_live_off = False
    try:
        if profile == "read_only":
            new_config = _set_config_values(
                config,
                {
                    "agent_mode": "plan_readonly",
                    "approval_mode": "deny",
                    "live_provider_enabled": False,
                    "network_enabled": False,
                },
                options.config_path,
            )
            force_live_off = True
        elif profile == "auto_safe":
            new_config = _set_config_values(
                config,
                {"agent_mode": "build_safe", "approval_mode": "prompt"},
                options.config_path,
            )
        elif profile == "ask_before_risky":
            new_config = _set_config_values(
                config,
                {"agent_mode": "review", "approval_mode": "prompt"},
                options.config_path,
            )
        elif profile == "dry_run_only":
            new_config = _set_config_values(
                config,
                {
                    "agent_mode": "plan_readonly",
                    "approval_mode": "prompt",
                    "live_provider_enabled": False,
                    "network_enabled": False,
                },
                options.config_path,
            )
            force_live_off = True
        else:
            _write(output_stream, _invalid(lang))
            return {}
    except ConfigError as exc:
        _write(output_stream, _config_error(lang, exc))
        return {}
    config.clear()
    config.update(new_config)
    _write(output_stream, _changed_message("permissions", profile, lang=lang))
    _write(output_stream, _format_permissions(config, live=bool(config.get("live_provider_enabled")), lang=lang))
    return {"live": False} if force_live_off else {}


def _resolve_ledger_path(config: dict[str, object], options: InteractiveOptions) -> str | None:
    if options.ledger_path:
        return options.ledger_path
    if config.get("ledger_enabled") is not True:
        return None
    return str(_default_ledger_path(options.config_path))


def _resolve_memory_store_path(config: dict[str, object]) -> str | None:
    if config.get("memory_enabled") is not True:
        return None
    return "__default__"


def _default_ledger_path(config_path: str | None) -> Path:
    try:
        base = default_config_path() if config_path is None else Path(config_path).expanduser()
        return base.with_name("runs.jsonl")
    except Exception:
        return Path("yonerai-runs.jsonl")


def _canonical_command(value: str) -> str:
    raw = value.strip()
    return COMMAND_ALIASES.get(raw, COMMAND_ALIASES.get(raw.lower(), raw.lower()))


def _canonical_value(value: str) -> str:
    raw = value.strip()
    return VALUE_ALIASES.get(raw, VALUE_ALIASES.get(raw.lower(), raw))


def _canonical_agent_mode_value(value: str) -> str:
    normalized = _canonical_value(value)
    return "plan_readonly" if normalized == "read_only" else normalized


def _format_chat_response(report: dict[str, Any], *, lang: str) -> str:
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    auto = report.get("auto") if isinstance(report.get("auto"), dict) else {}
    provider = report.get("provider") if isinstance(report.get("provider"), dict) else {}
    response = report.get("response") if isinstance(report.get("response"), dict) else {}
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    output = response.get("output_text") or error.get("message") or "no output"
    run_id = run.get("run_id") or run.get("id") or "none"
    provider_id = provider.get("provider_id") or auto.get("provider_id") or auto.get("provider") or "unknown"
    memory_line = _format_chat_memory_line(report, lang=lang)
    if lang == "ja":
        return "\n".join(
            (
                "YonerAI ミッションコントロール",
                f"  実行ID（run_id）: {_safe(run_id)}",
                f"  経路（処理方法）: {_route_label(auto.get('route'), lang='ja')}",
                f"  提供元（AI接続元）: {_provider_label(provider_id, lang='ja')}",
                f"  ローカルノード: {_local_node_state(report, lang='ja')}",
                f"  履歴: {_ledger_state_from_report(report, lang='ja')}",
                "  安全: ネットワーク初期値オフ / ファイルはワークスペース内のみ / 任意シェル無効",
                f"  承認: {'必要' if auto.get('approval_required') else '不要'}",
                "",
                _format_task_progress(report, lang="ja").rstrip(),
                _format_agents(report, lang="ja").rstrip(),
                memory_line,
                "",
                f"  出力: {_safe(output)}",
                "",
            )
        )
    return "\n".join(
        (
            "YonerAI response",
            f"  run_id: {_safe(run_id)}",
            f"  route: {_safe(auto.get('route') or 'unknown')}",
            f"  provider: {_safe(provider_id)}",
            f"  local_node: {_local_node_state(report, lang='en')}",
            f"  ledger: {_ledger_state_from_report(report, lang='en')}",
            "  safety: network off by default / workspace file only / arbitrary shell disabled",
            f"  approval: {'required' if auto.get('approval_required') else 'not required'}",
            "",
            _format_task_progress(report, lang="en").rstrip(),
            _format_agents(report, lang="en").rstrip(),
            memory_line,
            "",
            f"  output: {_safe(output)}",
            "",
        )
    )


def _format_chat_memory_line(report: dict[str, Any], *, lang: str) -> str:
    memory = report.get("memory") if isinstance(report.get("memory"), dict) else {}
    ids = memory.get("used_ids") if isinstance(memory.get("used_ids"), list) else []
    safe_ids = [_safe(memory_id) for memory_id in ids[:8]]
    if not safe_ids:
        return "記憶: 参照なし" if lang == "ja" else "Memory: not used"
    joined = ", ".join(safe_ids)
    if lang == "ja":
        return f"記憶を参照しました: memory_used={joined} / raw内容は表示・送信しません"
    return f"Memory used: {joined} / raw memory content not shown or sent"


def _format_task_progress(report: dict[str, Any], *, lang: str) -> str:
    progress = report.get("task_progress") if isinstance(report.get("task_progress"), dict) else {}
    steps = progress.get("steps") if isinstance(progress.get("steps"), list) else []
    if not steps:
        return "進行状況: まだありません\n" if lang == "ja" else "Task progress: none yet\n"
    lines = ["進行状況" if lang == "ja" else "Task progress"]
    for step in steps:
        if not isinstance(step, dict):
            continue
        if lang == "ja":
            lines.append(
                f"  {_progress_state_label(step.get('state'), lang='ja')}: "
                f"{_progress_step_label(step.get('id'), lang='ja')} - "
                f"{_progress_summary_label(step.get('id'), step.get('summary'), lang='ja')}"
            )
        else:
            lines.append(f"  {step.get('state')}: {_safe(step.get('id') or 'step')} - {_safe(step.get('summary') or '')}")
    lines.append("")
    return "\n".join(lines)


def _format_tasks(last_report: dict[str, Any] | None, runs_report: dict[str, Any], *, lang: str) -> str:
    runs = runs_report.get("runs") if isinstance(runs_report.get("runs"), list) else []
    if lang == "ja":
        lines = ["タスク"]
        if isinstance(last_report, dict):
            run = last_report.get("run") if isinstance(last_report.get("run"), dict) else {}
            lines.append(f"  現在/直近: run_id={_safe(run.get('run_id') or run.get('id') or 'none')}")
            lines.append(_format_task_progress(last_report, lang="ja").rstrip())
        else:
            lines.append("  現在/直近: まだ実行がありません。通常文を入力すると ask --auto 経路でタスクを作ります。")
        if runs:
            lines.append("  最近の履歴")
            for run in runs[:5]:
                if isinstance(run, dict):
                    lines.append(
                        f"    run_id={_safe(run.get('run_id') or 'none')} "
                        f"状態={_run_status_label(run.get('status'), lang='ja')} "
                        f"進行イベント={len(_run_progress_events(run))}"
                    )
        else:
            lines.append("  最近の履歴: ローカル履歴が未設定、または記録がありません。")
        lines.append("  サブエージェント: まだ実行しません。計画表示のみです。")
        lines.append("")
        return "\n".join(lines)
    lines = ["Tasks"]
    if isinstance(last_report, dict):
        run = last_report.get("run") if isinstance(last_report.get("run"), dict) else {}
        lines.append(f"  current/recent: run_id={_safe(run.get('run_id') or run.get('id') or 'none')}")
        lines.append(_format_task_progress(last_report, lang="en").rstrip())
    else:
        lines.append("  current/recent: no run yet. Type a message to create an ask --auto task.")
    lines.append("  subagents: not started; plan display only")
    lines.append("")
    return "\n".join(lines)


def _format_agents(report: dict[str, Any] | None, *, lang: str) -> str:
    reviewer = report.get("reviewer_plan") if isinstance(report, dict) and isinstance(report.get("reviewer_plan"), dict) else {}
    subtasks = reviewer.get("subtasks") if isinstance(reviewer.get("subtasks"), list) else []
    if not reviewer:
        if lang == "ja":
            return "\n".join(
                (
                    "エージェント計画",
                    "  まだ実行結果がありません。質問後に /エージェント で確認できます。",
                    "  実サブエージェントはまだ起動しません。安全な計画表示だけです。",
                    "",
                )
            )
        return "Agent plan\n  No run yet. This is a public-safe plan display; no subagents are started.\n"
    lines = ["エージェント計画" if lang == "ja" else "Agent plan"]
    if not reviewer.get("enabled"):
        lines.append("  今回は複数担当の計画は不要です。" if lang == "ja" else "  multi-role plan: not required for this run")
    for item in subtasks:
        if isinstance(item, dict):
            if lang == "ja":
                lines.append(f"  {_agent_role_label(item.get('role'), lang='ja')}: {_safe(item.get('goal') or '')}")
            else:
                lines.append(f"  {item.get('role')}: {_safe(item.get('goal') or '')}")
    lines.append("  実サブエージェント起動: なし（計画表示のみ）" if lang == "ja" else "  subagents_started: false")
    lines.append("")
    return "\n".join(lines)


def _format_run_progress(run: dict[str, Any], *, lang: str) -> str:
    progress_events = _run_progress_events(run)
    if not progress_events:
        return "進行状況: 記録なし\n" if lang == "ja" else "Task progress: not recorded\n"
    lines = ["進行状況" if lang == "ja" else "Task progress"]
    for event in progress_events:
        step = str(event.get("name") or "").removeprefix("task_progress_")
        if lang == "ja":
            lines.append(
                f"  {_progress_state_label(event.get('status'), lang='ja')}: "
                f"{_progress_step_label(step, lang='ja')} - {_progress_summary_label(step, event.get('summary'), lang='ja')}"
            )
        else:
            lines.append(f"  {event.get('status')}: {_safe(step)} - {_safe(event.get('summary') or '')}")
    lines.append("")
    return "\n".join(lines)


def _format_run_agents(run: dict[str, Any], *, lang: str) -> str:
    events = run.get("events") if isinstance(run.get("events"), list) else []
    reviewer_event = next((event for event in events if isinstance(event, dict) and event.get("name") == "auto_reviewer_plan"), None)
    if lang == "ja":
        lines = ["エージェント計画"]
        if reviewer_event:
            lines.append(f"  レビュー計画: {_safe(reviewer_event.get('summary') or '')}")
        else:
            lines.append("  この履歴にはレビュー計画の記録がありません。")
        lines.append("  実サブエージェント起動: なし（計画表示のみ）")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Agent plan",
            f"  reviewer_plan: {_safe(reviewer_event.get('summary') if isinstance(reviewer_event, dict) else 'not recorded')}",
            "  subagents_started: false",
            "",
        )
    )


def _run_progress_events(run: dict[str, Any]) -> list[dict[str, Any]]:
    events = run.get("events") if isinstance(run.get("events"), list) else []
    return [event for event in events if isinstance(event, dict) and str(event.get("name") or "").startswith("task_progress_")]


def _run_route(run: dict[str, Any]) -> object:
    route_decision = run.get("route_decision") if isinstance(run.get("route_decision"), dict) else {}
    auto_runtime = route_decision.get("auto_runtime") if isinstance(route_decision.get("auto_runtime"), dict) else {}
    return route_decision.get("route_strategy") or auto_runtime.get("route") or route_decision.get("route") or "unknown"


def _run_provider(run: dict[str, Any]) -> object:
    provider_decision = run.get("provider_decision") if isinstance(run.get("provider_decision"), dict) else {}
    return provider_decision.get("provider_id") or "unknown"


def _local_node_state(report: dict[str, Any], *, lang: str) -> str:
    local_node = report.get("local_node") if isinstance(report.get("local_node"), dict) else {}
    if local_node.get("used"):
        return "使用中（ローカル開発 / ループバック限定）" if lang == "ja" else "used local-dev loopback-only"
    return "待機中（ローカル開発 / ループバック限定）" if lang == "ja" else "standby local-dev loopback-only"


def _ledger_state_from_report(report: dict[str, Any], *, lang: str) -> str:
    ledger = report.get("ledger") if isinstance(report.get("ledger"), dict) else {}
    if ledger.get("file_backed") or ledger.get("enabled"):
        return "オン（ローカルのみ）" if lang == "ja" else "on local-only"
    return "オフ（初期値）" if lang == "ja" else "off by default"


def _progress_step_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "step")
    return {
        "classify": "分類",
        "route": "経路選択",
        "provider_selection": "提供元選択",
        "execution": "実行",
        "review": "レビュー",
        "result": "結果",
    }.get(str(value), _safe(value or "不明"))


def _progress_state_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "unknown")
    return {
        "pending": "待機",
        "running": "実行中",
        "done": "完了",
        "skipped": "スキップ",
        "blocked": "ブロック",
        "error": "エラー",
        "ok": "完了",
        "failed": "エラー",
    }.get(str(value), _safe(value or "不明"))


def _progress_summary_label(step: object, summary: object, *, lang: str) -> str:
    text = _safe(summary or "")
    if lang != "ja":
        return text
    return (
        text.replace("difficulty=instant", "難易度=即時")
        .replace("difficulty=task", "難易度=タスク")
        .replace("difficulty=agent", "難易度=複雑")
        .replace("privacy=public", "公開")
        .replace("privacy=local_file", "ローカルファイル")
        .replace("privacy=private", "非公開")
        .replace("route=instant_local", "経路=ローカル即時")
        .replace("route=local_llm", "経路=ローカルLLM")
        .replace("route=cloud_contract_candidate", "経路=クラウド候補")
        .replace("route=deny", "経路=拒否")
        .replace("approval_required=false", "承認不要")
        .replace("approval_required=true", "承認必要")
        .replace("provider=mock", "提供元=モック")
        .replace("provider=oracle-stub", "提供元=オラクルスタブ")
        .replace("provider=local", "提供元=ローカル")
    )


def _agent_role_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "agent")
    return {
        "planner": "計画担当",
        "researcher": "調査担当",
        "implementer": "実装担当",
        "tester": "テスト担当",
        "reviewer": "レビュー担当",
        "executor": "実行担当",
    }.get(str(value), _safe(value or "担当"))


def _format_command_palette(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "コマンドパレット",
                "  / を入力すると候補を表示します。Tab/矢印が使えない端末では、この一覧と /選択 の番号入力を使います。",
                "  日本語コマンドを優先表示します。/settings などの英語aliasも互換用に使えます。",
                "",
                slash_command_summary(lang).rstrip(),
                "",
            )
        )
    return "\n".join(
        (
            "Command palette",
            "  Type / to show suggestions. If Tab/arrows are unavailable, use this list and /select numbered fallback.",
            "  English aliases remain available; Japanese mode shows Japanese commands first.",
            "",
            slash_command_summary(lang).rstrip(),
            "",
        )
    )


def _format_mode_state(config: dict[str, object], *, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    current = str(values.get("agent_mode") or "plan_readonly")
    if lang == "ja":
        return "\n".join(
            (
                "作業モード",
                f"  現在: {_agent_mode_label(current, lang='ja')}",
                "",
                f"{_selector('plan_readonly', current)} 計画（読み取り専用）: 調査・計画・確認だけ。変更や外部実行はしません。",
                f"{_selector('build_safe', current)} 安全実行: 公開runtimeで許可済みのdry-run/安全操作だけ候補にします。",
                f"{_selector('review', current)} レビュー: 差分・安全境界・テスト観点を優先します。",
                f"{_selector('memory', current)} 記憶: ローカル記憶の確認・整理を優先します。",
                "",
                "変更: /モード 計画|安全実行|レビュー|記憶",
                "ショートカット: /計画 /レビュー",
                "実サブエージェント起動: なし。表示するのは計画だけです。",
                "",
            )
        )
    return "\n".join(
        (
            "Agent mode",
            f"  current: {current}",
            "  plan_readonly: plan and inspect only",
            "  build_safe: safe public-runtime dry-run actions only",
            "  review: prioritize review and verification",
            "  memory: prioritize local memory inspection",
            "  change: /mode plan|build|review|memory",
            "  shortcuts: /plan /review",
            "  real subagent execution: none; this only displays a plan.",
            "",
        )
    )


def _format_permissions(config: dict[str, object], *, live: bool, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    mode = str(values.get("agent_mode") or "plan_readonly")
    approval = str(values.get("approval_mode") or "prompt")
    tools = str(values.get("tools_mode") or "dry_run")
    if lang == "ja":
        return "\n".join(
            (
                "権限と承認",
                f"  作業モード: {_agent_mode_label(mode, lang='ja')}",
                f"  承認: {_approval_label(approval, lang='ja')}",
                f"  ツール: {_safe(tools)}（public runtime は dry-run 固定）",
                f"  ライブ接続: {'オン（明示許可）' if live else 'オフ（初期値）'}",
                "",
                f"{_selector('read_only', _permission_profile(config))} 読み取り専用: 変更しない。計画・レビューだけ。",
                f"{_selector('auto_safe', _permission_profile(config))} 自動安全: 安全なdry-run候補だけ。任意shellや外部fileは不可。",
                f"{_selector('ask_before_risky', _permission_profile(config))} 危険時確認: 危険操作は approval_required / deny。",
                f"{_selector('dry_run_only', _permission_profile(config))} ドライランのみ: 実行ではなく計画だけ。",
                "",
                "変更: /権限 読み取り専用|自動安全|危険時確認|ドライランのみ",
                "境界: 任意shellなし / workspace外fileなし / provider key表示なし / local private memory自動uploadなし。",
                "",
            )
        )
    return "\n".join(
        (
            "Permissions and approval",
            f"  agent_mode: {mode}",
            f"  approval: {approval}",
            f"  tools: {tools} (public runtime is dry-run only)",
            f"  live: {'on' if live else 'off'}",
            "  profiles: read-only, auto-safe, ask-before-risky, dry-run-only",
            "  change: /permissions read-only|auto-safe|ask-before-risky|dry-run-only",
            "  boundaries: no arbitrary shell, no files outside workspace, no provider key output, no local private memory auto-upload.",
            "",
        )
    )


def _permission_profile(config: dict[str, object]) -> str:
    if config.get("approval_mode") == "deny":
        return "read_only"
    if config.get("agent_mode") == "plan_readonly":
        return "dry_run_only"
    if config.get("agent_mode") == "build_safe":
        return "auto_safe"
    return "ask_before_risky"


def _format_agent_mention_preview(text: str, *, config: dict[str, object], lang: str) -> str | None:
    parts = text.strip().split(maxsplit=1)
    if not parts or not parts[0].startswith("@"):
        return None
    raw_role = parts[0][1:].strip().lower()
    role_aliases = {
        "general": "planner",
        "planner": "planner",
        "researcher": "researcher",
        "reviewer": "reviewer",
    }
    role = role_aliases.get(raw_role)
    if role is None:
        return None
    summary = _safe(parts[1] if len(parts) > 1 else "no task provided")
    mode = str(config.get("agent_mode") or "plan_readonly")
    if lang == "ja":
        return "\n".join(
            (
                "サブエージェント計画",
                f"  指名: @{raw_role} / {_agent_role_label(role, lang='ja')}",
                f"  作業モード: {_agent_mode_label(mode, lang='ja')}",
                f"  依頼要約: {summary}",
                "  状態: planned",
                "  実サブエージェント起動: なし",
                "  自律実行: なし",
                "  次にやること: 通常のメッセージとして送ると ask --auto 経路で処理します。",
                "",
            )
        )
    return "\n".join(
        (
            "Subagent plan",
            f"  mention: @{raw_role} / {role}",
            f"  agent_mode: {mode}",
            f"  request_summary: {summary}",
            "  state: planned",
            "  real_subagent_execution: none",
            "  autonomous_actions: none",
            "  next: send the task as a normal message to use ask --auto.",
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
    values = build_config_report(config, exists=True)["config"]
    local_state = _provider_state(provider_report or {}, "local")
    ledger = "on" if values.get("ledger_enabled") else "off"
    update_notice = "on" if values.get("update_notice_enabled") else "off"
    if lang == "ja":
        return "\n".join(
            (
                "設定",
                "  まとめて全設定を流しません。カテゴリを選んで1つずつ確認・切替します。",
                "",
                "カテゴリ",
                "  1. 言語: " + _language_label(values["language"] or "ja", lang="ja") + "  /設定 言語",
                "  2. 提供元: " + _provider_label(provider, lang="ja") + "  /設定 提供元",
                "  3. モデル: " + _safe(values.get("model_preference") or "auto") + "  /設定 モデル",
                "  4. モード: " + _agent_mode_label(values.get("agent_mode"), lang="ja") + "  /設定 モード",
                "  5. 安全: 承認="
                + _approval_label(values["approval_mode"], lang="ja")
                + " / ファイル="
                + _file_access_label(values["file_access_mode"], lang="ja")
                + "  /設定 安全",
                "  6. 記憶: ローカル優先 / local->cloud自動同期なし  /設定 記憶",
                "  7. 更新: 通知=" + update_notice + " / 自動適用なし  /設定 更新",
                "  8. 認証: Google OAuthドライラン契約のみ  /設定 認証",
                "  9. プライバシー: 共有トラフィックオフ  /設定 プライバシー",
                "",
                "個別切替",
                "  /選択 1 日本語|英語",
                "  /選択 2 自動|モック|ローカル|OpenAI互換|アンソロピック|ジェミニ",
                "  /選択 3 毎回確認|拒否",
                "  /選択 4 ワークスペース内のみ|無効",
                "  /選択 5 オン|オフ  （履歴記録）",
                "  /選択 6 オン|オフ  （ライブ接続）",
                "  /選択 7 オン|オフ  （ネットワーク）",
                "  /選択 8 自動|llama3.1  （モデル）",
                "  /選択 9 オン|オフ  （更新通知）",
                "  /選択 10 計画|安全実行|レビュー|記憶  （作業モード）",
                "",
                f"状態: ローカルLLM={_state_label(local_state, lang='ja')} / 履歴={ledger} / ライブ={'オン' if live else 'オフ'}",
                "秘密情報（APIキーなど）は表示・保存しません。ローカルパスは出力しません。",
                "",
            )
        )
    return "\n".join(
        (
            "Settings",
            "  Open one category instead of dumping every setting:",
            "  /settings language",
            "  /settings providers",
            "  /settings models",
            "  /settings mode",
            "  /settings safety",
            "  /settings memory",
            "  /settings update",
            "  /settings auth",
            "  /settings privacy",
            f"  current: language={values['language'] or 'ja'} provider={provider} model={values.get('model_preference') or 'auto'} agent_mode={values.get('agent_mode')} local_llm={local_state}",
            f"  toggles: ledger={ledger} live={'on' if live else 'off'} network={'on' if values['network_enabled'] else 'off'} update_notice={update_notice}",
            "  numbered fallback: /select 1 en, /select 2 mock, /select 8 llama3.1, /select 9 on, /select 10 review",
            "  secrets and local paths are not printed.",
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


def _format_settings_category(
    category: str,
    config: dict[str, object],
    *,
    provider: str,
    live: bool,
    lang: str,
    provider_report: dict[str, Any] | None = None,
) -> str:
    if category == "back":
        return _format_settings(config, provider=provider, live=live, lang=lang, provider_report=provider_report)
    if category == "language":
        return _format_settings_language(config, lang=lang)
    if category == "providers":
        return _format_providers(provider_report or {}, lang=lang)
    if category == "models":
        return _format_models(config, provider_report or {}, lang=lang)
    if category == "safety":
        return _format_safety(config, live=live, lang=lang)
    if category == "mode":
        return _format_mode_state(config, lang=lang)
    if category == "update":
        return _format_settings_update(config, lang=lang)
    if category == "auth":
        return _format_auth_status(config, lang=lang)
    if category == "privacy":
        return _format_privacy_status(config, lang=lang)
    return _format_settings(config, provider=provider, live=live, lang=lang, provider_report=provider_report)


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
                "  通常更新: 通知だけ。作業中は割り込まない",
                "  セキュリティ更新: 警告だけ。自動適用しない",
                "  クリティカル更新: 次回起動時に先に表示。基本のローカルmockチャットは止めない",
                "  自動更新: なし",
                "  強制サイレント更新: なし",
                "  変更: /更新通知 オン|オフ または /選択 9 オン|オフ",
                "  確認: /更新",
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


def _format_settings_memory(config: dict[str, object], status_report: dict[str, Any] | None, *, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    status = status_report or {}
    enabled = bool(values.get("memory_enabled"))
    scope = str(values.get("memory_default_scope") or "local_private")
    count = status.get("record_count", 0)
    if lang == "ja":
        lines = [
            "設定: 記憶",
            f"  記憶: {'オン' if enabled else 'オフ'}",
            f"  既定スコープ: {_safe(scope)}",
            f"  active件数: {_safe(count)}",
            f"  cloud -> local preview: {'オン' if values.get('memory_cloud_to_local_preview_enabled') else 'オフ'}",
            "  local -> cloud: 承認必須 / 自動同期なし",
            f"  self-evolution signal memory: {'オン' if values.get('memory_self_evolution_signal_enabled') else 'オフ'}",
            "  shared traffic: オフ",
            "  変更:",
            "    /設定 記憶 オン|オフ",
            "    /設定 記憶 scope local_private|procedural|shared_preference|project|session",
            "    /設定 記憶 cloud-preview オン|オフ",
            "    /設定 記憶 self-evolution オン|オフ",
            "  操作:",
            "    /記憶 add <内容>",
            "    /記憶 list",
            "    /記憶 forget <memory_id>",
            "    /記憶 sync preview cloud-to-local",
            "    /記憶 sync preview local-to-cloud",
            "  ローカルprivate記憶はcloudへ自動同期しません。secret/local path形状はredactされます。",
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
                f"{_selector('provider', network_selected)} 提供元のみ許可（--liveで明示した時だけ）",
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
                f"履歴記録（ローカル履歴）: {'オン（秘匿済み / ローカルのみ）' if values.get('ledger_enabled') else 'オフ'}",
                "シェル実行（PC操作）: 任意コマンドは無効",
                "クラウド候補: 非公開ファイルやローカルファイルは送りません",
                "ライブ提供元: 明示許可と provider 別 env opt-in が必要です",
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
            f"  ledger: {'on' if values.get('ledger_enabled') else 'off'}",
            "  shell: arbitrary shell disabled",
            "  cloud: private/local files never sent to cloud candidates",
            "",
        )
    )


def _format_providers(report: dict[str, Any], *, lang: str) -> str:
    providers = report.get("providers") if isinstance(report.get("providers"), list) else []
    lines = ["提供元（AI接続元）" if lang == "ja" else "Providers"]
    for item in providers:
        if not isinstance(item, dict):
            continue
        capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), dict) else {}
        command = _safe(item.get("command") or 'yonerai ask "hello" --auto --json')
        if lang == "ja":
            lines.append(
                f"  {_provider_label(item.get('provider_id'), lang='ja')}: "
                f"{_state_label(item.get('plain_state') or item.get('setup_status'), lang='ja')} "
                f"（設定={_yes_no(item.get('configured'), lang='ja')}）"
            )
            lines.append(f"    次に試す: {command}")
            lines.append(f"    セットアップ: {_provider_hint_ja(item)}")
            lines.append(f"    できること: {_capability_summary(capabilities, lang=lang)}")
            lines.append(f"    しないこと: {_safe(item.get('does_not') or 'キー表示、既定のlive呼び出し、任意操作はしません')}")
        else:
            lines.append(
                f"  {item.get('provider_id')}: {item.get('plain_state') or item.get('setup_status')} "
                f"(configured={item.get('configured')})"
            )
            lines.append(f"    next: {command}")
            lines.append(f"    setup: {_safe(item.get('setup_hint') or 'No setup hint.')}")
            lines.append(f"    capabilities: {_capability_summary(capabilities, lang=lang)}")
            lines.append(f"    does_not: {_safe(item.get('does_not') or '')}")
    lines.append("  キー（秘密情報）: 表示しません。設定にも保存しません" if lang == "ja" else "  keys: redacted / not printed")
    if lang == "ja":
        lines.append("  ローカルLLM: localhost / 127.0.0.1 / ::1 だけを許可します")
        lines.append("  外部API: --live と provider別 env opt-in がある時だけ呼びます")
    lines.append("")
    return "\n".join(_safe(line) for line in lines)


def _format_models(config: dict[str, object], report: dict[str, Any], *, lang: str) -> str:
    model = _safe(config.get("model_preference") or "auto")
    local_state = _provider_state(report, "local")
    capabilities = tui_capability_report()
    if lang == "ja":
        return "\n".join(
            (
                "モデル（AIモデル）",
                f"  現在のモデル指定: {model}",
                f"  ローカルLLM（PC内モデル）: {_state_label(local_state, lang='ja')}",
                f"  補完UI: {'利用可能' if capabilities['slash_completion'] else '通常入力にフォールバック'}",
                "  変更: /モデル auto または /モデル llama3.1 など",
                "  ローカルLLM設定: localhost / 127.0.0.1 / ::1 のみ。非ループバックURLは拒否します。",
                "  Ollama例: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=ollama, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:11434",
                "  LM Studio例: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=lmstudio, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:1234/v1",
                "  実行しないこと: モデルの自動インストール、外部URL探索、APIキー保存、プロンプト送信",
                "",
            )
        )
    return "\n".join(
        (
            "Models",
            f"  model_preference: {model}",
            f"  local_llm: {local_state}",
            f"  slash_completion: {capabilities['slash_completion']}",
            "  change: /model auto or /model llama3.1",
            "  local LLM endpoints: localhost / 127.0.0.1 / ::1 only",
            "  not_performed: no model installation, no external probing, no key storage, no prompt sent",
            "",
        )
    )


def _format_local_llm_setup(report: dict[str, Any], *, lang: str) -> str:
    local_state = _provider_state(report, "local")
    local_llm = report.get("local_llm") if isinstance(report.get("local_llm"), dict) else {}
    probes = local_llm.get("probes") if isinstance(local_llm.get("probes"), list) else []
    detected = str(local_llm.get("status") or "unknown")
    endpoint_label = _safe(local_llm.get("endpoint_label") or local_llm.get("detected_label") or "未検出")
    if lang == "ja":
        lines = [
            "ローカルLLMセットアップ",
            f"  現在の状態: {_state_label(local_state, lang='ja')}",
            f"  検出状態: {_local_llm_status_label(detected, lang='ja')}",
            f"  検出endpoint: {endpoint_label}",
            "  対応形態: Ollama系 / LM Studio系 / OpenAI互換のローカルHTTP API",
            "  許可する接続先: localhost / 127.0.0.1 / ::1 のみ",
            "  例（Ollama）: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=ollama, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:11434",
            "  例（LM Studio）: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=lmstudio, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:1234/v1",
            "  使う: /提供元選択 ローカル。その後、この画面で通常文を入力します。",
            "  実行しないこと: 外部URL接続、APIキー保存、任意シェル実行、モデルの自動インストール",
        ]
        if probes:
            lines.append("  確認した候補（プロンプト送信なし）:")
            for probe in probes[:4]:
                if isinstance(probe, dict):
                    lines.append(
                        f"    - {_safe(probe.get('label') or probe.get('provider') or 'local')}: "
                        f"{_local_llm_status_label(probe.get('status'), lang='ja')} / {_safe(probe.get('reason') or '理由なし')}"
                    )
        lines.append("  次に試す: 先に Ollama または LM Studio を起動し、必要な env を設定してから /提供元選択 ローカル")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Local LLM setup",
            f"  current_state: {_safe(local_state)}",
            f"  detection_status: {_safe(detected)}",
            f"  endpoint: {endpoint_label}",
            "  supported: Ollama-style / LM Studio-style / local OpenAI-compatible HTTP API",
            "  allowed_endpoint: localhost / 127.0.0.1 / ::1 only",
            "  Ollama example: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=ollama, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:11434",
            "  LM Studio example: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=lmstudio, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:1234/v1",
            "  use: /provider local or yonerai ask \"hello\" --provider local --live",
            "  not_performed: no external URL, no key storage, no arbitrary shell, no model installation",
            "",
        )
    )


def _format_auth_status(config: dict[str, object], *, lang: str) -> str:
    report = build_google_auth_status(config)
    flow = report.get("flow") if isinstance(report.get("flow"), dict) else {}
    storage = report.get("storage") if isinstance(report.get("storage"), dict) else {}
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    if lang == "ja":
        lines = [
            "認証",
            f"  Google認証: {'設定あり' if report.get('configured') else '未設定'}",
            "  状態: ドライラン契約のみ。本番Googleログインはまだ有効にしていません",
            f"  ループバックredirectのみ: {_yes_no(flow.get('loopback_redirect_only'), lang='ja')}",
            f"  PKCE必須: {_yes_no(flow.get('pkce_required'), lang='ja')}",
            f"  state必須: {_yes_no(flow.get('state_required'), lang='ja')}",
            f"  embedded webview: {'禁止' if not flow.get('embedded_webview_allowed') else '許可'}",
            f"  token保存: {_safe(storage.get('refresh_token_storage') or 'disabled_by_default')}",
            "  次に試す: yonerai auth google login --dry-run --pretty --lang ja",
        ]
        if error:
            lines.append(f"  補足: {_safe(error.get('message') or error.get('code'))}")
        lines.append("  実行しないこと:")
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Auth",
            f"  google_auth: {'configured' if report.get('configured') else 'not configured'}",
            "  mode: dry-run contract only; production Google login is disabled",
            f"  loopback_redirect_only: {bool(flow.get('loopback_redirect_only'))}",
            f"  pkce_required: {bool(flow.get('pkce_required'))}",
            f"  state_required: {bool(flow.get('state_required'))}",
            f"  token_storage: {_safe(storage.get('refresh_token_storage') or 'disabled_by_default')}",
            "  next: yonerai auth google login --dry-run --pretty",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "",
        )
    )


def _format_privacy_status(config: dict[str, object], *, lang: str) -> str:
    report = build_privacy_status(config)
    sharing = report.get("data_sharing") if isinstance(report.get("data_sharing"), dict) else {}
    exclusion = report.get("private_content_exclusion") if isinstance(report.get("private_content_exclusion"), dict) else {}
    ledger = report.get("ledger") if isinstance(report.get("ledger"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    excluded = exclusion.get("excluded") if isinstance(exclusion.get("excluded"), list) else []
    if lang == "ja":
        lines = [
            "プライバシー",
            f"  OpenAI共有トラフィック: {'オン' if sharing.get('openai_shared_traffic_enabled') else 'オフ'}",
            f"  ユーザーopt-in必要: {_yes_no(sharing.get('requires_explicit_opt_in'), lang='ja')}",
            f"  private/local内容の除外: {_yes_no(exclusion.get('active'), lang='ja')}",
            f"  ledger shared_traffic既定値: {_value_label(bool(ledger.get('default_shared_traffic')), lang='ja')}",
            f"  raw prompt保存: {_value_label(bool(ledger.get('raw_prompt_persisted')), lang='ja')}",
            "  共有しない内容:",
        ]
        for item in excluded[:6]:
            lines.append(f"    - {_safe(item)}")
        lines.append("  実行しないこと:")
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Privacy",
            f"  openai_shared_traffic_enabled: {bool(sharing.get('openai_shared_traffic_enabled'))}",
            f"  requires_explicit_opt_in: {bool(sharing.get('requires_explicit_opt_in'))}",
            f"  private_content_exclusion_active: {bool(exclusion.get('active'))}",
            f"  ledger_default_shared_traffic: {bool(ledger.get('default_shared_traffic'))}",
            f"  raw_prompt_persisted: {bool(ledger.get('raw_prompt_persisted'))}",
            "  excluded: " + ", ".join(_safe(item) for item in excluded[:6]),
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "",
        )
    )


def _format_memory_status(report: dict[str, Any], *, lang: str) -> str:
    counts = report.get("counts_by_scope") if isinstance(report.get("counts_by_scope"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    if lang == "ja":
        lines = [
            "記憶",
            f"  ローカル記憶: {'利用可能' if report.get('ok') else '利用不可'}",
            f"  active件数: {_safe(report.get('record_count') or 0)}",
            f"  local -> cloud自動同期: {'オン' if report.get('local_to_cloud_enabled_by_default') else 'オフ'}",
            f"  cloud同期: {'オン' if report.get('cloud_sync_enabled') else 'オフ'}",
            f"  raw prompt保存: {'オン' if report.get('raw_prompt_persisted') else 'オフ'}",
            f"  local path出力: {'オン' if report.get('local_absolute_path_persisted') else 'オフ'}",
            "  scope別:",
        ]
        for key in ("session", "local_private", "shared_preference", "project", "procedural", "cloud_account"):
            lines.append(f"    - {key}: {_safe(counts.get(key, 0))}")
        lines.extend(
            [
                "  試す: yonerai memory add \"note\" --scope local --pretty",
                "  同期preview: yonerai memory sync preview --direction local-to-cloud --pretty",
                "  実行しないこと:",
            ]
        )
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Memory",
            f"  available: {bool(report.get('ok'))}",
            f"  active_records: {_safe(report.get('record_count') or 0)}",
            f"  local_to_cloud_enabled_by_default: {bool(report.get('local_to_cloud_enabled_by_default'))}",
            f"  cloud_sync_enabled: {bool(report.get('cloud_sync_enabled'))}",
            f"  raw_prompt_persisted: {bool(report.get('raw_prompt_persisted'))}",
            f"  local_absolute_path_persisted: {bool(report.get('local_absolute_path_persisted'))}",
            "  try: yonerai memory add \"note\" --scope local --pretty",
            "  sync preview: yonerai memory sync preview --direction local-to-cloud --pretty",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "",
        )
    )


def _format_sync_status(report: dict[str, Any], *, lang: str) -> str:
    cloud_link = report.get("cloud_link") if isinstance(report.get("cloud_link"), dict) else {}
    directions = report.get("directions") if isinstance(report.get("directions"), dict) else {}
    cloud_to_local = directions.get("cloud_to_local") if isinstance(directions.get("cloud_to_local"), dict) else {}
    local_to_cloud = directions.get("local_to_cloud") if isinstance(directions.get("local_to_cloud"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    if lang == "ja":
        lines = [
            "同期",
            f"  認証状態: {_safe(report.get('auth_state') or cloud_link.get('auth_state') or 'dry_run')}",
            "  cloud -> local: ログイン済み + 選択したcloud会話だけ同期downできます",
            f"    現在有効: {_yes_no(cloud_to_local.get('enabled_now'), lang='ja')}",
            "  local -> cloud: 初期値では無効。明示承認とaudit理由が必要です",
            f"    初期値有効: {_yes_no(local_to_cloud.get('enabled_by_default'), lang='ja')}",
            f"    明示承認必須: {_yes_no(local_to_cloud.get('requires_explicit_approval'), lang='ja')}",
            "  除外: private file / local memory / local node payload / provider keys",
            f"  共有トラフィック: {'オン' if report.get('shared_traffic_enabled') else 'オフ'}",
            "  public repo: contract/fixtureのみ。本番Official Cloud/Oracleには接続しません",
            "  試す: yonerai sync preview --direction cloud-to-local --json",
            "  実行しないこと:",
        ]
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Sync",
            f"  auth_state: {_safe(report.get('auth_state') or cloud_link.get('auth_state') or 'dry_run')}",
            f"  cloud_to_local_enabled: {bool(cloud_to_local.get('enabled_now'))}",
            f"  local_to_cloud_enabled_by_default: {bool(local_to_cloud.get('enabled_by_default'))}",
            f"  local_to_cloud_requires_approval: {bool(local_to_cloud.get('requires_explicit_approval'))}",
            "  excluded: private file, local memory, local node payload, provider keys",
            f"  shared_traffic_enabled: {bool(report.get('shared_traffic_enabled'))}",
            "  public_repo: contract/fixture only; no production Official Cloud or Oracle call",
            "  try: yonerai sync preview --direction cloud-to-local --json",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "",
        )
    )


def _format_sync_unavailable(lang: str) -> str:
    if lang == "ja":
        return "同期状態はこのビルドでは利用できません。\n"
    return "Sync status is unavailable in this build.\n"


def _format_memory_unavailable(lang: str) -> str:
    if lang == "ja":
        return "記憶状態はこのビルドでは利用できません。\n"
    return "Memory status is unavailable in this build.\n"


def _memory_action_help(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "記憶操作",
                "  /記憶 add <内容>",
                "  /記憶 list",
                "  /記憶 forget <memory_id>",
                "  /記憶 sync preview cloud-to-local",
                "  /記憶 sync preview local-to-cloud",
                "",
            )
        )
    return "Memory actions: /memory add <text>, /memory list, /memory forget <memory_id>, /memory sync preview local-to-cloud\n"


def _memory_cloud_preview_disabled(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "cloud -> local memory preview: オフ",
                "  設定で無効です。同期previewは実行しません。",
                "  変更: /設定 記憶 cloud-preview オン",
                "",
            )
        )
    return "\n".join(
        (
            "cloud-to-local memory preview is off",
            "  The preview callback was not executed.",
            "  Change: /settings memory cloud-preview on",
            "",
        )
    )


def _memory_write_disabled(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "記憶: オフ",
                "  記憶が無効なため、新しい記憶は保存しません。",
                "  変更: /設定 記憶 オン",
                "",
            )
        )
    return "\n".join(
        (
            "Memory is off",
            "  New memory records are not saved while memory is disabled.",
            "  Change: /settings memory on",
            "",
        )
    )


def _format_memory_action_report(report: dict[str, Any], *, lang: str) -> str:
    operation = str(report.get("operation") or "unknown")
    if operation == "add":
        record = report.get("record") if isinstance(report.get("record"), dict) else {}
        if lang == "ja":
            return "\n".join(
                (
                    "記憶を追加しました",
                    f"  memory_id: {_safe(record.get('memory_id') or 'none')}",
                    f"  scope: {_safe(record.get('scope') or 'unknown')}",
                    f"  sync_policy: {_safe(record.get('sync_policy') or 'unknown')}",
                    f"  summary: {_safe(record.get('text') or '')}",
                    "  cloud同期: なし",
                    "  raw prompt保存: なし",
                    "",
                )
            )
        return "\n".join(
            (
                "Memory added",
                f"  memory_id: {_safe(record.get('memory_id') or 'none')}",
                f"  scope: {_safe(record.get('scope') or 'unknown')}",
                f"  sync_policy: {_safe(record.get('sync_policy') or 'unknown')}",
                f"  summary: {_safe(record.get('text') or '')}",
                "  cloud_sync: false",
                "  raw_prompt_persisted: false",
                "",
            )
        )
    if operation == "list":
        records = report.get("records") if isinstance(report.get("records"), list) else []
        lines = ["記憶一覧" if lang == "ja" else "Memory list", f"  count: {_safe(report.get('count') or 0)}"]
        if not records:
            lines.append("  記憶はまだありません" if lang == "ja" else "  no memory records")
        for record in records[:10]:
            if isinstance(record, dict):
                lines.append(f"  - {_safe(record.get('memory_id') or 'mem_unknown')}: {_safe(record.get('text') or '')}")
        lines.append("")
        return "\n".join(lines)
    if operation == "forget":
        if lang == "ja":
            return "\n".join(
                (
                    "記憶を忘却しました" if report.get("forgotten") else "記憶が見つかりませんでした",
                    f"  memory_id: {_safe(report.get('memory_id') or 'none')}",
                    "  cloud同期: なし",
                    "",
                )
            )
        return "\n".join(
            (
                "Memory forgotten" if report.get("forgotten") else "Memory not found",
                f"  memory_id: {_safe(report.get('memory_id') or 'none')}",
                "  cloud_sync: false",
                "",
            )
        )
    if operation == "sync_preview":
        decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
        actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
        if lang == "ja":
            lines = [
                "記憶同期プレビュー",
                f"  direction: {_safe(report.get('direction') or 'unknown')}",
                f"  decision: {_safe(decision.get('state') or 'unknown')}",
                f"  reason: {_safe(decision.get('reason') or 'none')}",
                f"  explicit approval required: {_yes_no(decision.get('requires_explicit_approval'), lang='ja')}",
                "  local private memory: cloudへ自動同期しません",
                "  sync_performed: なし",
                "  実行しないこと:",
            ]
            for action in actions[:8]:
                lines.append(f"    - {_safe(action)}")
            lines.append("")
            return "\n".join(lines)
        return "\n".join(
            (
                "Memory sync preview",
                f"  direction: {_safe(report.get('direction') or 'unknown')}",
                f"  decision: {_safe(decision.get('state') or 'unknown')}",
                f"  reason: {_safe(decision.get('reason') or 'none')}",
                f"  requires_explicit_approval: {bool(decision.get('requires_explicit_approval'))}",
                "  local_private_memory: never uploads automatically",
                "  sync_performed: false",
                "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
                "",
            )
        )
    return _memory_action_help(lang)


def _format_evolve_status(report: dict[str, Any], *, lang: str) -> str:
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    policy = report.get("input_policy") if isinstance(report.get("input_policy"), dict) else {}
    if lang == "ja":
        lines = [
            "自己進化プロポーザル",
            f"  状態: {_safe(report.get('status') or '不明')}",
            f"  proposal-only: {_yes_no(report.get('proposal_only'), lang='ja')}",
            f"  既定signal数: {_safe(report.get('default_signal_count') or 0)}",
            "  入力: 合成/低解像度signalだけ",
            f"  raw prompt許可: {_yes_no(policy.get('raw_prompt_allowed'), lang='ja')}",
            f"  PII許可: {_yes_no(policy.get('pii_allowed'), lang='ja')}",
            f"  安定ユーザー追跡: {_yes_no(policy.get('stable_user_tracking_allowed'), lang='ja')}",
            "  実行しないこと:",
        ]
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("  試す: yonerai evolve simulate --pretty --lang ja")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Self-evolution proposals",
            f"  status: {_safe(report.get('status') or 'unknown')}",
            f"  proposal_only: {bool(report.get('proposal_only'))}",
            f"  default_signal_count: {_safe(report.get('default_signal_count') or 0)}",
            "  input: synthetic low-resolution signals only",
            f"  raw_prompt_allowed: {bool(policy.get('raw_prompt_allowed'))}",
            f"  pii_allowed: {bool(policy.get('pii_allowed'))}",
            f"  stable_user_tracking_allowed: {bool(policy.get('stable_user_tracking_allowed'))}",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "  try: yonerai evolve simulate --pretty --lang en",
            "",
        )
    )


def _format_evolve_unavailable(lang: str) -> str:
    if lang == "ja":
        return "自己進化プロポーザルキューはこのビルドでは利用できません。\n"
    return "Self-evolution proposal queue is unavailable in this build.\n"


def _format_update_check(report: dict[str, Any], *, lang: str) -> str:
    artifact = report.get("artifact_status") if isinstance(report.get("artifact_status"), dict) else {}
    signature = report.get("signature_status") if isinstance(report.get("signature_status"), dict) else {}
    policy = report.get("update_policy") if isinstance(report.get("update_policy"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    if lang == "ja":
        lines = [
            "更新確認",
            f"  現在のバージョン: {_safe(report.get('current_version') or '不明')}",
            f"  manifest上のバージョン: {_safe(report.get('latest_manifest_version') or '不明')}",
            f"  最新stable: {_safe(report.get('latest_stable') or '不明')}",
            f"  チャンネル: {_safe(report.get('channel') or '不明')}",
            f"  更新あり: {_value_label(bool(report.get('update_available')), lang='ja')}",
            f"  比較結果: {_safe(report.get('version_comparison') or '不明')}",
            f"  artifact: {_safe(artifact.get('actual_filename') or artifact.get('selected_artifact') or '未選択')}",
            f"  sha256: {'あり' if artifact.get('sha256_present') else 'なし'}",
            f"  署名/信頼: {_safe(signature.get('state') or '不明')} / 検証済み={_yes_no(signature.get('verified'), lang='ja')}",
            f"  rollback計画: {_value_label(bool(report.get('rollback_plan_available')), lang='ja')}",
            f"  次の安全な確認: {_safe(report.get('next_safe_command') or 'yonerai update plan --pretty')}",
            f"  Quick install: {_safe(report.get('quick_install_command') or '不明')}",
            f"  GitHub fallback: {_safe(report.get('github_install_fallback_command') or '不明')}",
            f"  Verified install: {_safe(report.get('verified_install_page') or 'https://yonerai.com/install')}",
            f"  セキュリティ更新: {'あり' if report.get('security_update') else 'なし'}",
            f"  クリティカル更新: {'あり' if report.get('critical_update') else 'なし'}",
            f"  強制更新: {'あり' if report.get('forced_update_enabled') else 'なし'}",
            f"  自動適用: {'あり' if report.get('auto_update_apply_enabled') else 'なし'}",
            f"  作業中の扱い: {_safe(policy.get('active_session_behavior') or 'warn_only_do_not_interrupt')}",
            f"  次回起動時: {_safe(policy.get('next_startup_behavior') or 'show_update_screen_first_only_if_critical')}",
            f"  基本ローカルmockチャット: {'利用可' if policy.get('basic_local_mock_chat_allowed', True) else '制限'}",
            "  実行しなかったこと:",
        ]
        for action in actions:
            lines.append(f"    - {_safe(action)}")
        if warnings:
            lines.append("  注意:")
            for warning in warnings[:5]:
                lines.append(f"    - {_safe(warning)}")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Update check",
            f"  current_version: {_safe(report.get('current_version') or 'unknown')}",
            f"  latest_manifest_version: {_safe(report.get('latest_manifest_version') or 'unknown')}",
            f"  latest_stable: {_safe(report.get('latest_stable') or 'unknown')}",
            f"  channel: {_safe(report.get('channel') or 'unknown')}",
            f"  update_available: {bool(report.get('update_available'))}",
            f"  version_comparison: {_safe(report.get('version_comparison') or 'unknown')}",
            f"  selected_artifact: {_safe(artifact.get('actual_filename') or artifact.get('selected_artifact') or 'none')}",
            f"  sha256_present: {bool(artifact.get('sha256_present'))}",
            f"  signature: {_safe(signature.get('state') or 'unknown')} verified={bool(signature.get('verified'))}",
            f"  rollback_plan_available: {bool(report.get('rollback_plan_available'))}",
            f"  next_safe_command: {_safe(report.get('next_safe_command') or 'yonerai update plan --pretty')}",
            f"  quick_install_command: {_safe(report.get('quick_install_command') or 'unknown')}",
            f"  github_install_fallback_command: {_safe(report.get('github_install_fallback_command') or 'unknown')}",
            f"  verified_install_page: {_safe(report.get('verified_install_page') or 'https://yonerai.com/install')}",
            f"  security_update: {bool(report.get('security_update'))}",
            f"  critical_update: {bool(report.get('critical_update'))}",
            f"  forced_update_enabled: {bool(report.get('forced_update_enabled'))}",
            f"  auto_update_apply_enabled: {bool(report.get('auto_update_apply_enabled'))}",
            f"  active_session_behavior: {_safe(policy.get('active_session_behavior') or 'warn_only_do_not_interrupt')}",
            f"  next_startup_behavior: {_safe(policy.get('next_startup_behavior') or 'show_update_screen_first_only_if_critical')}",
            f"  basic_local_mock_chat_allowed: {bool(policy.get('basic_local_mock_chat_allowed', True))}",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions),
            "",
        )
    )


def _format_update_error(exc: Exception, *, lang: str) -> str:
    message = _safe(str(exc) or exc.__class__.__name__)
    if lang == "ja":
        return f"更新確認に失敗しました: {message}\n"
    return f"Update check failed: {message}\n"


def _joined_arg_after_command(text: str, command_token: str) -> str | None:
    value = text[len(command_token) :].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value or None


def _format_runs(report: dict[str, Any], *, lang: str) -> str:
    runs = report.get("runs") if isinstance(report.get("runs"), list) else []
    if not runs:
        if lang == "ja":
            return "\n".join(
                (
                    "実行履歴: まだありません",
                    "履歴は明示したローカル履歴だけを読みます。",
                    "対話画面では /選択 5 オン で秘匿済みローカル履歴を有効化できます。",
                    "",
                )
            )
        return "Runs: none yet\nLedger is opt-in and local-only.\n"
    lines = ["実行履歴" if lang == "ja" else "Runs"]
    for run in runs:
        if isinstance(run, dict):
            route = _run_route(run)
            provider = _run_provider(run)
            event_count = len(_run_progress_events(run))
            if lang == "ja":
                lines.append(
                    f"  実行ID（run_id）{run.get('run_id')}: {_run_status_label(run.get('status'), lang='ja')} "
                    f"{run.get('task_summary')} / 経路={_route_label(route, lang='ja')} / "
                    f"提供元={_provider_label(provider, lang='ja')} / 進行={event_count}件"
                )
            else:
                lines.append(
                    f"  {run.get('run_id')}: {run.get('status')} {run.get('task_summary')} "
                    f"/ route={_safe(route)} / provider={_safe(provider)} / progress_events={event_count}"
                )
    lines.append("")
    return "\n".join(_safe(line) for line in lines)


def _format_run(report: dict[str, Any], *, lang: str) -> str:
    if not report.get("ok"):
        return "実行が見つかりません\n" if lang == "ja" else "Run not found\n"
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    if lang == "ja":
        return "\n".join(
            (
                "実行",
                f"  実行ID（run_id）: {_safe(run.get('run_id') or 'none')}",
                f"  状態: {_run_status_label(run.get('status'), lang='ja')}",
                f"  経路（処理方法）: {_route_label(_run_route(run), lang='ja')}",
                f"  提供元（AI接続元）: {_provider_label(_run_provider(run), lang='ja')}",
                f"  タスク: {_safe(run.get('task_summary') or 'なし')}",
                "",
                _format_run_progress(run, lang="ja").rstrip(),
                _format_run_agents(run, lang="ja").rstrip(),
                "",
            )
        )
    return "\n".join(
        (
            "Run",
            f"  run_id: {_safe(run.get('run_id') or 'none')}",
            f"  status: {_safe(run.get('status') or 'unknown')}",
            f"  route: {_safe(_run_route(run))}",
            f"  provider: {_safe(_run_provider(run))}",
            f"  task: {_safe(run.get('task_summary') or 'none')}",
            "",
            _format_run_progress(run, lang="en").rstrip(),
            _format_run_agents(run, lang="en").rstrip(),
            "",
        )
    )


def _welcome(
    lang: str,
    *,
    provider: str,
    live: bool,
    config_exists: bool,
    config: dict[str, object],
    ledger_path: str | None,
) -> str:
    ledger = "オン" if ledger_path else "オフ"
    ledger_en = "on" if ledger_path else "off"
    model = _safe(config.get("model_preference") or "auto")
    agent_mode = _safe(config.get("agent_mode") or "plan_readonly")
    update_notice = "オン" if config.get("update_notice_enabled") else "オフ"
    update_notice_en = "on" if config.get("update_notice_enabled") else "off"
    if lang == "ja":
        safety = f"承認={_approval_label(config.get('approval_mode'), lang='ja')} / ファイル={_file_access_label(config.get('file_access_mode'), lang='ja')}"
        return "\n".join(
            (
                "YonerAI ミッションコントロール CLI",
                "日本語モード。/ヘルプ でコマンドを表示します。",
                "状態ヘッダー",
                f"  提供元（AI接続元）: {_provider_label(provider, lang='ja')}",
                f"  モデル（AIモデル）: {model}",
                f"  作業モード: {_agent_mode_label(agent_mode, lang='ja')}",
                "  経路（処理方法）: 未実行",
                "  ローカルノード: 待機中（ローカル開発 / ループバック限定）",
                f"  履歴: {ledger}（秘匿済みローカル履歴）",
                f"  安全: {safety} / ネットワーク初期値オフ / 任意シェル無効",
                f"  ライブ接続: {'オン（明示許可）' if live else 'オフ（初期値）'} / 設定={'既存' if config_exists else '初期値'}",
                f"  更新通知: {update_notice}（ローカルmanifest確認のみ）",
                "  認証/同期/プライバシー: Google OAuthドライランのみ / local->cloud自動同期なし / 共有トラフィックオフ",
                "  自己進化: proposal-only / 合成signalだけ / 自動PR・deployなし",
                "使う: そのまま質問を書く / / で候補表示 / /コマンド / /設定 / /モード / /計画 / /レビュー / /権限 / /モデル / /提供元 / /安全 / /履歴 / /認証 / /同期 / /自己進化 / /更新",
                "設定を変える: /選択 <番号> <値>",
                "",
            )
        )
    return "\n".join(
        (
            "YonerAI Mission Control CLI",
            "English mode. Type /help for commands.",
            f"provider={provider} model={model} agent_mode={agent_mode} route=not_run local_node=standby ledger={ledger_en} live={'on' if live else 'off'} update_notice={update_notice_en} config={'found' if config_exists else 'created/default'}",
            "Safety: network off / tools dry-run / workspace file only / arbitrary shell disabled / live providers off by default",
            "Auth/sync/privacy: Google OAuth dry-run only / no automatic local-to-cloud sync / shared traffic off",
            "Self-evolution: proposal-only, synthetic signals only, no PR/deploy/mutation",
            "Use: type a message, / for suggestions, /palette, /settings, /mode, /plan, /review, /permissions, /models, /providers, /safety, /runs, /auth, /sync, /evolve, /update",
            "",
        )
    )


def _help(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "コマンド",
                "  /状態                 状態ヘッダーをもう一度表示する",
                "  /ホーム               状態ヘッダーをもう一度表示する",
                "  /コマンド             コマンドパレットを表示する",
                "  /設定                 設定を見る",
                "  /モード 計画|安全実行|レビュー|記憶",
                "  /計画                 読み取り専用の計画モードにする",
                "  /レビュー             レビュー優先モードにする",
                "  /権限                 承認と権限の状態を見る",
                "  /モデル               モデルとローカルLLMの設定を見る",
                "  /提供元               提供元（AI接続元）を見る",
                "  /安全                 安全境界を見る",
                "  /タスク               現在/最近のタスク進行を見る",
                "  /エージェント         計画中の担当（計画担当・レビュー担当など）を見る",
                "  /履歴                 実行履歴を見る",
                "  /表示 <実行ID>        1件の実行を見る",
                "  /ローカルLLM          PC内モデルの接続方法を見る",
                "  /認証                 Google OAuthドライラン状態を見る",
                "  /同期                 cloud/local同期境界を見る",
                "  /プライバシー         共有とプライバシー境界を見る",
                "  /自己進化             proposal-only自己進化キューを見る",
                "  /更新                 ローカルmanifestで更新を確認",
                "  /更新通知 オン|オフ   起動時の更新案内設定を変更",
                "  /言語 日本語|英語     表示言語を変更",
                "  /提供元選択 自動|モック|ローカル|OpenAI互換|Anthropic|Gemini",
                "  /承認 確認|拒否       危険操作の扱いを変更",
                "  /ファイル ワークスペース内のみ|無効",
                "  /履歴記録 オン|オフ   秘匿済みローカル履歴の記録を変更",
                "  /ライブ接続 オン|オフ 外部/ローカル実行の明示許可を変更",
                "  /ネットワーク オン|オフ 外部通信の明示許可を変更",
                "  /選択 <番号> <値>      設定画面の番号で変更",
                "  /終了                 終了",
                "",
            )
        )
    return "\n".join(
        (
            "Commands",
            "  /status          Show the Mission Control status header again",
            "  /home            Show the Mission Control status header again",
            "  /palette         Show command palette",
            "  /settings        Show settings",
            "  /mode plan|build|review|memory Change agent mode",
            "  /plan            Switch to read-only planning mode",
            "  /review          Switch to review mode",
            "  /permissions     Show approval and permission policy",
            "  /models          Show model and local LLM setup",
            "  /providers       Show provider status",
            "  /safety          Show safety boundaries",
            "  /tasks           Show current/recent task progress",
            "  /agents          Show planned agent/reviewer roles",
            "  /runs            Show run history",
            "  /show <run_id>   Show one run",
            "  /local-llm       Show local LLM loopback setup",
            "  /auth            Show Google OAuth dry-run status",
            "  /sync            Show cloud/local sync boundaries",
            "  /privacy         Show shared-traffic and private-content policy",
            "  /evolve          Show proposal-only self-evolution queue",
            "  /update          Check local manifest update status",
            "  /update-notice on|off Toggle startup update notice setting",
            "  /language ja|en  Change language",
            "  /provider auto|mock|local|openai-compatible|anthropic|gemini",
            "  /ledger on|off    Toggle redacted local ledger",
            "  /live on|off      Toggle explicit live/local execution permission",
            "  /network on|off   Toggle explicit network permission",
            "  /select <n> <value> Change a numbered setting",
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
                "対話で使う: yonerai",
                "明示して使う: yonerai chat",
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


def _config_error(lang: str, exc: ConfigError) -> str:
    message = _safe(str(exc) or "config error")
    if lang == "ja":
        return f"設定を保存できませんでした: {message}\n"
    return f"Could not save config: {message}\n"


def _unknown(lang: str) -> str:
    return "不明なコマンドです。/ヘルプ を見てください\n" if lang == "ja" else "Unknown command. Type /help\n"


def _read_update_notice_report(
    config: dict[str, object],
    callbacks: InteractiveCallbacks,
    lang: str,
) -> dict[str, Any] | None:
    if config.get("update_notice_enabled") is not True or callbacks.update_check is None:
        return None
    try:
        report = callbacks.update_check(None, lang)
    except Exception:
        return None
    if not (report.get("update_available") or report.get("security_update") or report.get("critical_update")):
        return None
    return report


def _format_update_notice(report: dict[str, Any] | None, lang: str, *, phase: str) -> str | None:
    if report is None:
        return None
    policy = report.get("update_policy") if isinstance(report.get("update_policy"), dict) else {}
    if lang == "ja":
        title = "起動時の更新通知" if phase == "startup" else "タスク後の更新通知"
        return "\n".join(
            (
                title,
                f"  current: {_safe(report.get('current_version') or 'unknown')}",
                f"  latest_stable: {_safe(report.get('latest_stable') or report.get('latest_manifest_version') or 'unknown')}",
                f"  update_available: {_value_label(bool(report.get('update_available')), lang='ja')}",
                f"  critical_update: {_value_label(bool(report.get('critical_update')), lang='ja')}",
                f"  behavior: {_safe(policy.get('active_session_behavior') or 'warn_only_do_not_interrupt')}",
                f"  next: {_safe(report.get('next_safe_command') or 'yonerai update check --pretty')}",
                "  自動適用なし / 強制サイレント更新なし / ローカルmock chatは継続できます",
                "",
            )
        )
    title = "Startup update notice" if phase == "startup" else "Post-task update notice"
    return "\n".join(
        (
            title,
            f"  current: {_safe(report.get('current_version') or 'unknown')}",
            f"  latest_stable: {_safe(report.get('latest_stable') or report.get('latest_manifest_version') or 'unknown')}",
            f"  update_available: {bool(report.get('update_available'))}",
            f"  critical_update: {bool(report.get('critical_update'))}",
            f"  behavior: {_safe(policy.get('active_session_behavior') or 'warn_only_do_not_interrupt')}",
            f"  next: {_safe(report.get('next_safe_command') or 'yonerai update check --pretty')}",
            "  no auto-apply / no forced silent update / local mock chat remains available",
            "",
        )
    )


def _update_unavailable(lang: str) -> str:
    if lang == "ja":
        return "更新確認はこのビルドでは利用できません。yonerai update check --pretty を試してください。\n"
    return "Update check is unavailable in this build. Try yonerai update check --pretty.\n"


def _bye(lang: str) -> str:
    return "終了しました\n" if lang == "ja" else "Goodbye\n"


def _safe(value: object) -> str:
    text = " ".join(str(value).split())
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    for pattern in PATH_PATTERNS:
        text = pattern.sub("[LOCAL_PATH]", text)
    text = text.translate(CONTROL_CHARACTER_TRANSLATION)
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
        "openai-compatible": "OpenAI互換（外部API）",
        "anthropic": "Anthropic（外部API）",
        "gemini": "Gemini（外部API）",
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
        "cloud_contract_candidate": "クラウド候補（ローカル開発スタブ）",
        "deny": "拒否",
    }
    return labels.get(value, _safe(value or "不明"))


def _approval_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {"prompt": "毎回確認", "deny": "拒否"}.get(str(value), _safe(value))


def _agent_mode_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {
        "plan_readonly": "計画（読み取り専用）",
        "build_safe": "安全実行",
        "review": "レビュー",
        "memory": "記憶",
    }.get(str(value), _safe(value))


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
        "blocked_by_loopback_policy": "ループバック以外のため拒否",
        "invalid_configuration": "設定が不正",
        "unknown": "不明",
    }
    return labels.get(str(value), _safe(value))


def _local_llm_status_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "unknown")
    labels = {
        "detected": "検出済み",
        "unavailable": "未検出",
        "blocked": "安全ポリシーで拒否",
        "ready": "利用可能",
        "ready_now": "今すぐ利用可能",
        "disabled": "無効",
        "unknown": "不明",
    }
    return labels.get(str(value), _safe(value or "不明"))


def _capability_summary(capabilities: dict[str, Any], *, lang: str) -> str:
    names = [
        ("chat", "チャット"),
        ("streaming", "ストリーミング"),
        ("json", "JSON"),
        ("tool_calling", "ツール呼び出し"),
        ("vision", "画像"),
        ("search", "検索"),
        ("embeddings", "埋め込み"),
    ]
    if lang == "ja":
        enabled = [label for key, label in names if capabilities.get(key)]
        return " / ".join(enabled) if enabled else "公開できるcapabilityは未設定"
    enabled_en = [key for key, _label in names if capabilities.get(key)]
    return ", ".join(enabled_en) if enabled_en else "none"


def _provider_hint_ja(item: dict[str, Any]) -> str:
    provider_id = str(item.get("provider_id") or "")
    hint = _safe(item.get("setup_hint") or "")
    if provider_id == "mock":
        return "設定不要。初期値で使えます"
    if provider_id == "local":
        return "Ollama / LM Studio をPC内で起動し、loopback endpointだけを設定します"
    if item.get("external_provider"):
        return "環境変数と --live が必要です。キーの値は表示・保存しません"
    return hint or "状態を確認してください"


def _setting_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    labels = {
        "language": "表示言語",
        "provider": "提供元（AI接続元）",
        "model": "モデル（AIモデル）",
        "agent_mode": "作業モード",
        "permissions": "権限と承認",
        "approval": "承認（危険操作）",
        "file_access": "ファイルアクセス（ファイル読み取り）",
        "ledger": "履歴記録（ローカル履歴）",
        "memory_enabled": "記憶（ローカル記憶）",
        "memory_default_scope": "記憶の既定スコープ",
        "memory_cloud_to_local_preview_enabled": "cloud -> local記憶preview",
        "memory_self_evolution_signal_enabled": "self-evolution signal記憶",
        "update_notice": "更新通知（ローカルmanifest確認）",
        "live_provider": "ライブ接続（外部/ローカル実行）",
        "network": "ネットワーク（外部通信）",
    }
    return labels.get(str(value), _safe(value))


def _value_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    if value in {"ja", "en"}:
        return _language_label(value, lang=lang)
    if value in PROVIDER_PREFERENCES:
        return _provider_label(value, lang=lang)
    if value in AGENT_MODES:
        return _agent_mode_label(value, lang=lang)
    if value in APPROVAL_MODES:
        return _approval_label(value, lang=lang)
    permission_labels = {
        "read_only": "読み取り専用",
        "auto_safe": "自動安全",
        "ask_before_risky": "危険時確認",
        "dry_run_only": "ドライランのみ",
    }
    if value in permission_labels:
        return permission_labels[str(value)]
    if value in FILE_ACCESS_MODES:
        return _file_access_label(value, lang=lang)
    if type(value) is bool:
        return "オン" if value else "オフ"
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
