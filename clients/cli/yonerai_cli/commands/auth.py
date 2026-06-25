from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Mapping
from typing import Any

from yonerai_cli.auth_policy import (
    build_google_auth_status,
    build_google_login_dry_run,
    build_google_login_staging,
    build_privacy_status,
)
from yonerai_cli.config import ConfigError, load_cli_config
from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.screens.auth_privacy import format_auth_status_report
from yonerai_cli.screens.control_spine import (
    format_control_spine_compact,
    format_control_spine_pretty,
    format_login_flow_compact,
)
from yonerai_cli.screens.labels import _safe
from yonerai_cli.services.auth_session_service import save_staging_auth_claim
from yonerai_cli.services.control_spine_service import (
    ControlSpineServiceError,
    build_session_report,
    build_whoami_report,
    load_config_for_control_spine,
)
from yonerai_cli.services.provider_sharing_service import (
    ProviderSharingError,
    build_provider_sharing_disable_report,
    build_provider_sharing_enable_report,
    build_provider_sharing_status_report,
)
from yonerai_cli.services.staging_session_service import (
    build_staging_session_status,
    clear_staging_session,
    save_staging_session,
)


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

    auth_session = auth_subcommands.add_parser("session", help="Inspect safe staging session storage.")
    auth_session_subcommands = auth_session.add_subparsers(dest="auth_session_command", required=True)
    auth_session_status = auth_session_subcommands.add_parser("status", help="Show staging session claim status.")
    auth_session_status.add_argument("--config-path", help="Optional local CLI config path.")
    auth_session_status_output = auth_session_status.add_mutually_exclusive_group()
    auth_session_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    auth_session_status_output.add_argument("--pretty", action="store_true", help="Print a readable staging session status.")
    auth_session_status.add_argument(
        "--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja."
    )
    auth_session_status.add_argument(
        "--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto."
    )

    auth_logout = auth_subcommands.add_parser("logout", help="Clear local staging auth/session state.")
    auth_logout.add_argument("--staging", action="store_true", help="Clear only the staging YonerAI session claim.")
    auth_logout.add_argument("--config-path", help="Optional local CLI config path.")
    auth_logout_output = auth_logout.add_mutually_exclusive_group()
    auth_logout_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    auth_logout_output.add_argument("--pretty", action="store_true", help="Print a readable logout result.")
    auth_logout.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    auth_logout.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    auth_sessions = auth_subcommands.add_parser("sessions", help="List staging CLI sessions if the backend supports it.")
    _add_control_spine_output(auth_sessions, lang_choices=lang_choices, color_choices=color_choices)

    auth_revoke = auth_subcommands.add_parser("revoke-session", help="Revoke a staging CLI session if the backend supports it.")
    auth_revoke.add_argument("session_id", help="Session id returned by `yonerai auth sessions`.")
    _add_control_spine_output(auth_revoke, lang_choices=lang_choices, color_choices=color_choices)

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
    auth_google_login.add_argument("--poll-request-id", help="Poll a one-time staging CLI bridge request id.")
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

    sharing = privacy_subcommands.add_parser(
        "provider-sharing",
        help="Inspect or change per-conversation provider-sharing consent. Default is off.",
    )
    sharing_subcommands = sharing.add_subparsers(dest="privacy_provider_sharing_command", required=True)
    sharing_status = sharing_subcommands.add_parser("status", help="Show provider-sharing consent status.")
    sharing_status.add_argument("conversation_id", nargs="?", help="Optional conversation id.")
    sharing_status.add_argument("--store", dest="provider_sharing_store", help="Optional consent store path.")
    sharing_status.add_argument("--config-path", help="Optional local CLI config path.")
    sharing_status_output = sharing_status.add_mutually_exclusive_group()
    sharing_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    sharing_status_output.add_argument("--pretty", action="store_true", help="Print readable provider-sharing status.")
    sharing_status.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    sharing_status.add_argument(
        "--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto."
    )

    sharing_enable = sharing_subcommands.add_parser(
        "enable",
        help="Enable OpenAI shared traffic for one conversation after explicit confirmation.",
    )
    sharing_enable.add_argument("conversation_id", help="Conversation id to enable.")
    sharing_enable.add_argument(
        "--sync-policy",
        choices=("cloud_to_local", "bidirectional_explicit", "paused", "local_only"),
        default="cloud_to_local",
        help="Current sync policy for this conversation.",
    )
    sharing_enable.add_argument("--confirm", action="store_true", help="Record explicit per-conversation consent.")
    sharing_enable.add_argument("--store", dest="provider_sharing_store", help="Optional consent store path.")
    sharing_enable.add_argument("--config-path", help="Optional local CLI config path.")
    sharing_enable_output = sharing_enable.add_mutually_exclusive_group()
    sharing_enable_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    sharing_enable_output.add_argument("--pretty", action="store_true", help="Print readable consent result.")
    sharing_enable.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    sharing_enable.add_argument(
        "--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto."
    )

    sharing_disable = sharing_subcommands.add_parser("disable", help="Disable future provider sharing for one conversation.")
    sharing_disable.add_argument("conversation_id", help="Conversation id to disable.")
    sharing_disable.add_argument("--store", dest="provider_sharing_store", help="Optional consent store path.")
    sharing_disable.add_argument("--config-path", help="Optional local CLI config path.")
    sharing_disable_output = sharing_disable.add_mutually_exclusive_group()
    sharing_disable_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    sharing_disable_output.add_argument("--pretty", action="store_true", help="Print readable consent result.")
    sharing_disable.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    sharing_disable.add_argument(
        "--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto."
    )


