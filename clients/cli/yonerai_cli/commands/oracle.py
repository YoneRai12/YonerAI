from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping

from yonerai_cli.screens.oracle import format_oracle_pretty


class OracleCommandError(Exception):
    pass


class OracleCommandUserInputError(OracleCommandError):
    pass


def add_oracle_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    color_choices: tuple[str, ...],
) -> None:
    oracle = subcommands.add_parser("oracle", help="Run public-safe local-dev Oracle stub fixtures.")
    oracle_subcommands = oracle.add_subparsers(dest="oracle_command", required=True)

    oracle_status = oracle_subcommands.add_parser("status", help="Show Oracle stub availability without contacting cloud.")
    oracle_status_output = oracle_status.add_mutually_exclusive_group()
    oracle_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    oracle_status_output.add_argument("--pretty", action="store_true", help="Print a readable Oracle stub status.")
    oracle_status.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    oracle_queue = oracle_subcommands.add_parser("queue", help="Queue one safe cloud-candidate task into the local-dev Oracle stub.")
    oracle_queue.add_argument("task", nargs="*", help="Public task text. Defaults to a public reasoning fixture.")
    oracle_queue.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    oracle_queue_output = oracle_queue.add_mutually_exclusive_group()
    oracle_queue_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    oracle_queue_output.add_argument("--pretty", action="store_true", help="Print a readable Oracle stub queue result.")
    oracle_queue.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_oracle_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> int:
    report = build_oracle_report(args, prepare_import_paths=prepare_import_paths, env=env)
    if args.pretty:
        print(format_oracle_pretty(report, color=args.color))
    else:
        print_json(report)
    return 0 if report["ok"] else 1


def build_oracle_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.execution import build_run_ledger_from_env
        from ora_core.hybrid import (
            DEFAULT_ORACLE_STUB_TASK,
            build_oracle_stub_queue_report,
            build_oracle_stub_status_report,
        )
    except Exception as exc:
        raise OracleCommandError("Oracle stub fixture is unavailable.") from exc
    if args.oracle_command == "status":
        return build_oracle_stub_status_report()
    if args.oracle_command == "queue":
        task = " ".join(args.task).strip() or DEFAULT_ORACLE_STUB_TASK
        ledger = build_run_ledger_from_env(args.ledger_path) if args.ledger_path or env.get("YONERAI_RUN_LEDGER_PATH") else None
        return build_oracle_stub_queue_report(task, ledger=ledger)
    raise OracleCommandUserInputError("unknown oracle command")
