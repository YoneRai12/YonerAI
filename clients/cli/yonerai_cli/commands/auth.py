from __future__ import annotations

import argparse
from typing import Any, Callable

from yonerai_cli.auth_policy import build_google_auth_status, build_google_login_dry_run, build_privacy_status
from yonerai_cli.config import ConfigError, load_cli_config
from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


class AuthCommandError(Exception):
    pass


def add_auth_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    auth = subcommands.add_parser("auth", help="Inspect local auth contracts without starting production login.")
    auth_subcommands = auth.add_subparsers(dest="auth_command", required=True)
    auth_status = auth_subcommands.add_parser(
        "status", help="Show auth readiness and disabled production-login boundaries."
    )
    auth_status_output = auth_status.add_mutually_exclusive_group()
    auth_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    auth_status_output.add_argument("--pretty", action="store_true", help="Print a readable auth status.")
    auth_status.add_argument("--config-path", help="Optional local CLI config path.")
    auth_status.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    auth_status.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    auth_google = auth_subcommands.add_parser("google", help="Preview Google OAuth installed-app flow contracts.")
    auth_google_subcommands = auth_google.add_subparsers(dest="auth_google_command", required=True)
    auth_google_login = auth_google_subcommands.add_parser(
        "login", help="Dry-run Google OAuth login contract. No live OAuth is started."
    )
    auth_google_login.add_argument("--dry-run", action="store_true", help="Required; do not open a browser or contact Google.")
    auth_google_login.add_argument("--config-path", help="Optional local CLI config path.")
    auth_google_login_output = auth_google_login.add_mutually_exclusive_group()
    auth_google_login_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    auth_google_login_output.add_argument("--pretty", action="store_true", help="Print a readable OAuth dry-run report.")
    auth_google_login.add_argument(
        "--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja."
    )
    auth_google_login.add_argument(
        "--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto."
    )


def add_privacy_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    privacy = subcommands.add_parser("privacy", help="Inspect privacy and shared-traffic policy status.")
    privacy_subcommands = privacy.add_subparsers(dest="privacy_command", required=True)
    privacy_status = privacy_subcommands.add_parser(
        "status", help="Show data sharing, private-content exclusion, and auth privacy state."
    )
    privacy_status.add_argument("--config-path", help="Optional local CLI config path.")
    privacy_status_output = privacy_status.add_mutually_exclusive_group()
    privacy_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    privacy_status_output.add_argument("--pretty", action="store_true", help="Print a readable privacy status.")
    privacy_status.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    privacy_status.add_argument(
        "--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto."
    )


def handle_auth_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    if args.auth_command == "status":
        report = build_google_auth_status(_load_config(args))
    elif args.auth_command == "google" and args.auth_google_command == "login":
        if not args.dry_run:
            raise AuthCommandError("auth google login requires --dry-run in the public repo.")
        report = build_google_login_dry_run(_load_config(args))
    else:
        raise AuthCommandError("unknown auth command")

    if args.json:
        print_json(report)
    else:
        print(format_auth_pretty(report, lang=args.lang, color=args.color))
    return 0 if report["ok"] else 1


def handle_privacy_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    if args.privacy_command != "status":
        raise AuthCommandError("unknown privacy command")

    report = build_privacy_status(_load_config(args))
    if args.json:
        print_json(report)
    else:
        print(format_privacy_pretty(report, lang=args.lang, color=args.color))
    return 0 if report["ok"] else 1


def format_auth_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    flow = report.get("flow") if isinstance(report.get("flow"), dict) else {}
    storage = report.get("storage") if isinstance(report.get("storage"), dict) else {}
    error = report.get("error") if isinstance(report.get("error"), dict) else None
    if lang == "ja":
        title = "YonerAI 認証ステータス"
        flow_title = "Google OAuth 契約"
        storage_title = "保存方針"
        boundary_title = "実行しないこと"
    else:
        title = "YonerAI auth status"
        flow_title = "Google OAuth contract"
        storage_title = "Storage policy"
        boundary_title = "Non-actions"
    flow_rows = (
        CliRow("configured", report.get("configured"), "ok" if report.get("configured") else "warn"),
        CliRow(
            "production_login_enabled",
            report.get("production_login_enabled"),
            "fail" if report.get("production_login_enabled") else "ok",
        ),
        CliRow("live_oauth_enabled", report.get("live_oauth_enabled"), "fail" if report.get("live_oauth_enabled") else "ok"),
        CliRow("scopes", " ".join(str(scope) for scope in flow.get("scopes", [])), "ok"),
        CliRow("pkce_required", flow.get("pkce_required"), "ok" if flow.get("pkce_required") else "fail"),
        CliRow("state_required", flow.get("state_required"), "ok" if flow.get("state_required") else "fail"),
        CliRow(
            "loopback_redirect_only",
            flow.get("loopback_redirect_only"),
            "ok" if flow.get("loopback_redirect_only") else "fail",
        ),
        CliRow(
            "embedded_webview_allowed",
            flow.get("embedded_webview_allowed"),
            "fail" if flow.get("embedded_webview_allowed") else "ok",
        ),
        CliRow("token_printed", report.get("token_printed"), "fail" if report.get("token_printed") else "ok"),
    )
    storage_rows = (
        CliRow("refresh_token_storage", storage.get("refresh_token_storage"), "ok"),
        CliRow(
            "plain_text_token_storage_allowed",
            storage.get("plain_text_token_storage_allowed"),
            "fail" if storage.get("plain_text_token_storage_allowed") else "ok",
        ),
        CliRow("keyring_only_future", storage.get("keyring_only_future"), "ok" if storage.get("keyring_only_future") else "warn"),
    )
    non_action_rows = tuple(CliRow(item, True, "ok") for item in report.get("actions_not_performed", []))
    sections = (
        CliSection(flow_title, flow_rows),
        CliSection(storage_title, storage_rows),
        CliSection(boundary_title, non_action_rows),
    )
    if error:
        sections = (*sections, CliSection("Error", (CliRow(str(error.get("code")), error.get("message"), "warn"),)))
    return render_report(title, sections, color=color)