def _add_control_spine_output(
    parser: argparse.ArgumentParser,
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    parser.add_argument("--config-path", help="Optional local CLI config path.")
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="Network timeout. Default: 10.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    output.add_argument("--pretty", action="store_true", help="Print a readable staging session report.")
    parser.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    parser.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_auth_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    if args.auth_command == "status":
        report = build_google_auth_status(_load_config(args), claim_path=getattr(args, "config_path", None))
        formatter = format_auth_pretty
    elif args.auth_command == "session" and args.auth_session_command == "status":
        report = build_staging_session_status(getattr(args, "config_path", None))
        formatter = format_session_pretty
    elif args.auth_command == "logout":
        if not args.staging:
            raise AuthCommandError("auth logout requires --staging in the public repo.")
        report = clear_staging_session(getattr(args, "config_path", None))
        formatter = format_control_spine_compact if getattr(args, "short_command", False) else format_session_pretty
    elif args.auth_command == "sessions":
        try:
            report = build_session_report(
                "list",
                config=load_config_for_control_spine(getattr(args, "config_path", None)),
                env=os.environ,
                claim_path=getattr(args, "config_path", None),
                timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
            )
        except ControlSpineServiceError as exc:
            raise AuthCommandError(exc.message) from exc
        formatter = format_control_spine_compact if getattr(args, "short_command", False) else format_control_spine_pretty
    elif args.auth_command == "revoke-session":
        try:
            report = build_session_report(
                "revoke",
                session_id=getattr(args, "session_id", None),
                config=load_config_for_control_spine(getattr(args, "config_path", None)),
                env=os.environ,
                claim_path=getattr(args, "config_path", None),
                timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
            )
        except ControlSpineServiceError as exc:
            raise AuthCommandError(exc.message) from exc
        formatter = format_control_spine_compact if getattr(args, "short_command", False) else format_control_spine_pretty
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
                session_claim_handler=_staging_session_handler(
                    getattr(args, "config_path", None),
                    origin=_configured_staging_origin(),
                ),
            )
            _persist_staging_claim_if_linked(report, config_path=getattr(args, "config_path", None))
            formatter = format_auth_pretty
        elif args.dry_run:
            if args.bridge or args.poll_request_id:
                raise AuthCommandError("--bridge and --poll-request-id require --staging.")
            report = build_google_login_dry_run(_load_config(args))
            formatter = format_auth_pretty
        else:
            raise AuthCommandError("auth google login requires --dry-run or --staging in the public repo.")
    else:
        raise AuthCommandError("unknown auth command")

    if args.json:
        print_json(report)
    else:
        if formatter is format_control_spine_compact:
            print(formatter(report, lang=args.lang))
        else:
            print(formatter(report, lang=args.lang, color=args.color))
    return 0 if report["ok"] else 1


