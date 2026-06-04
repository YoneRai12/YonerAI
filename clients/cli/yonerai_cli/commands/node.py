from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping

from yonerai_cli.screens.node import format_node_pair_pretty, format_node_status_pretty, format_relay_status_pretty


class NodeCommandError(Exception):
    pass


class NodeCommandUserInputError(NodeCommandError):
    pass


def add_node_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    color_choices: tuple[str, ...],
) -> None:
    node = subcommands.add_parser("node", help="Inspect public-safe Hybrid Wire Local Node fixtures.")
    node_subcommands = node.add_subparsers(dest="node_command", required=True)
    node_status = node_subcommands.add_parser("status", help="Show public-safe Local Node fixture status.")
    node_status_output = node_status.add_mutually_exclusive_group()
    node_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    node_status_output.add_argument("--pretty", action="store_true", help="Print a readable Local Node status.")
    node_status.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    node_pair = node_subcommands.add_parser("pair", help="Preview Local Node pairing without performing it.")
    node_pair.add_argument("--dry-run", action="store_true", help="Required; do not pair or contact any service.")
    node_pair_output = node_pair.add_mutually_exclusive_group()
    node_pair_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    node_pair_output.add_argument("--pretty", action="store_true", help="Print a readable Local Node pairing preview.")
    node_pair.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def add_relay_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    color_choices: tuple[str, ...],
) -> None:
    relay = subcommands.add_parser("relay", help="Inspect public-safe Hybrid Relay local-dev fixtures.")
    relay_subcommands = relay.add_subparsers(dest="relay_command", required=True)
    relay_status = relay_subcommands.add_parser("status", help="Show local-dev Relay fixture status without starting it.")
    relay_status_output = relay_status.add_mutually_exclusive_group()
    relay_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    relay_status_output.add_argument("--pretty", action="store_true", help="Print a readable Relay local-dev status.")
    relay_status.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_node_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
) -> int:
    if args.node_command == "status":
        report = build_node_status_report(prepare_import_paths=prepare_import_paths)
        if args.pretty:
            print(format_node_status_pretty(report, color=args.color))
        else:
            print_json(report)
        return 0
    if args.node_command == "pair":
        report = build_node_pair_report(args, prepare_import_paths=prepare_import_paths)
        if args.pretty:
            print(format_node_pair_pretty(report, color=args.color))
        else:
            print_json(report)
        return 0
    raise NodeCommandUserInputError("unknown node command")


def handle_relay_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> int:
    report = build_relay_status_report(prepare_import_paths=prepare_import_paths, env=env)
    if args.pretty:
        print(format_relay_status_pretty(report, color=args.color))
    else:
        print_json(report)
    return 0 if report["ok"] else 1


def build_node_status_report(*, prepare_import_paths: Callable[[], None]) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.hybrid.wire_contract import build_local_node_status_report
    except Exception as exc:
        raise NodeCommandError("Hybrid Wire Local Node status is unavailable.") from exc
    return build_local_node_status_report()


def build_node_pair_report(args: argparse.Namespace, *, prepare_import_paths: Callable[[], None]) -> dict[str, Any]:
    if not args.dry_run:
        raise NodeCommandUserInputError("yonerai node pair is dry-run only in this public repo.")
    try:
        prepare_import_paths()
        from ora_core.hybrid.wire_contract import build_pairing_dry_run_report
    except Exception as exc:
        raise NodeCommandError("Hybrid Wire Local Node pairing dry-run is unavailable.") from exc
    return build_pairing_dry_run_report()


def build_relay_status_report(
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.hybrid.relay_status import build_relay_status_report
    except Exception as exc:
        raise NodeCommandError("Hybrid Relay local-dev status is unavailable.") from exc
    return build_relay_status_report(env)
