from __future__ import annotations

import argparse
import os
from typing import Any, Callable

from yonerai_cli.screens.control_spine import format_control_spine_pretty
from yonerai_cli.services.control_spine_service import (
    ControlSpineServiceError,
    build_project_report,
    load_config_for_control_spine,
)


class ProjectCommandError(Exception):
    pass


def add_project_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    project = subcommands.add_parser("project", help="Inspect or select the staging YonerAI project.")
    project_subcommands = project.add_subparsers(dest="project_command", required=True)

    project_list = project_subcommands.add_parser("list", help="List staging projects for the linked CLI session.")
    _add_common_options(project_list, lang_choices=lang_choices, color_choices=color_choices)

    project_current = project_subcommands.add_parser("current", help="Show the current staging project.")
    _add_common_options(project_current, lang_choices=lang_choices, color_choices=color_choices)

    project_use = project_subcommands.add_parser("use", help="Select a staging project if the backend allows it.")
    project_use.add_argument("project_id", help="Project id returned by `yonerai project list`.")
    _add_common_options(project_use, lang_choices=lang_choices, color_choices=color_choices)


def handle_project_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    try:
        report = build_project_report(
            args.project_command,
            project_id=getattr(args, "project_id", None),
            config=load_config_for_control_spine(getattr(args, "config_path", None)),
            env=os.environ,
            claim_path=getattr(args, "config_path", None),
            timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
        )
    except ControlSpineServiceError as exc:
        raise ProjectCommandError(exc.message) from exc
    if args.json:
        print_json(report)
    else:
        print(format_control_spine_pretty(report, lang=args.lang, color=args.color))
    return 0 if report.get("ok", True) else 1


def _add_common_options(
    parser: argparse.ArgumentParser,
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    parser.add_argument("--config-path", help="Optional local CLI config path.")
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="Network timeout. Default: 10.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    output.add_argument("--pretty", action="store_true", help="Print a readable project report.")
    parser.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    parser.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")
