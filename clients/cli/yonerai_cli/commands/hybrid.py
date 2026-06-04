from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


class HybridCommandError(Exception):
    pass


def add_hybrid_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    provider_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    hybrid = subcommands.add_parser("hybrid", help="Run public-safe local-dev Hybrid execution slices.")
    hybrid_subcommands = hybrid.add_subparsers(dest="hybrid_command", required=True)
    hybrid_run = hybrid_subcommands.add_parser(
        "run",
        help="Run the local-dev Hybrid execution slice: route, local relay, oracle stub, provider, ledger.",
    )
    hybrid_run.add_argument("task", nargs="*", help="Optional task text. Defaults to the deterministic fixture task.")
    hybrid_run.add_argument("--provider", choices=provider_choices, default="mock", help="Provider for local provider execution. Default: mock.")
    hybrid_run.add_argument("--live", action="store_true", help="Allow explicitly configured local/provider execution. Default: off.")
    hybrid_run.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    hybrid_run_output = hybrid_run.add_mutually_exclusive_group()
    hybrid_run_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    hybrid_run_output.add_argument("--pretty", action="store_true", help="Print a readable Hybrid execution slice summary.")
    hybrid_run.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_hybrid_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> int:
    report = build_hybrid_report(args, prepare_import_paths=prepare_import_paths, env=env)
    if args.pretty:
        print(format_hybrid_pretty(report, color=args.color))
    else:
        print_json(report)
    return 0 if report["ok"] else 1


def build_hybrid_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.execution import build_run_ledger_from_env
        from ora_core.hybrid import DEFAULT_HYBRID_EXECUTION_TASK, build_hybrid_execution_slice_report
    except Exception as exc:
        raise HybridCommandError("Hybrid execution slice is unavailable.") from exc
    if args.hybrid_command != "run":
        raise HybridCommandError("unknown hybrid command")
    task = " ".join(args.task).strip() or DEFAULT_HYBRID_EXECUTION_TASK
    ledger = build_run_ledger_from_env(args.ledger_path)
    return build_hybrid_execution_slice_report(
        task,
        provider=args.provider,
        live=args.live,
        ledger=ledger,
        env=env,
    )


def format_hybrid_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    provider = report.get("provider_execution") if isinstance(report.get("provider_execution"), dict) else {}
    provider_run = provider.get("run") if isinstance(provider.get("run"), dict) else {}
    provider_response = provider.get("response") if isinstance(provider.get("response"), dict) else {}
    selected_route = report.get("selected_route") if isinstance(report.get("selected_route"), dict) else {}
    local_node = report.get("local_node_runtime") if isinstance(report.get("local_node_runtime"), dict) else {}
    proxy = local_node.get("http_proxy_fixture") if isinstance(local_node.get("http_proxy_fixture"), dict) else {}
    oracle = report.get("oracle_stub_execution") if isinstance(report.get("oracle_stub_execution"), dict) else {}
    oracle_request = oracle.get("request") if isinstance(oracle.get("request"), dict) else {}
    boundaries = report.get("boundaries") if isinstance(report.get("boundaries"), dict) else {}
    route_rows = tuple(
        CliRow(
            str(item.get("name")),
            str(item.get("route_strategy")),
            "ok",
            note=f"privacy={item.get('privacy_class')} approval={item.get('approval_state')}",
        )
        for item in report.get("route_matrix", [])
        if isinstance(item, dict)
    )
    sections = (
        CliSection(
            "Hybrid run",
            (
                CliRow("status", "ok" if report.get("ok") else "failed", "ok" if report.get("ok") else "fail"),
                CliRow("selected_route", selected_route.get("route_strategy"), "ok"),
                CliRow("provider_run_id", provider_run.get("run_id"), "ok" if provider_run.get("run_id") else "warn"),
                CliRow("provider", provider_response.get("provider") or "none", "ok" if provider_response else "warn"),
            ),
        ),
        CliSection(
            "Local-dev node and relay",
            (
                CliRow("local_node_runtime", local_node.get("ok"), "ok" if local_node.get("ok") else "fail"),
                CliRow(
                    "relay_loopback_only",
                    _nested_dict(local_node.get("relay"), "loopback_only"),
                    "ok" if _nested_dict(local_node.get("relay"), "loopback_only") is True else "fail",
                ),
                CliRow("proxy_status", proxy.get("status"), "ok" if proxy.get("status") == "completed" else "warn"),
                CliRow("message_body_persisted", boundaries.get("message_body_persisted"), "fail" if boundaries.get("message_body_persisted") else "ok"),
            ),
        ),
        CliSection(
            "Oracle stub",
            (
                CliRow("status", oracle.get("status"), "ok" if oracle.get("ok") else "warn"),
                CliRow("run_id", oracle_request.get("run_id"), "ok" if oracle_request.get("run_id") else "warn"),
                CliRow("route_strategy", oracle_request.get("route_strategy"), "ok"),
                CliRow("raw_prompt_sent", boundaries.get("raw_prompt_sent_to_oracle_stub"), "fail" if boundaries.get("raw_prompt_sent_to_oracle_stub") else "ok"),
                CliRow(
                    "private_file_sent",
                    boundaries.get("private_file_content_sent_to_oracle_stub"),
                    "fail" if boundaries.get("private_file_content_sent_to_oracle_stub") else "ok",
                ),
            ),
        ),
        CliSection("Route matrix", route_rows),
        CliSection(
            "Non-actions",
            tuple(CliRow("boundary", item, "ok") for item in report.get("actions_not_performed", [])),
        ),
    )
    return render_report("YonerAI Hybrid local-dev run", sections, color=color)


def _nested_dict(value: object, key: str) -> object:
    return value.get(key) if isinstance(value, dict) else None
