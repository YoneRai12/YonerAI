from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from typing import Any

from yonerai_cli import __version__
from yonerai_cli.cli_dispatch import CliDispatchError, CliRuntimeHooks, dispatch_command
from yonerai_cli.commands import diagnostics as diagnostics_command
from yonerai_cli.commands.providers import build_providers_report as _build_interactive_providers_report
from yonerai_cli.commands.diagnostics import (
    DiagnosticsCommandError,
    _build_doctor_report,
    _build_start_report,
    _build_status_report,
    _prepare_trusted_cli_import_paths,
    _run_mcp_deny_policy_self_check,
    _run_redaction_self_check,
    _read_repo_version,
    _repo_root,
)
from yonerai_cli.screens.diagnostics import (
    _format_doctor_pretty,
    _format_status_pretty,
    _hybrid_node_relay_contract_rows,
    _print_doctor_pretty,
    _print_start_pretty,
    _print_status_pretty,
    _provider_setup_rows,
    _relay_status_rows,
)
from yonerai_cli.commands.hybrid import format_hybrid_pretty as _format_hybrid_pretty
from yonerai_cli.cli_parser import build_parser as build_cli_parser
from yonerai_cli.config import ConfigError, load_cli_config
from yonerai_cli.services import core_api_service
from yonerai_cli.services.core_api_service import (
    DEFAULT_API_ORIGIN,
    TOKEN_ENV,
    CoreApiServiceError,
    safe_http_error as _safe_http_error,
)
from yonerai_cli.services import interactive_service
from yonerai_cli.services import control_spine_callbacks
from yonerai_cli.services.interactive_service import InteractiveServiceError


