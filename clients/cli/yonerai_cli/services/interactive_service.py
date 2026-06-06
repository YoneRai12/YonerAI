from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from yonerai_cli import __version__
from yonerai_cli.commands.ask import build_auto_ask_report
from yonerai_cli.commands.memory import (
    MemoryCommandError,
    MemoryCommandUserInputError,
    build_memory_command_report,
)
from yonerai_cli.commands.runs import build_runs_report
from yonerai_cli.config import ConfigError


class InteractiveServiceError(Exception):
    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def build_interactive_ask_report(
    task: str,
    provider: str,
    live: bool,
    ledger_path: str | None,
    memory_store_path: str | None,
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    if memory_store_path == "__default__":
        prepare_import_paths()
        from ora_core.memory import default_memory_store_path

        memory_store_path = str(default_memory_store_path())
    args = argparse.Namespace(
        task=[task],
        provider=provider,
        live=live,
        ledger_path=ledger_path,
        memory_store=memory_store_path,
        file=None,
        workspace=None,
        file_max_bytes=65536,
    )
    return build_auto_ask_report(args, prepare_import_paths=prepare_import_paths, env=env)


def build_interactive_runs_list(
    ledger_path: str | None,
    limit: int,
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    args = argparse.Namespace(runs_command="list", ledger_path=ledger_path, limit=limit)
    return build_runs_report(args, prepare_import_paths=prepare_import_paths, env=env)


def build_interactive_runs_show(
    run_id: str,
    ledger_path: str | None,
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str],
) -> dict[str, Any]:
    args = argparse.Namespace(runs_command="show", ledger_path=ledger_path, run_id=run_id, limit=1)
    return build_runs_report(args, prepare_import_paths=prepare_import_paths, env=env)


def build_interactive_update_check(
    manifest_path: str | None,
    *,
    repo_root: Path,
    current_version: str | None,
) -> dict[str, Any]:
    from yonerai_cli.services.update_service import UpdateServiceError, build_update_report

    args = argparse.Namespace(update_command="check", manifest=manifest_path, channel="stable")
    try:
        return build_update_report(args, repo_root=repo_root, current_version=current_version or __version__)
    except UpdateServiceError as exc:
        raise InteractiveServiceError(str(exc), exit_code=1) from exc


def build_interactive_memory_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
) -> dict[str, Any]:
    try:
        return build_memory_command_report(args, prepare_import_paths=prepare_import_paths)
    except MemoryCommandUserInputError as exc:
        raise InteractiveServiceError(str(exc), exit_code=2) from exc
    except MemoryCommandError as exc:
        raise InteractiveServiceError(str(exc), exit_code=1) from exc


def build_interactive_memory_action(
    action: str,
    values: list[str],
    default_scope: str | None,
    *,
    prepare_import_paths: Callable[[], None],
) -> dict[str, Any]:
    if action == "add":
        text = values[0] if values else ""
        args = argparse.Namespace(
            memory_command="add",
            text=[text],
            store=None,
            scope=default_scope or "local_private",
            confirm_local=True,
            tag=[],
        )
        return build_interactive_memory_report(args, prepare_import_paths=prepare_import_paths)
    if action == "list":
        args = argparse.Namespace(memory_command="list", store=None, scope=None)
        return build_interactive_memory_report(args, prepare_import_paths=prepare_import_paths)
    if action == "forget":
        args = argparse.Namespace(memory_command="forget", store=None, memory_id=values[0] if values else "")
        return build_interactive_memory_report(args, prepare_import_paths=prepare_import_paths)
    if action == "sync-preview":
        direction = (values[0] if values else "cloud-to-local").replace("_", "-")
        args = argparse.Namespace(
            memory_command="sync",
            memory_sync_command="preview",
            store=None,
            direction=direction,
            approve=False,
        )
        return build_interactive_memory_report(args, prepare_import_paths=prepare_import_paths)
    raise InteractiveServiceError("unknown interactive memory action", exit_code=2)


def build_interactive_policy_status(
    config: dict[str, object],
    *,
    prepare_import_paths: Callable[[], None],
) -> dict[str, Any]:
    prepare_import_paths()
    from ora_core.policies import build_policy_status_report

    return build_policy_status_report(config)


def build_interactive_status_check(*, prepare_import_paths: Callable[[], None]) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.official import build_status_check_report

        return build_status_check_report(profile="operational")
    except ValueError as exc:
        raise InteractiveServiceError(str(exc), exit_code=2) from exc


def build_interactive_api_status(*, prepare_import_paths: Callable[[], None]) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.official import build_official_api_status_report, build_status_check_report

        report = build_official_api_status_report(auth_state="dry_run")
        report["status_bridge"] = build_status_check_report(profile="operational")
        return report
    except ValueError as exc:
        raise InteractiveServiceError(str(exc), exit_code=2) from exc


def build_interactive_sync_status(*, prepare_import_paths: Callable[[], None]) -> dict[str, Any]:
    from yonerai_cli.services.staging_sync_service import build_staging_sync_status

    return build_staging_sync_status(config={})


def build_interactive_evolve_status(*, prepare_import_paths: Callable[[], None]) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from src.self_evolution import build_queue_status_report

        return build_queue_status_report()
    except Exception as exc:
        raise InteractiveServiceError("self-evolution proposal queue is unavailable.", exit_code=1) from exc


def run_interactive_chat(args: argparse.Namespace, callbacks: Any) -> int:
    from yonerai_cli.interactive import InteractiveOptions, run_interactive_cli

    options = InteractiveOptions(
        config_path=args.config_path,
        lang=args.lang,
        provider=args.provider,
        live=args.live,
        ledger_path=args.ledger_path,
        script=args.script,
        color=args.color,
    )
    try:
        return run_interactive_cli(options, callbacks)
    except ConfigError as exc:
        raise InteractiveServiceError(str(exc), exit_code=2) from exc
