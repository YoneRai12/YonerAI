from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TextIO

from yonerai_cli.config import (
    APPROVAL_MODES,
    ConfigError,
    FILE_ACCESS_MODES,
    PROVIDER_PREFERENCES,
    build_config_report,
    default_config_path,
    load_cli_config,
    save_cli_config,
    set_cli_config_value,
)


INTERACTIVE_SCHEMA_VERSION = "yonerai-interactive-cli/v0.4"
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
    "/タスク": "/tasks",
    "/tasks": "/tasks",
    "/表示": "/show",
    "/show": "/show",
    "/エージェント": "/agents",
    "/agents": "/agents",
    "/agent": "/agents",
    "/ローカルllm": "/local-llm",
    "/ローカルLLM": "/local-llm",
    "/local-llm": "/local-llm",
    "/llm": "/local-llm",
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
    "オープンai互換": "openai-compatible",
    "openai互換": "openai-compatible",
    "アンソロピック": "anthropic",
    "ジェミニ": "gemini",
    "確認": "prompt",
    "毎回確認": "prompt",
    "拒否": "deny",
    "ワークスペース内のみ": "workspace_only",
    "無効": "disabled",
    "オン": "on",
    "有効": "on",
    "記録オン": "on",
    "オフ": "off",
    "記録オフ": "off",
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
    ledger_path = _resolve_ledger_path(config, options)

    if not options.script and not _is_interactive(input_stream):
        _write(output_stream, _non_tty_fallback(lang))
        return 0

    last_report: dict[str, Any] | None = None
    _write(
        output_stream,
        _welcome(
            lang,
            provider=provider,
            live=live,
            config_exists=config_exists,
            config=config,
            ledger_path=ledger_path,
        ),
    )
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
                ledger_path=ledger_path,
                last_report=last_report,
                output_stream=output_stream,
            )
            provider = command_result.get("provider", provider)
            lang = command_result.get("lang", lang)
            live = bool(command_result.get("live", live))
            ledger_path = command_result.get("ledger_path", ledger_path)
            if command_result.get("exit"):
                _write(output_stream, _bye(lang))
                return 0
            continue

        report = callbacks.ask_auto(text, provider, live, ledger_path, lang)
        last_report = report
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
    ledger_path: str | None,
    last_report: dict[str, Any] | None,
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
    if command == "/local-llm":
        _write(output_stream, _format_local_llm_setup(callbacks.providers(), lang=lang))
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
            new_lang = _set_config(config, "language", value, options.config_path)
        except ConfigError as exc:
            _write(output_stream, _config_error(lang, exc))
            return {}
        _write(output_stream, _changed_message("language", new_lang["language"], lang=str(new_lang["language"])))
        return {"lang": str(new_lang["language"])}
    if command == "/provider" and args:
        value = _canonical_value(args[0])
        if value not in PROVIDER_PREFERENCES:
            _write(output_stream, _invalid(lang))
            return {}
        try:
            new_config = _set_config(config, "provider", value, options.config_path)
        except ConfigError as exc:
            _write(output_stream, _config_error(lang, exc))
            return {}
        new_provider = str(new_config["provider_preference"])
        _write(output_stream, _changed_message("provider", new_provider, lang=lang))
        return {"provider": new_provider}
    if command == "/approval" and args:
        value = _canonical_value(args[0])
        if value not in APPROVAL_MODES:
            _write(output_stream, _invalid(lang))
            return {}
        try:
            new_config = _set_config(config, "approval", value, options.config_path)
        except ConfigError as exc:
            _write(output_stream, _config_error(lang, exc))
            return {}
        _write(output_stream, _changed_message("approval", new_config["approval_mode"], lang=lang))
        return {}
    if command == "/file-access" and args:
        value = _canonical_value(args[0])
        if value not in FILE_ACCESS_MODES:
            _write(output_stream, _invalid(lang))
            return {}
        try:
            new_config = _set_config(config, "file_access", value, options.config_path)
        except ConfigError as exc:
            _write(output_stream, _config_error(lang, exc))
            return {}
        _write(output_stream, _changed_message("file_access", new_config["file_access_mode"], lang=lang))
        return {}
    if command == "/ledger" and args:
        value = _canonical_value(args[0])
        if value not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
            _write(output_stream, _invalid(lang))
            return {}
        try:
            new_config = _set_config(config, "ledger", value, options.config_path)
        except ConfigError as exc:
            _write(output_stream, _config_error(lang, exc))
            return {}
        _write(output_stream, _changed_message("ledger", new_config["ledger_enabled"], lang=lang))
        return {"ledger_path": _resolve_ledger_path(new_config, options)}
    if command == "/live-provider" and args:
        value = _canonical_value(args[0])
        if value not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
            _write(output_stream, _invalid(lang))
            return {}
        try:
            new_config = _set_config(config, "live_provider", value, options.config_path)
        except ConfigError as exc:
            _write(output_stream, _config_error(lang, exc))
            return {}
        new_live = bool(new_config["live_provider_enabled"])
        _write(output_stream, _changed_message("live_provider", new_live, lang=lang))
        return {"live": new_live}
    if command == "/network" and args:
        value = _canonical_value(args[0])
        if value not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
            _write(output_stream, _invalid(lang))
            return {}
        try:
            new_config = _set_config(config, "network", value, options.config_path)
        except ConfigError as exc:
            _write(output_stream, _config_error(lang, exc))
            return {}
        _write(output_stream, _changed_message("network", new_config["network_enabled"], lang=lang))
        return {}
    _write(output_stream, _unknown(lang))
    return {}