def _staging_session_handler(
    config_path: str | None,
    *,
    origin: str,
) -> Callable[[str, Mapping[str, object], Mapping[str, object]], Mapping[str, object]]:
    def store(session_token: str, poll_report: Mapping[str, object], account_report: Mapping[str, object]) -> Mapping[str, object]:
        account = account_report.get("account") if isinstance(account_report.get("account"), dict) else {}
        claim = save_staging_session(
            session_token=session_token,
            origin=origin,
            account=account,
            expires_at=poll_report.get("expires_at"),
            config_path=config_path,
        )
        return {
            "stored": True,
            "storage_backend": claim.get("storage_backend"),
            "session_hash": claim.get("session_hash"),
            "expires_at": claim.get("expires_at"),
            "token_printed": False,
            "google_token_stored": False,
            "google_access_token_stored": False,
            "google_id_token_stored": False,
            "google_refresh_token_stored": False,
            "auth_code_stored": False,
            "plaintext_session_token_stored": False,
        }

    return store


def _configured_staging_origin() -> str:
    return (
        os.environ.get("YONERAI_STAGING_AUTH_ORIGIN")
        or os.environ.get("YONERAI_OFFICIAL_API_STAGING_ORIGIN")
        or "https://api-staging.yonerai.com"
    )


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


def build_staging_login_report(
    config_path: str | None,
    *,
    lang: str,
    bridge: bool,
    open_browser: bool,
    wait_linked: bool,
    timeout_seconds: float = 10.0,
    max_wait_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
) -> dict[str, Any]:
    login_env = dict(os.environ)
    if not any(str(login_env.get(key) or "").strip() for key in ("YONERAI_STAGING_AUTH_ORIGIN", "YONERAI_OFFICIAL_API_STAGING_ORIGIN")):
        login_env["YONERAI_STAGING_AUTH_ORIGIN"] = _configured_staging_origin()
    try:
        config = load_cli_config(config_path)
    except ConfigError as exc:
        raise AuthCommandError(str(exc)) from exc
    report = build_google_login_staging(
        config,
        env=login_env,
        bridge=bridge,
        timeout_seconds=timeout_seconds,
        open_browser=open_browser,
        wait_linked=wait_linked,
        max_wait_seconds=max_wait_seconds,
        poll_interval_seconds=poll_interval_seconds,
        session_claim_handler=_staging_session_handler(
            config_path,
            origin=_configured_staging_origin(),
        ),
    )
    _persist_staging_claim_if_linked(report, config_path=config_path)
    return report


def handle_login_alias_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    if not getattr(args, "staging", True):
        raise AuthCommandError("public CLI login is staging-only in this build.")
    explicit_flow_flags = (
        bool(getattr(args, "bridge", False))
        or bool(getattr(args, "open_browser", False))
        or bool(getattr(args, "wait_linked", False))
    )
    implicit_user_login = not bool(getattr(args, "json", False)) and not explicit_flow_flags
    bridge = bool(getattr(args, "bridge", False) or implicit_user_login)
    open_browser = bool(getattr(args, "open_browser", False) or implicit_user_login)
    wait_linked = bool(getattr(args, "wait_linked", False) or implicit_user_login)
    if open_browser and not bridge:
        raise AuthCommandError("--open-browser requires --bridge.")
    if wait_linked and not bridge:
        raise AuthCommandError("--wait-linked requires --bridge.")
    report = build_staging_login_report(
        getattr(args, "config_path", None),
        lang=args.lang,
        bridge=bridge,
        open_browser=open_browser,
        wait_linked=wait_linked,
        timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
        max_wait_seconds=float(getattr(args, "max_wait_seconds", 120.0)),
        poll_interval_seconds=float(getattr(args, "poll_interval_seconds", 2.0)),
    )
    if args.json:
        print_json(report)
    else:
        print(format_login_flow_compact(report, lang=args.lang))
    return 0 if report["ok"] else 1


def handle_whoami_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    report = build_whoami_report(
        config=load_config_for_control_spine(getattr(args, "config_path", None)),
        env=os.environ,
        claim_path=getattr(args, "config_path", None),
        timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
    )
    if args.json:
        print_json(report)
    else:
        formatter = format_control_spine_compact if getattr(args, "short_command", False) else format_control_spine_pretty
        if formatter is format_control_spine_compact:
            print(formatter(report, lang=args.lang))
        else:
            print(formatter(report, lang=args.lang, color=args.color))
    return 0 if report.get("ok", True) else 1


