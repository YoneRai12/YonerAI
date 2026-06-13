from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

from yonerai_cli.screens.update import format_install_pretty, format_update_pretty
from yonerai_cli.services.update_service import (
    UpdateServiceError,
    build_install_report,
    build_update_apply_report,
    build_update_choice_report,
    build_update_report,
)
from yonerai_cli.tui import open_choice_dialog


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
    update = subcommands.add_parser("update", help="Show safe update choices without downloading or installing.")
    update_output = update.add_mutually_exclusive_group()
    update_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    update_output.add_argument("--pretty", action="store_true", help="Print a readable update choice screen.")
    update.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")
    update_subcommands = update.add_subparsers(dest="update_command", required=False)

    update_plan = update_subcommands.add_parser("plan", help="Build a local manifest update dry-run plan.")
    update_plan.add_argument("--manifest", help="Local release manifest JSON path. Defaults to releases/manifest.example.json.")
    update_plan.add_argument("--channel", choices=("stable", "alpha"), default="stable", help="Default manifest channel when --manifest is omitted. Default: stable.")
    update_plan_output = update_plan.add_mutually_exclusive_group()
    update_plan_output.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Print stable machine-readable JSON.")
    update_plan_output.add_argument("--pretty", action="store_true", default=argparse.SUPPRESS, help="Print a readable update plan.")
    update_plan.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    update_check = update_subcommands.add_parser("check", help="Check local manifest update status without downloading or installing.")
    update_check.add_argument("--manifest", help="Local release manifest JSON path. Defaults to the newest releases/manifest.v*.json.")
    update_check.add_argument("--channel", choices=("stable", "alpha"), default="stable", help="Default manifest channel when --manifest is omitted. Default: stable.")
    update_check_output = update_check.add_mutually_exclusive_group()
    update_check_output.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Print stable machine-readable JSON.")
    update_check_output.add_argument("--pretty", action="store_true", default=argparse.SUPPRESS, help="Print a readable update check.")
    update_check.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    update_stable = update_subcommands.add_parser(
        "stable",
        aliases=["release", "安定版", "リリース"],
        help="Check the latest stable release. Short form for update check --channel stable.",
    )
    update_stable_output = update_stable.add_mutually_exclusive_group()
    update_stable_output.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Print stable machine-readable JSON.")
    update_stable_output.add_argument("--pretty", action="store_true", default=argparse.SUPPRESS, help="Print a readable update check.")
    update_stable.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")
    update_stable.set_defaults(channel="stable")

    update_alpha = update_subcommands.add_parser(
        "beta",
        aliases=[
            "alpha",
            "アルファ",
            "ベータ",
            "ベータ版",
            "アルファ",
            "アルファ版",
        ],
        help="Check the beta build. Short form for the prerelease update channel.",
    )
    update_alpha_output = update_alpha.add_mutually_exclusive_group()
    update_alpha_output.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Print stable machine-readable JSON.")
    update_alpha_output.add_argument("--pretty", action="store_true", default=argparse.SUPPRESS, help="Print a readable update check.")
    update_alpha.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")
    update_alpha.set_defaults(channel="alpha")

    update_apply = update_subcommands.add_parser(
        "apply",
        aliases=["適用"],
        help="Apply a selected update only after explicit confirmation. No silent auto-update.",
    )
    update_apply.add_argument(
        "channel",
        choices=(
            "stable",
            "alpha",
            "beta",
            "アルファ",
            "安定版",
            "ベータ",
            "ベータ版",
            "アルファ版",
        ),
        nargs="?",
        default="stable",
    )
    update_apply.add_argument(
        "--yes",
        "--confirm",
        action="store_true",
        dest="confirmed",
        help="Required to run the manual update apply action.",
    )
    update_apply_output = update_apply.add_mutually_exclusive_group()
    update_apply_output.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Print stable machine-readable JSON.")
    update_apply_output.add_argument("--pretty", action="store_true", default=argparse.SUPPRESS, help="Print a readable update apply report.")
    update_apply.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


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
    return 0 if report.get("ok", True) else 1


def handle_update_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    repo_root: Path,
    current_version: str,
) -> int:
    try:
        if args.update_command is None:
            selected_channel = _maybe_prompt_update_channel(args)
            if selected_channel in {"stable", "alpha"}:
                args = argparse.Namespace(
                    **{
                        **vars(args),
                        "update_command": "check",
                        "channel": selected_channel,
                        "manifest": None,
                    }
                )
                report = build_update_report(args, repo_root=repo_root, current_version=current_version)
            else:
                report = build_update_choice_report(repo_root=repo_root, current_version=current_version)
        elif args.update_command in {"apply", "適用"}:
            report = build_update_apply_report(
                channel=_normalize_apply_channel(getattr(args, "channel", "stable")),
                confirmed=bool(getattr(args, "confirmed", False)),
                repo_root=repo_root,
                current_version=current_version,
            )
        else:
            args = _normalize_short_update_args(args)
            report = build_update_report(args, repo_root=repo_root, current_version=current_version)
    except UpdateServiceError as exc:
        raise InstallUpdateCommandError(str(exc)) from exc

    if args.json:
        print_json(report)
    else:
        print(format_update_pretty(report, color=args.color))
    return 0 if report["ok"] else 1


def _maybe_prompt_update_channel(args: argparse.Namespace) -> str | None:
    if bool(getattr(args, "json", False)):
        return None
    if not _interactive_stdio_ready():
        return None
    opened, selection = open_choice_dialog(
        title="YonerAI / 更新",
        text="どちらを確認しますか。",
        values=[
            ("stable", "安定版を確認"),
            ("alpha", "ベータ版を確認"),
        ],
        ok_text="開く",
        cancel_text="閉じる",
    )
    if opened and selection in {"stable", "alpha"}:
        return selection
    return None


def _interactive_stdio_ready() -> bool:
    stdin_is_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
    stdout_is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    return stdin_is_tty and stdout_is_tty


def _normalize_apply_channel(value: str) -> str:
    if value in {
        "alpha",
        "beta",
        "アルファ",
        "ベータ",
        "ベータ版",
        "アルファ版",
    }:
        return "alpha"
    return "stable"


def _normalize_short_update_args(args: argparse.Namespace) -> argparse.Namespace:
    command = getattr(args, "update_command", None)
    alpha_aliases = {
        "beta",
        "alpha",
        "アルファ",
        "ベータ",
        "ベータ版",
        "アルファ",
        "アルファ版",
    }
    if command in {"stable", "release", "安定版", "リリース", *alpha_aliases}:
        channel = "alpha" if command in alpha_aliases else "stable"
        return argparse.Namespace(
            **{
                **vars(args),
                "update_command": "check",
                "channel": channel,
                "manifest": None,
            }
        )
    return args