def _set_config(config: dict[str, object], key: str, value: str, config_path: str | None) -> dict[str, object]:
    updated = set_cli_config_value(key, value, config_path)
    config.clear()
    config.update(updated)
    return updated


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
            if selected not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
                _write(output_stream, _invalid(lang))
                return {}
            new_config = _set_config(config, "ledger", selected, options.config_path)
            _write(output_stream, _changed_message("ledger", new_config["ledger_enabled"], lang=lang))
            return {"ledger_path": _resolve_ledger_path(new_config, options)}
        if number == "6":
            selected = value or ("off" if config.get("live_provider_enabled") is True else "on")
            if selected not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
                _write(output_stream, _invalid(lang))
                return {}
            new_config = _set_config(config, "live_provider", selected, options.config_path)
            new_live = bool(new_config["live_provider_enabled"])
            _write(output_stream, _changed_message("live_provider", new_live, lang=lang))
            return {"live": new_live}
        if number == "7":
            selected = value or ("off" if config.get("network_enabled") is True else "on")
            if selected not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
                _write(output_stream, _invalid(lang))
                return {}
            new_config = _set_config(config, "network", selected, options.config_path)
            _write(output_stream, _changed_message("network", new_config["network_enabled"], lang=lang))
            return {}
    except ConfigError as exc:
        _write(output_stream, _config_error(lang, exc))
        return {}
    _write(output_stream, _settings_selection_help(lang))
    return {"provider": provider, "live": live}


