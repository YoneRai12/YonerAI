from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from yonerai_cli import __version__
from yonerai_cli.commands.api import ApiCommandError, handle_api_command
from yonerai_cli.commands.audit import AuditCommandError, handle_audit_command
from yonerai_cli.commands.ask import (
    AskCommandError,
    AskCommandUserInputError,
    handle_ask_command,
    handle_plan_command,
)
from yonerai_cli.commands.auth import (
    AuthCommandError,
    handle_auth_command,
    handle_login_alias_command,
    handle_privacy_command,
    handle_whoami_command,
)
from yonerai_cli.commands.config import ConfigCommandError, handle_config_command
from yonerai_cli.commands.discord import DiscordCommandError, handle_discord_command
from yonerai_cli.commands.evolve import EvolveCommandError, handle_evolve_command
from yonerai_cli.commands.hybrid import HybridCommandError, handle_hybrid_command
from yonerai_cli.commands.manifest import ManifestCommandError, handle_manifest_command
from yonerai_cli.commands.memory import MemoryCommandError, MemoryCommandUserInputError, handle_memory_command
from yonerai_cli.commands.node import (
    NodeCommandError,
    NodeCommandUserInputError,
    handle_node_command,
    handle_relay_command,
)
from yonerai_cli.commands.ops import OpsCommandError, handle_ops_command
from yonerai_cli.commands.oracle import OracleCommandError, handle_oracle_command
from yonerai_cli.commands.policy import handle_policy_command
from yonerai_cli.commands.providers import ProvidersCommandError, handle_providers_command
from yonerai_cli.commands.project import ProjectCommandError, handle_project_command
from yonerai_cli.commands.route import RouteCommandError, handle_route_command
from yonerai_cli.commands.runs import RunsCommandError, handle_runs_command
from yonerai_cli.commands.search import SearchCommandError, handle_search_command
from yonerai_cli.commands.sync import SyncCommandError, handle_sync_command
from yonerai_cli.commands.update import InstallUpdateCommandError, handle_install_command, handle_update_command


class CliDispatchError(Exception):
    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class CliRuntimeHooks:
    print_json: Callable[[dict[str, Any]], None]
    request_json: Callable[..., dict[str, Any]]
    run_interactive_chat: Callable[[argparse.Namespace], int]
    run_public_mvp_smoke: Callable[..., int]
    run_public_demo: Callable[..., int]
    build_start_report: Callable[..., dict[str, Any]]
    print_start_pretty: Callable[..., None]
    build_doctor_report: Callable[..., dict[str, Any]]
    print_doctor_pretty: Callable[..., None]
    build_providers_report: Callable[..., dict[str, Any]]
    prepare_import_paths: Callable[[], None]
    load_config_for_policy: Callable[[argparse.Namespace], dict[str, object]]
    build_status_report: Callable[..., dict[str, Any]]
    print_status_pretty: Callable[..., None]
    repo_root: Callable[[], Path]
    read_repo_version: Callable[[], str | None]
    prompt_from_args: Callable[[list[str]], str]


