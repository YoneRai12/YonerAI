from __future__ import annotations

import sys
import inspect
from difflib import SequenceMatcher
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TextIO

from yonerai_cli.config import (
    AGENT_MODES,
    APPROVAL_MODES,
    ConfigError,
    DEFAULT_CONFIG,
    FILE_ACCESS_MODES,
    MEMORY_DEFAULT_SCOPES,
    MODEL_RE,
    PROVIDER_PREFERENCES,
    default_config_path,
    load_cli_config,
    save_cli_config,
    set_cli_config_value,
)
from yonerai_cli.auth_policy import build_google_auth_status
from yonerai_cli.screens.agent_console import (
    _format_agent_mention_preview,
    _format_chat_memory_line,
    _format_agents,
    _format_chat_response,
    _format_command_palette,
    _format_command_palette_query,
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
from yonerai_cli.screens.control_spine_interactive import (
    format_control_spine_callback,
    format_control_spine_tui,
    format_login_flow_compact,
    format_staging_login_hint,
)
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
    _route_label,
    _safe,
    _state_label,
)
from yonerai_cli.screens.policy import format_policy_status_pretty
from yonerai_cli.screens.runs import (
    _format_run,
    _format_run_agents,
    _format_run_progress,
    _format_runs,
)
from yonerai_cli.screens.providers import (
    _format_models,
    _format_providers,
    format_models_compact,
    format_providers_compact,
)
from yonerai_cli.screens.progress import format_running_preview, format_thinking_status
from yonerai_cli.screens.home import _welcome, build_home_policy_line, build_home_safety_badge, build_home_safety_line
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
    _format_settings_display,
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
from yonerai_cli.startup_home import render_startup_home_header
from yonerai_cli.services.control_spine_callbacks import interactive_runtime_env
from yonerai_cli.tui.themes import THEME_CHOICES_HELP, normalize_theme, theme_from_input, theme_label
from yonerai_cli.tui.palette import normalize_command_display_mode
from yonerai_cli.services.onboarding_service import run_auth_onboarding
from yonerai_cli.tui.aliases import canonical_agent_mode_value as _canonical_agent_mode_value
from yonerai_cli.tui.aliases import COMMAND_ALIASES, canonical_command as _canonical_command
from yonerai_cli.tui.aliases import canonical_value as _canonical_value
from yonerai_cli.tui.keymap import resolve_submitted_slash_command as _resolve_submitted_slash_command
from yonerai_cli.tui import (
    COMMAND_PALETTE_TRIGGER,
    open_choice_dialog,
    open_command_palette,
    prompt_line,
    prompt_toolkit_available,
    prompt_toolkit_console_ready,
    render_panel,
    render_text_block,
    run_with_status,
    slash_command_summary,
)

INTERACTIVE_SCHEMA_VERSION = "yonerai-interactive-cli/v0.8"
ESC = chr(27)

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
    ping_status: Callable[[str], dict[str, Any]] | None = None
    rate_limit_status: Callable[[str], dict[str, Any]] | None = None
    sync_status: Callable[[str], dict[str, Any]] | None = None
    sync_action: Callable[[list[str], str], dict[str, Any]] | None = None
    whoami: Callable[[str], dict[str, Any]] | None = None
    project_status: Callable[[str], dict[str, Any]] | None = None
    session_status: Callable[[str], dict[str, Any]] | None = None
    auth_logout: Callable[[str], dict[str, Any]] | None = None
    session_revoke: Callable[[str, str], dict[str, Any]] | None = None
    audit_status: Callable[[str], dict[str, Any]] | None = None
    native_run_status: Callable[[str], dict[str, Any]] | None = None
    worker_status: Callable[[str], dict[str, Any]] | None = None
    capability_list: Callable[[str], dict[str, Any]] | None = None
    module_list: Callable[[str], dict[str, Any]] | None = None
    memory_status: Callable[[str], dict[str, Any]] | None = None
    memory_action: Callable[[str, list[str], str, str | None], dict[str, Any]] | None = None
    policy_status: Callable[[dict[str, object]], dict[str, Any]] | None = None
    update_apply: Callable[[str, bool, str], dict[str, Any]] | None = None
    auth_login: Callable[[str, bool], dict[str, Any]] | None = None


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
    config_load_error = False
    try:
        config = load_cli_config(options.config_path)
    except ConfigError:
        config = dict(DEFAULT_CONFIG)
        config["_config_load_error"] = True
        config_load_error = True
    _attach_runtime_config_path(config, options.config_path)
    config_exists = _config_exists(options.config_path) and not config_load_error
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

    interactive_session = not options.script and _is_interactive(input_stream) and _is_interactive(output_stream)
    last_report: dict[str, Any] | None = None
    chat_blocks: list[str] = []
    composer = RomajiComposer()
    use_tui_prompt = interactive_session and _can_use_prompt_toolkit(
        options,
        input_stream=input_stream,
        output_stream=output_stream,
    )
    prefill_line = ""
    policy_report = _safe_policy_status(callbacks, config)
    provider_report = callbacks.providers()
    auth_report = build_google_auth_status(
        config,
        env=interactive_runtime_env(),
        claim_path=str(options.config_path or "") or None,
    )
    provider = _maybe_offer_first_launch_local_llm(
        config=config,
        options=options,
        config_exists=config_exists,
        provider=provider,
        provider_report=provider_report,
        lang=lang,
        input_stream=input_stream,
        output_stream=output_stream,
    )
    provider_report = callbacks.providers()
    welcome_body = _welcome(
        lang,
        provider=provider,
        live=_effective_live(live, config, provider=provider),
        config_exists=config_exists,
        config=config,
        ledger_path=ledger_path,
        policy_report=policy_report,
        provider_report=provider_report,
        auth_report=auth_report,
    )
    if policy_report:
        safety_label = "安全" if lang == "ja" else "safety"
        welcome_body = f"{welcome_body.rstrip()}\n  {safety_label}: {build_home_safety_badge(policy_report, config=config, lang=lang)}\n"
    update_notice_report = _read_update_notice_report(config, callbacks, lang)
    startup_update_notice = _format_update_notice(update_notice_report, lang, phase="startup")
    startup_prelude = _startup_prelude(
        config=config,
        lang=lang,
        update_notice=startup_update_notice,
        auth_report=auth_report,
    )
    if use_tui_prompt:
        _present_screen(
            output_stream,
            welcome_body,
            title="YonerAI",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=True,
            show_header=False,
            prelude=startup_prelude,
        )
    else:
        if startup_prelude:
            _write(output_stream, startup_prelude if startup_prelude.endswith("\n") else startup_prelude + "\n")
        _write(output_stream, welcome_body)

    # The interactive app should feel like a chat surface, not a diagnostics
    # dump. Detailed route/progress remains available through /tasks, /progress,
    # and /runs.
    compact_chat = True

    while True:
        if use_tui_prompt:
            line = prompt_line(
                lang=lang,
                bottom_toolbar=_bottom_toolbar(
                    lang, provider=provider, live=_effective_live(live, config, provider=provider), config=config
                ),
                display_mode=_command_display_mode(config, lang),
                default_text=prefill_line,
            )
            prefill_line = ""
        elif interactive_session:
            output_stream.write("yonerai> ")
            output_stream.flush()
            line = input_stream.readline()
        else:
            line = input_stream.readline()
        if line == COMMAND_PALETTE_TRIGGER or line.startswith(f"{COMMAND_PALETTE_TRIGGER}:"):
            query = None
            if line.startswith(f"{COMMAND_PALETTE_TRIGGER}:"):
                query = line.split(":", 1)[1].strip() or None
            opened, selection = open_command_palette(
                lang=lang,
                display_mode=_command_display_mode(config, lang),
                query=query,
            )
            if selection:
                line = selection
            else:
                if opened:
                    prefill_line = query or ""
                continue
        if line == "":
            if use_tui_prompt:
                continue
            _write(output_stream, _bye(lang))
            return 0
        text = line.strip()
        if not text:
            continue
        coerced_command = _coerce_interactive_short_command(text)
        if coerced_command is not None:
            text = coerced_command
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
                interactive_tty=interactive_session,
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

        effective_live = _effective_live(live, config, provider=provider)
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
        chat_block = _format_chat_turn(text, report, lang=lang, compact=compact_chat)
        report_for_notice = update_notice_report if config.get("update_notice_enabled") is True else None
        after_task_notice = _format_update_notice(report_for_notice, lang, phase="after_task")
        if use_tui_prompt:
            chat_blocks.append(chat_block)
            chat_blocks = chat_blocks[-4:]
            body = _format_chat_view(chat_blocks, lang=lang)
            if after_task_notice:
                body = f"{body.rstrip()}\n\n{after_task_notice.strip()}"
            _present_screen(
                output_stream,
                body,
                title="YonerAI / 会話" if lang == "ja" else "YonerAI / Chat",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=True,
            )
        else:
            _write(output_stream, chat_block)
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