def _resolve_ledger_path(config: dict[str, object], options: InteractiveOptions) -> str | None:
    if options.ledger_path:
        return options.ledger_path
    if config.get("ledger_enabled") is not True:
        return None
    return str(_default_ledger_path(options.config_path))


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
                "YonerAI ミッションコントロール",
                f"  実行ID（run_id）: {_safe(run.get('run_id') or 'なし')}",
                f"  経路（処理方法）: {_route_label(auto.get('route'), lang='ja')}",
                f"  プロバイダー（AI接続先）: {_provider_label(provider.get('provider_id') or auto.get('provider_id'), lang='ja')}",
                f"  ローカルノード: {_local_node_state(report, lang='ja')}",
                f"  履歴: {_ledger_state_from_report(report, lang='ja')}",
                f"  安全: ネットワーク初期値オフ / ファイルはワークスペース内のみ / 任意シェル無効",
                f"  承認: {'必要' if auto.get('approval_required') else '不要'}",
                "",
                _format_task_progress(report, lang="ja").rstrip(),
                _format_agents(report, lang="ja").rstrip(),
                "",
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
            f"  local_node: {_local_node_state(report, lang='en')}",
            f"  ledger: {_ledger_state_from_report(report, lang='en')}",
            f"  safety: network off by default / workspace file only / arbitrary shell disabled",
            f"  approval: {'required' if auto.get('approval_required') else 'not required'}",
            "",
            _format_task_progress(report, lang="en").rstrip(),
            _format_agents(report, lang="en").rstrip(),
            "",
            f"  output: {_safe(output)}",
            "",
        )
    )


def _format_task_progress(report: dict[str, Any], *, lang: str) -> str:
    progress = report.get("task_progress") if isinstance(report.get("task_progress"), dict) else {}
    steps = progress.get("steps") if isinstance(progress.get("steps"), list) else []
    if not steps:
        return "進行状況: まだありません\n" if lang == "ja" else "Task progress: none yet\n"
    if lang == "ja":
        lines = ["進行状況"]
        for step in steps:
            if not isinstance(step, dict):
                continue
            lines.append(
                f"  {_progress_state_label(step.get('state'), lang='ja')}: "
                f"{_progress_step_label(step.get('id'), lang='ja')} - "
                f"{_progress_summary_label(step.get('id'), step.get('summary'), lang='ja')}"
            )
        lines.append("")
        return "\n".join(lines)
    lines = ["Task progress"]
    for step in steps:
        if isinstance(step, dict):
            lines.append(f"  {step.get('state')}: {_safe(step.get('id') or 'step')} - {_safe(step.get('summary') or '')}")
    lines.append("")
    return "\n".join(lines)


def _format_tasks(last_report: dict[str, Any] | None, runs_report: dict[str, Any], *, lang: str) -> str:
    runs = runs_report.get("runs") if isinstance(runs_report.get("runs"), list) else []
    if lang == "ja":
        lines = ["タスク"]
        if isinstance(last_report, dict):
            run = last_report.get("run") if isinstance(last_report.get("run"), dict) else {}
            lines.append(f"  現在/直近: run_id={_safe(run.get('run_id') or 'なし')}")
            lines.append(_format_task_progress(last_report, lang="ja").rstrip())
        else:
            lines.append("  現在/直近: まだ実行がありません。通常文を入力すると `ask --auto` 経路でタスクを作ります。")
        if runs:
            lines.append("  最近の履歴")
            for run in runs[:5]:
                if isinstance(run, dict):
                    lines.append(
                        f"    run_id={_safe(run.get('run_id') or 'なし')} "
                        f"状態={_run_status_label(run.get('status'), lang='ja')} "
                        f"進行イベント={len(_run_progress_events(run))}"
                    )
        else:
            lines.append("  最近の履歴: ローカル履歴が未設定、または記録がありません。")
        lines.append("  サブエージェント: 実行はしません。計画表示だけです。")
        lines.append("")
        return "\n".join(lines)

    lines = ["Tasks"]
    if isinstance(last_report, dict):
        run = last_report.get("run") if isinstance(last_report.get("run"), dict) else {}
        lines.append(f"  current/recent: run_id={_safe(run.get('run_id') or 'none')}")
        lines.append(_format_task_progress(last_report, lang="en").rstrip())
    else:
        lines.append("  current/recent: no run yet. Type a message to create an ask --auto task.")
    if runs:
        lines.append("  recent history")
        for run in runs[:5]:
            if isinstance(run, dict):
                lines.append(
                    f"    run_id={_safe(run.get('run_id') or 'none')} "
                    f"status={_safe(run.get('status') or 'unknown')} "
                    f"progress_events={len(_run_progress_events(run))}"
                )
    else:
        lines.append("  recent history: local ledger is not configured or has no runs.")
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
                    "  実サブエージェントはまだ起動しません。公開安全な計画表示だけです。",
                    "",
                )
            )
        return "Agent plan\n  No run yet. This is a public-safe plan display; no subagents are started.\n"
    if lang == "ja":
        lines = ["エージェント計画"]
        if not reviewer.get("enabled"):
            lines.append("  今回は複数担当の計画は不要です。単純なローカル/モック経路で処理します。")
        for item in subtasks:
            if isinstance(item, dict):
                lines.append(
                    f"  {_agent_role_label(item.get('role'), lang='ja')}: "
                    f"{_safe(item.get('goal') or '')}"
                )
        checks = (reviewer.get("reviewer") or {}).get("checks") if isinstance(reviewer.get("reviewer"), dict) else []
        if checks:
            lines.append("  レビュー: " + ", ".join(_safe(check) for check in checks[:5]))
        lines.append("  実サブエージェント起動: なし（計画表示のみ）")
        lines.append("")
        return "\n".join(lines)
    lines = ["Agent plan"]
    if not reviewer.get("enabled"):
        lines.append("  multi-role plan: not required for this run")
    for item in subtasks:
        if isinstance(item, dict):
            lines.append(f"  {item.get('role')}: {_safe(item.get('goal') or '')}")
    lines.append("  subagents_started: false")
    lines.append("")
    return "\n".join(lines)


