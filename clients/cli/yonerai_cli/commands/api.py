from __future__ import annotations

import argparse
import importlib.util
import os
from typing import Any, Callable

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.screens.control_spine import format_control_spine_pretty
from yonerai_cli.services.control_spine_service import (
    CONTROL_SPINE_SCHEMA_VERSION,
    build_control_spine_ping_report,
    build_control_spine_rate_limit_report,
    build_control_spine_status_report,
    load_config_for_control_spine,
)


class ApiCommandError(Exception):
    pass


SYNC_AUTH_STATE_CHOICES = ("unauthenticated", "dry_run", "pending", "linked", "expired", "revoked")
STATUS_PROFILE_CHOICES = (
    "operational",
    "degraded_api",
    "maintenance",
    "oracle_not_production",
    "auth_dry_run_only",
    "install_operational",
    "alpha_available_stable_current",
)


def add_api_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    api = subcommands.add_parser("api", help="Inspect official API contracts and explicit staging API state.")
    api_subcommands = api.add_subparsers(dest="api_command", required=True)

    status = api_subcommands.add_parser("status", help="Show official API readiness or staging Control Spine status.")
    status.add_argument("--auth-state", choices=SYNC_AUTH_STATE_CHOICES, default="dry_run")
    status.add_argument(
        "--status-source",
        help="Optional local status-feed JSON path or allowlisted HTTPS status URL. URL fetch also requires --allow-network-status-fetch.",
    )
    status.add_argument(
        "--allow-network-status-fetch",
        action="store_true",
        help="Explicitly allow fetching an allowlisted HTTPS status URL. Disabled by default.",
    )
    status.add_argument("--status-profile", choices=STATUS_PROFILE_CHOICES, default="operational")
    _add_staging_options(status)
    _add_output_and_locale(status, lang_choices=lang_choices, color_choices=color_choices, pretty_help="Print readable official API status.")

    contract = api_subcommands.add_parser("contract", help="Show the official API fixture contract.")
    _add_output_and_locale(contract, lang_choices=lang_choices, color_choices=color_choices, pretty_help="Print readable official API contract.")

    rate_limit = api_subcommands.add_parser("rate-limit", help="Show rate-limit policy or explicit staging rate-limit state.")
    _add_staging_options(rate_limit)
    _add_output_and_locale(rate_limit, lang_choices=lang_choices, color_choices=color_choices, pretty_help="Print readable official API rate-limit policy.")

    ping = api_subcommands.add_parser("ping", help="Ping the explicit staging Control Spine API when configured.")
    _add_staging_options(ping)
    _add_output_and_locale(ping, lang_choices=lang_choices, color_choices=color_choices, pretty_help="Print readable staging API ping.")


def handle_api_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
) -> int:
    report = build_api_report(args, prepare_import_paths=prepare_import_paths)
    if args.json:
        print_json(report)
    else:
        print(format_api_pretty(report, lang=args.lang, color=args.color))
    return 0 if report.get("ok", True) else 1


def build_api_report(args: argparse.Namespace, *, prepare_import_paths: Callable[[], None]) -> dict[str, Any]:
    if args.api_command == "ping":
        return build_control_spine_ping_report(
            config=load_config_for_control_spine(getattr(args, "config_path", None)),
            env=os.environ,
            claim_path=getattr(args, "config_path", None),
            timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
        )
    if args.api_command == "status" and _staging_origin_configured():
        return build_control_spine_status_report(
            config=load_config_for_control_spine(getattr(args, "config_path", None)),
            env=os.environ,
            claim_path=getattr(args, "config_path", None),
            timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
        )
    if args.api_command == "rate-limit" and _staging_origin_configured():
        return build_control_spine_rate_limit_report(
            config=load_config_for_control_spine(getattr(args, "config_path", None)),
            env=os.environ,
            claim_path=getattr(args, "config_path", None),
            timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
        )

    prepare_import_paths()
    importlib.invalidate_caches()
    official_available = (
        importlib.util.find_spec("ora_core") is not None
        and importlib.util.find_spec("ora_core.official") is not None
    )
    if not official_available:
        raise ApiCommandError("official API contract fixtures are unavailable.")
    from ora_core.official import (
        build_official_api_contract_fixture,
        build_official_api_status_report,
        build_rate_limit_policy_report,
        build_status_check_report,
    )

    try:
        if args.api_command == "status":
            report = build_official_api_status_report(auth_state=getattr(args, "auth_state", "dry_run"))
            report["status_bridge"] = build_status_check_report(
                source=getattr(args, "status_source", None),
                allow_network=bool(getattr(args, "allow_network_status_fetch", False)),
                profile=getattr(args, "status_profile", "operational"),
            )
            return report
        if args.api_command == "contract":
            return build_official_api_contract_fixture()
        if args.api_command == "rate-limit":
            return build_rate_limit_policy_report()
    except ValueError as exc:
        raise ApiCommandError(str(exc)) from exc
    raise ApiCommandError("unknown api command")


def format_api_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    if report.get("schema_version") == CONTROL_SPINE_SCHEMA_VERSION:
        return format_control_spine_pretty(report, lang=lang, color=color)

    title = "YonerAI Official API" if lang != "ja" else "YonerAI 公式API"
    rows = [
        CliRow("schema_version", report.get("schema_version"), "ok"),
        CliRow("ok", report.get("ok", True), "ok" if report.get("ok", True) else "fail"),
    ]
    for key in (
        "official_api_configured",
        "endpoint_url",
        "auth_state",
        "official_backend_called",
        "production_backend_included",
        "shared_traffic_enabled",
    ):
        if key in report:
            level = "fail" if key.endswith("included") and report.get(key) else "ok"
            rows.append(CliRow(key, report.get(key), level))
    status_bridge = report.get("status_bridge") if isinstance(report.get("status_bridge"), dict) else {}
    sections = [CliSection("Status", tuple(rows))]
    if status_bridge:
        sections.append(
            CliSection(
                "Status API bridge",
                (
                    CliRow("status", status_bridge.get("status"), "warn"),
                    CliRow("component_count", status_bridge.get("component_count"), "ok"),
                    CliRow(
                        "private_runtime_details_included",
                        status_bridge.get("private_runtime_details_included"),
                        "fail" if status_bridge.get("private_runtime_details_included") else "ok",
                    ),
                ),
            )
        )
    actions = tuple(CliRow(f"action_{idx}", item, "ok") for idx, item in enumerate(report.get("actions_not_performed", []), start=1))
    if actions:
        sections.append(CliSection("Non-actions", actions))
    return render_report(title, tuple(sections), color=color)


def _add_staging_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config-path", help="Optional local CLI config path.")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="Network timeout for explicit staging API calls. Default: 10.",
    )


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


def _staging_origin_configured() -> bool:
    return bool(os.environ.get("YONERAI_STAGING_AUTH_ORIGIN") or os.environ.get("YONERAI_OFFICIAL_API_STAGING_ORIGIN"))