_INTERACTIVE_BARE_COMMANDS_NOARGS = {
    "status": "/status",
    "home": "/status",
    "login": "/login",
    "ログイン": "/ログイン",
    "whoami": "/whoami",
    "アカウント": "/アカウント",
    "session": "/sessions",
    "sessions": "/sessions",
    "セッション": "/セッション",
    "rate": "/rate-limit",
    "ping": "/ping",
    "疎通": "/疎通",
    "rate-limit": "/rate-limit",
    "ratelimit": "/rate-limit",
    "レート": "/レート",
    "auth": "/auth",
    "認証": "/認証",
    "sync": "/sync",
    "同期": "/同期",
    "logout": "/logout",
    "ログアウト": "/ログアウト",
    "api": "/api",
    "api-status": "/api",
    "API": "/API",
    "状態": "/状態",
    "ホーム": "/ホーム",
    "commands": "/commands",
    "palette": "/palette",
    "コマンド": "/コマンド",
    "パレット": "/パレット",
    "settings": "/settings",
    "safety": "/safety",
    "安全": "/安全",
    "permissions": "/permissions",
    "権限": "/権限",
    "providers": "/providers",
    "履歴": "/履歴",
    "tasks": "/tasks",
    "タスク": "/タスク",
    "agents": "/agents",
    "agent": "/agents",
    "エージェント": "/エージェント",
    "policy": "/policy",
    "方針": "/方針",
    "runs": "/runs",
    "memory": "/memory",
    "ヘルプ": "/ヘルプ",
    "help": "/help",
    "quit": "/quit",
    "exit": "/quit",
    "終了": "/終了",
}

_INTERACTIVE_BARE_COMMANDS_WITH_ARGS = {
    "projects": "/projects",
    "project": "/project",
    "プロジェクト": "/プロジェクト",
    "settings": "/settings",
    "設定": "/設定",
    "update": "/update",
    "更新": "/更新",
    "revoke": "/revoke",
    "取り消し": "/取り消し",
    "show": "/show",
    "表示": "/表示",
    "local-llm": "/local-llm",
    "ローカルLLM": "/ローカルLLM",
    "memory": "/memory",
    "記憶": "/記憶",
    "メモリ": "/メモリ",
    "models": "/models",
    "model": "/モデル",
    "モデル": "/モデル",
    "provider": "/provider",
    "providers": "/providers",
    "提供元": "/提供元",
    "permissions": "/permissions",
    "approval": "/approval",
    "file": "/file-access",
    "file-access": "/file-access",
    "network": "/network",
    "live": "/live-provider",
    "display": "/display",
    "表示方式": "/表示方式",
    "language": "/language",
    "言語": "/言語",
    "theme": "/theme",
    "テーマ": "/テーマ",
    "mode": "/mode",
    "モード": "/モード",
}


def _coerce_interactive_short_command(text: str) -> str | None:
    raw = text.strip()
    if not raw or raw.startswith("/"):
        return None
    parts = raw.split()
    if not parts:
        return None
    head = parts[0].strip().lower()
    tail = parts[1:]
    if head in _INTERACTIVE_BARE_COMMANDS_NOARGS:
        if not tail:
            return _INTERACTIVE_BARE_COMMANDS_NOARGS[head]
    if head in _INTERACTIVE_BARE_COMMANDS_WITH_ARGS:
        command = _INTERACTIVE_BARE_COMMANDS_WITH_ARGS[head]
        return f"{command} {' '.join(tail)}".rstrip()
    fuzzy_head = _best_interactive_bare_head(head)
    if fuzzy_head in _INTERACTIVE_BARE_COMMANDS_NOARGS:
        if not tail:
            return _INTERACTIVE_BARE_COMMANDS_NOARGS[fuzzy_head]
    if fuzzy_head in _INTERACTIVE_BARE_COMMANDS_WITH_ARGS:
        command = _INTERACTIVE_BARE_COMMANDS_WITH_ARGS[fuzzy_head]
        return f"{command} {' '.join(tail)}".rstrip()
    return None


def _best_interactive_bare_head(head: str) -> str | None:
    if len(head) < 4:
        return None
    candidates = set(_INTERACTIVE_BARE_COMMANDS_NOARGS) | set(_INTERACTIVE_BARE_COMMANDS_WITH_ARGS)
    scored_matches: list[tuple[float, str, str]] = []
    for candidate in sorted(candidates):
        if not candidate or candidate[0] != head[0]:
            continue
        score = SequenceMatcher(None, head, candidate).ratio()
        if candidate.startswith(head):
            score += 0.15
        if head.startswith(candidate):
            score += 0.05
        if score < 0.74:
            continue
        mapped_value = (
            _INTERACTIVE_BARE_COMMANDS_NOARGS.get(candidate)
            or _INTERACTIVE_BARE_COMMANDS_WITH_ARGS.get(candidate)
            or candidate
        )
        scored_matches.append((score, candidate, mapped_value))
    if not scored_matches:
        return None
    best_score = max(score for score, _candidate, _mapped in scored_matches)
    near_matches = [(score, candidate, mapped) for score, candidate, mapped in scored_matches if best_score - score < 0.02]
    mapped_values = {mapped for _score, _candidate, mapped in near_matches}
    if len(mapped_values) != 1:
        return None
    best_candidates = [candidate for score, candidate, _mapped in near_matches if score == best_score]
    return sorted(best_candidates)[0] if best_candidates else None


def _can_use_prompt_toolkit(options: InteractiveOptions, *, input_stream: TextIO, output_stream: TextIO) -> bool:
    if options.script or options.color == "never":
        return False
    if input_stream is not sys.stdin or output_stream is not sys.stdout:
        return False
    return (
        _is_interactive(input_stream)
        and _is_interactive(output_stream)
        and prompt_toolkit_available(output_stream)
        and prompt_toolkit_console_ready(output_stream)
    )


def _effective_live(live: bool, config: dict[str, object], *, provider: str | None = None) -> bool:
    if provider == "local" and config.get("local_llm_enabled") is True:
        return True
    agent_mode = str(config.get("agent_mode") or "plan_readonly")
    approval_mode = str(config.get("approval_mode") or "prompt")
    return bool(
        (live or bool(config.get("live_provider_enabled")))
        and config.get("network_enabled") is not False
        and agent_mode != "plan_readonly"
        and approval_mode != "deny"
    )


def _command_display_mode(config: dict[str, object], lang: str) -> str:
    return normalize_command_display_mode(config.get("command_display_mode"), lang=lang)