def _format_run_progress(run: dict[str, Any], *, lang: str) -> str:
    progress_events = _run_progress_events(run)
    if not progress_events:
        return "進行状況: 記録なし\n" if lang == "ja" else "Task progress: not recorded\n"
    if lang == "ja":
        lines = ["進行状況"]
        for event in progress_events:
            step = str(event.get("name") or "").removeprefix("task_progress_")
            lines.append(
                f"  {_progress_state_label(event.get('status'), lang='ja')}: "
                f"{_progress_step_label(step, lang='ja')} - {_progress_summary_label(step, event.get('summary'), lang='ja')}"
            )
        lines.append("")
        return "\n".join(lines)
    lines = ["Task progress"]
    for event in progress_events:
        step = str(event.get("name") or "").removeprefix("task_progress_")
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
    if ledger.get("file_backed"):
        return "オン（ローカルのみ）" if lang == "ja" else "on local-only"
    if ledger.get("enabled"):
        return "オン（ローカルのみ）" if lang == "ja" else "on local-only"
    return "オフ（初期値）" if lang == "ja" else "off by default"


def _progress_step_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "step")
    labels = {
        "classify": "分類",
        "route": "経路選択",
        "provider_selection": "提供元選択",
        "execution": "実行",
        "review": "レビュー",
        "result": "結果",
    }
    return labels.get(str(value), _safe(value or "不明"))


def _progress_state_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "unknown")
    labels = {
        "pending": "待機",
        "running": "実行中",
        "done": "完了",
        "skipped": "スキップ",
        "blocked": "ブロック",
        "error": "エラー",
        "ok": "完了",
        "failed": "エラー",
    }
    return labels.get(str(value), _safe(value or "不明"))


