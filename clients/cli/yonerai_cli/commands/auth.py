from __future__ import annotations

import argparse
from typing import Any, Callable

from yonerai_cli.auth_policy import (
    build_google_auth_status,
    build_google_login_dry_run,
    build_google_login_staging,
    build_privacy_status,
)
from yonerai_cli.config import ConfigError, load_cli_config
from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.services.auth_session_service import save_staging_auth_claim


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
        "login", help="Dry-run or staging Google OAuth login contract. Production OAuth is disabled."
    )
    mode_group = auth_google_login.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="Preview the installed-app OAuth contract only.")
    mode_group.add_argument(
        "--staging",
        action="store_true",
        help="Generate a staging YonerAI auth URL when an allowlisted staging origin is configured.",
    )
    auth_google_login.add_argument(
        "--bridge",
        action="store_true",
        help="Explicitly call the staging CLI bridge start endpoint. Network is off unless this is set.",
    )
    auth_google_login.add_argument(
        "--poll-request-id",
        help="Poll a one-time staging CLI bridge request id. Does not print tokens.",
    )
    auth_google_login.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="Network timeout for explicit staging bridge calls. Default: 10.",
    )
    auth_google_login.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the staging Google auth URL after starting a bridge request.",
    )
    auth_google_login.add_argument(
        "--wait-linked",
        action="store_true",
        help="Poll the staging CLI bridge until it links or times out. Does not print tokens.",
    )
    auth_google_login.add_argument(
        "--max-wait-seconds",
        type=float,
        default=120.0,
        help="Maximum wait for --wait-linked. Default: 120.",
    )
    auth_google_login.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=2.0,
        help="Polling interval for --wait-linked. Default: 2.",
    )
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
        report = build_google_auth_status(_load_config(args), claim_path=getattr(args, "config_path", None))
    elif args.auth_command == "google" and args.auth_google_command == "login":
        if args.staging:
            if args.open_browser and not args.bridge:
                raise AuthCommandError("--open-browser requires --bridge.")
            if args.wait_linked and not (args.bridge or args.poll_request_id):
                raise AuthCommandError("--wait-linked requires --bridge or --poll-request-id.")
            report = build_google_login_staging(
                _load_config(args),
                bridge=bool(args.bridge),
                poll_request_id=args.poll_request_id,
                timeout_seconds=args.timeout_seconds,
                open_browser=bool(args.open_browser),
                wait_linked=bool(args.wait_linked),
                max_wait_seconds=args.max_wait_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
            )
            _persist_staging_claim_if_linked(report, config_path=getattr(args, "config_path", None))
        elif args.dry_run:
            if args.bridge or args.poll_request_id:
                raise AuthCommandError("--bridge and --poll-request-id require --staging.")
            report = build_google_login_dry_run(_load_config(args))
        else:
            raise AuthCommandError("auth google login requires --dry-run or --staging in the public repo.")
    else:
        raise AuthCommandError("unknown auth command")

    if args.json:
        print_json(report)
    else:
        print(format_auth_pretty(report, lang=args.lang, color=args.color))
    return 0 if report["ok"] else 1


