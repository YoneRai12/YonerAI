from __future__ import annotations

import sys
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TextIO

from yonerai_cli.config import (
    AGENT_MODES,
    APPROVAL_MODES,
    ConfigError,
    FILE_ACCESS_MODES,
    MEMORY_DEFAULT_SCOPES,
    MODEL_RE,
    PROVIDER_PREFERENCES,
    default_config_path,
    load_cli_config,
    save_cli_config,
    set_cli_config_value,
)
from yonerai_cli.screens.agent_console import (
    _format_agent_mention_preview,
    _format_agents,
    _format_chat_response,
    _format_command_palette,
    _format_mode_state,
    _format_permissions,
    _format_task_progress,
    _format_tasks,
)
from yonerai_cli.screens.auth_privacy import (
    _format_auth_status,
    _format_privacy_status,
)
from yonerai_cli.screens.composer import (
    format_input_composer,
    _composer_buffer_preview,
    _composer_msg,
    _format_composer_status,
    _handle_ime_command,
    _handle_composer_command,
)
from yonerai_cli.screens.context import format_context_screen
from yonerai_cli.screens.control_spine import format_control_spine_callback, format_control_spine_tui, format_staging_login_hint
from yonerai_cli.screens.theme import _handle_theme_command
from yonerai_cli.screens.help import _help, _non_tty_fallback, _unknown, _bye, _config_error
from yonerai_cli.screens.evolve import (
    _format_evolve_status,
    _format_evolve_unavailable,
)
from yonerai_cli.screens.memory import (
    _format_memory_action_report,
    _format_memory_status,
    _format_memory_unavailable,
    _format_sync_status,
    _format_sync_unavailable,
    _memory_action_help,
    _memory_cloud_preview_disabled,
    _memory_write_disabled,
)
from yonerai_cli.screens.labels import (
    _agent_mode_label,
    _provider_label,
    _safe,
)
from yonerai_cli.screens.policy import format_policy_status_pretty
from yonerai_cli.screens.runs import (
    _format_run,
    _format_run_agents,
    _format_run_progress,
    _format_runs,
)
from yonerai_cli.screens.providers import (
    _format_local_llm_setup,
    _format_models,
    _format_providers,
)
from yonerai_cli.screens.progress import format_running_preview, format_thinking_status
from yonerai_cli.screens.home import _welcome
from yonerai_cli.screens.safety import _format_safety
from yonerai_cli.screens.update import (
    _format_update_check,
    _format_update_error,
    _format_update_notice,
    _update_unavailable,
)
from yonerai_cli.screens.settings import (
    _changed_message,
    _format_settings,
    _format_settings_language,
    _format_settings_memory,
    _invalid,
    _format_settings_update,
    _provider_state,
    _settings_category_from_args,
    _settings_selection_help,
    _settings_memory_help,
)
from yonerai_cli.screens.status_api import (
    _format_api_status,
    _format_api_unavailable,
    _format_status_check,
)
from yonerai_cli.ime import RomajiComposer
from yonerai_cli.tui.themes import THEME_CHOICES_HELP, normalize_theme, theme_label
from yonerai_cli.services.onboarding_service import run_auth_onboarding
from yonerai_cli.startup_home import render_startup_home_header
from yonerai_cli.tui.aliases import canonical_agent_mode_value as _canonical_agent_mode_value
from yonerai_cli.tui.aliases import canonical_command as _canonical_command
from yonerai_cli.tui.aliases import canonical_value as _canonical_value
from yonerai_cli.tui import (
    prompt_line,
    prompt_toolkit_available,
    render_panel,
    run_with_status,
    slash_command_summary,
)


INTERACTIVE_SCHEMA_VERSION = "yonerai-interactive-cli/v0.8"