def handle_privacy_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    if args.privacy_command == "status":
        report = build_privacy_status(_load_config(args))
        formatter = format_privacy_pretty
    elif args.privacy_command == "provider-sharing":
        try:
            if args.privacy_provider_sharing_command == "status":
                report = build_provider_sharing_status_report(
                    conversation_id=getattr(args, "conversation_id", None),
                    store_path=getattr(args, "provider_sharing_store", None),
                    config_path=getattr(args, "config_path", None),
                )
            elif args.privacy_provider_sharing_command == "enable":
                report = build_provider_sharing_enable_report(
                    str(args.conversation_id),
                    sync_policy=str(getattr(args, "sync_policy", "cloud_to_local")),
                    confirm=bool(getattr(args, "confirm", False)),
                    store_path=getattr(args, "provider_sharing_store", None),
                    config_path=getattr(args, "config_path", None),
                )
            elif args.privacy_provider_sharing_command == "disable":
                report = build_provider_sharing_disable_report(
                    str(args.conversation_id),
                    store_path=getattr(args, "provider_sharing_store", None),
                    config_path=getattr(args, "config_path", None),
                )
            else:
                raise AuthCommandError("unknown provider-sharing command")
        except ProviderSharingError as exc:
            raise AuthCommandError(exc.message) from exc
        formatter = format_provider_sharing_pretty
    else:
        raise AuthCommandError("unknown privacy command")
    if args.json:
        print_json(report)
    else:
        print(formatter(report, lang=args.lang, color=args.color))
    return 0 if report["ok"] else 1


def format_auth_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    del color
    return format_auth_status_report(report, lang=lang)


def format_session_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    if lang == "ja":
        title = "YonerAI ステージングセッション"
        session_title = "安全なセッション claim"
        boundary_title = "保存しないもの"
    else:
        title = "YonerAI staging session"
        session_title = "Safe session claim"
        boundary_title = "Never stored"
    auth_state = str(report.get("auth_state", "unauthenticated"))
    session_rows = (
        CliRow("operation", report.get("operation"), "ok"),
        CliRow("auth_state", auth_state, "ok" if auth_state == "linked" else "warn"),
        CliRow("session_available", report.get("session_available", False), "ok" if report.get("session_available") else "warn"),
        CliRow("origin", report.get("origin", "not_configured"), "ok" if report.get("origin") != "not_configured" else "warn"),
        CliRow("account", report.get("redacted_email") or report.get("display_name") or "not-linked", "ok" if report.get("session_available") else "warn"),
        CliRow("expires_at", report.get("expires_at") or "not-linked", "ok" if report.get("expires_at") else "warn"),
        CliRow(
            "relogin_action",
            "yonerai login" if auth_state in {"expired", "revoked", "unauthenticated"} else "not_needed",
            "warn" if auth_state in {"expired", "revoked", "unauthenticated"} else "ok",
        ),
        CliRow("storage_backend", report.get("storage_backend", "none"), "ok" if report.get("storage_backend") != "none" else "warn"),
        CliRow("session_hash", report.get("session_hash") or "not-linked", "ok" if report.get("session_hash") else "warn"),
        CliRow("session_removed", report.get("session_removed", False), "ok" if report.get("operation") == "staging_logout" else "warn"),
    )
    boundary_rows = (
        CliRow("token_printed", report.get("token_printed", False), "fail" if report.get("token_printed") else "ok"),
        CliRow("google_token_stored", report.get("google_token_stored", False), "fail" if report.get("google_token_stored") else "ok"),
        CliRow(
            "google_access_token_stored",
            report.get("google_access_token_stored", False),
            "fail" if report.get("google_access_token_stored") else "ok",
        ),
        CliRow(
            "google_refresh_token_stored",
            report.get("google_refresh_token_stored", False),
            "fail" if report.get("google_refresh_token_stored") else "ok",
        ),
        CliRow("auth_code_stored", report.get("auth_code_stored", False), "fail" if report.get("auth_code_stored") else "ok"),
        CliRow(
            "plaintext_session_token_stored",
            report.get("plaintext_session_token_stored", False),
            "fail" if report.get("plaintext_session_token_stored") else "ok",
        ),
        CliRow(
            "production_login_enabled",
            report.get("production_login_enabled", False),
            "fail" if report.get("production_login_enabled") else "ok",
        ),
    )
    return render_report(
        title,
        (
            CliSection(session_title, session_rows),
            CliSection(boundary_title, boundary_rows),
        ),
        color=color,
    )