def _persist_staging_claim_if_linked(report: dict[str, Any], *, config_path: str | None) -> None:
    claim = report.get("staging_linked_claim")
    if not isinstance(claim, dict):
        return
    try:
        saved = save_staging_auth_claim(claim, config_path=config_path)
    except ValueError:
        report["ok"] = False
        report["staging_linked"] = False
        report["staging_linked_claim"] = None
        report["staging_claim_saved"] = False
        report["staging_session_token_stored"] = False
        report["error"] = {
            "code": "staging_claim_save_failed",
            "message": "Staging linked account claim could not be saved safely.",
            "private_path_printed": False,
            "token_printed": False,
        }
        return
    report["staging_linked_claim"] = saved
    report["staging_claim_saved"] = True
    report["staging_session_token_stored"] = False


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
    staging = report.get("staging") if isinstance(report.get("staging"), dict) else {}
    staging_api = report.get("staging_api") if isinstance(report.get("staging_api"), dict) else {}
    staging_session = report.get("staging_session") if isinstance(report.get("staging_session"), dict) else {}
    linked_claim = report.get("staging_linked_claim") if isinstance(report.get("staging_linked_claim"), dict) else {}
    cli_bridge = report.get("cli_bridge") if isinstance(report.get("cli_bridge"), dict) else {}
    account_me = cli_bridge.get("account_me") if isinstance(cli_bridge.get("account_me"), dict) else {}
    account = (
        linked_claim.get("account")
        if isinstance(linked_claim.get("account"), dict)
        else staging_session.get("account")
        if isinstance(staging_session.get("account"), dict)
        else {}
    )
    error = report.get("error") if isinstance(report.get("error"), dict) else None
    if lang == "ja":
        title = "YonerAI 認証ステータス"
        flow_title = "Google OAuth 契約"
        staging_title = "Staging Googleログイン"
        storage_title = "保存方針"
        boundary_title = "実行しないこと"
    else:
        title = "YonerAI auth status"
        flow_title = "Google OAuth contract"
        staging_title = "Staging Google login"
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
    staging_available = bool(report.get("staging_login_available") or report.get("staging_login") or staging.get("configured"))
    staging_rows = (
        CliRow(
            "staging_login_available",
            staging_available,
            "ok" if staging_available else "warn",
        ),
        CliRow("origin", staging.get("origin", "not_configured"), "ok" if staging.get("configured") else "warn"),
        CliRow(
            "auth_state",
            report.get("staging_auth_state") or staging_session.get("auth_state") or ("linked" if linked_claim else "unauthenticated"),
            "ok" if (report.get("staging_auth_state") == "linked" or staging_session.get("auth_state") == "linked" or linked_claim) else "warn",
        ),
        CliRow("linked_account", _staging_account_label(account), "ok" if account else "warn"),
        CliRow(
            "authorization_url",
            report.get("authorization_url", "not_started_or_not_configured"),
            "ok" if report.get("authorization_url") else "warn",
        ),
        CliRow("browser_opened", report.get("browser_opened", False), "ok" if report.get("browser_opened") else "warn"),
        CliRow(
            "client_secret_required",
            report.get("client_secret_required", False),
            "fail" if report.get("client_secret_required") else "ok",
        ),
        CliRow(
            "token_exchange_performed",
            report.get("token_exchange_performed", False),
            "fail" if report.get("token_exchange_performed") else "ok",
        ),
        CliRow("account_sync_performed", False, "ok"),
        CliRow("staging_contract_fixture_only", staging_api.get("fixture_only", True), "ok"),
        CliRow("bridge_network_called", cli_bridge.get("network_called", False), "warn" if cli_bridge.get("network_called") else "ok"),
        CliRow("bridge_request_id", cli_bridge.get("request_id") or "not_started", "ok" if cli_bridge.get("request_id") else "warn"),
        CliRow("bridge_poll_status", cli_bridge.get("poll_status") or "not_started", "ok"),
        CliRow(
            "staging_session_received",
            cli_bridge.get("staging_session_received", False),
            "ok" if cli_bridge.get("staging_session_received") else "warn",
        ),
        CliRow(
            "staging_claim_saved",
            report.get("staging_claim_saved", False),
            "ok" if report.get("staging_claim_saved") else "warn",
        ),
        CliRow(
            "account_me_status",
            account_me.get("status_code") or "not_called",
            "ok" if account_me.get("ok") else "warn",
        ),
        CliRow(
            "staging_session_token_printed",
            cli_bridge.get("staging_session_token_printed", False),
            "fail" if cli_bridge.get("staging_session_token_printed") else "ok",
        ),
        CliRow(
            "staging_session_token_stored",
            report.get("staging_session_token_stored", False),
            "fail" if report.get("staging_session_token_stored") else "ok",
        ),
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
        CliSection(staging_title, staging_rows),
        CliSection(storage_title, storage_rows),
        CliSection(boundary_title, non_action_rows),
    )
    if error:
        sections = (*sections, CliSection("Error", (CliRow(str(error.get("code")), error.get("message"), "warn"),)))
    return render_report(title, sections, color=color)


def _staging_account_label(account: dict[str, object]) -> object:
    email = account.get("email_redacted")
    if email and email != "not-linked":
        return email
    return account.get("display_name") or "not-linked"


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