def _progress_summary_label(step: object, summary: object, *, lang: str) -> str:
    text = _safe(summary or "")
    if lang != "ja":
        return text
    step_id = str(step)
    if step_id == "classify" and "difficulty=" in text:
        return text.replace("difficulty=instant", "難易度=即時").replace("difficulty=task", "難易度=タスク").replace(
            "difficulty=agent", "難易度=複雑"
        ).replace("privacy=public", "公開").replace("privacy=local_file", "ローカルファイル").replace("privacy=private", "非公開")
    if step_id == "route" and "route=" in text:
        return text.replace("route=instant_local", "経路=ローカル即時").replace("route=local_llm", "経路=ローカルLLM").replace(
            "route=cloud_contract_candidate", "経路=クラウド候補"
        ).replace("route=deny", "経路=拒否").replace("approval_required=false", "承認不要").replace(
            "approval_required=true", "承認必要"
        )
    if step_id == "provider_selection" and "provider=" in text:
        return text.replace("provider=mock", "提供元=モック").replace("provider=oracle-stub", "提供元=オラクルスタブ").replace(
            "provider=local", "提供元=ローカル"
        )
    if step_id == "execution":
        if text.startswith("executed route="):
            return "選択した安全な経路で実行しました"
        if text.startswith("execution skipped"):
            return "安全上、実行をスキップしました"
        if text.startswith("execution stopped"):
            return "実行を停止しました"
    if step_id == "review":
        if text.startswith("reviewer plan not required"):
            return "この経路ではレビュー計画は不要です"
        if text.startswith("subagents_planned="):
            return text.replace("subagents_planned=", "担当計画=").replace(" reviewer_required=true", " / レビューあり")
    if step_id == "result":
        if text.startswith("result returned"):
            return "秘匿済みの安全な結果を返しました"
        if text.startswith("blocked safely"):
            return "安全にブロックしました"
        if text.startswith("result unavailable"):
            return "結果は利用できません"
    return text


