from __future__ import annotations

import argparse
from typing import Any, Callable

from yonerai_cli.screens.policy import format_policy_status_pretty


def add_policy_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    policy = subcommands.add_parser("policy", help="Show public-safe runtime policy state.")
    policy_subcommands = policy.add_subparsers(dest="policy_command", required=True)
    status = policy_subcommands.add_parser("status", help="Show provider/model/permission/update policy state.")
    status_output = status.add_mutually_exclusive_group()
    status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    status_output.add_argument("--pretty", action="store_true", help="Print readable policy state.")
    status.add_argument("--config-path", help="Optional local CLI config JSON path.")
    status.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    status.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_policy_command(
    args: argparse.Namespace,
    *,
    config: dict[str, object],
    print_json: Callable[[dict[str, Any]], None],
) -> int:
    if args.policy_command != "status":
        raise ValueError("unknown policy command")

    from ora_core.policies import build_policy_status_report

    report = build_policy_status_report(config)
    if args.json:
        print_json(report)
    else:
        print(format_policy_status_pretty(report, lang=args.lang, color=args.color))
    return 0 if report["ok"] else 1