def _bottom_toolbar(lang: str, *, provider: str, live: bool, config: dict[str, object]) -> str:
    if lang == "ja":
        if provider == "local" and config.get("local_llm_enabled") is True:
            return "/ で候補 / ↑↓で移動 / Enterで実行 / ローカルLLM"
        if live:
            return "/ で候補 / ↑↓で移動 / Enterで実行 / 外部live"
        return "/ で候補 / ↑↓で移動 / Enterで実行"
    if provider == "local" and config.get("local_llm_enabled") is True:
        return "/ shows suggestions / arrows move / Enter runs / local LLM"
    if live:
        return "/ shows suggestions / arrows move / Enter runs / external live"
    return "/ shows suggestions / arrows move / Enter runs"


def _slash_popup_hint(lang: str) -> str:
    if lang == "ja":
        return (
            "コマンド候補\n"
            "  / で入力欄のそばに候補を出します。文字を足すとその場で絞り込みます。\n"
            "  よく使う: /ログイン /ローカルLLM /更新 /設定\n"
        )
    return (
        "Command suggestions\n"
        "  / shows suggestions near the input box. Keep typing to filter in place.\n"
        "  Common: /login /local-llm /update /settings\n"
    )



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
        output_stream.write("  端末の見た目を選びます。あとで /テーマ でも変更できます。\n")
    else:
        output_stream.write("YonerAI display theme\n")
        output_stream.write("  Pick a look for your terminal (change later with /theme)\n")
    output_stream.write(f"  {THEME_CHOICES_HELP}\n> ")
    output_stream.flush()
    choice = _canonical_value(input_stream.readline().strip())
    theme = theme_from_input(choice) or "auto"
    config["theme"] = theme
    save_cli_config(config, options.config_path)
    label = theme_label(theme, lang=lang)
    output_stream.write((f"テーマ: {label}\n" if lang == "ja" else f"theme: {label}\n"))
    return theme


