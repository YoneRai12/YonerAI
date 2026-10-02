from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


class EvolveCommandError(Exception):
    pass


def add_evolve_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    evolve = subcommands.add_parser("evolve", help="Inspect proposal-only self-evolution queue fixtures.")
    evolve_subcommands = evolve.add_subparsers(dest="evolve_command", required=True)

    status = evolve_subcommands.add_parser("status", help="Show proposal-only queue boundaries.")
    _add_output_and_locale(status, lang_choices=lang_choices, color_choices=color_choices, pretty_help="Print a readable queue status.")

    simulate = evolve_subcommands.add_parser("simulate", help="Generate owner-reviewable proposals from synthetic low-resolution signals.")
    simulate.add_argument("--fixture", help="Optional local public-safe queue signal fixture JSON.")
    _add_output_and_locale(simulate, lang_choices=lang_choices, color_choices=color_choices, pretty_help="Print a readable simulation report.")

    proposals = evolve_subcommands.add_parser("proposals", help="List or show proposal-only queue items.")
    proposals_subcommands = proposals.add_subparsers(dest="evolve_proposals_command", required=True)
    list_parser = proposals_subcommands.add_parser("list", help="List synthetic proposal queue items.")
    list_parser.add_argument("--fixture", help="Optional local public-safe queue signal fixture JSON.")
    _add_output_and_locale(list_parser, lang_choices=lang_choices, color_choices=color_choices, pretty_help="Print a readable proposal list.")

    show_parser = proposals_subcommands.add_parser("show", help="Show one synthetic proposal queue item.")
    show_parser.add_argument("proposal_id")
    show_parser.add_argument("--fixture", help="Optional local public-safe queue signal fixture JSON.")
    _add_output_and_locale(show_parser, lang_choices=lang_choices, color_choices=color_choices, pretty_help="Print a readable proposal detail.")


def handle_evolve_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
    repo_root: Path,
) -> int:
    report = build_evolve_report(args, prepare_import_paths=prepare_import_paths, repo_root=repo_root)
    if args.json:
        print_json(report)
    else:
        print(format_evolve_pretty(report, lang=args.lang, color=args.color))
    return 0 if report.get("ok", True) else 1


def build_evolve_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
    repo_root: Path,
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from src.self_evolution import (
            UnsafeSignalError,
            build_queue_list_report,
            build_queue_show_report,
            build_queue_simulation_report,
            build_queue_status_report,
        )
    except Exception as exc:
        raise EvolveCommandError("self-evolution proposal queue is unavailable.") from exc

    try:
        if args.evolve_command == "status":
            return build_queue_status_report()
        signals = _load_evolve_signals(args, prepare_import_paths=prepare_import_paths, repo_root=repo_root)
        if args.evolve_command == "simulate":
            return build_queue_simulation_report(signals)
        if args.evolve_command == "proposals" and args.evolve_proposals_command == "list":
            return build_queue_list_report(signals)
        if args.evolve_command == "proposals" and args.evolve_proposals_command == "show":
            return build_queue_show_report(args.proposal_id, signals)
    except UnsafeSignalError as exc:
        raise EvolveCommandError(str(exc)) from exc
    raise EvolveCommandError("unknown evolve command")


def format_evolve_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    title = "YonerAI self-evolution proposal queue" if lang != "ja" else "YonerAI 自己進化プロポーザルキュー"
    rows = [
        CliRow("schema_version", report.get("schema_version"), "ok"),
        CliRow("ok", report.get("ok", True), "ok" if report.get("ok", True) else "fail"),
    ]
    for key in ("status", "proposal_only", "dry_run", "source", "signal_count", "proposal_count"):
        if key in report:
            rows.append(CliRow(key, report.get(key), "ok"))
    proposal_rows: list[CliRow] = []
    proposals = report.get("proposals")
    if isinstance(proposals, list):
        for item in proposals[:8]:
            if not isinstance(item, dict):
                continue
            signal = item.get("signal") if isinstance(item.get("signal"), dict) else {}
            surface = item.get("surface") or signal.get("surface") or "unknown"
            proposal_rows.append(
                CliRow(
                    str(item.get("proposal_id") or signal.get("feature_id") or "proposal"),
                    f"{item.get('approval_state') or 'unknown'} / {surface}",
                    "warn" if item.get("approval_state") == "needs_owner" else "ok",
                )
            )
    proposal = report.get("proposal")
    if isinstance(proposal, dict):
        signal = proposal.get("signal") if isinstance(proposal.get("signal"), dict) else {}
        candidate = proposal.get("candidate") if isinstance(proposal.get("candidate"), dict) else {}
        proposal_rows.extend(
            [
                CliRow("proposal_id", proposal.get("proposal_id"), "ok"),
                CliRow("approval_state", proposal.get("approval_state"), "warn"),
                CliRow("feature_id", signal.get("feature_id"), "ok"),
                CliRow("surface", signal.get("surface"), "ok"),
                CliRow("user_impact", candidate.get("user_impact"), "ok"),
                CliRow("privacy_risk", candidate.get("privacy_risk"), "ok"),
                CliRow("test_plan", candidate.get("test_plan"), "ok"),
                CliRow("rollback_plan", candidate.get("rollback_plan"), "ok"),
            ]
        )
    actions = tuple(CliRow(item, True, "ok") for item in report.get("actions_not_performed", []))
    sections = [CliSection("Status", tuple(rows))]
    if proposal_rows:
        sections.append(CliSection("Proposals", tuple(proposal_rows)))
    if actions:
        sections.append(CliSection("Non-actions", actions))
    return render_report(title, tuple(sections), color=color)


def _load_evolve_signals(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
    repo_root: Path,
) -> list[Any] | None:
    fixture = getattr(args, "fixture", None)
    if not fixture:
        return None
    try:
        fixture_path = Path(fixture).expanduser().resolve()
        allowed_roots = (repo_root.resolve(), Path.cwd().resolve())
        if not any(fixture_path.is_relative_to(root) for root in allowed_roots):
            raise EvolveCommandError("self-evolution fixture must be inside the current workspace.")
        prepare_import_paths()
        from src.self_evolution import load_queue_signal_fixture

        return list(load_queue_signal_fixture(fixture_path))
    except EvolveCommandError:
        raise
    except Exception as exc:
        raise EvolveCommandError("self-evolution fixture is unavailable.") from exc


def _add_output_and_locale(
    parser: argparse.ArgumentParser,
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
    pretty_help: str,
) -> None:
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    output.add_argument("--pretty", action="store_true", help=pretty_help)
    parser.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    parser.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")
