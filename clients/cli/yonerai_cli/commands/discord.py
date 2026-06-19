from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping

from yonerai_cli.commands.ask import prompt_from_args
from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.services.ledger_service import build_ledger_status, start_cli_boundary_run


class DiscordCommandError(Exception):
    pass


def add_discord_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    color_choices: tuple[str, ...],
) -> None:
    discord = subcommands.add_parser("discord", help="Inspect public-safe Discord gateway adapter boundaries.")
    discord_subcommands = discord.add_subparsers(dest="discord_command", required=True)
    discord_synthetic = discord_subcommands.add_parser("synthetic", help="Run a synthetic Discord mention fixture.")
    discord_synthetic.add_argument("message", nargs="+")
    discord_synthetic.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    discord_synthetic_output = discord_synthetic.add_mutually_exclusive_group()
    discord_synthetic_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    discord_synthetic_output.add_argument("--pretty", action="store_true", help="Print a readable Discord adapter summary.")
    discord_synthetic.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_discord_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> int:
    report = build_discord_report(args, prepare_import_paths=prepare_import_paths, env=env)
    if args.json:
        print_json(report)
    else:
        print(format_discord_pretty(report, color=args.color))
    return 0 if report["ok"] else 1


def build_discord_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.discord_gateway import SyntheticDiscordGatewayAdapter
        from ora_core.execution.ledger import build_run_ledger_from_env
    except Exception as exc:
        raise DiscordCommandError("Discord gateway adapter is unavailable.") from exc

    prompt = prompt_from_args(args.message)
    ledger = build_run_ledger_from_env(args.ledger_path)
    ledger_status = build_ledger_status(args.ledger_path, env=env)
    run = start_cli_boundary_run(
        ledger,
        task_text=f"discord synthetic {prompt}",
        category="synthetic_discord_gateway",
        route="synthetic_discord_gateway",
        provider_id="synthetic-discord-gateway",
        provider_available=True,
    )
    result = SyntheticDiscordGatewayAdapter().handle_mention(prompt)
    report = result.to_public_dict()
    ledger.append_event(run.run_id, "synthetic_discord_gateway", "ok", f"progress_events={report['progress_events']}")
    run = ledger.complete_run(run.run_id, result_summary="synthetic Discord gateway completed")
    report["run"] = run.to_public_dict()
    report["ledger"] = ledger_status
    return report


def format_discord_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    rows = (
        CliRow("run_id", report.get("run", {}).get("run_id", "unknown"), "ok"),
        CliRow("run_status", report.get("run", {}).get("status", "completed"), "ok"),
        CliRow("adapter", report["adapter"], "ok" if report["ok"] else "fail"),
        CliRow("synthetic", report["synthetic"], "ok" if report["synthetic"] else "fail"),
        CliRow("live_discord", report["live_discord"], "fail" if report["live_discord"] else "ok"),
        CliRow("token_required", report["token_required"], "fail" if report["token_required"] else "ok"),
        CliRow("final_once", report["final_once"], "ok" if report["final_once"] else "fail"),
        CliRow("progress_events", report["progress_events"], "ok"),
    )
    return render_report("YonerAI Discord gateway", (CliSection("Synthetic adapter", rows),), color=color)
