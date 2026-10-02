from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping

from yonerai_cli.commands.ask import prompt_from_args
from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.services.ledger_service import build_ledger_status, start_cli_boundary_run


class SearchCommandError(Exception):
    pass


def add_search_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    color_choices: tuple[str, ...],
) -> None:
    search = subcommands.add_parser("search", help="Run deterministic mock search or report live search as disabled.")
    search.add_argument("search_mode", choices=("mock", "live"), help="Search mode. Default-safe mode is mock.")
    search.add_argument("query", nargs="+")
    search.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    search_output = search.add_mutually_exclusive_group()
    search_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    search_output.add_argument("--pretty", action="store_true", help="Print a readable search fixture summary.")
    search.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_search_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> int:
    report = build_search_report(args, prepare_import_paths=prepare_import_paths, env=env)
    if args.json:
        print_json(report)
    else:
        print(format_search_pretty(report, color=args.color))
    return 0 if report["ok"] else 1


def build_search_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.execution.ledger import build_run_ledger_from_env
        from ora_core.search import MockSearchAdapter, SearchRequest, build_live_search_disabled_boundary
    except Exception as exc:
        raise SearchCommandError("search adapter is unavailable.") from exc

    ledger = build_run_ledger_from_env(args.ledger_path)
    ledger_status = build_ledger_status(args.ledger_path, env=env)
    if args.search_mode != "mock":
        query = _safe_prompt_from_args(args.query)
        live_boundary = build_live_search_disabled_boundary(query)
        run = start_cli_boundary_run(
            ledger,
            task_text=f"search live {query}",
            category="web_search_boundary",
            route="live_search_disabled_boundary",
            provider_id="live-search",
            provider_available=False,
            disabled_reason=live_boundary["reason"],
        )
        ledger.append_event(run.run_id, "live_search_boundary", "blocked", live_boundary["reason"])
        run = ledger.fail_run(run.run_id, error_summary=live_boundary["message"], blocked=True)
        return {
            "schema_version": "yonerai-search/v1",
            "ok": False,
            "adapter": args.search_mode,
            "query": query,
            "run": run.to_public_dict(),
            "ledger": ledger_status,
            "execution_performed": False,
            "network_performed": False,
            "live_boundary": live_boundary,
            "error": {"code": "search_live_disabled", "message": "live search is not implemented in this public runtime"},
            "results": [],
        }

    query = prompt_from_args(args.query)
    run = start_cli_boundary_run(
        ledger,
        task_text=f"search mock {query}",
        category="mock_web_search",
        route="mock_search_adapter",
        provider_id="mock-search",
        provider_available=True,
    )
    results = [result.to_public_dict() for result in MockSearchAdapter().search(SearchRequest(query=query))]
    ledger.append_event(run.run_id, "mock_search_results", "ok", f"result_count={len(results)}")
    run = ledger.complete_run(run.run_id, result_summary=f"mock search returned {len(results)} results")
    return {
        "schema_version": "yonerai-search/v1",
        "ok": True,
        "adapter": "mock",
        "run": run.to_public_dict(),
        "ledger": ledger_status,
        "execution_performed": False,
        "network_performed": False,
        "query": query,
        "results": results,
    }


def format_search_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    if not report["ok"]:
        boundary = report.get("live_boundary") or {}
        run = report.get("run") or {}
        reason = str(boundary.get("reason") or "unknown")
        reason_status = "fail" if reason == "unknown" else "warn"
        message = str(boundary.get("message") or report.get("error", {}).get("message") or "no message")
        actions = ", ".join(boundary.get("actions_not_performed") or ())
        return render_report(
            "YonerAI search",
            (
                CliSection(
                    "Live search boundary",
                    (
                        CliRow("run_id", run.get("run_id", "unknown"), "warn"),
                        CliRow("run_status", run.get("status", "blocked"), "warn"),
                        CliRow("status", boundary.get("status", "disabled"), "warn"),
                        CliRow("reason", reason, reason_status),
                        CliRow("message", message, reason_status),
                        CliRow("network_performed", report.get("network_performed", False), "ok"),
                        CliRow("actions_not_performed", actions or "no network request", "ok"),
                    ),
                ),
            ),
            color=color,
        )

    run = report.get("run") or {}
    rows = tuple(CliRow(result["title"], result["snippet"], "ok") for result in report["results"])
    return render_report(
        "YonerAI search",
        (
            CliSection(
                "Run",
                (
                    CliRow("run_id", run.get("run_id", "unknown"), "ok"),
                    CliRow("run_status", run.get("status", "completed"), "ok"),
                ),
            ),
            CliSection("Mock results", rows),
        ),
        color=color,
    )


def _safe_prompt_from_args(parts: list[str] | tuple[str, ...]) -> str:
    return " ".join(" ".join(str(part or "").split()) for part in parts).strip()
