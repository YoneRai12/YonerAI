from __future__ import annotations

import argparse
from typing import Any, Callable

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


class OpsCommandError(Exception):
    pass


def add_ops_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    color_choices: tuple[str, ...],
) -> None:
    ops = subcommands.add_parser("ops", help="Plan safe diagnostic operations without arbitrary shell execution.")
    ops_subcommands = ops.add_subparsers(dest="ops_command", required=True)
    ops_plan = ops_subcommands.add_parser("plan", help="Preview a SafeShell diagnostic operation.")
    ops_plan.add_argument("operation", choices=("python-version", "git-status", "node-version"))
    ops_plan_output = ops_plan.add_mutually_exclusive_group()
    ops_plan_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    ops_plan_output.add_argument("--pretty", action="store_true", help="Print a readable operation plan.")
    ops_plan.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_ops_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
) -> int:
    report = build_ops_plan_report(args, prepare_import_paths=prepare_import_paths)
    if args.json:
        print_json(report)
    else:
        print(format_ops_plan_pretty(report, color=args.color))
    return 0 if report["ok"] else 1


def build_ops_plan_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.ops import plan_operation
    except Exception as exc:
        raise OpsCommandError("SafeShell planner is unavailable.") from exc
    plan = plan_operation(args.operation)
    return {
        "schema_version": "yonerai-ops-plan/v1",
        "ok": plan.status == "planned",
        "plan": plan.to_public_dict(),
        "shell_executed": False,
        "mutation_performed": False,
    }


def format_ops_plan_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    plan = report["plan"]
    rows = (
        CliRow("operation", plan["operation_id"], "ok" if report["ok"] else "fail"),
        CliRow("status", plan["status"], "ok" if report["ok"] else "fail"),
        CliRow("command_preview", " ".join(plan["command_preview"]) if plan["command_preview"] else "none", "ok" if report["ok"] else "warn"),
        CliRow("approval_required", plan["approval_required"], "warn" if plan["approval_required"] else "ok"),
        CliRow("shell_executed", report["shell_executed"], "fail" if report["shell_executed"] else "ok"),
    )
    return render_report("YonerAI ops plan", (CliSection("SafeShell", rows),), color=color)