def _staging_account_label(account: Mapping[str, object]) -> object:
    email = account.get("email_redacted")
    if email and email != "not-linked":
        return email
    return account.get("display_name") or "not-linked"


def _friendly_auth_state(state: str, *, lang: str) -> str:
    if lang == "ja":
        return {
            "linked": "連携済み (α/stagingのみ)",
            "pending": "ログイン待ち (α/stagingのみ)",
            "expired": "期限切れ (α/stagingのみ)",
            "revoked": "失効済み (α/stagingのみ)",
            "unauthenticated": "未連携 (α/stagingのみ)",
        }.get(state, f"{state} (α/stagingのみ)")
    return {
        "linked": "linked (staging only)",
        "pending": "waiting for login (staging only)",
        "expired": "expired (staging only)",
        "revoked": "revoked (staging only)",
        "unauthenticated": "not linked (staging only)",
    }.get(state, f"{state} (staging only)")


def _friendly_auth_account_label(report: Mapping[str, Any], *, lang: str) -> str:
    for candidate in (
        report.get("staging_account"),
        report.get("staging_session_claim"),
        report.get("staging_linked_claim"),
        report.get("staging_session"),
    ):
        if isinstance(candidate, Mapping):
            email = str(candidate.get("email_redacted") or candidate.get("redacted_email") or "").strip()
            if email and email != "not-linked":
                return email
            display_name = str(candidate.get("display_name") or "").strip()
            if display_name and display_name != "not-linked":
                return display_name
            account = candidate.get("account")
            if isinstance(account, Mapping):
                nested_email = str(account.get("email_redacted") or account.get("redacted_email") or "").strip()
                if nested_email and nested_email != "not-linked":
                    return nested_email
                nested_display_name = str(account.get("display_name") or "").strip()
                if nested_display_name and nested_display_name != "not-linked":
                    return nested_display_name
    return "未連携" if lang == "ja" else "not linked"


def _friendly_staging_label(*, staging_ready: bool, error_code: str, lang: str) -> str:
    if staging_ready:
        return "利用可 (α/staging)" if lang == "ja" else "available (staging)"
    if error_code.startswith("staging_origin_") and error_code != "staging_auth_origin_not_configured":
        return (
            "設定が無効です。allowlisted HTTPS host に直してください"
            if lang == "ja"
            else "configured value is invalid; use an allowlisted HTTPS host"
        )
    return (
        "簡単ログイン可 (既定の staging 接続先)"
        if lang == "ja"
        else "ready via the default staging origin"
    )


def _friendly_auth_note(
    *,
    raw_state: str,
    error_code: str,
    error_message: str,
    lang: str,
) -> str:
    if raw_state == "unauthenticated":
        return (
            "まだクラウド連携していません。`yonerai login` でブラウザ連携を始められます。"
            if lang == "ja"
            else "Your cloud account is not linked yet. Run `yonerai login` to start browser sign-in."
        )
    if error_code == "google_oauth_client_not_configured":
        return (
            "Google client secret はこの CLI に保存しません。staging 側でログインを完結させます。"
            if lang == "ja"
            else "This CLI does not keep a Google client secret. Sign-in is completed on the staging side."
        )
    if error_code == "staging_auth_origin_not_configured":
        return (
            "接続先を変えない限り環境変数は不要です。既定では https://api-staging.yonerai.com を使います。"
            if lang == "ja"
            else "You do not need env vars unless you want a different staging target. The default is https://api-staging.yonerai.com."
        )
    if error_code.startswith("staging_origin_"):
        return (
            "現在の staging 接続先設定が無効です。allowlisted HTTPS host に直してください。"
            if lang == "ja"
            else "The current staging origin setting is invalid. Replace it with an allowlisted HTTPS host."
        )
    if error_message:
        return error_message
    return ""


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


