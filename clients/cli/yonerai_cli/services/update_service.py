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
            build_install_update_status,
            build_install_plan,
            build_install_plan_from_default,
            build_windows_install_plan,
            build_windows_install_plan_from_default,
        )
    except Exception as exc:
        raise UpdateServiceError("Install planner is unavailable.") from exc

    try:
        if args.install_command == "status":
            report = build_install_update_status()
            if isinstance(report, dict):
                report.setdefault("channel", args.channel)
            return report
        if args.install_command == "plan":
            if args.manifest:
                return build_install_plan(args.manifest)
            return _call_default_install_builder(build_install_plan_from_default, repo_root, channel=args.channel)
        if args.manifest:
            return build_windows_install_plan(args.manifest)
        return _call_default_install_builder(build_windows_install_plan_from_default, repo_root, channel=args.channel)
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


def build_update_choice_report(*, repo_root: Path, current_version: str) -> dict[str, Any]:
    choices: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for channel, label_ja, label_en, command in (
        ("stable", "安定版", "Stable release", "yonerai update stable"),
        ("alpha", "最新アルファ版", "Latest alpha", "yonerai update alpha"),
    ):
        try:
            channel_args = argparse.Namespace(update_command="check", manifest=None, channel=channel)
            report = build_update_report(channel_args, repo_root=repo_root, current_version=current_version)
        except UpdateServiceError as exc:
            errors.append({"channel": channel, "message": str(exc)})
            choices.append(
                {
                    "id": channel,
                    "label_ja": label_ja,
                    "label_en": label_en,
                    "command": command,
                    "available": False,
                    "error": str(exc),
                }
            )
            continue
        choices.append(
            {
                "id": channel,
                "label_ja": label_ja,
                "label_en": label_en,
                "command": command,
                "available": bool(report.get("ok")),
                "latest_version": report.get("latest_manifest_version"),
                "update_available": bool(report.get("update_available")),
                "version_comparison": report.get("version_comparison"),
                "selected_artifact": (report.get("artifact_status") or {}).get("actual_filename")
                if isinstance(report.get("artifact_status"), dict)
                else None,
                "signature_state": (report.get("signature_status") or {}).get("state")
                if isinstance(report.get("signature_status"), dict)
                else None,
                "next_safe_command": report.get("next_safe_command"),
            }
        )
    return {
        "schema_version": "yonerai-update-choice/v0.1",
        "ok": any(choice.get("available") for choice in choices) and not errors,
        "dry_run": True,
        "command": "yonerai update",
        "current_version": current_version,
        "default_channel": "stable",
        "choices": choices,
        "errors": errors,
        "actions_not_performed": [
            "no download",
            "no install",
            "no PATH mutation",
            "no remote execution",
            "no forced update",
            "no auto-apply update",
        ],
        "next_step_ja": "安定版なら `yonerai update stable`、アルファ版なら `yonerai update alpha` を実行してください。",
        "next_step_en": "Run `yonerai update stable` for stable, or `yonerai update alpha` for the latest alpha.",
        "forced_update_enabled": False,
        "auto_update_apply_enabled": False,
        "download_performed": False,
        "install_performed": False,
        "path_mutation": False,
        "remote_code_executed": False,
        "network_required": False,
    }


def _call_default_update_builder(builder: Any, repo_root: Path, *, current_version: str, channel: str) -> dict[str, Any]:
    parameters = inspect.signature(builder).parameters
    if "channel" in parameters:
        return builder(repo_root, current_version=current_version, channel=channel)
    report = builder(repo_root, current_version=current_version)
    if isinstance(report, dict):
        report.setdefault("channel", channel)
    return report


def _call_default_install_builder(builder: Any, repo_root: Path, *, channel: str) -> dict[str, Any]:
    parameters = inspect.signature(builder).parameters
    if "channel" in parameters:
        return builder(repo_root, channel=channel)
    report = builder(repo_root)
    if isinstance(report, dict):
        report.setdefault("channel", channel)
    return report
