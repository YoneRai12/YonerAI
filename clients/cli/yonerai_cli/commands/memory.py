from __future__ import annotations

import argparse
from typing import Any, Callable

from yonerai_cli.screens.memory import format_memory_pretty
from yonerai_cli.services.memory_service import MemoryServiceError, MemoryUserInputError, build_memory_report


class MemoryCommandError(Exception):
    pass


class MemoryCommandUserInputError(MemoryCommandError):
    pass


MEMORY_SCOPE_CHOICES = (
    "local",
    "session",
    "local_private",
    "cloud_account",
    "shared_preference",
    "project",
    "procedural",
    "self_evolution_signal",
)
MEMORY_SYNC_DIRECTION_CHOICES = ("cloud-to-local", "local-to-cloud")


def add_memory_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    memory = subcommands.add_parser("memory", help="Manage explicit opt-in local memory records and sync previews.")
    memory_subcommands = memory.add_subparsers(dest="memory_command", required=True)

    memory_status = memory_subcommands.add_parser("status", help="Show local memory status and cloud/local sync boundaries.")
    memory_status.add_argument("--store", help="Local JSONL memory store path. Defaults to the local YonerAI data path.")
    memory_status_output = memory_status.add_mutually_exclusive_group()
    memory_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    memory_status_output.add_argument("--pretty", action="store_true", help="Print a readable memory status.")
    memory_status.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    memory_status.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    memory_add = memory_subcommands.add_parser("add", help="Add a redacted local-only memory record.")
    memory_add.add_argument("text", nargs="+")
    memory_add.add_argument("--store", help="Local JSONL memory store path. Defaults to the local YonerAI data path.")
    memory_add.add_argument("--scope", choices=MEMORY_SCOPE_CHOICES, help="Memory scope. Use 'local' for local-private memory.")
    memory_add.add_argument("--confirm-local", action="store_true", help="Confirm this is explicit local-only memory.")
    memory_add.add_argument("--tag", action="append", help="Optional simple tag. Repeatable.")
    memory_add_output = memory_add.add_mutually_exclusive_group()
    memory_add_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    memory_add_output.add_argument("--pretty", action="store_true", help="Print a readable memory summary.")
    memory_add.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    memory_add.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    memory_list = memory_subcommands.add_parser("list", help="List redacted local-only memory records.")
    memory_list.add_argument("--store", help="Local JSONL memory store path. Defaults to the local YonerAI data path.")
    memory_list.add_argument("--scope", choices=MEMORY_SCOPE_CHOICES, help="Filter by memory scope.")
    memory_list_output = memory_list.add_mutually_exclusive_group()
    memory_list_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    memory_list_output.add_argument("--pretty", action="store_true", help="Print a readable memory list.")
    memory_list.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    memory_list.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    for command_name, help_text, result_name in (
        ("forget", "Forget one local memory record without uploading it.", "summary"),
        ("delete", "Delete one local-only memory record.", "summary"),
    ):
        memory_item = memory_subcommands.add_parser(command_name, help=help_text)
        memory_item.add_argument("memory_id")
        memory_item.add_argument("--store", help="Local JSONL memory store path. Defaults to the local YonerAI data path.")
        memory_item_output = memory_item.add_mutually_exclusive_group()
        memory_item_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
        memory_item_output.add_argument("--pretty", action="store_true", help=f"Print a readable memory {result_name}.")
        memory_item.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
        memory_item.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    memory_export = memory_subcommands.add_parser("export", help="Export redacted local-only memory records.")
    memory_export.add_argument("--store", help="Local JSONL memory store path. Defaults to the local YonerAI data path.")
    memory_export_output = memory_export.add_mutually_exclusive_group()
    memory_export_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    memory_export_output.add_argument("--pretty", action="store_true", help="Print a readable memory summary.")
    memory_export.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    memory_export.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")

    memory_sync = memory_subcommands.add_parser("sync", help="Preview memory sync boundaries without calling production cloud.")
    memory_sync_subcommands = memory_sync.add_subparsers(dest="memory_sync_command", required=True)
    memory_sync_preview = memory_sync_subcommands.add_parser("preview", help="Preview cloud/local memory sync decisions.")
    memory_sync_preview.add_argument("--store", help="Local JSONL memory store path. Defaults to the local YonerAI data path.")
    memory_sync_preview.add_argument("--direction", choices=MEMORY_SYNC_DIRECTION_CHOICES, required=True)
    memory_sync_preview.add_argument("--approve", action="store_true", help="Dry-run explicit approval flag; no sync is performed.")
    memory_sync_preview_output = memory_sync_preview.add_mutually_exclusive_group()
    memory_sync_preview_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    memory_sync_preview_output.add_argument("--pretty", action="store_true", help="Print a readable sync decision.")
    memory_sync_preview.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    memory_sync_preview.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_memory_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    prepare_import_paths: Callable[[], None],
) -> int:
    report = build_memory_command_report(args, prepare_import_paths=prepare_import_paths)
    if args.json:
        print_json(report)
    else:
        print(format_memory_pretty(report, lang=getattr(args, "lang", "en"), color=args.color))
    return 0 if report["ok"] else 1


def build_memory_command_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
) -> dict[str, Any]:
    try:
        return build_memory_report(args, prepare_import_paths=prepare_import_paths)
    except MemoryUserInputError as exc:
        raise MemoryCommandUserInputError(str(exc)) from exc
    except MemoryServiceError as exc:
        raise MemoryCommandError(str(exc)) from exc
