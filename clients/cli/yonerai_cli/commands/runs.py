from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping

from yonerai_cli.screens.runs import format_run_show_pretty, format_runs_list_pretty
from yonerai_cli.services.ledger_service import build_ledger_status


class RunsCommandError(Exception):
    pass


class RunsCommandUserInputError(RunsCommandError):
    pass


def add_runs_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    runs = subcommands.add_parser("runs", help="Inspect opt-in redacted local run ledger history.")
    runs_subcommands = runs.add_subparsers(dest="runs_command", required=True)

    runs_list = runs_subcommands.add_parser("list", help="List recent runs from an opt-in ledger.")
    runs_list.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Defaults to YONERAI_RUN_LEDGER_PATH.")
    runs_list.add_argument("--limit", type=int, default=20, help="Maximum runs to show. Default: 20.")
    runs_list_output = runs_list.add_mutually_exclusive_group()
    runs_list_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    runs_list_output.add_argument("--pretty", action="store_true", help="Print a readable run list.")
    runs_list.add_argument("--lang", choices=lang_choices, default="en", help="Pretty output language. Default: en.")
    runs_list.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    runs_show = runs_subcommands.add_parser("show", help="Show one run from an opt-in ledger.")
    runs_show.add_argument("run_id")
    runs_show.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Defaults to YONERAI_RUN_LEDGER_PATH.")
    runs_show_output = runs_show.add_mutually_exclusive_group()
    runs_show_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    runs_show_output.add_argument("--pretty", action="store_true", help="Print a readable run summary.")
    runs_show.add_argument("--lang", choices=lang_choices, default="en", help="Pretty output language. Default: en.")
    runs_show.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_runs_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> int:
    report = build_runs_report(args, prepare_import_paths=prepare_import_paths, env=env)
    if args.json:
        print_json(report)
    elif args.runs_command == "show":
        print(format_run_show_pretty(report, lang=args.lang, color=args.color))
    else:
        print(format_runs_list_pretty(report, lang=args.lang, color=args.color))
    return 0 if report["ok"] else 1


def build_runs_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.execution.ledger import build_run_ledger_from_env
    except Exception as exc:
        raise RunsCommandError("run ledger is unavailable.") from exc

    ledger = build_run_ledger_from_env(args.ledger_path)
    ledger_status = build_ledger_status(args.ledger_path, env=env)
    if args.runs_command == "list":
        runs = [run.to_public_dict() for run in ledger.list_runs(limit=args.limit)]
        return {
            "schema_version": "yonerai-runs-list/v1",
            "ok": True,
            "ledger": ledger_status,
            "runs": runs,
            "count": len(runs),
            "raw_prompt_persisted": False,
            "raw_completion_persisted": False,
        }
    if args.runs_command == "show":
        run = ledger.get_run(args.run_id)
        if run is None:
            return {
                "schema_version": "yonerai-runs-show/v1",
                "ok": False,
                "ledger": ledger_status,
                "error": {"code": "unknown_run", "message": "run_id was not found in the selected local ledger"},
                "run": None,
            }
        return {
            "schema_version": "yonerai-runs-show/v1",
            "ok": True,
            "ledger": ledger_status,
            "run": run.to_public_dict(),
            "raw_prompt_persisted": False,
            "raw_completion_persisted": False,
        }
    raise RunsCommandUserInputError("unknown runs command")
