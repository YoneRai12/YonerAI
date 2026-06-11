from __future__ import annotations

import argparse
import importlib.util
import os
from typing import Any, Callable

from yonerai_cli.config import ConfigError, load_cli_config
from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.services.staging_sync_service import (
    StagingSyncServiceError,
    build_staging_conversation_show_report,
    build_staging_conversations_report,
    build_staging_sync_preview_report,
    build_staging_sync_status,
)


class SyncCommandError(Exception):
    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


SYNC_AUTH_STATE_CHOICES = ("unauthenticated", "dry_run", "pending", "linked", "expired", "revoked")
SYNC_DIRECTION_CHOICES = ("cloud-to-local", "local-to-cloud")


def add_sync_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    sync = subcommands.add_parser("sync", help="Preview official account sync contracts and staging sync boundaries.")
    sync_subcommands = sync.add_subparsers(dest="sync_command", required=True)

    status = sync_subcommands.add_parser("status", help="Show cloud/local sync state and boundaries.")
    status.add_argument("--auth-state", choices=SYNC_AUTH_STATE_CHOICES, default="dry_run")
    status.add_argument("--selected", action="store_true", help="Fixture: cloud conversation is user-selected.")
    status.add_argument("--config-path", help="Optional local CLI config path.")
    status.add_argument("--timeout-seconds", type=float, default=10.0, help="Staging API timeout. Default: 10.")
    _add_output_and_locale(
        status,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable sync status.",
    )

    conversations = sync_subcommands.add_parser(
        "conversations",
        help="List staging cloud conversation refs if the account-required API is available.",
    )
    conversations.add_argument("--config-path", help="Optional local CLI config path.")
    conversations.add_argument("--timeout-seconds", type=float, default=10.0, help="Staging API timeout. Default: 10.")
    _add_output_and_locale(
        conversations,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable cloud conversation refs.",
    )

    conversation = sync_subcommands.add_parser("conversation", help="Inspect one staging cloud conversation ref.")
    conversation_subcommands = conversation.add_subparsers(dest="sync_conversation_command", required=True)
    conversation_show = conversation_subcommands.add_parser("show", help="Show a redacted staging cloud conversation summary.")
    conversation_show.add_argument("conversation_id", help="Cloud conversation id returned by sync conversations.")
    conversation_show.add_argument("--config-path", help="Optional local CLI config path.")
    conversation_show.add_argument("--timeout-seconds", type=float, default=10.0, help="Staging API timeout. Default: 10.")
    _add_output_and_locale(
        conversation_show,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print a readable cloud conversation summary.",
    )

    preview = sync_subcommands.add_parser("preview", help="Preview a sync decision. No sync is performed.")
    preview.add_argument("direction_value", nargs="?", choices=SYNC_DIRECTION_CHOICES, help="Optional short direction.")
    preview.add_argument("--direction", choices=SYNC_DIRECTION_CHOICES, default="cloud-to-local")
    preview.add_argument("--fixture-auth-state", choices=SYNC_AUTH_STATE_CHOICES, default="dry_run")
    preview.add_argument("--selected", action="store_true", help="Fixture: cloud conversation is user-selected.")
    preview.add_argument("--explicit-approval", action="store_true", help="Fixture: local-to-cloud approval exists.")
    preview.add_argument("--include-private-file", action="store_true", help="Fixture flag; content is still excluded.")
    preview.add_argument("--include-local-memory", action="store_true", help="Fixture flag; content is still excluded.")
    preview.add_argument("--include-local-node-payload", action="store_true", help="Fixture flag; content is still excluded.")
    preview.add_argument(
        "--conversation-ref",
        default="cloud-conversation-fixture",
        help="Public cloud conversation ref for staging preview.",
    )
    preview.add_argument(
        "--audit-reason",
        default="public_cli_sync_preview",
        help="Public audit reason for staging preview.",
    )
    preview.add_argument("--config-path", help="Optional local CLI config path.")
    preview.add_argument("--timeout-seconds", type=float, default=10.0, help="Staging API timeout. Default: 10.")
    _add_output_and_locale(
        preview,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable sync preview.",
    )

    approve = sync_subcommands.add_parser("approve", help="Dry-run explicit sync approval. No approval is recorded.")
    approve.add_argument("--dry-run", action="store_true", help="Required; do not call official backend.")
    approve.add_argument("--direction", choices=SYNC_DIRECTION_CHOICES, default="local-to-cloud")
    approve.add_argument("--fixture-auth-state", choices=SYNC_AUTH_STATE_CHOICES, default="dry_run")
    approve.add_argument("--selected", action="store_true", help="Fixture: cloud conversation is user-selected.")
    approve.add_argument("--explicit-approval", action="store_true", help="Fixture: approval would be present.")
    _add_output_and_locale(
        approve,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable dry-run approval.",
    )

    api_contract = sync_subcommands.add_parser("api-contract", help="Show official API fixture contract.")
    _add_output_and_locale(
        api_contract,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable API contract summary.",
    )

    rate_limit = sync_subcommands.add_parser("rate-limit", help="Show official rate-limit policy contract.")
    _add_output_and_locale(
        rate_limit,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable rate-limit contract summary.",
    )


def handle_sync_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
) -> int:
    report = build_sync_report(args, prepare_import_paths=prepare_import_paths)
    if args.json:
        print_json(report)
    else:
        print(format_sync_pretty(report, lang=args.lang, color=args.color))
    return 0 if report.get("ok", True) else 1


def build_sync_report(args: argparse.Namespace, *, prepare_import_paths: Callable[[], None]) -> dict[str, Any]:
    loaded_builders: dict[str, Any] | None = None

    def builders() -> dict[str, Any]:
        nonlocal loaded_builders
        if loaded_builders is None:
            loaded_builders = _load_official_contract_builders(prepare_import_paths)
        return loaded_builders

    auth_state = getattr(args, "auth_state", getattr(args, "fixture_auth_state", "dry_run"))
    selected = bool(getattr(args, "selected", False))
    try:
        if args.sync_command == "status":
            if _staging_origin_configured():
                return build_staging_sync_status(
                    config=_load_config(args),
                    env=os.environ,
                    claim_path=getattr(args, "config_path", None),
                    timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
                )
            return builders()["status"](auth_state=auth_state, selected=selected)
        if args.sync_command == "conversations":
            return build_staging_conversations_report(
                config=_load_config(args),
                env=os.environ,
                claim_path=getattr(args, "config_path", None),
                timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
            )
        if args.sync_command == "conversation" and args.sync_conversation_command == "show":
            return build_staging_conversation_show_report(
                conversation_id=str(getattr(args, "conversation_id", "")),
                config=_load_config(args),
                env=os.environ,
                claim_path=getattr(args, "config_path", None),
                timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
            )
        if args.sync_command == "preview":
            direction = _effective_sync_direction(args)
            if _staging_origin_configured() or direction == "local-to-cloud":
                return build_staging_sync_preview_report(
                    direction=direction,
                    config=_load_config(args),
                    env=os.environ,
                    claim_path=getattr(args, "config_path", None),
                    conversation_ref=str(getattr(args, "conversation_ref", "cloud-conversation-fixture")),
                    audit_reason=str(getattr(args, "audit_reason", "public_cli_sync_preview")),
                    explicit_approval=bool(getattr(args, "explicit_approval", False)),
                    timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
                )
            return builders()["preview"](
                direction=_sync_direction_for_core(direction),
                auth_state=auth_state,
                selected=selected,
                explicit_approval=bool(getattr(args, "explicit_approval", False)),
                contains_private_file_content=bool(getattr(args, "include_private_file", False)),
                contains_local_memory=bool(getattr(args, "include_local_memory", False)),
                contains_local_node_payload=bool(getattr(args, "include_local_node_payload", False)),
            )
        if args.sync_command == "approve":
            if not args.dry_run:
                raise SyncCommandError("sync approve requires --dry-run in the public repo.")
            return builders()["approve"](
                direction=_sync_direction_for_core(args.direction),
                auth_state=auth_state,
                selected=selected,
                explicit_approval=bool(getattr(args, "explicit_approval", False)),
            )
        if args.sync_command == "api-contract":
            return builders()["api"]()
        if args.sync_command == "rate-limit":
            return builders()["rate_limit"]()
    except (ConfigError, StagingSyncServiceError, ValueError) as exc:
        raise SyncCommandError(str(exc)) from exc
    raise SyncCommandError("unknown sync command")


def _effective_sync_direction(args: argparse.Namespace) -> str:
    return str(getattr(args, "direction_value", None) or getattr(args, "direction", "cloud-to-local"))


def format_sync_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    title = "YonerAI sync boundary" if lang != "ja" else "YonerAI 同期境界"
    rows = [
        CliRow("schema_version", report.get("schema_version"), "ok"),
        CliRow("ok", report.get("ok", True), "ok" if report.get("ok", True) else "fail"),
    ]
    for key in (
        "operation",
        "direction",
        "auth_state",
        "staging_origin",
        "staging_claim_present",
        "staging_session_available",
        "preview_only",
        "sync_allowed",
        "sync_performed",
        "official_backend_called",
        "backend_status_code",
    ):
        if key in report:
            status = "ok"
            if key == "staging_session_available" and report.get(key) is False:
                status = "warn"
            if key == "sync_performed" and report.get(key) is True:
                status = "fail"
            rows.append(CliRow(key, report.get(key), status))
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    if decision:
        rows.append(CliRow("decision", decision.get("state"), "warn" if decision.get("state") == "approval_required" else "ok"))
        rows.append(CliRow("reason", decision.get("reason"), "ok"))
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        rows.append(CliRow("error", error.get("code"), "fail"))
        rows.append(CliRow("message", error.get("message"), "warn"))
    conversations = report.get("conversations") if isinstance(report.get("conversations"), list) else []
    conversation = report.get("conversation") if isinstance(report.get("conversation"), dict) else {}
    conversation_rows = tuple(
        CliRow(str(item.get("cloud_conversation_id") or "cloud"), item.get("title"), "ok")
        for item in conversations
        if isinstance(item, dict)
    )
    conversation_detail_rows = tuple(
        CliRow(key, conversation.get(key), "ok")
        for key in (
            "cloud_conversation_id",
            "title",
            "summary",
            "selected_by_user",
            "created_at",
            "updated_at",
            "message_count",
            "raw_body_included",
        )
        if key in conversation
    )
    actions = tuple(
        CliRow(f"action_{idx}", item, "ok") for idx, item in enumerate(report.get("actions_not_performed", []), start=1)
    )
    sections = [CliSection("Status", tuple(rows))]
    if conversation_rows:
        sections.append(CliSection("Cloud conversations", conversation_rows))
    if conversation_detail_rows:
        sections.append(CliSection("Cloud conversation", conversation_detail_rows))
    if actions:
        sections.append(CliSection("Non-actions", actions))
    return render_report(title, tuple(sections), color=color)


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


def _load_official_contract_builders(prepare_import_paths: Callable[[], None]) -> dict[str, Any]:
    prepare_import_paths()
    importlib.invalidate_caches()
    core_available = importlib.util.find_spec("ora_core") is not None
    official_available = core_available and importlib.util.find_spec("ora_core.official") is not None
    if not official_available:
        raise SyncCommandError("official sync contract fixtures are unavailable.", exit_code=1)
    from ora_core.official import (
        build_official_api_contract_fixture,
        build_rate_limit_policy_report,
        build_sync_approval_dry_run_report,
        build_sync_preview_report,
        build_sync_status_report,
    )

    return {
        "api": build_official_api_contract_fixture,
        "rate_limit": build_rate_limit_policy_report,
        "approve": build_sync_approval_dry_run_report,
        "preview": build_sync_preview_report,
        "status": build_sync_status_report,
    }


def _sync_direction_for_core(value: str) -> str:
    normalized = value.replace("-", "_")
    if normalized not in {"cloud_to_local", "local_to_cloud"}:
        raise SyncCommandError(f"unsupported sync direction: {value}")
    return normalized


def _staging_origin_configured() -> bool:
    return any(
        str(os.environ.get(key) or "").strip()
        for key in ("YONERAI_STAGING_AUTH_ORIGIN", "YONERAI_OFFICIAL_API_STAGING_ORIGIN")
    )


def _load_config(args: argparse.Namespace) -> dict[str, object]:
    return load_cli_config(getattr(args, "config_path", None))