class CliError(Exception):
    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def normalize_loopback_origin(origin: str) -> str:
    try:
        return core_api_service.normalize_loopback_origin(origin)
    except CoreApiServiceError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def request_json(method: str, origin: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return core_api_service.request_json(method, origin, path, body)
    except CoreApiServiceError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _run_public_mvp_smoke(*, json_output: bool = False, pretty: bool = False) -> int:
    try:
        _prepare_trusted_cli_import_paths()
        public_mvp_smoke = _load_public_mvp_smoke_module()
    except Exception as exc:
        raise DiagnosticsCommandError("public MVP smoke is unavailable.", exit_code=1) from exc
    try:
        argv = ["--json"] if json_output else ["--pretty"] if pretty else []
        return public_mvp_smoke.main(argv)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        raise DiagnosticsCommandError("public MVP smoke failed.", exit_code=1) from exc


def _run_public_demo(*, json_output: bool = False, pretty: bool = False) -> int:
    try:
        _prepare_trusted_cli_import_paths()
        public_demo = _load_public_demo_module()
    except Exception as exc:
        raise DiagnosticsCommandError("YonerAI public demo is unavailable.", exit_code=1) from exc
    try:
        argv = ["--json"] if json_output else ["--pretty"] if pretty else ["--pretty"]
        return public_demo.main(argv)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        raise DiagnosticsCommandError("YonerAI public demo failed.", exit_code=1) from exc


def _load_public_mvp_smoke_module() -> Any:
    return diagnostics_command._load_public_mvp_smoke_module()


def _load_public_demo_module() -> Any:
    return diagnostics_command._load_public_demo_module()


def _load_config_for_policy(args: argparse.Namespace) -> dict[str, object]:
    try:
        return load_cli_config(getattr(args, "config_path", None))
    except ConfigError as exc:
        raise CliError(str(exc), exit_code=2) from exc


def _interactive_runtime_env(config_path: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    try:
        config = load_cli_config(config_path)
    except ConfigError:
        return env
    if config.get("local_llm_enabled") is not True:
        return env
    try:
        from yonerai_cli.first_run import detect_local_llm
    except Exception:
        return env
    detected = detect_local_llm(env)
    if detected.get("status") != "detected":
        return env
    provider = str(detected.get("detected_provider") or "ollama")
    base_url = str(detected.get("setup_base_url") or "")
    if not base_url:
        return env
    env["ORA_LOCAL_LLM_ENABLED"] = "1"
    env["ORA_LOCAL_LLM_PROVIDER"] = provider
    env["ORA_LOCAL_LLM_BASE_URL"] = base_url
    return env


def _interactive_providers_report(config_path: str | None = None) -> dict[str, Any]:
    return _build_interactive_providers_report(
        prepare_import_paths=_prepare_trusted_cli_import_paths,
        env=_interactive_runtime_env(config_path),
    )


def _interactive_auth_login(lang: str, interactive_tty: bool, *, config_path: str | None = None) -> dict[str, Any]:
    from yonerai_cli.commands.auth import build_staging_login_report

    try:
        return build_staging_login_report(
            config_path,
            lang=lang,
            bridge=True,
            open_browser=interactive_tty,
            wait_linked=interactive_tty,
        )
    except ConfigError as exc:
        raise CliError(str(exc), exit_code=2) from exc


def _interactive_callbacks(config_path: str | None = None):
    from yonerai_cli.interactive import InteractiveCallbacks

    return InteractiveCallbacks(
        providers=lambda: _interactive_providers_report(config_path),
        ask_auto=lambda task, provider, live, ledger_path, lang, memory_store_path=None: _call_interactive_ask_auto(
            task,
            provider,
            live,
            ledger_path,
            lang,
            memory_store_path,
            config_path=config_path,
        ),
        runs_list=_interactive_runs_list,
        runs_show=_interactive_runs_show,
        update_check=_interactive_update_check,
        update_apply=_interactive_update_apply,
        status_check=_interactive_status_check,
        api_status=lambda lang: _interactive_api_status(lang, config_path=config_path),
        ping_status=lambda lang: control_spine_callbacks.interactive_ping_status(lang, config_path=config_path),
        rate_limit_status=lambda lang: control_spine_callbacks.interactive_rate_limit_status(
            lang, config_path=config_path
        ),
        sync_status=lambda lang: _interactive_sync_status(lang, config_path=config_path),
        sync_action=lambda values, lang: interactive_service.build_interactive_sync_action(values, lang=lang),
        whoami=lambda lang: control_spine_callbacks.interactive_whoami(lang, config_path=config_path),
        project_status=lambda lang: control_spine_callbacks.interactive_project_status(lang, config_path=config_path),
        session_status=lambda lang: control_spine_callbacks.interactive_session_status(lang, config_path=config_path),
        auth_logout=lambda lang: control_spine_callbacks.interactive_logout(lang, config_path=config_path),
        session_revoke=lambda lang, session_id: control_spine_callbacks.interactive_session_revoke(
            lang,
            session_id,
            config_path=config_path,
        ),
        audit_status=lambda lang: control_spine_callbacks.interactive_audit_status(lang, config_path=config_path),
        native_run_status=lambda lang: control_spine_callbacks.interactive_native_run_help(
            lang,
            config_path=config_path,
        ),
        worker_status=lambda lang: control_spine_callbacks.interactive_worker_status(lang, config_path=config_path),
        capability_list=lambda lang: control_spine_callbacks.interactive_capability_list(
            lang,
            config_path=config_path,
        ),
        module_list=lambda lang: control_spine_callbacks.interactive_module_list(lang, config_path=config_path),
        evolve_status=_interactive_evolve_status,
        memory_status=_interactive_memory_status,
        memory_action=_interactive_memory_action,
        policy_status=_interactive_policy_status,
        auth_login=lambda lang, interactive_tty: _interactive_auth_login(
            lang,
            interactive_tty,
            config_path=config_path,
        ),
    )


def _call_interactive_ask_auto(
    task: str,
    provider: str,
    live: bool,
    ledger_path: str | None,
    lang: str,
    memory_store_path: str | None = None,
    *,
    config_path: str | None = None,
) -> dict[str, Any]:
    import inspect

    callback = _interactive_ask_auto
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        signature = None
    supports_config_path = False
    supports_varargs = False
    supports_memory_store_path = False
    positional_capacity = 0
    if signature is not None:
        parameters = tuple(signature.parameters.values())
        supports_varargs = any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters)
        supports_config_path = "config_path" in signature.parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters
        )
        supports_memory_store_path = "memory_store_path" in signature.parameters
        positional_capacity = sum(
            1
            for parameter in parameters
            if parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        )
    call_args: list[Any] = [task, provider, live, ledger_path, lang]
    if supports_memory_store_path or supports_varargs or positional_capacity >= 6:
        call_args.append(memory_store_path)
    if supports_config_path:
        return callback(*call_args, config_path=config_path)
    return callback(*call_args)


