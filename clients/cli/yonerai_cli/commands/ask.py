from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping

from yonerai_cli.screens.ask import (
    format_auto_runtime_pretty,
    format_execution_plan_pretty,
    format_execution_result_pretty,
)
from yonerai_cli.services.ledger_service import build_ledger_status


class AskCommandError(Exception):
    pass


class AskCommandUserInputError(AskCommandError):
    pass


def add_plan_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    provider_choices: tuple[str, ...],
    mode_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    plan = subcommands.add_parser("plan", help="Preview classification, route, provider, and approval without executing.")
    plan.add_argument("task", nargs="+")
    plan_output = plan.add_mutually_exclusive_group()
    plan_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    plan_output.add_argument("--pretty", action="store_true", help="Print a readable execution plan summary.")
    plan.add_argument("--provider", choices=provider_choices, default="auto", help="Provider preference. Default: auto.")
    plan.add_argument("--mode", choices=mode_choices, default="managed-contract", help="Planning mode. Default: managed-contract.")
    plan.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def add_ask_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    provider_choices: tuple[str, ...],
    mode_choices: tuple[str, ...],
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    ask = subcommands.add_parser("ask", help="Execute a safe YonerAI ask path or preview it with --dry-run.")
    ask.add_argument("task", nargs="+")
    ask.add_argument("--auto", action="store_true", help="Use the auto runtime router: classify, route, execute safe paths, and record run_id.")
    ask.add_argument("--dry-run", action="store_true", help="Preview only; no provider call is made.")
    ask.add_argument("--live", action="store_true", help="Allow explicitly gated local or external live provider execution.")
    ask.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    ask.add_argument("--memory-store", help="Optional local JSONL memory store. Only allowed memory IDs are used in ledger/output.")
    ask.add_argument("--file", help="Optional workspace-local UTF-8 text file to summarize or use as ask context.")
    ask.add_argument("--workspace", help="Required workspace root when --file is used.")
    ask.add_argument("--file-max-bytes", type=int, default=65536, help="Maximum file bytes to read. Default: 65536.")
    ask_output = ask.add_mutually_exclusive_group()
    ask_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    ask_output.add_argument("--pretty", action="store_true", help="Print a readable execution summary.")
    ask.add_argument("--provider", choices=provider_choices, default="auto", help="Provider preference. Default: auto.")
    ask.add_argument("--mode", choices=mode_choices, default="self-host", help="Execution planning mode. Default: self-host.")
    ask.add_argument("--lang", choices=lang_choices, default="en", help="Pretty output language. Default: en.")
    ask.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_plan_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
) -> int:
    report = build_execution_plan_report(args, command="yonerai plan", dry_run=True, prepare_import_paths=prepare_import_paths)
    if args.json:
        print_json(report)
    else:
        print(format_execution_plan_pretty(report, color=args.color))
    return 0


def handle_ask_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> int:
    if args.dry_run:
        report = build_execution_plan_report(args, command="yonerai ask --dry-run", dry_run=True, prepare_import_paths=prepare_import_paths)
    elif args.auto:
        report = build_auto_ask_report(args, prepare_import_paths=prepare_import_paths, env=env)
    else:
        report = build_ask_report(args, prepare_import_paths=prepare_import_paths, env=env)
    if args.json:
        print_json(report)
    elif args.dry_run:
        print(format_execution_plan_pretty(report, color=args.color))
    elif args.auto:
        print(format_auto_runtime_pretty(report, lang=args.lang, color=args.color))
    else:
        print(format_execution_result_pretty(report, color=args.color))
    return 0 if args.dry_run or report["ok"] else 1