def _maybe_offer_first_launch_local_llm(
    *,
    config: dict[str, object],
    options: InteractiveOptions,
    config_exists: bool,
    provider: str,
    provider_report: dict[str, Any],
    lang: str,
    input_stream: TextIO,
    output_stream: TextIO,
) -> str:
    if options.script or config_exists or not _is_interactive(input_stream):
        return provider
    if config.get("local_llm_enabled") is True or options.provider:
        return provider

    local_llm = provider_report.get("local_llm") if isinstance(provider_report.get("local_llm"), dict) else {}
    if local_llm.get("status") != "detected":
        return provider

    label = _safe(local_llm.get("detected_label") or local_llm.get("endpoint_label") or "local LLM")
    endpoint = _safe(local_llm.get("endpoint_label") or "loopback")
    use_now = False

    if _can_use_prompt_toolkit(options, input_stream=input_stream, output_stream=output_stream):
        opened, selection = open_choice_dialog(
            title="YonerAI / ローカルLLM" if lang == "ja" else "YonerAI / Local LLM",
            text=(
                f"{label} を見つけました ({endpoint})。今すぐ使いますか？"
                if lang == "ja"
                else f"Detected {label} at {endpoint}. Use it now?"
            ),
            values=[
                ("use", "使う" if lang == "ja" else "Use now"),
                ("later", "後で" if lang == "ja" else "Later"),
            ],
            ok_text="決定" if lang == "ja" else "Choose",
            cancel_text="閉じる" if lang == "ja" else "Close",
        )
        use_now = opened and selection == "use"
    else:
        if lang == "ja":
            output_stream.write("ローカルLLM候補\n")
            output_stream.write(f"1) 使う ({label} / {endpoint})\n")
            output_stream.write("2) 後で\n> ")
        else:
            output_stream.write("Local LLM detected\n")
            output_stream.write(f"1) Use now ({label} / {endpoint})\n")
            output_stream.write("2) Later\n> ")
        output_stream.flush()
        use_now = input_stream.readline().strip().lower() in {"1", "use", "y", "yes", "はい"}

    if not use_now:
        return provider

    try:
        _set_config_values(
            config,
            {
                "provider_preference": "local",
                "local_llm_enabled": True,
            },
            options.config_path,
        )
    except ConfigError as exc:
        _write(output_stream, _config_error(lang, exc))
        return provider

    if lang == "ja":
        output_stream.write(f"ローカルLLMを有効化しました: {label} ({endpoint})\n")
    else:
        output_stream.write(f"Local LLM enabled: {label} ({endpoint})\n")
    output_stream.flush()
    return "local"


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
    interactive_tty: bool = False,
) -> dict[str, object]:
    resolved_slash = _resolve_submitted_slash_command(text)
    if resolved_slash is not None:
        text = resolved_slash
    parts = text.split()
    if parts[0] == "/":
        if interactive_tty:
            opened, selection = open_command_palette(
                lang=lang,
                display_mode=_command_display_mode(config, lang),
            )
            if selection:
                return _handle_slash_command(
                    selection,
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
                    interactive_tty=interactive_tty,
                )
            if opened:
                return {}
        _present_screen(
            output_stream,
            _format_command_palette(
                lang,
                display_mode=_command_display_mode(config, lang),
                color=options.color,
            ),
            title="YonerAI / コマンド" if lang == "ja" else "YonerAI / Commands",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    command = _canonical_command(parts[0])
    if (
        len(parts) == 1
        and parts[0].startswith("/")
        and parts[0] not in {"/", "/palette"}
        and parts[0] not in COMMAND_ALIASES
        and parts[0].lower() not in COMMAND_ALIASES
    ):
        encoding_hint = _script_encoding_hint(parts[0], lang)
        if encoding_hint is not None:
            _write(output_stream, encoding_hint)
            return {}
        if interactive_tty:
            opened, selection = open_command_palette(
                lang=lang,
                display_mode=_command_display_mode(config, lang),
                query=parts[0],
            )
            if selection:
                return _handle_slash_command(
                    selection,
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
                    interactive_tty=interactive_tty,
                )
            if opened:
                return {}
        _present_screen(
            output_stream,
            _format_command_palette_query(
                lang,
                parts[0],
                display_mode=_command_display_mode(config, lang),
                color=options.color,
            ),
            title="YonerAI / コマンド" if lang == "ja" else "YonerAI / Commands",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    args = parts[1:]
    if command == "/quit":
        return {"exit": True}
    if command == "/status":
        body = (
            _welcome(
                lang,
                provider=provider,
                live=_effective_live(live, config, provider=provider),
                config_exists=_config_exists(options.config_path),
                config=config,
                ledger_path=ledger_path,
                provider_report=callbacks.providers(),
                auth_report=build_google_auth_status(
                    config,
                    env=interactive_runtime_env(),
                    claim_path=str(options.config_path or "") or None,
                ),
        )
        )
        if callbacks.status_check is not None:
            body = f"{body.rstrip()}\n\n{_format_status_check(callbacks.status_check(lang), lang=lang).strip()}"
        _present_screen(
            output_stream,
            body,
            title="YonerAI / 状態" if lang == "ja" else "YonerAI / Status",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/help":
        _present_screen(
            output_stream,
            _help(lang),
            title="YonerAI / ヘルプ" if lang == "ja" else "YonerAI / Help",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
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
        _present_screen(
            output_stream,
            _format_command_palette(
                lang,
                display_mode=_command_display_mode(config, lang),
                color=options.color,
            ),
            title="YonerAI / コマンド" if lang == "ja" else "YonerAI / Commands",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
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
                live=_effective_live(live, config, provider=provider),
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
            if interactive_tty:
                opened, selection = open_choice_dialog(
                    title="YonerAI / 設定" if lang == "ja" else "YonerAI / Settings",
                    text=(
                        "開くカテゴリを選んでください。"
                        if lang == "ja"
                        else "Choose a settings category."
                    ),
                    values=_settings_category_dialog_values(lang),
                    ok_text="開く" if lang == "ja" else "Open",
                    cancel_text="閉じる" if lang == "ja" else "Close",
                )
                if selection:
                    category = selection
                elif opened:
                    return {}
        if category is None:
            _present_screen(
                output_stream,
                _format_settings(
                    config,
                    provider=provider,
                    live=_effective_live(live, config, provider=provider),
                    lang=lang,
                    provider_report=provider_report,
                ),
                title="YonerAI / 設定" if lang == "ja" else "YonerAI / Settings",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        if category == "policy":
            if callbacks.policy_status is None:
                _write(
                    output_stream,
                    "ポリシー状態はこの build では利用できません。\n"
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
            _present_screen(
                output_stream,
                _format_settings_memory(config, status_report, lang=lang),
                title="YonerAI / 記憶設定" if lang == "ja" else "YonerAI / Memory Settings",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        if category == "display":
            _present_screen(
                output_stream,
                _format_settings_display(config, lang=lang),
                title="YonerAI / 表示方式" if lang == "ja" else "YonerAI / Display",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        if category == "update" and callbacks.update_check is not None:
            _present_screen(
                output_stream,
                _format_settings_update(config, lang=lang),
                title="YonerAI / 更新設定" if lang == "ja" else "YonerAI / Update Settings",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        _present_screen(
            output_stream,
            _format_settings_category(
                category,
                config,
                provider=provider,
                live=_effective_live(live, config, provider=provider),
                lang=lang,
                provider_report=provider_report,
            ),
            title="YonerAI / 設定" if lang == "ja" else "YonerAI / Settings",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
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
        _present_screen(
            output_stream,
            format_models_compact(config, callbacks.providers(), lang=lang),
            title="YonerAI / モデル" if lang == "ja" else "YonerAI / Models",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/safety":
        _present_screen(
            output_stream,
            _format_safety(config, live=_effective_live(live, config, provider=provider), lang=lang),
            title="YonerAI / 安全" if lang == "ja" else "YonerAI / Safety",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/policy":
        if callbacks.policy_status is None:
            _write(
                output_stream,
                "ポリシー状態はこの build では利用できません。\n"
                if lang == "ja"
                else "Policy status is unavailable in this build.\n",
            )
            return {}
        _write(output_stream, format_policy_status_pretty(callbacks.policy_status(config), lang=lang))
        return {}
    if command == "/providers":
        _present_screen(
            output_stream,
            format_providers_compact(callbacks.providers(), lang=lang),
            title="YonerAI / 提供元" if lang == "ja" else "YonerAI / Providers",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/runs":
        _present_screen(
            output_stream,
            _format_runs(callbacks.runs_list(ledger_path, 10, lang), lang=lang),
            title="YonerAI / 履歴" if lang == "ja" else "YonerAI / Runs",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/tasks":
        _present_screen(
            output_stream,
            _format_tasks(last_report, callbacks.runs_list(ledger_path, 5, lang), lang=lang),
            title="YonerAI / タスク" if lang == "ja" else "YonerAI / Tasks",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/progress":
        if last_report is not None:
            body = format_running_preview(last_report, lang=lang)
        else:
            body = format_thinking_status(
                lang=lang,
                provider=provider,
                live=_effective_live(live, config, provider=provider),
                memory_enabled=bool(config.get("memory_enabled")),
            )
        _present_screen(
            output_stream,
            body,
            title="YonerAI / 進行" if lang == "ja" else "YonerAI / Progress",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/show" and args:
        _present_screen(
            output_stream,
            _format_run(callbacks.runs_show(args[0], ledger_path, lang), lang=lang),
            title="YonerAI / run" if lang == "ja" else "YonerAI / run",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/agents":
        _present_screen(
            output_stream,
            _format_agents(last_report, lang=lang),
            title="YonerAI / エージェント" if lang == "ja" else "YonerAI / Agents",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/context":
        _present_screen(
            output_stream,
            format_context_screen(lang=lang),
            title="YonerAI / 参照" if lang == "ja" else "YonerAI / Context",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
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
            _present_screen(
                output_stream,
                _format_mode_state(config, lang=lang),
                title="YonerAI / モード" if lang == "ja" else "YonerAI / Mode",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return result
        _present_screen(
            output_stream,
            _format_mode_state(config, lang=lang),
            title="YonerAI / モード" if lang == "ja" else "YonerAI / Mode",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/plan":
        success, result = _set_and_report("agent_mode", "plan_readonly", config, options, lang, output_stream)
        if not success:
            return {}
        _present_screen(
            output_stream,
            _format_mode_state(config, lang=lang),
            title="YonerAI / 計画" if lang == "ja" else "YonerAI / Plan",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        if args:
            preview = _format_agent_mention_preview("@planner " + " ".join(args), config=config, lang=lang)
            if preview is not None:
                _write(output_stream, preview)
        return result
    if command == "/review":
        success, result = _set_and_report("agent_mode", "review", config, options, lang, output_stream)
        if not success:
            return {}
        _present_screen(
            output_stream,
            _format_mode_state(config, lang=lang),
            title="YonerAI / レビュー" if lang == "ja" else "YonerAI / Review",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
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
        _present_screen(
            output_stream,
            _format_permissions(config, live=_effective_live(live, config, provider=provider), lang=lang),
            title="YonerAI / 権限" if lang == "ja" else "YonerAI / Permissions",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/auth":
        _present_screen(
            output_stream,
            _format_auth_status(config, lang=lang),
            title="YonerAI / 認証" if lang == "ja" else "YonerAI / Auth",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/login":
        if callbacks.auth_login is not None:
            report = callbacks.auth_login(lang, interactive_tty)
            _present_screen(
                output_stream,
                _format_login_compact(report, lang=lang),
                title="YonerAI / ログイン" if lang == "ja" else "YonerAI / Login",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        _present_screen(
            output_stream,
            format_staging_login_hint(lang=lang),
            title="YonerAI / ログイン" if lang == "ja" else "YonerAI / Login",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/logout":
        if callbacks.auth_logout is None:
            _present_screen(
                output_stream,
                _format_api_unavailable(lang),
                title="YonerAI / ログアウト" if lang == "ja" else "YonerAI / Logout",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        report = callbacks.auth_logout(lang)
        _present_screen(
            output_stream,
            format_control_spine_tui(report, lang=lang),
            title="YonerAI / ログアウト" if lang == "ja" else "YonerAI / Logout",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/revoke":
        if callbacks.session_revoke is None:
            _present_screen(
                output_stream,
                _format_api_unavailable(lang),
                title="YonerAI / セッション" if lang == "ja" else "YonerAI / Sessions",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        if not args:
            _write(
                output_stream,
                "使い方: /取り消し <session_id>\n" if lang == "ja" else "Usage: /revoke <session_id>\n",
            )
            return {}
        report = callbacks.session_revoke(lang, args[0])
        _present_screen(
            output_stream,
            format_control_spine_tui(report, lang=lang),
            title="YonerAI / セッション" if lang == "ja" else "YonerAI / Sessions",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command in {
        "/api",
        "/project",
        "/projects",
        "/whoami",
        "/sessions",
        "/audit",
        "/rate-limit",
        "/ping",
        "/run",
        "/worker",
        "/capabilities",
        "/modules",
    }:
        _present_screen(
            output_stream,
            format_control_spine_callback(command, callbacks, lang=lang) or _format_api_unavailable(lang),
            title="YonerAI / Control Spine" if lang == "ja" else "YonerAI / Control Spine",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/privacy":
        _present_screen(
            output_stream,
            _format_privacy_status(config, lang=lang),
            title="YonerAI / プライバシー" if lang == "ja" else "YonerAI / Privacy",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
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
        _present_screen(
            output_stream,
            _format_memory_status(callbacks.memory_status(lang), lang=lang),
            title="YonerAI / 記憶" if lang == "ja" else "YonerAI / Memory",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/sync":
        if callbacks.sync_status is None:
            _write(output_stream, _format_sync_unavailable(lang))
            return {}
        if args:
            if callbacks.sync_action is None:
                _write(output_stream, _format_sync_unavailable(lang))
                return {}
            _write(
                output_stream,
                _format_sync_action_report(
                    callbacks.sync_action(args, lang),
                    lang=lang,
                    color=options.color,
                ),
            )
            return {}
        _present_screen(
            output_stream,
            _format_sync_status(callbacks.sync_status(lang), lang=lang),
            title="YonerAI / 同期" if lang == "ja" else "YonerAI / Sync",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    if command == "/evolve":
        if callbacks.evolve_status is None:
            _write(output_stream, _format_evolve_unavailable(lang))
            return {}
        _write(output_stream, _format_evolve_status(callbacks.evolve_status(lang), lang=lang))
        return {}
    if command == "/local-llm":
        return _handle_local_llm_command(
            args,
            callbacks=callbacks,
            config=config,
            options=options,
            provider=provider,
            lang=lang,
            output_stream=output_stream,
            interactive_tty=interactive_tty,
            color=options.color,
        )
    if command == "/update":
        if args and _canonical_value(args[0]) in {"apply", "適用"}:
            if callbacks.update_apply is None:
                _write(output_stream, _update_unavailable(lang))
                return {}
            channel = _update_channel_from_args(args[1:])
            confirmed = _update_apply_confirmed(args[1:])
            if interactive_tty and channel is None:
                opened, selection = open_choice_dialog(
                    title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
                    text=(
                        "どの更新を適用しますか。"
                        if lang == "ja"
                        else "Choose which update to apply."
                    ),
                    values=[
                        ("stable", "安定版を適用" if lang == "ja" else "Apply stable"),
                        ("alpha", "ベータ版を適用" if lang == "ja" else "Apply beta"),
                    ],
                    ok_text="次へ" if lang == "ja" else "Next",
                    cancel_text="閉じる" if lang == "ja" else "Close",
                )
                if selection in {"stable", "alpha"}:
                    channel = selection
                elif opened:
                    return {}
            channel = channel or "stable"
            if interactive_tty and not confirmed:
                opened, selection = open_choice_dialog(
                    title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
                    text=(
                        (
                            "安定版を適用します。続けますか。"
                            if channel == "stable"
                            else "ベータ版を適用します。続けますか。"
                        )
                        if lang == "ja"
                        else (
                            "Apply the stable update now?"
                            if channel == "stable"
                            else "Apply the beta update now?"
                        )
                    ),
                    values=[
                        ("confirm", "はい、適用する" if lang == "ja" else "Yes, apply"),
                        ("cancel", "いいえ" if lang == "ja" else "No"),
                    ],
                    ok_text="実行" if lang == "ja" else "Run",
                    cancel_text="戻る" if lang == "ja" else "Back",
                )
                if selection == "confirm":
                    confirmed = True
                elif opened:
                    return {}
            try:
                report = callbacks.update_apply(channel, confirmed, lang)
            except Exception as exc:
                _present_screen(
                    output_stream,
                    _format_update_error(exc, lang=lang),
                    title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
                    color=options.color,
                    theme=str(config.get("theme") or "auto"),
                    interactive_tty=interactive_tty,
                )
                return {}
            _present_screen(
                output_stream,
                _format_update_check(report, lang=lang),
                title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        if callbacks.update_check is None:
            _write(output_stream, _update_unavailable(lang))
            return {}
        if not args:
            if interactive_tty:
                opened, selection = open_choice_dialog(
                    title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
                    text=(
                        "どちらを確認しますか。"
                        if lang == "ja"
                        else "Choose which channel to check."
                    ),
                    values=[
                        ("stable", "安定版を確認" if lang == "ja" else "Check stable"),
                        ("alpha", "ベータ版を確認" if lang == "ja" else "Check beta"),
                    ],
                    ok_text="開く" if lang == "ja" else "Open",
                    cancel_text="閉じる" if lang == "ja" else "Close",
                )
                if selection in {"stable", "alpha"}:
                    args = [selection]
                elif opened:
                    return {}
        if not args:
            try:
                stable_report = callbacks.update_check("stable", lang)
                alpha_report = callbacks.update_check("alpha", lang)
            except Exception as exc:
                _present_screen(
                    output_stream,
                    _format_update_error(exc, lang=lang),
                    title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
                    color=options.color,
                    theme=str(config.get("theme") or "auto"),
                    interactive_tty=interactive_tty,
                )
                return {}
            _present_screen(
                output_stream,
                _format_interactive_update_overview(stable_report, alpha_report, lang=lang),
                title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        channel = _update_channel_from_args(args)
        if channel is not None:
            try:
                report = callbacks.update_check(channel, lang)
            except Exception as exc:
                _present_screen(
                    output_stream,
                    _format_update_error(exc, lang=lang),
                    title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
                    color=options.color,
                    theme=str(config.get("theme") or "auto"),
                    interactive_tty=interactive_tty,
                )
                return {}
            _present_screen(
                output_stream,
                _format_update_check(report, lang=lang),
                title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        try:
            report = callbacks.update_check(_joined_arg_after_command(text, parts[0]), lang)
        except Exception as exc:
            _present_screen(
                output_stream,
                _format_update_error(exc, lang=lang),
                title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        _present_screen(
            output_stream,
            _format_update_check(report, lang=lang),
            title="YonerAI / 更新" if lang == "ja" else "YonerAI / Update",
            color=options.color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
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
    if command == "/display":
        if not args:
            _present_screen(
                output_stream,
                _format_settings_display(config, lang=lang),
                title="YonerAI / 表示方式" if lang == "ja" else "YonerAI / Display",
                color=options.color,
                theme=str(config.get("theme") or "auto"),
                interactive_tty=interactive_tty,
            )
            return {}
        value = _canonical_value(args[0])
        if value not in {"ja_only", "ja_with_en", "en_with_ja", "en_only"}:
            _write(output_stream, _invalid(lang))
            return {}
        success, result = _set_and_report("command_display", value, config, options, lang, output_stream)
        if not success:
            return {}
        return result
    if command == "/provider" and args:
        value = _canonical_value(args[0])
        if value not in PROVIDER_PREFERENCES:
            _write(output_stream, _invalid(lang))
            return {}
        if value == "local":
            return _enable_detected_local_llm(
                callbacks=callbacks,
                config=config,
                options=options,
                lang=lang,
                output_stream=output_stream,
                interactive_tty=interactive_tty,
                color=options.color,
            )
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
    _write(output_stream, _unknown_with_encoding_hint(text, lang))
    return {}


def _update_channel_from_args(args: list[str]) -> str | None:
    for arg in args:
        value = _canonical_value(arg)
        if value in {"stable", "release", "安定版", "リリース"}:
            return "stable"
        if value in {"alpha", "beta", "ベータ", "ベータ版", "アルファ", "アルファ版", "最新アルファ版"}:
            return "alpha"
    return None


def _unknown_with_encoding_hint(text: str, lang: str) -> str:
    hint = _script_encoding_hint(text, lang)
    return hint if hint is not None else _unknown(lang)


def _script_encoding_hint(text: str, lang: str) -> str | None:
    if not text.startswith("/"):
        return None
    body = text[1:].strip()
    if not body or body == "?":
        return None
    tokens = [token for token in body.split() if token]
    if not tokens:
        return None
    question_only = sum(1 for token in tokens if set(token) <= {"?"})
    if question_only == 0 or question_only < max(1, len(tokens) // 2):
        return None
    if lang == "ja":
        return (
            "コマンドが文字化けした可能性があります。Windows PowerShell では日本語コマンドが `?` に化けることがあります。"
            " `/quit` や `/update beta` のような ASCII コマンドを使うか、"
            " `$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)`"
            " を設定してからやり直してください。\n"
        )
    return (
        "This command may have been mojibake-corrupted by Windows PowerShell pipeline"
        " encoding. Use ASCII aliases such as `/quit` or `/update beta`, or set"
        " `$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)`"
        " before retrying.\n"
    )


def _update_apply_confirmed(args: list[str]) -> bool:
    for arg in args:
        raw = arg.strip()
        value = _canonical_value(arg)
        if value in {"confirm", "confirmed", "yes", "y", "true", "1", "prompt"}:
            return True
        if raw in {"確認", "はい", "適用"}:
            return True
    return False



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
        "command_display": "command_display_mode",
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


def _format_login_compact(report: dict[str, Any], *, lang: str) -> str:
    return format_login_flow_compact(report, lang=lang)


def _handle_local_llm_command(
    args: list[str],
    *,
    callbacks: InteractiveCallbacks,
    config: dict[str, object],
    options: InteractiveOptions,
    provider: str,
    lang: str,
    output_stream: TextIO,
    interactive_tty: bool,
    color: str,
) -> dict[str, object]:
    report = callbacks.providers()
    local_llm = report.get("local_llm") if isinstance(report.get("local_llm"), dict) else {}
    action = _canonical_value(args[0]) if args else ""
    if action in {"use", "on", "enable", "使う", "有効", "利用"}:
        return _enable_detected_local_llm(
            callbacks=callbacks,
            config=config,
            options=options,
            lang=lang,
            output_stream=output_stream,
            interactive_tty=interactive_tty,
            color=color,
        )
    if action in {"ollama", "lmstudio", "openai_compatible_local"}:
        target = "lmstudio" if action in {"lmstudio", "openai_compatible_local"} else "ollama"
        _present_screen(
            output_stream,
            _format_local_llm_launch_hint(report, lang=lang, target=target),
            title="YonerAI / ローカルLLM" if lang == "ja" else "YonerAI / Local LLM",
            color=color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    local_already_enabled = config.get("local_llm_enabled") is True and provider == "local"
    if (
        not args
        and interactive_tty
        and local_llm.get("status") == "detected"
        and not local_already_enabled
    ):
        opened, selection = open_choice_dialog(
            title="YonerAI / ローカルLLM" if lang == "ja" else "YonerAI / Local LLM",
            text=(
                "ローカルLLMを検出しました。どうしますか。"
                if lang == "ja"
                else "A local LLM was detected. What do you want to do?"
            ),
            values=[
                ("use", "今すぐ使う" if lang == "ja" else "Use now"),
                ("details", "状態を見る" if lang == "ja" else "Show details"),
            ],
            ok_text="開く" if lang == "ja" else "Open",
            cancel_text="閉じる" if lang == "ja" else "Close",
        )
        if selection == "use":
            return _enable_detected_local_llm(
                callbacks=callbacks,
                config=config,
                options=options,
                lang=lang,
                output_stream=output_stream,
                interactive_tty=interactive_tty,
                color=color,
            )
        if opened and selection is None:
            return {}
    if not args and interactive_tty and local_llm.get("status") != "detected":
        launch_choices = _local_llm_launch_choices(local_llm, lang=lang)
        if launch_choices:
            opened, selection = open_choice_dialog(
                title="YonerAI / ローカルLLM" if lang == "ja" else "YonerAI / Local LLM",
                text=(
                    "まだローカルLLMに接続できません。案内したい候補を選んでください。"
                    if lang == "ja"
                    else "No local LLM is ready yet. Choose the setup path you want to open."
                ),
                values=launch_choices,
                ok_text="開く" if lang == "ja" else "Open",
                cancel_text="閉じる" if lang == "ja" else "Close",
            )
            if selection in {"ollama", "lmstudio"}:
                _present_screen(
                    output_stream,
                    _format_local_llm_launch_hint(report, lang=lang, target=selection),
                    title="YonerAI / ローカルLLM" if lang == "ja" else "YonerAI / Local LLM",
                    color=color,
                    theme=str(config.get("theme") or "auto"),
                    interactive_tty=interactive_tty,
                )
                return {}
            if opened and selection is None:
                return {}
    _present_screen(
        output_stream,
        _format_local_llm_quickstart(
            report,
            lang=lang,
            provider=provider,
            enabled=config.get("local_llm_enabled") is True and provider == "local",
        ),
        title="YonerAI / ローカルLLM" if lang == "ja" else "YonerAI / Local LLM",
        color=color,
        theme=str(config.get("theme") or "auto"),
        interactive_tty=interactive_tty,
    )
    return {}


def _enable_detected_local_llm(
    *,
    callbacks: InteractiveCallbacks,
    config: dict[str, object],
    options: InteractiveOptions,
    lang: str,
    output_stream: TextIO,
    interactive_tty: bool,
    color: str,
) -> dict[str, object]:
    report = callbacks.providers()
    local_llm = report.get("local_llm") if isinstance(report.get("local_llm"), dict) else {}
    if local_llm.get("status") != "detected":
        _present_screen(
            output_stream,
            _format_local_llm_quickstart(
                report,
                lang=lang,
                provider=str(config.get("provider_preference") or "auto"),
                enabled=False,
            ),
            title="YonerAI / ローカルLLM" if lang == "ja" else "YonerAI / Local LLM",
            color=color,
            theme=str(config.get("theme") or "auto"),
            interactive_tty=interactive_tty,
        )
        return {}
    try:
        _set_config_values(
            config,
            {
                "provider_preference": "local",
                "local_llm_enabled": True,
            },
            options.config_path,
        )
    except ConfigError as exc:
        _write(output_stream, _config_error(lang, exc))
        return {}
    _present_screen(
        output_stream,
        _format_local_llm_quickstart(
            callbacks.providers(),
            lang=lang,
            provider="local",
            enabled=True,
        ),
        title="YonerAI / ローカルLLM" if lang == "ja" else "YonerAI / Local LLM",
        color=color,
        theme=str(config.get("theme") or "auto"),
        interactive_tty=interactive_tty,
    )
    return {"provider": "local"}


def _format_local_llm_quickstart(
    report: dict[str, Any],
    *,
    lang: str,
    provider: str,
    enabled: bool,
) -> str:
    local_llm = report.get("local_llm") if isinstance(report.get("local_llm"), dict) else {}
    detected = str(local_llm.get("status") or "unknown")
    detected_label = _safe(local_llm.get("detected_label") or local_llm.get("endpoint_label") or "not-detected")
    endpoint = _safe(local_llm.get("endpoint_label") or "not-detected")
    provider_state = _provider_state(report, "local")
    if lang == "ja":
        if enabled and provider == "local":
            state = "使用中"
        elif detected == "detected":
            state = "検出済み"
        elif detected == "blocked":
            state = "拒否"
        else:
            state = _state_label(provider_state, lang=lang)
    else:
        if enabled and provider == "local":
            state = "active"
        elif detected == "detected":
            state = "detected"
        elif detected == "blocked":
            state = "blocked"
        else:
            state = _state_label(provider_state, lang=lang)
    probes = local_llm.get("probes") if isinstance(local_llm.get("probes"), list) else []
    installed_apps = local_llm.get("installed_apps") if isinstance(local_llm.get("installed_apps"), list) else []
    if lang == "ja":
        lines = ["ローカルLLM"]
        lines.append(f"  状態: {state}")
        detected_line = {
            "detected": f"  検出: {detected_label}",
            "blocked": "  検出: 拒否",
        }.get(detected, "  検出: 未検出")
        lines.append(detected_line)
        if detected == "detected":
            lines.append(f"  現在: {detected_label} / {endpoint}")
            lines.append("  次: そのまま話す" if enabled else "  次: /ローカルLLM 使う")
        elif detected == "blocked":
            lines.append("  現在: loopback 以外の URL は拒否します")
            lines.append("  許可: localhost / 127.0.0.1 / ::1")
        else:
            lines.append("  現在: まだ使えるサーバーがありません")
        app_labels = [
            _safe(app.get("label") or "")
            for app in installed_apps
            if isinstance(app, dict) and app.get("installed") is True and _safe(app.get("label") or "")
        ]
        if app_labels:
            lines.append(f"  候補: {', '.join(app_labels[:2])}")
        if detected != "detected":
            lines.append("  次: Ollama か LM Studio を起動して /ローカルLLM")
        lines.append("  個別案内: /ローカルLLM ollama / lmstudio")
        lines.append("  境界: 外部API送信なし / key保存なし / 自動インストールなし")
        lines.append("")
        return "\n".join(lines)

    lines = ["Local LLM"]
    lines.append(f"  now: {state}")
    if detected == "detected":
        lines.append(f"  current: {detected_label} / {endpoint}")
        if enabled:
            lines.append("  action: type normally")
        else:
            lines.append("  action: /local-llm use")
    elif detected == "blocked":
        lines.append("  current: non-loopback URLs are rejected")
        lines.append("  allowlist: localhost / 127.0.0.1 / ::1")
    else:
        lines.append("  current: no local server yet")
    app_labels = [
        _safe(app.get("label") or "")
        for app in installed_apps
        if isinstance(app, dict) and app.get("installed") is True and _safe(app.get("label") or "")
    ]
    if app_labels:
        lines.append(f"  candidates: {', '.join(app_labels[:2])}")
    if detected != "detected":
        lines.append("  action: start Ollama or LM Studio, then run /local-llm")
    lines.append("  per-app guide: /local-llm ollama / lmstudio")
    lines.append("  boundaries: no external API call / no key storage / no auto-install")
    lines.append("")
    return "\n".join(lines)


def _local_llm_launch_choices(local_llm: dict[str, Any], *, lang: str) -> list[tuple[str, str]]:
    installed_apps = local_llm.get("installed_apps") if isinstance(local_llm.get("installed_apps"), list) else []
    choices: list[tuple[str, str]] = []
    for app in installed_apps:
        if not isinstance(app, dict) or app.get("installed") is not True:
            continue
        provider = str(app.get("provider") or "")
        if provider == "ollama":
            choices.append(("ollama", "Ollama の案内" if lang == "ja" else "Ollama setup"))
        elif provider == "openai_compatible_local":
            choices.append(("lmstudio", "LM Studio の案内" if lang == "ja" else "LM Studio setup"))
    return choices


def _format_local_llm_launch_hint(
    report: dict[str, Any],
    *,
    lang: str,
    target: str,
) -> str:
    local_llm = report.get("local_llm") if isinstance(report.get("local_llm"), dict) else {}
    probes = local_llm.get("probes") if isinstance(local_llm.get("probes"), list) else []
    installed_apps = local_llm.get("installed_apps") if isinstance(local_llm.get("installed_apps"), list) else []
    is_lmstudio = target == "lmstudio"
    provider_id = "openai_compatible_local" if is_lmstudio else "ollama"
    title_ja = "LM Studio 接続案内" if is_lmstudio else "Ollama 接続案内"
    title_en = "LM Studio setup" if is_lmstudio else "Ollama setup"
    endpoint = "http://127.0.0.1:1234/v1" if is_lmstudio else "http://127.0.0.1:11434"
    probe = next(
        (
            item for item in probes
            if isinstance(item, dict) and str(item.get("provider") or "") == provider_id
        ),
        None,
    )
    installed = any(
        isinstance(app, dict)
        and str(app.get("provider") or "") == provider_id
        and app.get("installed") is True
        for app in installed_apps
    )
    probe_state = str(probe.get("status") or "unavailable") if isinstance(probe, dict) else "unavailable"
    if lang == "ja":
        lines = [title_ja]
        lines.append(f"  アプリ: {'見つかりました' if installed else 'まだ見つかっていません'}")
        lines.append(f"  応答: {_local_llm_probe_state_ja(probe_state, _safe(probe.get('reason') or '')) if isinstance(probe, dict) else '未確認'}")
        lines.append(f"  endpoint: {endpoint}")
        if probe_state == 'detected':
            lines.append("  次: /ローカルLLM 使う")
        elif is_lmstudio:
            lines.append("  次: LM Studio を開き、ローカルサーバーを ON にしてから /ローカルLLM")
        else:
            lines.append("  次: Ollama を起動してから /ローカルLLM")
        lines.append("  境界: 外部URL接続なし / key保存なし / 自動インストールなし")
        lines.append("")
        return "\n".join(lines)
    lines = [title_en]
    lines.append(f"  app: {'detected' if installed else 'not detected'}")
    lines.append(f"  probe: {_local_llm_probe_state_en(probe_state, _safe(probe.get('reason') or '')) if isinstance(probe, dict) else 'not checked'}")
    lines.append(f"  endpoint: {endpoint}")
    if probe_state == "detected":
        lines.append("  next: /local-llm use")
    elif is_lmstudio:
        lines.append("  next: open LM Studio, enable the local server, then run /local-llm")
    else:
        lines.append("  next: start Ollama, then run /local-llm")
    lines.append("  non_actions: no external URL, no key storage, no model auto-install")
    lines.append("")
    return "\n".join(lines)


def _local_llm_probe_lines(probes: list[object], *, lang: str) -> list[str]:
    entries = [probe for probe in probes if isinstance(probe, dict)]
    if not entries:
        return []
    lines = ["  候補状態:" if lang == "ja" else "  candidates:"]
    for probe in entries[:2]:
        label = _safe(probe.get("label") or probe.get("provider") or "local")
        endpoint = _safe(probe.get("endpoint_label") or "")
        status = str(probe.get("status") or "unknown")
        reason = _safe(probe.get("reason") or "")
        if lang == "ja":
            state = _local_llm_probe_state_ja(status, reason)
            lines.append(f"    - {label}: {state}{f' / {endpoint}' if endpoint else ''}")
        else:
            state = _local_llm_probe_state_en(status, reason)
            lines.append(f"    - {label}: {state}{f' / {endpoint}' if endpoint else ''}")
    return lines


def _local_llm_installed_app_lines(installed_apps: list[object], *, lang: str) -> list[str]:
    labels = [
        _safe(app.get("label") or "")
        for app in installed_apps
        if isinstance(app, dict) and app.get("installed") is True
    ]
    labels = [label for label in labels if label]
    if not labels:
        return []
    joined = " / ".join(labels[:2])
    if lang == "ja":
        return [f"  アプリ検出: {joined}"]
    return [f"  installed apps: {joined}"]


def _local_llm_probe_state_ja(status: str, reason: str) -> str:
    if status == "detected":
        return "検出済み"
    if status == "blocked":
        return "拒否"
    if reason == "connection_failed":
        return "未起動"
    if reason.startswith("http_status_"):
        return f"応答ありだが未対応 ({reason.replace('http_status_', 'HTTP ')})"
    if reason == "invalid_json":
        return "応答ありだが形式不明"
    return "未検出"


def _local_llm_probe_state_en(status: str, reason: str) -> str:
    if status == "detected":
        return "detected"
    if status == "blocked":
        return "blocked"
    if reason == "connection_failed":
        return "not running"
    if reason.startswith("http_status_"):
        return f"responded but unsupported ({reason.replace('http_status_', 'HTTP ')})"
    if reason == "invalid_json":
        return "responded but unknown shape"
    return "not detected"




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
                "local -> cloud 記憶同期は public runtime では承認必須のままで、無効化できません。\n"
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


def _format_sync_action_report(report: dict[str, Any], *, lang: str, color: str) -> str:
    from yonerai_cli.commands.sync import format_sync_pretty_v2

    return format_sync_pretty_v2(report, lang=lang, color=color)


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
            live=_effective_live(live, config, provider=provider),
            lang=lang,
            provider_report=provider_report,
        )
    if category == "language":
        return _format_settings_language(config, lang=lang)
    if category == "display":
        return _format_settings_display(config, lang=lang)
    if category == "providers":
        return _format_providers(provider_report or {}, lang=lang)
    if category == "models":
        return _format_models(config, provider_report or {}, lang=lang)
    if category == "safety":
        return _format_safety(config, live=_effective_live(live, config, provider=provider), lang=lang)
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
        live=_effective_live(live, config, provider=provider),
        lang=lang,
        provider_report=provider_report,
    )


def _settings_category_dialog_values(lang: str) -> list[tuple[str, str]]:
    if lang == "ja":
        return [
            ("language", "表示言語"),
            ("display", "表示方式"),
            ("providers", "提供元"),
            ("models", "モデル"),
            ("safety", "安全"),
            ("memory", "記憶"),
            ("update", "更新"),
            ("auth", "認証"),
            ("privacy", "プライバシー"),
            ("policy", "ポリシー"),
        ]
    return [
        ("language", "Language"),
        ("providers", "Providers"),
        ("models", "Model"),
        ("safety", "Safety"),
        ("memory", "Memory"),
        ("update", "Update"),
        ("auth", "Auth"),
        ("privacy", "Privacy"),
        ("policy", "Policy"),
    ]


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


def _clear_tty_screen(stream: TextIO) -> None:
    if not _is_interactive(stream):
        return
    stream.write(f"{ESC}[2J{ESC}[H")
    stream.flush()


def _present_screen(
    stream: TextIO,
    body: str,
    *,
    title: str,
    color: str,
    theme: str,
    interactive_tty: bool,
    show_header: bool = False,
    prelude: str | None = None,
) -> None:
    if not interactive_tty:
        if prelude:
            _write(stream, prelude if prelude.endswith("\n") else prelude + "\n")
        _write(stream, body)
        return
    _clear_tty_screen(stream)
    header = render_startup_home_header(color=color, stream=stream, theme=theme, compact=True) if show_header else ""
    if header.strip():
        render_text_block(header if header.endswith("\n") else header + "\n", stream=stream, color=color)
        stream.write("\n")
    if prelude:
        render_text_block(prelude if prelude.endswith("\n") else prelude + "\n", stream=stream, color=color)
        stream.write("\n")
    render_panel(body, title=title, stream=stream, color=color)
    stream.flush()


def _startup_prelude(
    *,
    config: dict[str, object],
    lang: str,
    update_notice: str | None,
    auth_report: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = []
    if update_notice:
        lines.append(update_notice.strip())
    if config.get("_config_load_error") is True:
        if lang == "ja":
            lines.append(
                "設定を読み込めなかったため、既定値で起動しました。"
                " 必要なら `/設定` で保存し直すか、壊れた設定を退避して再起動してください。"
            )
        else:
            lines.append(
                "The local config could not be read, so YonerAI started with defaults."
                " Use `/settings` to save a fresh config or move the broken config aside and restart."
            )
    auth_report = auth_report or build_google_auth_status(
        config,
        claim_path=str(config.get("_runtime_config_path") or "") or None,
    )
    state = str(auth_report.get("staging_auth_state") or "unauthenticated")
    if bool(auth_report.get("staging_login_available")) and state in {"unauthenticated", "expired", "revoked"}:
        if lang == "ja":
            lines.append(
                "ログイン案内: `/ログイン` または `/login` で α/staging を試せます。"
                " ローカルだけならそのまま話せます。"
            )
        else:
            lines.append(
                "Login hint: use `/login` or `/ログイン` for alpha/staging."
                " Local-only chat still works immediately."
            )
    return "\n".join(line for line in lines if line).strip()


def _format_chat_turn(
    user_text: str,
    report: dict[str, Any],
    *,
    lang: str,
    compact: bool = False,
) -> str:
    if not compact:
        return _format_chat_response(report, lang=lang)

    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    auto = report.get("auto") if isinstance(report.get("auto"), dict) else {}
    provider = report.get("provider") if isinstance(report.get("provider"), dict) else {}
    response = report.get("response") if isinstance(report.get("response"), dict) else {}
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    output = _safe(response.get("output_text") or error.get("message") or "no output")
    run_id = _safe(run.get("run_id") or run.get("id") or "none")
    provider_id = provider.get("provider_id") or auto.get("provider_id") or auto.get("provider") or "unknown"
    memory_line = _format_chat_memory_line(report, lang=lang)
    memory_used = "memory_used=" in memory_line

    if lang == "ja":
        lines = [
            f"経路: {_route_label(auto.get('route'), lang='ja')} / 提供元: {_provider_label(provider_id, lang='ja')} / run_id: {run_id}",
        ]
        if auto.get("approval_required"):
            lines.append("確認: この内容は承認が必要です。")
        if memory_used:
            lines.append(memory_line)
        lines.extend(("", output))
        return "\n".join(lines)

    lines = [
        f"Route: {_safe(auto.get('route') or 'unknown')} / Provider: {_provider_label(provider_id, lang='en')} / run_id: {run_id}",
    ]
    if auto.get("approval_required"):
        lines.append("Approval: required for this request.")
    if memory_used:
        lines.append(memory_line)
    lines.extend(("", output))
    return "\n".join(lines)


def _format_chat_view(chat_blocks: list[str], *, lang: str) -> str:
    body = "\n\n".join(block.strip() for block in chat_blocks if block.strip())
    if body:
        return body.rstrip()
    return (
        "そのまま入力して会話します。/ でコマンド候補を開きます。"
        if lang == "ja"
        else "Type normally to chat. Use / to open commands."
    )


def _format_interactive_update_overview(
    stable_report: dict[str, Any],
    alpha_report: dict[str, Any],
    *,
    lang: str,
) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "更新",
                f"  現在: {_safe(stable_report.get('current_version') or alpha_report.get('current_version') or '不明')}",
                f"  安定版: {_safe(stable_report.get('latest_manifest_version') or stable_report.get('latest_stable') or '不明')} / "
                f"{'更新あり' if stable_report.get('update_available') else '最新'}",
                f"  ベータ版: {_safe(alpha_report.get('latest_manifest_version') or '不明')} / "
                f"{'更新あり' if alpha_report.get('update_available') else '最新'}",
                "",
                "  1. 安定版を確認   → /更新 安定版 (/update stable)",
                "  2. ベータ版を確認 → /更新 ベータ版 (/update beta)",
                "  3. 安定版を適用   → /更新 適用 安定版 確認 (/update apply stable confirm)",
                "  4. ベータ版を適用 → /更新 適用 ベータ版 確認 (/update apply beta confirm)",
                "",
                "  自動適用なし / 強制サイレント更新なし / 失敗時は repair 案内だけ出します。",
            )
        )
    return "\n".join(
        (
            "Update",
            f"  current: {_safe(stable_report.get('current_version') or alpha_report.get('current_version') or 'unknown')}",
            f"  stable: {_safe(stable_report.get('latest_manifest_version') or stable_report.get('latest_stable') or 'unknown')} / "
            f"{'update available' if stable_report.get('update_available') else 'current'}",
            f"  beta: {_safe(alpha_report.get('latest_manifest_version') or 'unknown')} / "
            f"{'update available' if alpha_report.get('update_available') else 'current'}",
            "",
            "  1. Check stable  -> /update stable (/更新 安定版)",
            "  2. Check beta    -> /update beta (/更新 ベータ版)",
            "  3. Apply stable  -> /update apply stable confirm (/更新 適用 安定版 確認)",
            "  4. Apply beta    -> /update apply beta confirm (/更新 適用 ベータ版 確認)",
            "",
            "  No auto-apply, no forced silent update, and repair guidance only on failure.",
        )
    )


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