def _interactive_ask_auto(
    task: str,
    provider: str,
    live: bool,
    ledger_path: str | None,
    _lang: str,
    memory_store_path: str | None = None,
    *,
    config_path: str | None = None,
) -> dict[str, Any]:
    return interactive_service.build_interactive_ask_report(
        task,
        provider,
        live,
        ledger_path,
        memory_store_path,
        prepare_import_paths=_prepare_trusted_cli_import_paths,
        env=_interactive_runtime_env(config_path),
    )


def _interactive_runs_list(ledger_path: str | None, limit: int, _lang: str) -> dict[str, Any]:
    return interactive_service.build_interactive_runs_list(
        ledger_path,
        limit,
        prepare_import_paths=_prepare_trusted_cli_import_paths,
        env=os.environ,
    )


def _interactive_runs_show(run_id: str, ledger_path: str | None, _lang: str) -> dict[str, Any]:
    return interactive_service.build_interactive_runs_show(
        run_id,
        ledger_path,
        prepare_import_paths=_prepare_trusted_cli_import_paths,
        env=os.environ,
    )


def _interactive_update_check(manifest_path: str | None, _lang: str) -> dict[str, Any]:
    try:
        return interactive_service.build_interactive_update_check(
            manifest_path,
            repo_root=_repo_root(),
            current_version=_read_repo_version() or __version__,
        )
    except InteractiveServiceError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def _interactive_update_apply(channel: str, confirmed: bool, _lang: str) -> dict[str, Any]:
    try:
        return interactive_service.build_interactive_update_apply(
            channel,
            confirmed=confirmed,
            repo_root=_repo_root(),
            current_version=_read_repo_version() or __version__,
            env=os.environ,
        )
    except InteractiveServiceError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def _interactive_status_check(_lang: str) -> dict[str, Any]:
    try:
        return interactive_service.build_interactive_status_check(
            prepare_import_paths=_prepare_trusted_cli_import_paths,
        )
    except InteractiveServiceError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def _interactive_api_status(_lang: str, *, config_path: str | None = None) -> dict[str, Any]:
    control_spine_report = control_spine_callbacks.interactive_api_status(_lang, config_path=config_path)
    if control_spine_report is not None:
        return control_spine_report
    try:
        return interactive_service.build_interactive_api_status(
            prepare_import_paths=_prepare_trusted_cli_import_paths,
        )
    except InteractiveServiceError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def _interactive_sync_status(_lang: str, *, config_path: str | None = None) -> dict[str, Any]:
    try:
        from yonerai_cli.services.conversation_sync_policy_service import (
            ConversationSyncPolicyError,
            build_conversation_policy_status_report,
        )

        return build_conversation_policy_status_report(config_path=config_path)
    except ConversationSyncPolicyError as exc:
        raise CliError(str(exc), exit_code=1) from exc


def _interactive_evolve_status(_lang: str) -> dict[str, Any]:
    try:
        return interactive_service.build_interactive_evolve_status(
            prepare_import_paths=_prepare_trusted_cli_import_paths,
        )
    except InteractiveServiceError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def _interactive_memory_status(_lang: str) -> dict[str, Any]:
    args = argparse.Namespace(memory_command="status", store=None)
    return _interactive_memory_report(args)


def _interactive_memory_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        return interactive_service.build_interactive_memory_report(
            args,
            prepare_import_paths=_prepare_trusted_cli_import_paths,
        )
    except InteractiveServiceError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def _interactive_policy_status(config: dict[str, object]) -> dict[str, Any]:
    return interactive_service.build_interactive_policy_status(
        config,
        prepare_import_paths=_prepare_trusted_cli_import_paths,
    )


