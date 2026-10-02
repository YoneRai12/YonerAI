from __future__ import annotations

import argparse
import os
from typing import Any, Callable

from yonerai_cli.screens.native_run import format_native_run_compact, format_native_run_pretty
from yonerai_cli.services.core_api_service import DEFAULT_API_ORIGIN
from yonerai_cli.services.native_run_service import (
    NativeRunServiceError,
    build_capability_list_report,
    build_module_list_report,
    build_native_run_cancel_report,
    build_native_run_events_report,
    build_native_run_result_report,
    build_native_run_status_report,
    build_native_run_submit_report,
    build_worker_status_report,
    load_config_for_native_run,
)


class NativeRunCommandError(Exception):
    pass


def add_native_run_parsers(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    run = subcommands.add_parser("run", help="Submit and inspect staging Native Run requests.")
    run_subcommands = run.add_subparsers(dest="run_command", required=True)

    submit = run_subcommands.add_parser("submit", help="Submit a staging Native Run. Requires `yonerai login`.")
    submit.add_argument("prompt", nargs="+", help="Short task text. Do not include secrets or local/private file content.")
    submit.add_argument("--project-id", default="personal-staging", help="Staging project id. Default: personal-staging.")
    submit.add_argument("--module-id", default="run.core", help="Native Run module id. Default: run.core.")
    submit.add_argument("--capability", default="run.echo", help="Native Run capability. Default: run.echo.")
    submit.add_argument("--conversation-id", help="Optional public-safe conversation id for sync policy enforcement.")
    submit.add_argument("--conversation-origin", choices=("local", "cloud", "web"), help="Conversation origin for sync policy enforcement.")
    submit.add_argument(
        "--sync-policy",
        choices=("local_only", "cloud_to_local", "bidirectional_explicit", "paused"),
        help="Conversation sync policy for this run. local_only is rejected before official-worker dispatch.",
    )
    submit.add_argument("--conversation-policy-store", help="Optional local conversation policy store path.")
    submit.add_argument(
        "--provider-data-policy",
        choices=("none", "local_provider", "openai_shared_explicit"),
        default="none",
        help="Provider data policy. OpenAI sharing requires per-conversation consent.",
    )
    submit.add_argument("--provider-sharing-store", help="Optional local provider-sharing consent store path.")
    submit.add_argument("--idempotency-key", help="Optional idempotency key for CI/retry tests.")
    _add_common_options(submit, lang_choices=lang_choices, color_choices=color_choices)

    status = run_subcommands.add_parser("status", help="Show staging Native Run status.")
    status.add_argument("run_id", help="Run id returned by `yonerai run submit`.")
    _add_common_options(status, lang_choices=lang_choices, color_choices=color_choices)

    events = run_subcommands.add_parser("events", help="Show sanitized staging Native Run events.")
    events.add_argument("run_id", help="Run id returned by `yonerai run submit`.")
    _add_common_options(events, lang_choices=lang_choices, color_choices=color_choices)

    result = run_subcommands.add_parser("result", help="Show staging Native Run result summary if available.")
    result.add_argument("run_id", help="Run id returned by `yonerai run submit`.")
    _add_common_options(result, lang_choices=lang_choices, color_choices=color_choices)

    cancel = run_subcommands.add_parser("cancel", help="Cancel a queued/claimed staging Native Run.")
    cancel.add_argument("run_id", help="Run id returned by `yonerai run submit`.")
    _add_common_options(cancel, lang_choices=lang_choices, color_choices=color_choices)

    local_smoke = run_subcommands.add_parser(
        "local-smoke",
        help="Compatibility: create a local Surface API run smoke request.",
    )
    local_smoke.add_argument(
        "--api-origin",
        default=DEFAULT_API_ORIGIN,
        help=f"Loopback Core API origin. Default: {DEFAULT_API_ORIGIN}",
    )
    local_smoke.add_argument("--mode", choices=["mock", "offline", "local"], default="mock")
    local_smoke.add_argument("prompt", nargs="+")

    worker = subcommands.add_parser("worker", help="Show public-safe Official Execution Worker status.")
    worker_subcommands = worker.add_subparsers(dest="worker_command", required=True)
    worker_status = worker_subcommands.add_parser("status", help="Show staging worker status snapshot.")
    _add_common_options(worker_status, lang_choices=lang_choices, color_choices=color_choices)

    capability = subcommands.add_parser("capability", help="Show staging Native Run capability manifest.")
    capability_subcommands = capability.add_subparsers(dest="capability_command", required=True)
    capability_list = capability_subcommands.add_parser("list", help="List public-safe staging Native Run capabilities.")
    _add_common_options(capability_list, lang_choices=lang_choices, color_choices=color_choices)

    module = subcommands.add_parser("module", help="Show staging Native Run module manifest.")
    module_subcommands = module.add_subparsers(dest="module_command", required=True)
    module_list = module_subcommands.add_parser("list", help="List public-safe staging Native Run modules.")
    _add_common_options(module_list, lang_choices=lang_choices, color_choices=color_choices)


def handle_native_run_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    try:
        report = build_native_run_report(args)
    except NativeRunServiceError as exc:
        raise NativeRunCommandError(exc.message) from exc
    _print_report(args, report, print_json=print_json)
    return 0 if report.get("ok", True) else 1


def handle_worker_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    if args.worker_command != "status":
        raise NativeRunCommandError("unknown worker command")
    report = build_worker_status_report(
        config=load_config_for_native_run(getattr(args, "config_path", None)),
        env=os.environ,
        claim_path=getattr(args, "config_path", None),
        timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
    )
    _print_report(args, report, print_json=print_json)
    return 0 if report.get("ok", True) else 1


def handle_capability_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    if args.capability_command != "list":
        raise NativeRunCommandError("unknown capability command")
    report = build_capability_list_report(
        config=load_config_for_native_run(getattr(args, "config_path", None)),
        env=os.environ,
        claim_path=getattr(args, "config_path", None),
        timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
    )
    _print_report(args, report, print_json=print_json)
    return 0 if report.get("ok", True) else 1


def handle_module_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    if args.module_command != "list":
        raise NativeRunCommandError("unknown module command")
    report = build_module_list_report(
        config=load_config_for_native_run(getattr(args, "config_path", None)),
        env=os.environ,
        claim_path=getattr(args, "config_path", None),
        timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
    )
    _print_report(args, report, print_json=print_json)
    return 0 if report.get("ok", True) else 1


def build_native_run_report(args: argparse.Namespace) -> dict[str, Any]:
    common = {
        "config": load_config_for_native_run(getattr(args, "config_path", None)),
        "env": os.environ,
        "claim_path": getattr(args, "config_path", None),
        "timeout_seconds": float(getattr(args, "timeout_seconds", 10.0)),
    }
    if args.run_command == "submit":
        return build_native_run_submit_report(
            " ".join(args.prompt),
            project_id=str(getattr(args, "project_id", "personal-staging")),
            module_id=str(getattr(args, "module_id", "run.core")),
            capability=str(getattr(args, "capability", "run.echo")),
            conversation_id=getattr(args, "conversation_id", None),
            conversation_origin=getattr(args, "conversation_origin", None),
            sync_policy=getattr(args, "sync_policy", None),
            conversation_policy_store=getattr(args, "conversation_policy_store", None),
            provider_data_policy=getattr(args, "provider_data_policy", "none"),
            provider_sharing_store=getattr(args, "provider_sharing_store", None),
            idempotency_key=getattr(args, "idempotency_key", None),
            **common,
        )
    if args.run_command == "status":
        return build_native_run_status_report(str(args.run_id), **common)
    if args.run_command == "events":
        return build_native_run_events_report(str(args.run_id), **common)
    if args.run_command == "result":
        return build_native_run_result_report(str(args.run_id), **common)
    if args.run_command == "cancel":
        return build_native_run_cancel_report(str(args.run_id), **common)
    raise NativeRunCommandError("unknown Native Run command")


def _print_report(
    args: argparse.Namespace,
    report: dict[str, Any],
    *,
    print_json: Callable[[dict[str, Any]], None],
) -> None:
    if getattr(args, "json", False):
        print_json(report)
    elif getattr(args, "pretty", False) and not getattr(args, "short_command", False):
        print(format_native_run_pretty(report, lang=getattr(args, "lang", "ja"), color=getattr(args, "color", "auto")))
    else:
        print(format_native_run_compact(report, lang=getattr(args, "lang", "ja")))


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
    output.add_argument("--pretty", action="store_true", help="Print a readable staging Native Run report.")
    parser.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    parser.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")