def build_execution_plan_report(
    args: argparse.Namespace,
    *,
    command: str,
    dry_run: bool,
    prepare_import_paths: Callable[[], None],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.planning import build_execution_plan
    except Exception as exc:
        raise AskCommandError("execution plan preview is unavailable.") from exc

    prompt = prompt_from_args(args.task)
    try:
        plan = build_execution_plan(
            prompt,
            command=command,
            mode=args.mode,
            provider=args.provider,
            dry_run=dry_run,
        )
    except ValueError as exc:
        raise AskCommandUserInputError(str(exc)) from exc
    return plan.to_public_dict()


def build_ask_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.execution.ledger import build_run_ledger_from_env
        from ora_core.execution.spine import execute_task
        from ora_core.execution.workspace_files import (
            WorkspaceFileError,
            build_workspace_file_access_event,
            build_workspace_file_prompt,
            read_workspace_text_file,
        )
    except Exception as exc:
        raise AskCommandError("execution spine is unavailable.") from exc

    prompt = prompt_from_args(args.task)
    ledger_status = build_ledger_status(args.ledger_path, env=env)
    provider_prompt = prompt
    file_context = None
    context_events = []
    if args.file:
        if not args.workspace:
            raise AskCommandUserInputError("--workspace is required when --file is used.")
        try:
            file_context = read_workspace_text_file(
                args.file,
                workspace=args.workspace,
                max_bytes=args.file_max_bytes,
            )
        except WorkspaceFileError as exc:
            return {
                "schema_version": "yonerai-execution-result/v1",
                "ok": False,
                "run": None,
                "plan": None,
                "response": None,
                "boundary_checks": {},
                "live_call_performed": False,
                "ledger": ledger_status,
                "file_context": None,
                "error": exc.to_public_dict(),
            }
        provider_prompt = build_workspace_file_prompt(prompt, file_context)
        context_events.append(build_workspace_file_access_event(file_context))
    try:
        result = execute_task(
            prompt,
            provider_prompt=provider_prompt,
            mode=args.mode,
            provider=args.provider,
            live=args.live,
            ledger=build_run_ledger_from_env(args.ledger_path),
            context_events=context_events,
        )
    except ValueError as exc:
        raise AskCommandUserInputError(str(exc)) from exc
    report = result.to_public_dict()
    report["ledger"] = ledger_status
    if file_context is not None:
        report["file_context"] = file_context.to_public_dict()
    return report


def build_auto_ask_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.execution.auto_runtime import build_auto_runtime_report
        from ora_core.execution.ledger import build_run_ledger_from_env
        from ora_core.execution.workspace_files import (
            WorkspaceFileError,
            build_workspace_file_access_event,
            build_workspace_file_prompt,
            read_workspace_text_file,
        )
        from ora_core.memory import LocalMemoryStore, select_allowed_memory_for_ask
    except Exception as exc:
        raise AskCommandError("auto runtime is unavailable.") from exc

    prompt = prompt_from_args(args.task)
    ledger_status = build_ledger_status(args.ledger_path, env=env)
    provider_prompt = prompt
    file_context = None
    context_events = []
    memory_records = None
    memory_store_path = getattr(args, "memory_store", None)
    if memory_store_path:
        try:
            memory_records = select_allowed_memory_for_ask(LocalMemoryStore(memory_store_path).list())
        except Exception as exc:
            raise AskCommandError("failed to read local memory store; verify store permissions and JSONL format.") from exc
    if args.file:
        if not args.workspace:
            raise AskCommandUserInputError("--workspace is required when --file is used.")
        try:
            file_context = read_workspace_text_file(
                args.file,
                workspace=args.workspace,
                max_bytes=args.file_max_bytes,
            )
        except WorkspaceFileError as exc:
            return {
                "schema_version": "yonerai-auto-runtime/v0.1",
                "ok": False,
                "command": "yonerai ask --auto",
                "run": None,
                "auto": None,
                "response": None,
                "ledger": ledger_status,
                "file_context": None,
                "live_call_performed": False,
                "error": exc.to_public_dict(),
            }
        provider_prompt = build_workspace_file_prompt(prompt, file_context)
        context_events.append(build_workspace_file_access_event(file_context))
    try:
        report = build_auto_runtime_report(
            prompt,
            provider_prompt=provider_prompt,
            provider=args.provider,
            live=args.live,
            ledger=build_run_ledger_from_env(args.ledger_path),
            context_events=context_events,
            memory_records=memory_records,
            local_file_context=file_context is not None,
        )
    except ValueError as exc:
        raise AskCommandUserInputError(str(exc)) from exc
    report["ledger"] = ledger_status
    if memory_store_path:
        report["memory_store"] = {
            "configured": True,
            "path_output": False,
            "used_ids": list((report.get("memory") or {}).get("used_ids") or []),
        }
    if file_context is not None:
        report["file_context"] = file_context.to_public_dict()
    return report


def prompt_from_args(parts: list[str] | tuple[str, ...]) -> str:
    text = " ".join(parts).strip()
    if not text:
        raise AskCommandUserInputError("prompt must not be empty")
    return text