def format_provider_sharing_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    title = "YonerAI provider sharing consent" if lang != "ja" else "YonerAI provider sharing consent"
    rows = [
        CliRow("ok", report.get("ok", True), "ok" if report.get("ok", True) else "fail"),
        CliRow("operation", report.get("operation"), "ok"),
        CliRow("shared_traffic_default", report.get("shared_traffic_default"), "fail" if report.get("shared_traffic_default") else "ok"),
        CliRow("implicit_consent_allowed", report.get("implicit_consent_allowed"), "fail" if report.get("implicit_consent_allowed") else "ok"),
        CliRow("sync_policy_is_separate", report.get("sync_policy_is_separate"), "ok" if report.get("sync_policy_is_separate") else "fail"),
        CliRow("provider_data_policy_is_separate", report.get("provider_data_policy_is_separate"), "ok" if report.get("provider_data_policy_is_separate") else "fail"),
        CliRow("local_only_openai_allowed", report.get("local_only_openai_allowed"), "fail" if report.get("local_only_openai_allowed") else "ok"),
    ]
    conversation = report.get("conversation") if isinstance(report.get("conversation"), dict) else {}
    if conversation:
        conversation_rows = (
            CliRow("conversation_id", conversation.get("conversation_id"), "ok"),
            CliRow("provider_data_policy", conversation.get("provider_data_policy"), "warn" if conversation.get("provider_data_policy") == "openai_shared_explicit" else "ok"),
            CliRow("sync_policy_at_consent", conversation.get("sync_policy_at_consent"), "ok"),
            CliRow("consent_state", conversation.get("consent_state"), "ok" if conversation.get("consent_state") == "enabled" else "warn"),
            CliRow("consent_version", conversation.get("consent_version"), "ok"),
            CliRow("raw_body_stored", conversation.get("raw_body_stored"), "fail" if conversation.get("raw_body_stored") else "ok"),
            CliRow("provider_key_stored", conversation.get("provider_key_stored"), "fail" if conversation.get("provider_key_stored") else "ok"),
            CliRow("google_token_stored", conversation.get("google_token_stored"), "fail" if conversation.get("google_token_stored") else "ok"),
            CliRow("local_path_stored", conversation.get("local_path_stored"), "fail" if conversation.get("local_path_stored") else "ok"),
        )
    else:
        conversation_rows = (
            CliRow("conversation_count", report.get("conversation_count", 0), "ok"),
            CliRow("empty_state", report.get("empty_state") or "has records", "warn" if report.get("empty_state") else "ok"),
        )
    consent_copy = report.get("consent_copy") if isinstance(report.get("consent_copy"), dict) else {}
    consent_rows = tuple(
        CliRow(key, consent_copy.get(key), "warn" if consent_copy.get(key) is True else "ok")
        for key in (
            "selected_conversation_content_sent_to_openai",
            "inputs_and_outputs_shared_under_openai_data_sharing_settings",
            "may_be_used_for_evaluation_improvement_or_training",
            "revocation_stops_future_sharing",
            "already_submitted_data_recall_promised",
            "local_only_excluded",
        )
        if key in consent_copy
    )
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    decision_rows = tuple(CliRow(key, value, "warn" if key == "state" and value != "written" else "ok") for key, value in decision.items())
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    error_rows = tuple(CliRow(key, value, "fail" if key == "code" else "warn") for key, value in error.items())
    action_rows = tuple(CliRow(f"boundary_{idx}", item, "ok") for idx, item in enumerate(report.get("actions_not_performed", []), start=1))
    sections = [
        CliSection("Status", tuple(rows)),
        CliSection("Conversation", conversation_rows),
    ]
    if consent_rows:
        sections.append(CliSection("Consent text", consent_rows))
    if decision_rows:
        sections.append(CliSection("Decision", decision_rows))
    if error_rows:
        sections.append(CliSection("Error", error_rows))
    if action_rows:
        sections.append(CliSection("Non-actions", action_rows))
    return render_report(title, tuple(sections), color=color)


def _load_config(args: argparse.Namespace) -> dict[str, object]:
    try:
        return load_cli_config(getattr(args, "config_path", None))
    except ConfigError as exc:
        raise AuthCommandError(str(exc)) from exc