def format_privacy_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    data_sharing = report.get("data_sharing") if isinstance(report.get("data_sharing"), dict) else {}
    exclusion = report.get("private_content_exclusion") if isinstance(report.get("private_content_exclusion"), dict) else {}
    ledger = report.get("ledger") if isinstance(report.get("ledger"), dict) else {}
    quota = report.get("quota") if isinstance(report.get("quota"), dict) else {}
    if lang == "ja":
        title = "YonerAI プライバシー状態"
        sharing_title = "OpenAI 共有トラフィック"
        exclusion_title = "除外する内容"
        ledger_title = "ledger"
        quota_title = "quota"
        boundary_title = "実行しないこと"
    else:
        title = "YonerAI privacy status"
        sharing_title = "OpenAI shared traffic"
        exclusion_title = "Private content exclusion"
        ledger_title = "Ledger"
        quota_title = "Quota"
        boundary_title = "Non-actions"
    sharing_rows = (
        CliRow(
            "requested",
            data_sharing.get("openai_shared_traffic_requested"),
            "warn" if data_sharing.get("openai_shared_traffic_requested") else "ok",
        ),
        CliRow(
            "enabled",
            data_sharing.get("openai_shared_traffic_enabled"),
            "fail" if data_sharing.get("openai_shared_traffic_enabled") else "ok",
        ),
        CliRow(
            "requires_explicit_opt_in",
            data_sharing.get("requires_explicit_opt_in"),
            "ok" if data_sharing.get("requires_explicit_opt_in") else "fail",
        ),
        CliRow(
            "runtime_supported",
            data_sharing.get("runtime_supported"),
            "warn" if data_sharing.get("runtime_supported") else "ok",
        ),
    )
    exclusion_rows = (
        CliRow("active", exclusion.get("active"), "ok" if exclusion.get("active") else "fail"),
        CliRow("excluded", ", ".join(str(item) for item in exclusion.get("excluded", [])), "ok"),
    )
    ledger_rows = (
        CliRow(
            "shared_traffic_flag_recorded",
            ledger.get("shared_traffic_flag_recorded"),
            "ok" if ledger.get("shared_traffic_flag_recorded") else "fail",
        ),
        CliRow("default_shared_traffic", ledger.get("default_shared_traffic"), "fail" if ledger.get("default_shared_traffic") else "ok"),
        CliRow("raw_prompt_persisted", ledger.get("raw_prompt_persisted"), "fail" if ledger.get("raw_prompt_persisted") else "ok"),
    )
    quota_rows = (
        CliRow("daily_quota_placeholder", quota.get("daily_quota_placeholder"), "warn" if quota.get("daily_quota_placeholder") else "ok"),
        CliRow("free_usage_claimed", quota.get("free_usage_claimed"), "fail" if quota.get("free_usage_claimed") else "ok"),
        CliRow(
            "owner_or_org_eligibility_assumed",
            quota.get("owner_or_org_eligibility_assumed"),
            "fail" if quota.get("owner_or_org_eligibility_assumed") else "ok",
        ),
    )
    non_action_rows = tuple(CliRow(item, True, "ok") for item in report.get("actions_not_performed", []))
    return render_report(
        title,
        (
            CliSection(sharing_title, sharing_rows),
            CliSection(exclusion_title, exclusion_rows),
            CliSection(ledger_title, ledger_rows),
            CliSection(quota_title, quota_rows),
            CliSection(boundary_title, non_action_rows),
        ),
        color=color,
    )


def _load_config(args: argparse.Namespace) -> dict[str, object]:
    try:
        return load_cli_config(getattr(args, "config_path", None))
    except ConfigError as exc:
        raise AuthCommandError(str(exc)) from exc