@dataclass(frozen=True)
class InteractiveCallbacks:
    providers: Callable[[], dict[str, Any]]
    ask_auto: Callable[..., dict[str, Any]]
    runs_list: Callable[[str | None, int, str], dict[str, Any]]
    runs_show: Callable[[str, str | None, str], dict[str, Any]]
    update_check: Callable[[str | None, str], dict[str, Any]] | None = None
    status_check: Callable[[str], dict[str, Any]] | None = None
    evolve_status: Callable[[str], dict[str, Any]] | None = None
    api_status: Callable[[str], dict[str, Any]] | None = None
    sync_status: Callable[[str], dict[str, Any]] | None = None
    whoami: Callable[[str], dict[str, Any]] | None = None; project_status: Callable[[str], dict[str, Any]] | None = None
    session_status: Callable[[str], dict[str, Any]] | None = None; audit_status: Callable[[str], dict[str, Any]] | None = None
    memory_status: Callable[[str], dict[str, Any]] | None = None
    memory_action: Callable[[str, list[str], str, str | None], dict[str, Any]] | None = None
    policy_status: Callable[[dict[str, object]], dict[str, Any]] | None = None


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
    _attach_runtime_config_path(config, options.config_path)
    config_exists = _config_exists(options.config_path)
    lang = _select_language(config, options, input_stream=input_stream, output_stream=output_stream)
    _select_theme(
        config,
        options,
        lang=lang,
        config_exists=config_exists,
        input_stream=input_stream,
        output_stream=output_stream,
    )
    run_auth_onboarding(
        config,
        config_path=options.config_path,
        config_exists=config_exists,
        script=options.script,
        lang=lang,
        input_stream=input_stream,
        output_stream=output_stream,
        color=options.color,
    )
    provider = options.provider or str(config.get("provider_preference") or "auto")
    if provider not in PROVIDER_PREFERENCES:
        provider = "auto"
    live = bool(options.live)
    ledger_path = _resolve_ledger_path(config, options)

    if not options.script and not _is_interactive(input_stream):
        _write(output_stream, _non_tty_fallback(lang))
        return 0

    last_report: dict[str, Any] | None = None
    composer = RomajiComposer()
    use_tui_prompt = _can_use_prompt_toolkit(options, input_stream=input_stream, output_stream=output_stream)
    policy_report = _safe_policy_status(callbacks, config)
    welcome_body = _welcome(
        lang,
        provider=provider,
        live=_effective_live(live, config),
        config_exists=config_exists,
        config=config,
        ledger_path=ledger_path,
        policy_report=policy_report,
    )
    welcome = _with_startup_home_header(
        render_startup_home_header(
            color=options.color,
            stream=output_stream,
            theme=str(config.get("theme") or "auto"),
        ),
        welcome_body,
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
                bottom_toolbar=_bottom_toolbar(
                    lang, provider=provider, live=_effective_live(live, config), config=config
                ),
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
                composer=composer,
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
            send_text = command_result.get("send_text")
            if isinstance(send_text, str) and send_text.strip():
                text = send_text
            else:
                continue
        elif composer.enabled:
            buffer_now = composer.append(text)
            _write(output_stream, _composer_buffer_preview(buffer_now, lang))
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
                lambda: _invoke_ask_auto(
                    callbacks.ask_auto, text, provider, effective_live, ledger_path, lang, memory_store_path
                ),
                stream=output_stream,
                color=options.color,
            )
        else:
            report = _invoke_ask_auto(
                callbacks.ask_auto, text, provider, effective_live, ledger_path, lang, memory_store_path
            )
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
    agent_mode = str(config.get("agent_mode") or "plan_readonly")
    approval_mode = str(config.get("approval_mode") or "prompt")
    return bool(
        live
        and config.get("network_enabled") is not False
        and agent_mode != "plan_readonly"
        and approval_mode != "deny"
    )


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


