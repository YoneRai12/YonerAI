from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from yonerai_cli.screens.update import format_install_pretty, format_update_pretty
from yonerai_cli.services.update_service import UpdateServiceError, build_install_report, build_update_report


class InstallUpdateCommandError(Exception):
    pass


def add_install_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    color_choices: tuple[str, ...],
) -> None:
    install = subcommands.add_parser("install", help="Plan installer actions without downloading or installing.")
    install_subcommands = install.add_subparsers(dest="install_command", required=True)

    install_status = install_subcommands.add_parser("status", help="Show one-command install source policy.")
    install_status.add_argument("--channel", choices=("stable", "alpha"), default="stable", help="Install channel to inspect. Default: stable.")
    install_status_output = install_status.add_mutually_exclusive_group()
    install_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    install_status_output.add_argument("--pretty", action="store_true", help="Print a readable installer source summary.")
    install_status.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    install_plan = install_subcommands.add_parser("plan", help="Build a local manifest install dry-run plan.")
    install_plan.add_argument("--manifest", help="Local release manifest JSON path. Defaults to releases/manifest.example.json.")
    install_plan.add_argument("--channel", choices=("stable", "alpha"), default="stable", help="Default manifest channel when --manifest is omitted. Default: stable.")
    install_plan_output = install_plan.add_mutually_exclusive_group()
    install_plan_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    install_plan_output.add_argument("--pretty", action="store_true", help="Print a readable installer plan.")
    install_plan.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    install_plan_windows = install_subcommands.add_parser("plan-windows", help="Build a Windows installer dry-run plan.")
    install_plan_windows.add_argument("--manifest", help="Local release manifest JSON path. Defaults to releases/manifest.example.json.")
    install_plan_windows.add_argument("--channel", choices=("stable", "alpha"), default="stable", help="Default manifest channel when --manifest is omitted. Default: stable.")
    install_plan_windows_output = install_plan_windows.add_mutually_exclusive_group()
    install_plan_windows_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    install_plan_windows_output.add_argument("--pretty", action="store_true", help="Print a readable installer plan.")
    install_plan_windows.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def add_update_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    color_choices: tuple[str, ...],
) -> None:
    update = subcommands.add_parser("update", help="Plan update actions without downloading or installing.")
    update_subcommands = update.add_subparsers(dest="update_command", required=True)

    update_plan = update_subcommands.add_parser("plan", help="Build a local manifest update dry-run plan.")
    update_plan.add_argument("--manifest", help="Local release manifest JSON path. Defaults to releases/manifest.example.json.")
    update_plan.add_argument("--channel", choices=("stable", "alpha"), default="stable", help="Default manifest channel when --manifest is omitted. Default: stable.")
    update_plan_output = update_plan.add_mutually_exclusive_group()
    update_plan_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    update_plan_output.add_argument("--pretty", action="store_true", help="Print a readable update plan.")
    update_plan.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    update_check = update_subcommands.add_parser("check", help="Check local manifest update status without downloading or installing.")
    update_check.add_argument("--manifest", help="Local release manifest JSON path. Defaults to the newest releases/manifest.v*.json.")
    update_check.add_argument("--channel", choices=("stable", "alpha"), default="stable", help="Default manifest channel when --manifest is omitted. Default: stable.")
    update_check_output = update_check.add_mutually_exclusive_group()
    update_check_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    update_check_output.add_argument("--pretty", action="store_true", help="Print a readable update check.")
    update_check.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_install_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    repo_root: Path,
) -> int:
    try:
        report = build_install_report(args, repo_root=repo_root)
    except UpdateServiceError as exc:
        raise InstallUpdateCommandError(str(exc)) from exc

    if args.json:
        print_json(report)
    else:
        print(format_install_pretty(report, color=args.color))
    return 0 if report["ok"] else 1


def handle_update_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    repo_root: Path,
    current_version: str,
) -> int:
    try:
        report = build_update_report(args, repo_root=repo_root, current_version=current_version)
    except UpdateServiceError as exc:
        raise InstallUpdateCommandError(str(exc)) from exc

    if args.json:
        print_json(report)
    else:
        print(format_update_pretty(report, color=args.color))
    return 0 if report["ok"] else 1
