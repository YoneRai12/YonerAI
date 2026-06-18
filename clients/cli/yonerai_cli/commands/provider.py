from __future__ import annotations

import argparse
import os
from typing import Any, Callable

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.services.provider_gateway_service import (
    build_provider_gateway_report,
    load_config_for_provider_gateway,
)


class ProviderCommandError(Exception):
    pass


def add_provider_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    provider = subcommands.add_parser(
        "provider",
        help="Inspect staging provider gateway state. Shared traffic is off by default.",
    )
    provider_subcommands = provider.add_subparsers(dest="provider_command", required=True)
    for name, help_text in (
        ("status", "Show staging provider gateway status."),
        ("quota", "Show staging provider quota state."),
        ("models", "Show staging provider model list if available."),
        ("disable", "Disable provider gateway locally for this CLI session report."),
    ):
        parser = provider_subcommands.add_parser(name, help=help_text)
        _add_common_options(parser, lang_choices=lang_choices, color_choices=color_choices)


def handle_provider_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    report = build_provider_gateway_report(
        str(args.provider_command),
        config=load_config_for_provider_gateway(getattr(args, "config_path", None)),
        env=os.environ,
        claim_path=getattr(args, "config_path", None),
        timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
    )
    if args.json:
        print_json(report)
    else:
        print(format_provider_gateway_pretty(report, lang=args.lang, color=args.color))
    return 0 if report.get("ok", True) else 1


def format_provider_gateway_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    title = "YonerAI provider gateway (alpha/staging)"
    status_rows = (
        CliRow("ok", report.get("ok", True), "ok" if report.get("ok", True) else "fail"),
        CliRow("operation", report.get("operation"), "ok"),
        CliRow("backend", report.get("backend_url"), "ok"),
        CliRow("staging_only", report.get("staging_only"), "ok"),
        CliRow("provider_gateway_available", report.get("provider_gateway_available"), "ok" if report.get("provider_gateway_available") else "warn"),
        CliRow("openai_shared_traffic_default", report.get("openai_shared_traffic_default"), "fail" if report.get("openai_shared_traffic_default") else "ok"),
        CliRow("openai_key_in_public_cli", report.get("openai_key_in_public_cli"), "fail" if report.get("openai_key_in_public_cli") else "ok"),
        CliRow("paid_overage_allowed", report.get("paid_overage_allowed"), "fail" if report.get("paid_overage_allowed") else "ok"),
    )
    sections = [CliSection("Status", status_rows)]
    for key, title_key in (
        ("provider_status", "Provider status"),
        ("quota", "Quota"),
    ):
        payload = report.get(key) if isinstance(report.get(key), dict) else {}
        if payload:
            sections.append(CliSection(title_key, tuple(CliRow(str(k), v, "ok") for k, v in payload.items())))
    models = report.get("models") if isinstance(report.get("models"), list) else []
    if models:
        sections.append(
            CliSection(
                "Models",
                tuple(
                    CliRow(f"model_{idx}", ", ".join(f"{k}={v}" for k, v in item.items()), "ok")
                    for idx, item in enumerate(models[:10], start=1)
                    if isinstance(item, dict)
                ),
            )
        )
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        sections.append(CliSection("Error", tuple(CliRow(str(k), v, "fail" if k == "code" else "warn") for k, v in error.items())))
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    if actions:
        sections.append(CliSection("Non-actions", tuple(CliRow(f"boundary_{idx}", item, "ok") for idx, item in enumerate(actions, start=1))))
    return render_report(title, tuple(sections), color=color)


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
    output.add_argument("--pretty", action="store_true", help="Print a readable provider gateway report.")
    parser.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    parser.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")
