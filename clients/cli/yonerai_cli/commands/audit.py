from __future__ import annotations

import argparse
import os
from typing import Any, Callable

from yonerai_cli.screens.control_spine import format_control_spine_pretty
from yonerai_cli.services.control_spine_service import build_audit_report, load_config_for_control_spine


class AuditCommandError(Exception):
    pass


def add_audit_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    audit = subcommands.add_parser("audit", help="Inspect sanitized staging audit metadata when available.")
    audit_subcommands = audit.add_subparsers(dest="audit_command", required=True)
    audit_list = audit_subcommands.add_parser("list", help="List sanitized audit events if the staging backend supports it.")
    audit_list.add_argument("--config-path", help="Optional local CLI config path.")
    audit_list.add_argument("--timeout-seconds", type=float, default=10.0, help="Network timeout. Default: 10.")
    output = audit_list.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    output.add_argument("--pretty", action="store_true", help="Print a readable audit report.")
    audit_list.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    audit_list.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_audit_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    if args.audit_command != "list":
        raise AuditCommandError("unknown audit command")
    report = build_audit_report(
        config=load_config_for_control_spine(getattr(args, "config_path", None)),
        env=os.environ,
        claim_path=getattr(args, "config_path", None),
        timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
    )
    if args.json:
        print_json(report)
    else:
        print(format_control_spine_pretty(report, lang=args.lang, color=args.color))
    return 0 if report.get("ok", True) else 1