def _agent_role_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "agent")
    labels = {
        "planner": "計画係",
        "researcher": "調査係",
        "implementer": "実装係",
        "tester": "テスト係",
        "reviewer": "レビュー係",
        "executor": "実行係",
    }
    return labels.get(str(value), _safe(value or "担当"))


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
    ledger = "on" if values.get("ledger_enabled") else "off"
    if lang == "ja":
        return "\n".join(
            (
                "設定",
                "  1. 表示言語: " + _language_label(values["language"] or "ja", lang="ja"),
                "     変更: /選択 1 日本語 または /選択 1 英語",
                "  2. プロバイダー（AI接続先）: " + _provider_label(provider, lang="ja"),
                "     変更: /選択 2 自動|モック|ローカル|オープンAI互換|アンソロピック|ジェミニ",
                "  3. 承認（危険操作）: " + _approval_label(values["approval_mode"], lang="ja"),
                "     変更: /選択 3 確認 または /選択 3 拒否",
                "  4. ファイルアクセス（ファイル読み取り）: " + _file_access_label(values["file_access_mode"], lang="ja"),
                "     変更: /選択 4 ワークスペース内のみ または /選択 4 無効",
                "  5. 履歴記録（ローカル履歴）: " + ("オン（秘匿済みローカルJSONL）" if values.get("ledger_enabled") else "オフ（初期値）"),
                "     変更: /選択 5 オン または /選択 5 オフ",
                "  6. ライブ接続（外部/ローカル実行）: " + ("オン（明示許可）" if live else "オフ（初期値）"),
                "     変更: /選択 6 オン または /選択 6 オフ",
                "  7. ネットワーク（外部通信）: " + ("オン（明示許可）" if values["network_enabled"] else "オフ（初期値）"),
                "     変更: /選択 7 オン または /選択 7 オフ",
                "",
                "状態",
                f"  表示言語: {_language_label(values['language'] or 'ja', lang='ja')}",
                f"  プロバイダー（AI接続先）: {_provider_label(provider, lang='ja')}",
                f"  ローカルLLM（PC内モデル）: {_state_label(local_state, lang='ja')}",
                f"  承認（危険操作）: {_approval_label(values['approval_mode'], lang='ja')}",
                f"  ファイルアクセス（ファイル読み取り）: {_file_access_label(values['file_access_mode'], lang='ja')}",
                f"  履歴記録（ローカル履歴）: {ledger}",
                f"  ライブ接続（外部/ローカル実行）: {'オン（明示許可）' if live else 'オフ（初期値）'}",
                f"  ネットワーク（外部通信）: {'オン（明示許可）' if values['network_enabled'] else 'オフ（初期値）'}",
                "  秘密情報（APIキーなど）: 保存しません",
                "  ローカルパス（PC内の場所）: 出力しません",
                "  操作方法: 番号で変える場合は /選択 <番号> <値> を使います",
                "  ローカルLLM案内: /ローカルLLM",
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
            f"  ledger: {ledger}",
            f"  live_provider: {'on' if live else 'off'}",
            f"  network: {'on' if values['network_enabled'] else 'off'}",
            "  secrets: not stored",
            "  path: not printed",
            "  numbered selection: /select 1 en, /select 2 mock, /select 5 on, /select 6 off, /select 7 off",
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
                f"{_selector('provider', network_selected)} プロバイダーだけ許可（--liveで明示した時だけ）",
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
    title = "プロバイダー（AI接続先）" if lang == "ja" else "Providers"
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
    lines.append("  キー（秘密情報）: 表示しません。設定にも保存しません" if lang == "ja" else "  keys: redacted / not printed")
    if lang == "ja":
        lines.append("  ローカルLLM: localhost / 127.0.0.1 / ::1 だけを許可します")
        lines.append("  外部API: --live と provider別env opt-in がある時だけ呼びます")
    lines.append("")
    return "\n".join(_safe(line) for line in lines)


def _format_local_llm_setup(report: dict[str, Any], *, lang: str) -> str:
    local_state = _provider_state(report, "local")
    if lang == "ja":
        lines = (
            "ローカルLLMセットアップ",
            f"  現在の状態: {_state_label(local_state, lang='ja')}",
            "  対応形態: Ollama系 / LM Studio系 / OpenAI互換のローカルHTTP API",
            "  許可する接続先: localhost / 127.0.0.1 / ::1 のみ",
            "  例（Ollama）: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=ollama, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:11434",
            "  例（LM Studio）: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=lmstudio, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:1234/v1",
            "  使う: /提供元選択 ローカル。その後、この画面で通常文を入力します。",
            "  実行しないこと: 外部URL接続、APIキー保存、任意シェル実行、モデルの自動インストール",
            "",
        )
        return "\n".join(_safe(line) for line in lines)
    lines = (
        "Local LLM setup",
        f"  current_state: {local_state}",
        "  supported: Ollama-style / LM Studio-style / local OpenAI-compatible HTTP API",
        "  allowed_endpoint: localhost / 127.0.0.1 / ::1 only",
        "  Ollama example: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=ollama, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:11434",
        "  LM Studio example: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=lmstudio, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:1234/v1",
        "  use: /provider local or yonerai ask \"hello\" --provider local --live",
        "  not_performed: no external URL, no key storage, no arbitrary shell, no model installation",
        "",
    )
    return "\n".join(_safe(line) for line in lines)


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
    title = "実行履歴" if lang == "ja" else "Runs"
    lines = [title]
    for run in runs:
        if isinstance(run, dict):
            route = _run_route(run)
            provider = _run_provider(run)
            event_count = len(_run_progress_events(run))
            if lang == "ja":
                lines.append(
                    f"  実行ID（run_id）={run.get('run_id')}: {_run_status_label(run.get('status'), lang='ja')} "
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
        return ("実行が見つかりません\n" if lang == "ja" else "Run not found\n")
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    if lang == "ja":
        lines = [
            "実行",
            f"  実行ID（run_id）: {_safe(run.get('run_id') or 'なし')}",
            f"  状態: {_run_status_label(run.get('status'), lang='ja')}",
            f"  経路（処理方法）: {_route_label(_run_route(run), lang='ja')}",
            f"  プロバイダー（AI接続先）: {_provider_label(_run_provider(run), lang='ja')}",
            f"  タスク: {_safe(run.get('task_summary') or 'なし')}",
            "",
            _format_run_progress(run, lang="ja").rstrip(),
            _format_run_agents(run, lang="ja").rstrip(),
            "",
        ]
        return "\n".join(lines)
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
    safety = f"承認={_approval_label(config.get('approval_mode'), lang='ja')} / ファイル={_file_access_label(config.get('file_access_mode'), lang='ja')}"
    if lang == "ja":
        return "\n".join(
            (
                "YonerAI ミッションコントロール CLI",
                "日本語モード。/ヘルプ でコマンドを表示します。",
                "状態ヘッダー",
                f"  プロバイダー（AI接続先）: {_provider_label(provider, lang='ja')}",
                "  経路（処理方法）: 未実行",
                "  ローカルノード: 待機中（ローカル開発 / ループバック限定）",
                f"  履歴: {ledger}（秘匿済みローカル履歴）",
                f"  安全: {safety} / ネットワーク初期値オフ / 任意シェル無効",
                f"  ライブ接続: {'オン（明示許可）' if live else 'オフ（初期値）'} / 設定={'既存' if config_exists else '初期値'}",
                "使う: そのまま質問を書く / /設定 / /安全 / /タスク / /エージェント / /履歴 / /表示 <run_id>",
                "設定を変える: /選択 <番号> <値>",
                "",
            )
        )
    return "\n".join(
        (
            "YonerAI Mission Control CLI",
            "English mode. Type /help for commands.",
            f"provider={provider} route=not_run local_node=standby ledger={ledger_en} live={'on' if live else 'off'} config={'found' if config_exists else 'created/default'}",
            "Safety: network off / tools dry-run / workspace file only / arbitrary shell disabled / live providers off by default",
            "Use: type a message, /settings, /safety, /tasks, /agents, /runs, /show <run_id>",
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
                "  /タスク               現在/最近のタスク進行を見る",
                "  /エージェント         計画中の担当（計画係/レビュー係など）を見る",
                "  /履歴                 実行履歴を見る",
                "  /表示 <実行ID>        1件の実行を見る",
                "  /ローカルLLM          PC内モデルの接続方法を見る",
                "  /言語 日本語|英語     表示言語を変更",
                "  /提供元選択 自動|モック|ローカル|オープンAI互換|アンソロピック|ジェミニ",
                "  /承認 確認|拒否       危険操作の扱いを変更",
                "  /ファイル ワークスペース内のみ|無効",
                "  /履歴記録 オン|オフ    秘匿済みローカル履歴の記録を変更",
                "  /ライブ接続 オン|オフ  外部/ローカル実行の明示許可を変更",
                "  /ネットワーク オン|オフ 外部通信の明示許可を変更",
                "  /選択 <番号> <値>      設定画面の番号で変更",
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
            "  /tasks           Show current/recent task progress",
            "  /agents          Show planned agent/reviewer roles",
            "  /runs            Show run history",
            "  /show <run_id>   Show one run",
            "  /local-llm       Show local LLM loopback setup",
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
    return "値が不正です\n" if lang == "ja" else "Invalid value\n"


def _settings_selection_help(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "番号設定の形式が不正です。",
                "例: /選択 1 日本語",
                "例: /選択 2 モック",
                "例: /選択 5 オン",
                "例: /選択 6 オフ",
                "例: /選択 7 オフ",
                "",
            )
        )
    return "Invalid numbered setting. Examples: /select 1 en, /select 2 mock, /select 5 on, /select 6 off, /select 7 off\n"


def _config_error(lang: str, exc: ConfigError) -> str:
    message = _safe(str(exc) or "config error")
    if lang == "ja":
        return f"設定を保存できませんでした: {message}\n"
    return f"Could not save config: {message}\n"


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
        "cloud_contract_candidate": "クラウド候補（ローカル開発スタブ）",
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
        "blocked_by_loopback_policy": "ループバック以外のため拒否",
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
        "ledger": "履歴記録（ローカル履歴）",
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
    if value in APPROVAL_MODES:
        return _approval_label(value, lang=lang)
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
