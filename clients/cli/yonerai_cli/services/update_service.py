from __future__ import annotations

import argparse
import inspect
from pathlib import Path
from typing import Any

from yonerai_cli.release_manifest import ManifestError


class UpdateServiceError(Exception):
    pass


def build_install_report(args: argparse.Namespace, *, repo_root: Path) -> dict[str, Any]:
    try:
        from yonerai_cli.install_planner import (
            build_install_plan,
            build_install_plan_from_default,
            build_install_status,
            build_windows_install_plan,
            build_windows_install_plan_from_default,
        )
    except Exception as exc:
        raise UpdateServiceError("Install planner is unavailable.") from exc

    try:
        if args.install_command == "status":
            return build_install_status(repo_root, channel=args.channel)
        if args.install_command == "plan":
            if args.manifest:
                return build_install_plan(args.manifest)
            return build_install_plan_from_default(repo_root, channel=args.channel)
        if args.manifest:
            return build_windows_install_plan(args.manifest)
        return build_windows_install_plan_from_default(repo_root, channel=args.channel)
    except ManifestError as exc:
        raise UpdateServiceError(str(exc)) from exc


def build_update_report(args: argparse.Namespace, *, repo_root: Path, current_version: str) -> dict[str, Any]:
    try:
        from yonerai_cli.install_planner import (
            build_update_check,
            build_update_check_from_default,
            build_update_plan,
            build_update_plan_from_default,
        )
    except Exception as exc:
        raise UpdateServiceError("Update planner is unavailable.") from exc

    try:
        if args.update_command == "check":
            if args.manifest:
                return build_update_check(args.manifest, current_version=current_version)
            return _call_default_update_builder(
                build_update_check_from_default,
                repo_root,
                current_version=current_version,
                channel=args.channel,
            )
        if args.manifest:
            return build_update_plan(args.manifest, current_version=current_version)
        return _call_default_update_builder(
            build_update_plan_from_default,
            repo_root,
            current_version=current_version,
            channel=args.channel,
        )
    except ManifestError as exc:
        raise UpdateServiceError(str(exc)) from exc


def _call_default_update_builder(builder: Any, repo_root: Path, *, current_version: str, channel: str) -> dict[str, Any]:
    parameters = inspect.signature(builder).parameters
    if "channel" in parameters:
        return builder(repo_root, current_version=current_version, channel=channel)
    report = builder(repo_root, current_version=current_version)
    if isinstance(report, dict):
        report.setdefault("channel", channel)
    return report
