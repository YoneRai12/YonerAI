from __future__ import annotations

import argparse
from typing import Any, Callable

from yonerai_cli.commands.ask import prompt_from_args
from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


class RouteCommandError(Exception):
    pass


class RouteCommandUserInputError(RouteCommandError):
    pass


def add_route_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    mode_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    route = subcommands.add_parser("route", help="Preview safe YonerAI task routing without executing it.")
    route_subcommands = route.add_subparsers(dest="route_command", required=True)
    route_preview = route_subcommands.add_parser("preview", help="Preview cloud/local/hybrid/disabled routing.")
    route_preview.add_argument("task", nargs="+")
    route_preview.add_argument(
        "--mode",
        choices=mode_choices,
        default="official_managed_cloud",
        help="YonerAI mode boundary. Default: official_managed_cloud.",
    )
    route_preview.add_argument("--capability", help="Optional explicit capability name.")
    route_preview.add_argument("--risk-hint", help="Optional public-safe operation class hint.")
    route_preview.add_argument("--has-local-node", action="store_true", help="Preview as if a user Local Node is available.")
    route_preview.add_argument(
        "--use-local-node-fixture",
        action="store_true",
        help="Use the public-safe Hybrid Wire v0.3 Local Node dev fixture for route preview.",
    )
    route_preview.add_argument(
        "--local-node-state",
        choices=(
            "missing",
            "present_unverified",
            "present_verified",
            "expired",
            "invalid_signature",
            "wrong_audience",
        ),
        help="Optional test-only Local Node verification state for route preview.",
    )
    route_preview.add_argument(
        "--local-node-capability",
        action="append",
        help="Optional declared capability for a verified test Local Node manifest. Repeatable.",
    )
    route_preview.add_argument(
        "--require-enrolled-verified-session",
        action="store_true",
        help="Require a public-safe enrolled verified Local Node session state for local work previews.",
    )
    route_preview.add_argument(
        "--session-state",
        choices=(
            "missing",
            "unenrolled",
            "pairing_pending",
            "enrolled_unverified",
            "enrolled_verified",
            "expired",
            "revoked",
            "wrong_audience",
        ),
        help="Optional public-safe Local Node enrollment/session state for route preview.",
    )
    route_preview_output = route_preview.add_mutually_exclusive_group()
    route_preview_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    route_preview_output.add_argument("--pretty", action="store_true", help="Print a readable route preview.")
    route_preview.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_route_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
) -> int:
    report = build_route_preview_report(args, prepare_import_paths=prepare_import_paths)
    if args.pretty:
        print(format_route_preview_pretty(report, color=args.color))
    else:
        print_json(report)
    return 0


def build_route_preview_report(args: argparse.Namespace, *, prepare_import_paths: Callable[[], None]) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.route_preview import preview_route
    except Exception as exc:
        raise RouteCommandError("route preview is unavailable.") from exc

    prompt = prompt_from_args(args.task)
    local_node_state = args.local_node_state
    fixture_inputs: dict[str, object] | None = None
    if getattr(args, "use_local_node_fixture", False):
        try:
            from ora_core.hybrid.wire_contract import (
                build_local_node_status_report,
                route_preview_inputs_from_node_status,
            )
        except Exception as exc:
            raise RouteCommandError("Hybrid Wire Local Node fixture is unavailable.") from exc
        status_report = build_local_node_status_report()
        local_node = status_report.get("local_node")
        if isinstance(local_node, dict):
            fixture_inputs = route_preview_inputs_from_node_status(local_node)

    has_local_node = args.has_local_node or local_node_state in {
        "present_unverified",
        "present_verified",
        "expired",
        "invalid_signature",
        "wrong_audience",
    }
    if local_node_state == "missing":
        has_local_node = False
    local_node_capabilities = tuple(args.local_node_capability or ()) or None
    require_session = args.require_enrolled_verified_session or args.session_state is not None
    session_state = args.session_state
    if fixture_inputs is not None:
        has_local_node = bool(fixture_inputs["has_local_node"])
        local_node_state = str(fixture_inputs["local_node_verification_state"])
        local_node_capabilities = tuple(fixture_inputs["local_node_capabilities"])  # type: ignore[arg-type]
        require_session = bool(fixture_inputs["require_enrolled_verified_session"])
        session_state = str(fixture_inputs["session_verification_state"])

    decision = preview_route(
        prompt,
        mode=args.mode,
        requested_capability=args.capability,
        has_local_node=has_local_node,
        local_node_verification_state=local_node_state,
        local_node_capabilities=local_node_capabilities,
        require_enrolled_verified_session=require_session,
        session_verification_state=session_state,
        risk_hint=args.risk_hint,
    )
    report = decision.to_public_dict()
    if fixture_inputs is not None:
        report["hybrid_wire_node_fixture_used"] = True
        report["node_posture_state"] = fixture_inputs.get("node_posture_state")
        report["local_work_preview_allowed"] = fixture_inputs.get("local_work_preview_allowed")
    return report


def format_route_preview_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    audit = report.get("audit_requirements")
    if not isinstance(audit, dict):
        audit = {}
    sections = (
        CliSection(
            "Route preview",
            (
                CliRow("route", report.get("route"), "fail" if report.get("route_strategy") == "deny" else "ok"),
                CliRow("route_strategy", report.get("route_strategy"), "ok"),
                CliRow("task_class", report.get("task_class"), "ok"),
                CliRow("privacy_class", report.get("privacy_class"), "warn" if report.get("privacy_class") != "public" else "ok"),
                CliRow("requested_capability", report.get("requested_capability"), "ok"),
            ),
        ),
        CliSection(
            "Local and cloud gates",
            (
                CliRow("node_posture_state", report.get("node_posture_state") or "none", "ok"),
                CliRow("capability_gate", report.get("capability_gate"), "ok" if report.get("capability_gate") == "satisfied" else "warn"),
                CliRow("approval_state", report.get("approval_state"), "warn" if report.get("approval_state") == "required" else "ok"),
                CliRow("cloud_escape_reason", report.get("cloud_escape_reason") or "none", "warn" if report.get("cloud_escape_reason") else "ok"),
                CliRow("oracle_stub_status", report.get("oracle_stub_status"), "ok" if report.get("oracle_stub_eligible") else "warn"),
            ),
        ),
        CliSection(
            "Audit requirements",
            (
                CliRow("audit_event_required", audit.get("audit_event_required"), "ok"),
                CliRow("args_hash_required", audit.get("args_hash_required"), "ok" if audit.get("args_hash_required") else "warn"),
                CliRow("preserve_approval", audit.get("cloud_escape_preserves_approval"), "ok"),
                CliRow("preserve_args_hash", audit.get("cloud_escape_preserves_args_hash"), "ok"),
            ),
        ),
    )
    return render_report("YonerAI route preview", sections, color=color)