def _interactive_memory_action(action: str, values: list[str], _lang: str, default_scope: str | None) -> dict[str, Any]:
    try:
        return interactive_service.build_interactive_memory_action(
            action,
            values,
            default_scope,
            prepare_import_paths=_prepare_trusted_cli_import_paths,
        )
    except InteractiveServiceError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def _run_interactive_chat(args: argparse.Namespace) -> int:
    try:
        return interactive_service.run_interactive_chat(args, _interactive_callbacks(getattr(args, "config_path", None)))
    except InteractiveServiceError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def _prompt_from_args(parts: list[str]) -> str:
    prompt = " ".join(parts).strip()
    if not prompt:
        raise CliError("prompt must not be empty.")
    return prompt


def build_parser() -> argparse.ArgumentParser:
    return build_cli_parser()


def _runtime_hooks() -> CliRuntimeHooks:
    return CliRuntimeHooks(
        print_json=_print_json,
        request_json=request_json,
        run_interactive_chat=_run_interactive_chat,
        run_public_mvp_smoke=_run_public_mvp_smoke,
        run_public_demo=_run_public_demo,
        build_start_report=_build_start_report,
        print_start_pretty=_print_start_pretty,
        build_doctor_report=_build_doctor_report,
        print_doctor_pretty=_print_doctor_pretty,
        build_providers_report=lambda: _build_interactive_providers_report(
            prepare_import_paths=_prepare_trusted_cli_import_paths,
            env=os.environ,
        ),
        prepare_import_paths=_prepare_trusted_cli_import_paths,
        load_config_for_policy=_load_config_for_policy,
        build_status_report=_build_status_report,
        print_status_pretty=_print_status_pretty,
        repo_root=_repo_root,
        read_repo_version=_read_repo_version,
        prompt_from_args=_prompt_from_args,
    )


def run(argv: list[str] | None = None) -> int:
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    if not actual_argv:
        return _run_interactive_chat(
            argparse.Namespace(
                config_path=None,
                lang=None,
                provider=None,
                live=False,
                ledger_path=None,
                script=False,
                color="auto",
            )
        )
    parser = build_parser()
    args = parser.parse_args(actual_argv)
    try:
        return dispatch_command(args, _runtime_hooks())
    except CliDispatchError as exc:
        raise CliError(str(exc), exit_code=exc.exit_code) from exc


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    try:
        return run(actual_argv)
    except DiagnosticsCommandError as exc:
        print(f"error: {_localized_cli_error(str(exc), actual_argv)}", file=sys.stderr)
        return exc.exit_code
    except CliError as exc:
        print(f"error: {_localized_cli_error(str(exc), actual_argv)}", file=sys.stderr)
        return exc.exit_code


def _localized_cli_error(message: str, argv: list[str]) -> str:
    if _explicit_lang(argv) == "en":
        return message
    mapping = {
        "public CLI login is staging-only in this build.": (
            "この公開CLIではステージングログインだけ使えます。正式ログインは無効です。"
        ),
        "Session id is invalid.": "セッションIDが正しくありません。`yonerai sessions` で確認してください。",
        "Staging login is required or the saved session expired.": (
            "ステージングセッションが未ログイン、または期限切れです。`yonerai login` を実行してください。"
        ),
    }
    if message in mapping:
        return mapping[message]
    lower_message = message.lower()
    if "Staging login is required" in message:
        return "ステージングログインが必要です。`yonerai login` を実行してください。"
    if "saved session expired" in lower_message or "session expired" in lower_message:
        return "保存済みセッションの期限が切れています。`yonerai login` でログインし直してください。"
    if "revoked" in lower_message:
        return "このセッションは取り消し済みです。`yonerai login` で新しくログインしてください。"
    return message


def _explicit_lang(argv: list[str]) -> str | None:
    for index, value in enumerate(argv):
        if value == "--lang" and index + 1 < len(argv):
            return argv[index + 1]
        if value.startswith("--lang="):
            return value.split("=", 1)[1]
    return None


def _configure_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue
