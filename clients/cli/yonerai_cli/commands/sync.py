from __future__ import annotations

import argparse
import importlib.util
import json
import os
from typing import Any, Callable

from yonerai_cli.config import ConfigError, load_cli_config
from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.services.conversation_sync_policy_service import (
    ConversationSyncPolicyError,
    SYNC_POLICIES,
    build_conversation_policy_list_report,
    build_conversation_policy_pause_report,
    build_conversation_policy_set_report,
    build_conversation_policy_status_report,
)
from yonerai_cli.services.realtime_sync_event_service import (
    SYNC_EVENT_FIXTURES,
    build_realtime_sync_event_fixture,
    build_realtime_sync_event_validation_report,
)
from yonerai_cli.services.realtime_sync_client_service import (
    build_realtime_sync_firestore_poll_report,
    build_realtime_sync_firebase_config_report,
    build_realtime_sync_firebase_token_report,
    build_realtime_sync_listener_readiness_report,
    build_realtime_sync_listener_fixture_report,
    build_realtime_sync_listener_once_report,
    build_realtime_sync_listener_poll_report,
)
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
    conversation_status = conversation_subcommands.add_parser(
        "status",
        help="Show local conversation sync policy boundaries. No sync is performed.",
    )
    conversation_status.add_argument("--store", help="Optional local conversation policy store path.")
    conversation_status.add_argument("--config-path", help="Optional local CLI config path.")
    _add_output_and_locale(
        conversation_status,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable conversation sync policy status.",
    )

    conversation_list = conversation_subcommands.add_parser(
        "list",
        help="List local conversation sync policies. No raw conversation body is stored.",
    )
    conversation_list.add_argument("--store", help="Optional local conversation policy store path.")
    conversation_list.add_argument("--config-path", help="Optional local CLI config path.")
    _add_output_and_locale(
        conversation_list,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable conversation sync policies.",
    )

    conversation_set = conversation_subcommands.add_parser(
        "set",
        help="Set a conversation sync policy. bidirectional_explicit requires --confirm.",
    )
    conversation_set.add_argument("conversation_id", help="Public-safe conversation id.")
    conversation_set.add_argument("sync_policy", choices=SYNC_POLICIES, help="Conversation sync policy.")
    conversation_set.add_argument("--origin", choices=("local", "cloud", "web"), help="Conversation origin.")
    conversation_set.add_argument("--confirm", action="store_true", help="Required for bidirectional_explicit.")
    conversation_set.add_argument(
        "--audit-reason",
        default="public_cli_conversation_policy_set",
        help="Public metadata-only audit reason.",
    )
    conversation_set.add_argument("--store", help="Optional local conversation policy store path.")
    conversation_set.add_argument("--config-path", help="Optional local CLI config path.")
    _add_output_and_locale(
        conversation_set,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable conversation sync policy decision.",
    )

    conversation_pause = conversation_subcommands.add_parser(
        "pause",
        help="Pause sync for a conversation. No upload is performed.",
    )
    conversation_pause.add_argument("conversation_id", help="Public-safe conversation id.")
    conversation_pause.add_argument(
        "--audit-reason",
        default="public_cli_conversation_policy_pause",
        help="Public metadata-only audit reason.",
    )
    conversation_pause.add_argument("--store", help="Optional local conversation policy store path.")
    conversation_pause.add_argument("--config-path", help="Optional local CLI config path.")
    _add_output_and_locale(
        conversation_pause,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable conversation pause decision.",
    )

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

    event = sync_subcommands.add_parser("event", help="Validate realtime sync metadata events without enabling a listener.")
    event_subcommands = event.add_subparsers(dest="sync_event_command", required=True)
    event_validate = event_subcommands.add_parser("validate", help="Validate a body-free SyncEvent fixture or JSON payload.")
    source = event_validate.add_mutually_exclusive_group()
    source.add_argument("--event-json", help="Inline JSON SyncEvent payload. No file is read.")
    source.add_argument(
        "--fixture",
        choices=tuple(sorted(SYNC_EVENT_FIXTURES)),
        default="valid",
        help="Safe built-in SyncEvent fixture. Default: valid.",
    )
    event_validate.add_argument("--linked-account-id", default="acct_public_001", help="Expected opaque linked account id.")
    event_validate.add_argument("--seen-event-id", action="append", default=[], help="Previously accepted event_id.")
    event_validate.add_argument("--seen-idempotency-key", action="append", default=[], help="Previously accepted idempotency_key.")
    _add_output_and_locale(
        event_validate,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable SyncEvent validation.",
    )

    listener = sync_subcommands.add_parser("listener", help="Consume realtime sync metadata events without Firestore body fallback.")
    listener_subcommands = listener.add_subparsers(dest="sync_listener_command", required=True)
    listener_once = listener_subcommands.add_parser(
        "once",
        help="Read one account-scoped Firestore SyncEvent and fetch AWS body only when allowed.",
    )
    listener_source = listener_once.add_mutually_exclusive_group()
    listener_source.add_argument("--event-json", help="Inline JSON SyncEvent payload. No file is read.")
    listener_source.add_argument(
        "--fixture",
        choices=tuple(sorted(SYNC_EVENT_FIXTURES)),
        help="Safe built-in SyncEvent fixture. If omitted, once reads Firestore metadata.",
    )
    listener_once.add_argument("--limit", type=int, default=1, help="Maximum Firestore events to request. Default: 1.")
    listener_once.add_argument("--config-path", help="Optional local CLI config path.")
    listener_once.add_argument("--state", help="Optional local cursor state path.")
    listener_once.add_argument("--timeout-seconds", type=float, default=10.0, help="Staging API timeout. Default: 10.")
    _add_output_and_locale(
        listener_once,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable realtime sync listener result.",
    )
    listener_poll = listener_subcommands.add_parser(
        "poll",
        help="Poll an account-scoped body-free realtime sync metadata feed.",
    )
    listener_poll.add_argument("--config-path", help="Optional local CLI config path.")
    listener_poll.add_argument("--state", help="Optional local cursor state path.")
    listener_poll.add_argument("--timeout-seconds", type=float, default=10.0, help="Staging API timeout. Default: 10.")
    listener_poll.add_argument(
        "--source-path",
        default="/v1/conversations/events",
        help="Allowed metadata event source path. Default: /v1/conversations/events.",
    )
    listener_poll.add_argument("--limit", type=int, default=10, help="Maximum events to request. Default: 10.")
    _add_output_and_locale(
        listener_poll,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable realtime sync listener poll result.",
    )
    listener_firestore = listener_subcommands.add_parser(
        "firestore-poll",
        help="Poll Firestore body-free SyncEvents, then fetch message bodies only from AWS.",
    )
    listener_firestore.add_argument("--config-path", help="Optional local CLI config path.")
    listener_firestore.add_argument("--state", help="Optional local cursor state path.")
    listener_firestore.add_argument("--timeout-seconds", type=float, default=10.0, help="Staging API timeout. Default: 10.")
    listener_firestore.add_argument("--limit", type=int, default=10, help="Maximum events to request. Default: 10.")
    _add_output_and_locale(
        listener_firestore,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable Firestore realtime sync listener result.",
    )
    listener_firebase = listener_subcommands.add_parser(
        "firebase-token",
        help="Validate the staging Firebase custom-token bridge for Firestore metadata reads.",
    )
    listener_firebase.add_argument("--config-path", help="Optional local CLI config path.")
    listener_firebase.add_argument("--timeout-seconds", type=float, default=10.0, help="Staging API timeout. Default: 10.")
    _add_output_and_locale(
        listener_firebase,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable Firebase read-auth bridge status.",
    )
    listener_firebase_config = listener_subcommands.add_parser(
        "firebase-config",
        help="Validate the staging public Firebase client config without printing config values.",
    )
    listener_firebase_config.add_argument("--config-path", help="Optional local CLI config path.")
    listener_firebase_config.add_argument("--timeout-seconds", type=float, default=10.0, help="Staging API timeout. Default: 10.")
    _add_output_and_locale(
        listener_firebase_config,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable Firebase public config status.",
    )
    listener_readiness = listener_subcommands.add_parser(
        "readiness",
        help="Show whether realtime sync listener prerequisites are ready without starting Firestore.",
    )
    listener_readiness.add_argument("--config-path", help="Optional local CLI config path.")
    listener_readiness.add_argument("--timeout-seconds", type=float, default=10.0, help="Staging API timeout. Default: 10.")
    _add_output_and_locale(
        listener_readiness,
        lang_choices=lang_choices,
        color_choices=color_choices,
        pretty_help="Print readable realtime sync listener readiness.",
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
        print(format_sync_pretty_v2(report, lang=args.lang, color=args.color))
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
        if args.sync_command == "conversation" and args.sync_conversation_command == "status":
            return build_conversation_policy_status_report(
                store_path=getattr(args, "store", None),
                config_path=getattr(args, "config_path", None),
            )
        if args.sync_command == "conversation" and args.sync_conversation_command == "list":
            return build_conversation_policy_list_report(
                store_path=getattr(args, "store", None),
                config_path=getattr(args, "config_path", None),
            )
        if args.sync_command == "conversation" and args.sync_conversation_command == "set":
            return build_conversation_policy_set_report(
                str(getattr(args, "conversation_id", "")),
                str(getattr(args, "sync_policy", "")),
                origin=getattr(args, "origin", None),
                confirm=bool(getattr(args, "confirm", False)),
                audit_reason=str(getattr(args, "audit_reason", "public_cli_conversation_policy_set")),
                store_path=getattr(args, "store", None),
                config_path=getattr(args, "config_path", None),
            )
        if args.sync_command == "conversation" and args.sync_conversation_command == "pause":
            return build_conversation_policy_pause_report(
                str(getattr(args, "conversation_id", "")),
                audit_reason=str(getattr(args, "audit_reason", "public_cli_conversation_policy_pause")),
                store_path=getattr(args, "store", None),
                config_path=getattr(args, "config_path", None),
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
        if args.sync_command == "event" and args.sync_event_command == "validate":
            event = _event_payload_from_args(args)
            report = build_realtime_sync_event_validation_report(
                event,
                linked_account_id=str(getattr(args, "linked_account_id", "") or ""),
                seen_event_ids=tuple(getattr(args, "seen_event_id", []) or ()),
                seen_idempotency_keys=tuple(getattr(args, "seen_idempotency_key", []) or ()),
            )
            report["operation"] = "realtime_sync_event_validate"
            report["listener_enabled"] = False
            report["firestore_enabled"] = False
            report["aws_body_fetch_performed"] = False
            report["fixture"] = getattr(args, "fixture", None)
            return report
        if args.sync_command == "listener" and args.sync_listener_command == "once":
            event_json = getattr(args, "event_json", None)
            kwargs = {
                "config": _load_config(args),
                "env": os.environ,
                "config_path": getattr(args, "config_path", None),
                "state_path": getattr(args, "state", None),
                "timeout_seconds": float(getattr(args, "timeout_seconds", 10.0)),
            }
            if event_json:
                event = _event_payload_from_args(args)
                return build_realtime_sync_listener_once_report(event=event, **kwargs)
            fixture = getattr(args, "fixture", None)
            if fixture:
                return build_realtime_sync_listener_fixture_report(
                    fixture=str(fixture),
                    **kwargs,
                )
            return build_realtime_sync_firestore_poll_report(
                config=_load_config(args),
                env=os.environ,
                config_path=getattr(args, "config_path", None),
                state_path=getattr(args, "state", None),
                timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
                limit=max(1, min(int(getattr(args, "limit", 1)), 1)),
            )
        if args.sync_command == "listener" and args.sync_listener_command == "poll":
            return build_realtime_sync_listener_poll_report(
                config=_load_config(args),
                env=os.environ,
                config_path=getattr(args, "config_path", None),
                state_path=getattr(args, "state", None),
                timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
                source_path=str(getattr(args, "source_path", "/v1/conversations/events") or "/v1/conversations/events"),
                limit=int(getattr(args, "limit", 10)),
            )
        if args.sync_command == "listener" and args.sync_listener_command == "firestore-poll":
            return build_realtime_sync_firestore_poll_report(
                config=_load_config(args),
                env=os.environ,
                config_path=getattr(args, "config_path", None),
                state_path=getattr(args, "state", None),
                timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
                limit=int(getattr(args, "limit", 10)),
            )
        if args.sync_command == "listener" and args.sync_listener_command == "firebase-token":
            return build_realtime_sync_firebase_token_report(
                config=_load_config(args),
                env=os.environ,
                config_path=getattr(args, "config_path", None),
                timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
            )
        if args.sync_command == "listener" and args.sync_listener_command == "firebase-config":
            return build_realtime_sync_firebase_config_report(
                config=_load_config(args),
                env=os.environ,
                config_path=getattr(args, "config_path", None),
                timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
            )
        if args.sync_command == "listener" and args.sync_listener_command == "readiness":
            return build_realtime_sync_listener_readiness_report(
                config=_load_config(args),
                env=os.environ,
                config_path=getattr(args, "config_path", None),
                timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
            )
        if args.sync_command == "api-contract":
            return builders()["api"]()
        if args.sync_command == "rate-limit":
            return builders()["rate_limit"]()
    except (ConfigError, ConversationSyncPolicyError, StagingSyncServiceError, ValueError) as exc:
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


def format_sync_pretty_v2(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
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
        "local_to_cloud_upload_performed",
        "official_worker_dispatch_performed",
        "official_backend_called",
        "backend_status_code",
        "conversation_count",
        "event_type",
        "origin",
        "sync_policy",
        "body_fetch_allowed",
        "body_fetch_reason",
        "listener_enabled",
        "ready",
        "firestore_enabled",
        "firestore_sdk_connected",
        "firestore_read_auth_bridge_ready",
        "firestore_sdk_dependency_available",
        "firestore_client_sign_in_config_present",
        "firestore_sdk_listener_ready",
        "firestore_body_fallback_allowed",
        "aws_body_fetch_performed",
        "body_received_from_aws",
        "message_body_from_firestore",
        "raw_prompt_from_firestore",
        "raw_audit_from_firestore",
        "event_source_kind",
        "event_source_path",
        "event_source_cursor",
        "event_source_query_included",
        "events_received",
        "events_processed",
        "events_rejected",
        "feed_next_cursor",
        "feed_has_more",
        "metadata_event_to_aws_body_fetch_completed",
        "live_web_to_cli_e2e_proven",
        "next_blocker",
        "firebase_token_endpoint",
        "firebase_token_endpoint_checked",
        "firebase_token_endpoint_live",
        "firebase_token_endpoint_status_code",
        "firebase_config_endpoint",
        "firebase_config_endpoint_checked",
        "firebase_config_endpoint_live",
        "firebase_config_endpoint_status_code",
        "firebase_config_contract_version",
        "firebase_public_config_ready",
        "firebase_public_api_key_received",
        "firebase_public_api_key_printed",
        "firebase_public_api_key_persisted",
        "firebase_auth_contract_version",
        "firebase_custom_token_received",
        "firebase_custom_token_printed",
        "firebase_custom_token_persisted",
        "firebase_token_type",
        "firebase_uid_matches_account",
        "firebase_account_id_matches_session",
        "firebase_expires_at",
        "firebase_expires_in_seconds",
        "firebase_claims_yonerai_staging",
        "firebase_claims_session_ref_present",
        "firebase_claims_session_expires_at_present",
        "firebase_revocation_mode",
        "firebase_revocation_immediate",
        "firebase_revocation_max_delay_seconds",
        "firebase_read_revocation_semantics",
        "firebase_external_alpha_requires_session_projection",
        "firestore_project_id",
        "firestore_database_id",
        "firestore_sync_enabled",
        "firestore_backend_sync_enabled",
        "firestore_sync_mode",
        "firestore_usage_policy_present",
        "firestore_usage_policy_accepted",
        "firestore_usage_policy_version",
        "firestore_initial_query_limit",
        "firestore_absolute_query_limit",
        "firestore_requested_limit",
        "firestore_effective_query_limit",
        "firestore_reconnect_cooldown_seconds",
        "firestore_reconnect_cooldown_remaining_seconds",
        "firestore_max_cli_listeners_per_account",
        "firestore_query_account_rooted",
        "firestore_offset_forbidden",
        "firestore_collection_group_query_allowed",
        "firestore_client_writes_allowed",
        "firestore_projection_write_allowed",
        "firestore_body_fetch_source",
        "firestore_sync_event_path_template",
        "firestore_account_data_binding_required",
        "client_policy_write_performed",
        "client_approval_write_performed",
        "cursor_saved",
        "reconnect_supported",
        "next_reconnect_cursor",
        "duplicate_event",
        "duplicate_idempotency_key",
    ):
        if key in report:
            status = "ok"
            if key == "staging_session_available" and report.get(key) is False:
                status = "warn"
            if key in {"sync_performed", "local_to_cloud_upload_performed", "official_worker_dispatch_performed"} and report.get(key) is True:
                status = "fail"
            rows.append(CliRow(key, report.get(key), status))
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    if decision:
        state = decision.get("state")
        rows.append(CliRow("decision", state, "warn" if state == "approval_required" else "ok"))
        rows.append(CliRow("reason", decision.get("reason"), "ok"))
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        rows.append(CliRow("error", error.get("code"), "fail"))
        rows.append(CliRow("message", error.get("message"), "warn"))

    conversations = report.get("conversations") if isinstance(report.get("conversations"), list) else []
    conversation = report.get("conversation") if isinstance(report.get("conversation"), dict) else {}
    cloud_rows = tuple(
        CliRow(str(item.get("cloud_conversation_id") or "cloud"), item.get("title"), "ok")
        for item in conversations
        if isinstance(item, dict) and item.get("cloud_conversation_id")
    )
    cloud_detail_rows = tuple(
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
    policy_rows = tuple(
        CliRow(str(item.get("conversation_id") or "conversation"), item.get("sync_policy"), _policy_status(item))
        for item in conversations
        if isinstance(item, dict) and item.get("conversation_id")
    )
    policy_counts = report.get("policy_counts") if isinstance(report.get("policy_counts"), dict) else {}
    policy_count_rows = tuple(CliRow(str(key), value, "ok") for key, value in policy_counts.items())
    policy_detail_rows = _conversation_policy_detail_rows(conversation)
    actions = tuple(
        CliRow(f"action_{idx}", item, "ok") for idx, item in enumerate(report.get("actions_not_performed", []), start=1)
    )
    next_actions = tuple(
        CliRow(f"next_{idx}", item, "warn") for idx, item in enumerate(report.get("required_next_actions", []), start=1)
    )

    sections = []
    summary = _sync_summary_rows(report, lang=lang)
    if summary:
        sections.append(CliSection("要約" if lang == "ja" else "Summary", summary))
    sections.append(CliSection("Status", tuple(rows)))
    if cloud_rows:
        sections.append(CliSection("Cloud conversations", cloud_rows))
    if cloud_detail_rows:
        sections.append(CliSection("Cloud conversation", cloud_detail_rows))
    if policy_count_rows:
        sections.append(CliSection("Conversation policy counts", policy_count_rows))
    if policy_rows:
        sections.append(CliSection("Conversation sync policies", policy_rows))
    if policy_detail_rows:
        sections.append(CliSection("Conversation policy boundary", policy_detail_rows))
    if actions:
        sections.append(CliSection("Non-actions", actions))
    if next_actions:
        sections.append(CliSection("Next actions", next_actions))
    message = report.get("message") if isinstance(report.get("message"), dict) else {}
    if message:
        sections.append(
            CliSection(
                "AWS message",
                tuple(
                    CliRow(key, message.get(key), "ok")
                    for key in ("conversation_id", "message_id", "display_text", "body_from_firestore", "body_stored_in_cursor")
                    if key in message
                ),
            )
        )
    return render_report(title, tuple(sections), color=color)


def _sync_summary_rows(report: dict[str, Any], *, lang: str) -> tuple[CliRow, ...]:
    if report.get("operation") != "realtime_sync_listener_readiness":
        return ()
    next_blocker = str(report.get("next_blocker") or "")
    if not next_blocker:
        return ()
    if lang != "ja":
        english_blockers: dict[str, tuple[str, str, str]] = {
            "canonical_account_id_required": (
                "not ready",
                "The saved staging login is from the older account_ref contract.",
                "Run yonerai logout, then yonerai login, then rerun sync listener readiness.",
            ),
            "firebase_public_config_not_ready": (
                "not ready",
                "The staging Firebase public client config is not ready yet.",
                "Wait for AWS to publish a ready public config, then rerun sync listener readiness.",
            ),
            "firebase_public_config_unavailable": (
                "not ready",
                "The staging Firebase public config endpoint could not be checked safely.",
                "Retry later or check the staging API status before starting the listener.",
            ),
            "firebase_token_contract_or_safety_violation": (
                "not ready",
                "The Firebase token endpoint returned an unsafe or unsupported contract.",
                "Do not start the listener; wait for the staging contract to be fixed.",
            ),
            "firestore_client_sign_in_config_missing": (
                "not ready",
                "The local Firebase client sign-in config is missing.",
                "Use the staging public config endpoint when it is ready; do not paste secrets.",
            ),
            "firestore_sync_disabled_until_live_e2e_and_owner_flip": (
                "auth ready, sync disabled",
                "Firestore sync stays disabled until live Web-to-CLI E2E is proven and the owner enables it.",
                "Do not claim client-ready; wait for the owner-controlled sync flag.",
            ),
            "opaque_staging_session_required": (
                "not ready",
                "The saved login does not contain a safe opaque YonerAI staging session.",
                "Run yonerai logout, then yonerai login, then rerun sync listener readiness.",
            ),
            "owner_gcp_token_signing_permission_required": (
                "not ready",
                "The staging backend still needs owner-side Firebase token-signing permission.",
                "Ask the owner to complete the minimal GCP permission step, then retry.",
            ),
            "private_aws_firebase_token_endpoint_not_live": (
                "not ready",
                "The private AWS Firebase token endpoint is not live on staging.",
                "Wait for AWS to send the Firebase client-auth ready notice.",
            ),
            "private_aws_firebase_token_endpoint_unavailable": (
                "not ready",
                "The private AWS Firebase token endpoint is temporarily unavailable.",
                "Retry after the staging API recovers; do not start the listener.",
            ),
            "staging_login_required": (
                "not ready",
                "A staging login is required before realtime sync can read account-scoped events.",
                "Run yonerai login, then rerun sync listener readiness.",
            ),
            "staging_origin_not_configured": (
                "not ready",
                "The staging API origin is not configured.",
                "Set YONERAI_STAGING_AUTH_ORIGIN=https://api-staging.yonerai.com and retry.",
            ),
            "staging_session_required": (
                "not ready",
                "The saved staging session was rejected by AWS.",
                "Run yonerai logout, then yonerai login, then rerun sync listener readiness.",
            ),
            "staging_sync_unreachable": (
                "not ready",
                "The staging sync endpoint could not be reached.",
                "Retry after checking staging API status; do not start the listener.",
            ),
        }
        state, reason, next_action = english_blockers.get(
            next_blocker,
            (
                "not ready",
                f"Realtime sync is blocked by {next_blocker}.",
                "Check sync listener readiness again after the blocker is resolved.",
            ),
        )
        return (
            CliRow("state", state, "warn"),
            CliRow("reason", reason, "warn"),
            CliRow("next", next_action, "warn"),
        )
    if next_blocker == "canonical_account_id_required":
        return (
            CliRow("状態", "同期リスナーはまだ使えません", "warn"),
            CliRow("理由", "保存済みログインが古い account_ref 形式です", "warn"),
            CliRow("次にやること", "yonerai logout の後に yonerai login を実行してください", "warn"),
        )
    if next_blocker == "firestore_sync_disabled_until_live_e2e_and_owner_flip":
        return (
            CliRow("状態", "同期リスナーの認証準備は進んでいます", "ok"),
            CliRow("理由", "Firestore 同期は owner が有効化するまで無効です", "warn"),
            CliRow("次にやること", "Web-to-CLI E2E 後に owner が同期フラグを有効化します", "warn"),
        )
    if next_blocker == "staging_session_required":
        return (
            CliRow("状態", "同期リスナーはまだ使えません", "warn"),
            CliRow("理由", "保存済み staging session が AWS に拒否されました", "warn"),
            CliRow("次にやること", "yonerai logout の後に yonerai login を実行してください", "warn"),
        )
    return ()


def _event_payload_from_args(args: argparse.Namespace) -> dict[str, object]:
    event_json = getattr(args, "event_json", None)
    if event_json:
        try:
            value = json.loads(str(event_json))
        except json.JSONDecodeError as exc:
            raise SyncCommandError("sync event validate received invalid JSON.", exit_code=1) from exc
        if not isinstance(value, dict):
            raise SyncCommandError("sync event validate requires a JSON object.", exit_code=1)
        return value
    return build_realtime_sync_event_fixture(str(getattr(args, "fixture", "valid") or "valid"))


def _policy_status(item: dict[str, Any]) -> str:
    policy = str(item.get("sync_policy") or "")
    if policy == "local_only":
        return "warn"
    if policy == "paused":
        return "fail"
    return "ok"


def _conversation_policy_detail_rows(conversation: dict[str, Any]) -> tuple[CliRow, ...]:
    if not conversation or "sync_policy" not in conversation:
        return ()
    rows = [
        CliRow("conversation_id", conversation.get("conversation_id"), "ok"),
        CliRow("origin", conversation.get("origin"), "ok"),
        CliRow("sync_policy", conversation.get("sync_policy"), _policy_status(conversation)),
    ]
    execution = conversation.get("execution") if isinstance(conversation.get("execution"), dict) else {}
    memory = conversation.get("memory") if isinstance(conversation.get("memory"), dict) else {}
    for key in ("official_worker_allowed", "local_loopback_required", "decision", "reason"):
        if key in execution:
            status = "fail" if key == "official_worker_allowed" and execution.get(key) is False else "ok"
            rows.append(CliRow(f"execution.{key}", execution.get(key), status))
    for key in ("inherits_conversation_policy", "memory_scope", "cloud_memory_index_allowed", "local_to_cloud_memory_sync"):
        if key in memory:
            status = "warn" if key == "cloud_memory_index_allowed" and memory.get(key) is False else "ok"
            rows.append(CliRow(f"memory.{key}", memory.get(key), status))
    return tuple(rows)


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