def dispatch_command(args: argparse.Namespace, hooks: CliRuntimeHooks) -> int:
    if args.command in {"chat", "interactive"}:
        return hooks.run_interactive_chat(args)
    if args.command == "login":
        try:
            return handle_login_alias_command(args, print_json=hooks.print_json)
        except AuthCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "whoami":
        try:
            return handle_whoami_command(args, print_json=hooks.print_json)
        except AuthCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "sessions":
        args.auth_command = "sessions"
        try:
            return handle_auth_command(args, print_json=hooks.print_json)
        except AuthCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "revoke":
        args.auth_command = "revoke-session"
        try:
            return handle_auth_command(args, print_json=hooks.print_json)
        except AuthCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "logout":
        args.auth_command = "logout"
        args.staging = True
        try:
            return handle_auth_command(args, print_json=hooks.print_json)
        except AuthCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "config":
        try:
            return handle_config_command(args, print_json=hooks.print_json)
        except ConfigCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "auth":
        try:
            return handle_auth_command(args, print_json=hooks.print_json)
        except AuthCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "privacy" and args.privacy_command == "status":
        try:
            return handle_privacy_command(args, print_json=hooks.print_json)
        except AuthCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "api":
        try:
            return handle_api_command(
                args, print_json=hooks.print_json, prepare_import_paths=hooks.prepare_import_paths
            )
        except ApiCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command in {"ping", "rate-limit"}:
        args.api_command = "ping" if args.command == "ping" else "rate-limit"
        try:
            return handle_api_command(
                args, print_json=hooks.print_json, prepare_import_paths=hooks.prepare_import_paths
            )
        except ApiCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "project":
        try:
            return handle_project_command(args, print_json=hooks.print_json)
        except ProjectCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "projects":
        args.project_command = args.project_short_command
        try:
            return handle_project_command(args, print_json=hooks.print_json)
        except ProjectCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "audit":
        try:
            return handle_audit_command(args, print_json=hooks.print_json)
        except AuditCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "sync":
        try:
            return handle_sync_command(
                args, print_json=hooks.print_json, prepare_import_paths=hooks.prepare_import_paths
            )
        except SyncCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=exc.exit_code) from exc
    if args.command == "evolve":
        try:
            return handle_evolve_command(
                args,
                print_json=hooks.print_json,
                prepare_import_paths=hooks.prepare_import_paths,
                repo_root=hooks.repo_root(),
            )
        except EvolveCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "health":
        hooks.print_json(hooks.request_json("GET", args.api_origin, "/health"))
        return 0
    if args.command == "smoke":
        return hooks.run_public_mvp_smoke(json_output=args.json, pretty=args.pretty)
    if args.command in {"demo", "quickstart"}:
        return hooks.run_public_demo(json_output=args.json, pretty=args.pretty)
    if args.command == "start":
        report = hooks.build_start_report(guided=args.guided)
        if args.json:
            hooks.print_json(report)
        else:
            hooks.print_start_pretty(report, lang=args.lang, color=args.color)
        return 0
    if args.command == "doctor":
        report = hooks.build_doctor_report()
        if args.json:
            hooks.print_json(report)
        else:
            hooks.print_doctor_pretty(report, lang=args.lang, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "providers":
        try:
            return handle_providers_command(
                args, print_json=hooks.print_json, report_builder=hooks.build_providers_report
            )
        except ProvidersCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "policy":
        hooks.prepare_import_paths()
        try:
            return handle_policy_command(args, config=hooks.load_config_for_policy(args), print_json=hooks.print_json)
        except ValueError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "status":
        report = hooks.build_status_report(
            source=args.source,
            status_source=getattr(args, "status_source", None),
            allow_network_status_fetch=bool(getattr(args, "allow_network_status_fetch", False)),
            profile=getattr(args, "profile", "operational"),
        )
        if args.json:
            hooks.print_json(report)
        else:
            hooks.print_status_pretty(report, lang=args.lang, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "manifest" and args.manifest_command == "verify":
        try:
            return handle_manifest_command(args, print_json=hooks.print_json)
        except ManifestCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "route" and args.route_command == "preview":
        try:
            return handle_route_command(
                args, print_json=hooks.print_json, prepare_import_paths=hooks.prepare_import_paths
            )
        except RouteCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "node":
        try:
            return handle_node_command(
                args, print_json=hooks.print_json, prepare_import_paths=hooks.prepare_import_paths
            )
        except NodeCommandUserInputError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
        except NodeCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "relay" and args.relay_command == "status":
        try:
            return handle_relay_command(
                args,
                print_json=hooks.print_json,
                prepare_import_paths=hooks.prepare_import_paths,
                env=os.environ,
            )
        except NodeCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "oracle":
        try:
            return handle_oracle_command(
                args,
                print_json=hooks.print_json,
                prepare_import_paths=hooks.prepare_import_paths,
                env=os.environ,
            )
        except OracleCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "hybrid":
        try:
            return handle_hybrid_command(
                args,
                print_json=hooks.print_json,
                prepare_import_paths=hooks.prepare_import_paths,
                env=os.environ,
            )
        except HybridCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "plan":
        try:
            return handle_plan_command(
                args, print_json=hooks.print_json, prepare_import_paths=hooks.prepare_import_paths
            )
        except AskCommandUserInputError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
        except AskCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "ask":
        try:
            return handle_ask_command(
                args,
                print_json=hooks.print_json,
                prepare_import_paths=hooks.prepare_import_paths,
                env=os.environ,
            )
        except AskCommandUserInputError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
        except AskCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "runs":
        try:
            return handle_runs_command(
                args,
                print_json=hooks.print_json,
                prepare_import_paths=hooks.prepare_import_paths,
                env=os.environ,
            )
        except RunsCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "search":
        try:
            return handle_search_command(
                args, print_json=hooks.print_json, prepare_import_paths=hooks.prepare_import_paths, env=os.environ
            )
        except SearchCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "discord" and args.discord_command == "synthetic":
        try:
            return handle_discord_command(
                args, print_json=hooks.print_json, prepare_import_paths=hooks.prepare_import_paths, env=os.environ
            )
        except DiscordCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "install" and args.install_command in {"status", "plan", "plan-windows"}:
        try:
            return handle_install_command(args, print_json=hooks.print_json, repo_root=hooks.repo_root())
        except InstallUpdateCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "update" and args.update_command in {"plan", "check"}:
        try:
            return handle_update_command(
                args,
                print_json=hooks.print_json,
                repo_root=hooks.repo_root(),
                current_version=hooks.read_repo_version() or __version__,
            )
        except InstallUpdateCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
    if args.command == "ops" and args.ops_command == "plan":
        try:
            return handle_ops_command(
                args, print_json=hooks.print_json, prepare_import_paths=hooks.prepare_import_paths
            )
        except OpsCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "memory":
        try:
            return handle_memory_command(
                args, print_json=hooks.print_json, prepare_import_paths=hooks.prepare_import_paths
            )
        except MemoryCommandUserInputError as exc:
            raise CliDispatchError(str(exc), exit_code=2) from exc
        except MemoryCommandError as exc:
            raise CliDispatchError(str(exc), exit_code=1) from exc
    if args.command == "message":
        prompt = hooks.prompt_from_args(args.prompt)
        hooks.print_json(
            hooks.request_json("POST", args.api_origin, "/v1/public/messages", {"message": prompt, "mode": args.mode})
        )
        return 0
    if args.command == "run":
        prompt = hooks.prompt_from_args(args.prompt)
        hooks.print_json(
            hooks.request_json("POST", args.api_origin, "/api/v1/agent/run", {"prompt": prompt, "mode": args.mode})
        )
        return 0
    raise CliDispatchError("unknown command", exit_code=2)