def _select_theme(
    config: dict[str, object],
    options: InteractiveOptions,
    *,
    lang: str,
    config_exists: bool,
    input_stream: TextIO,
    output_stream: TextIO,
) -> str:
    # Theme is only asked once, on a first-launch interactive TTY (no config
    # file existed at startup). Script mode and existing configs keep their
    # stored theme (default "auto"), so those flows are unaffected.
    current = normalize_theme(str(config.get("theme") or "auto"))
    if options.script or not _is_interactive(input_stream) or config_exists:
        return current
    if lang == "ja":
        output_stream.write("YonerAI 表示テーマ / theme\n")
        output_stream.write("  端末に合う見た目を選べます（後で /テーマ で変更可）\n")
    else:
        output_stream.write("YonerAI display theme\n")
        output_stream.write("  Pick a look for your terminal (change later with /theme)\n")
    output_stream.write(f"  {THEME_CHOICES_HELP}\n> ")
    output_stream.flush()
    choice = input_stream.readline().strip().lower()
    mapping = {"1": "auto", "2": "dark", "3": "light", "4": "mono"}
    theme = mapping.get(choice, choice if choice in {"auto", "dark", "light", "mono"} else "auto")
    config["theme"] = theme
    save_cli_config(config, options.config_path)
    label = theme_label(theme, lang=lang)
    output_stream.write((f"テーマ: {label}\n" if lang == "ja" else f"theme: {label}\n"))
    return theme


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
    composer: RomajiComposer | None = None,
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
        if callbacks.status_check is not None:
            _write(output_stream, _format_status_check(callbacks.status_check(lang), lang=lang))
        return {}
    if command == "/help":
        _write(output_stream, _help(lang))
        return {}
    if command == "/theme":
        return _handle_theme_command(
            args,
            config=config,
            config_path=options.config_path,
            color=options.color,
            lang=lang,
            output_stream=output_stream,
        )
    if command == "/palette":
        _write(output_stream, _format_command_palette(lang))
        return {}
    if command == "/composer":
        if composer is not None and args and _canonical_value(args[0]) in {"on", "off"}:
            if _canonical_value(args[0]) == "on":
                composer.enable()
                _write(output_stream, _composer_msg(lang, "enabled"))
            else:
                composer.disable()
                _write(output_stream, _composer_msg(lang, "disabled"))
            return {}
        _write(
            output_stream,
            format_input_composer(
                lang=lang,
                config=config,
                provider=provider,
                live=_effective_live(live, config),
            ),
        )
        if composer is not None:
            _write(output_stream, _format_composer_status(composer.status(), lang))
        return {}
    if command == "/ime" and composer is not None:
        return _handle_ime_command(args, composer=composer, lang=lang, output_stream=output_stream)
    if command in {"/convert", "/commit", "/revert", "/dict", "/style"} and composer is not None:
        return _handle_composer_command(command, args, composer=composer, lang=lang, output_stream=output_stream)
    if command == "/settings":
        provider_report = callbacks.providers()
        category = _settings_category_from_args(args)
        if category is None:
            _write(
                output_stream,
                _format_settings(
                    config,
                    provider=provider,
                    live=_effective_live(live, config),
                    lang=lang,
                    provider_report=provider_report,
                ),
            )
            return {}
        if category == "policy":
            if callbacks.policy_status is None:
                _write(
                    output_stream,
                    "ポリシー状態はこのbuildでは利用できません。\n"
                    if lang == "ja"
                    else "Policy status is unavailable in this build.\n",
                )
                return {}
            _write(output_stream, format_policy_status_pretty(callbacks.policy_status(config), lang=lang))
            return {}
        if category == "memory":
            if len(args) > 1:
                return _handle_memory_setting(
                    args[1:], config=config, options=options, lang=lang, output_stream=output_stream
                )
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
                live=_effective_live(live, config),
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
        _write(output_stream, _format_safety(config, live=_effective_live(live, config), lang=lang))
        return {}
    if command == "/policy":
        if callbacks.policy_status is None:
            _write(
                output_stream,
                "ポリシー状態はこのbuildでは利用できません。\n"
                if lang == "ja"
                else "Policy status is unavailable in this build.\n",
            )
            return {}
        _write(output_stream, format_policy_status_pretty(callbacks.policy_status(config), lang=lang))
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
    if command == "/progress":
        if last_report is not None:
            _write(output_stream, format_running_preview(last_report, lang=lang))
        else:
            _write(
                output_stream,
                format_thinking_status(
                    lang=lang,
                    provider=provider,
                    live=_effective_live(live, config),
                    memory_enabled=bool(config.get("memory_enabled")),
                ),
            )
        return {}
    if command == "/show" and args:
        _write(output_stream, _format_run(callbacks.runs_show(args[0], ledger_path, lang), lang=lang))
        return {}
    if command == "/agents":
        _write(output_stream, _format_agents(last_report, lang=lang))
        return {}
    if command == "/context":
        _write(output_stream, format_context_screen(lang=lang))
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
            return _handle_permission_profile(
                args,
                config=config,
                options=options,
                live=live,
                lang=lang,
                output_stream=output_stream,
            )
        _write(output_stream, _format_permissions(config, live=_effective_live(live, config), lang=lang))
        return {}
    if command == "/auth":
        _write(output_stream, _format_auth_status(config, lang=lang))
        if callbacks.whoami is not None:
            _write(output_stream, format_control_spine_tui(callbacks.whoami(lang), lang=lang))
        return {}
    if command == "/login":
        _write(output_stream, format_staging_login_hint(lang=lang))
        return {}
    if command in {"/api", "/project", "/sessions", "/audit"}:
        _write(output_stream, format_control_spine_callback(command, callbacks, lang=lang) or _format_api_unavailable(lang))
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
        result["live"] = bool(config.get("live_provider_enabled"))
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
    _attach_runtime_config_path(config, config_path)
    return updated


