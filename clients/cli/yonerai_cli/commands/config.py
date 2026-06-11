from __future__ import annotations

import argparse
from typing import Any, Callable

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.services.config_service import ConfigServiceError, build_config_status_report, set_config_status_report


class ConfigCommandError(Exception):
    pass


CONFIG_KEY_CHOICES = (
    "language",
    "lang",
    "command_display",
    "command_display_mode",
    "command_aliases",
    "commands_display",
    "コマンド表示",
    "コマンド",
    "provider",
    "provider_preference",
    "model",
    "model_preference",
    "agent_mode",
    "mode",
    "approval",
    "approval_mode",
    "file_access",
    "file_access_mode",
    "live_provider",
    "network",
    "ledger",
    "history",
    "memory",
    "memory_enabled",
    "memory_scope",
    "memory_default_scope",
    "memory_cloud_preview",
    "memory_cloud_to_local_preview",
    "memory_self_evolution_signal",
    "self_evolution_memory",
    "memory_local_to_cloud_approval_required",
    "google_auth",
    "auth_google",
    "openai_data_sharing",
    "data_sharing",
    "shared_traffic",
)


def add_config_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    config = subcommands.add_parser("config", help="Show or update local YonerAI CLI preferences. No secrets are stored.")
    config_subcommands = config.add_subparsers(dest="config_command", required=True)

    config_show = config_subcommands.add_parser("show", help="Show local CLI preferences without printing the config path.")
    config_show.add_argument("--config-path", help="Optional local CLI config path.")
    config_show_output = config_show.add_mutually_exclusive_group()
    config_show_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    config_show_output.add_argument("--pretty", action="store_true", help="Print a readable settings summary.")
    config_show.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    config_show.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    config_set = config_subcommands.add_parser("set", help="Set one local CLI preference. Provider keys are not accepted.")
    config_set.add_argument("config_key", choices=CONFIG_KEY_CHOICES)
    config_set.add_argument("config_value")
    config_set.add_argument("--config-path", help="Optional local CLI config path.")
    config_set_output = config_set.add_mutually_exclusive_group()
    config_set_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    config_set_output.add_argument("--pretty", action="store_true", help="Print a readable settings summary.")
    config_set.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    config_set.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_config_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    try:
        if args.config_command == "set":
            report = set_config_status_report(args)
        elif args.config_command == "show":
            report = build_config_status_report(args)
        else:
            raise ConfigCommandError("unknown config command")
    except ConfigServiceError as exc:
        raise ConfigCommandError(str(exc)) from exc

    if args.json:
        print_json(report)
    else:
        print(format_config_pretty(report, lang=args.lang, color=args.color))
    return 0


def format_config_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    config = report.get("config") if isinstance(report.get("config"), dict) else {}
    if lang == "ja":
        title = "YonerAI 設定"
        settings_title = "設定"
        boundary_title = "境界"
    else:
        title = "YonerAI config"
        settings_title = "Settings"
        boundary_title = "Boundary"
    rows = (
        CliRow("language", config.get("language") or "ja", "ok"),
        CliRow("command_display", config.get("command_display_mode") or "ja_only", "ok"),
        CliRow("provider", config.get("provider_preference"), "ok"),
        CliRow("model", config.get("model_preference"), "ok"),
        CliRow("approval", config.get("approval_mode"), "ok"),
        CliRow("file_access", config.get("file_access_mode"), "ok"),
        CliRow("live_provider", config.get("live_provider_enabled"), "warn" if config.get("live_provider_enabled") else "ok"),
        CliRow("network", config.get("network_enabled"), "warn" if config.get("network_enabled") else "ok"),
        CliRow("tools", config.get("tools_mode"), "ok"),
        CliRow("ledger", config.get("ledger_enabled"), "ok" if config.get("ledger_enabled") else "warn"),
        CliRow("google_auth", config.get("google_auth_enabled"), "warn" if config.get("google_auth_enabled") else "ok"),
        CliRow(
            "openai_data_sharing",
            config.get("openai_data_sharing_enabled"),
            "warn" if config.get("openai_data_sharing_enabled") else "ok",
        ),
    )
    boundary_rows = (
        CliRow("secrets_supported", report.get("secrets_supported"), "fail" if report.get("secrets_supported") else "ok"),
        CliRow(
            "path_persisted_in_output",
            report.get("path_persisted_in_output"),
            "fail" if report.get("path_persisted_in_output") else "ok",
        ),
    )
    return render_report(title, (CliSection(settings_title, rows), CliSection(boundary_title, boundary_rows)), color=color)