def _set_config_values(
    config: dict[str, object],
    values: dict[str, object],
    config_path: str | None,
) -> dict[str, object]:
    updated = load_cli_config(config_path)
    updated.update(values)
    updated.pop("_runtime_config_path", None)
    saved = save_cli_config(updated, config_path)
    config.clear()
    config.update(saved)
    _attach_runtime_config_path(config, config_path)
    return saved


def _attach_runtime_config_path(config: dict[str, object], config_path: str | None) -> None:
    if config_path:
        config["_runtime_config_path"] = str(config_path)


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
            _write(
                output_stream, _changed_message("language", new_config["language"], lang=str(new_config["language"]))
            )
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
    live: bool,
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
    _write(
        output_stream, _format_permissions(config, live=_effective_live(live and not force_live_off, config), lang=lang)
    )
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
        return _format_settings(
            config,
            provider=provider,
            live=_effective_live(live, config),
            lang=lang,
            provider_report=provider_report,
        )
    if category == "language":
        return _format_settings_language(config, lang=lang)
    if category == "providers":
        return _format_providers(provider_report or {}, lang=lang)
    if category == "models":
        return _format_models(config, provider_report or {}, lang=lang)
    if category == "safety":
        return _format_safety(config, live=_effective_live(live, config), lang=lang)
    if category == "mode":
        return _format_mode_state(config, lang=lang)
    if category == "update":
        return _format_settings_update(config, lang=lang)
    if category == "auth":
        return _format_auth_status(config, lang=lang)
    if category == "privacy":
        return _format_privacy_status(config, lang=lang)
    return _format_settings(
        config,
        provider=provider,
        live=_effective_live(live, config),
        lang=lang,
        provider_report=provider_report,
    )


def _joined_arg_after_command(text: str, command_token: str) -> str | None:
    value = text[len(command_token) :].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value or None


def _with_startup_home_header(home_header: str | None, body: str) -> str:
    if not home_header:
        return body
    return f"{home_header.rstrip()}\n\n{body}"


def _safe_policy_status(callbacks: InteractiveCallbacks, config: dict[str, object]) -> dict[str, Any] | None:
    if callbacks.policy_status is None:
        return None
    try:
        return callbacks.policy_status(config)
    except Exception:
        return None


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
