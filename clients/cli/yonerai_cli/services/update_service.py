from __future__ import annotations

import argparse
import inspect
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

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


def build_update_apply_report(
    *,
    channel: str,
    confirmed: bool,
    repo_root: Path,
    current_version: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if channel not in {"stable", "alpha"}:
        raise UpdateServiceError("unknown update channel")
    try:
        from yonerai_cli.install_planner import (
            AUTO_UPDATE_APPLY_ENABLED,
            FORCED_UPDATE_ENABLED,
            GITHUB_INSTALL_FALLBACK_COMMAND,
            QUICK_INSTALL_COMMAND,
            VERIFIED_INSTALL_COMMAND,
            YONERAI_INSTALL_PAGE,
            build_deferred_update_policy,
        )
    except Exception as exc:
        raise UpdateServiceError("Update planner is unavailable.") from exc

    check_args = argparse.Namespace(update_command="check", manifest=None, channel=channel)
    check = build_update_report(check_args, repo_root=repo_root, current_version=current_version)
    base_report: dict[str, Any] = {
        "schema_version": "yonerai-update-apply/v0.1",
        "ok": False,
        "dry_run": not confirmed,
        "manual_apply": True,
        "confirmation_required": not confirmed,
        "confirmation_phrase": "確認",
        "channel": channel,
        "current_version": check.get("current_version"),
        "latest_manifest_version": check.get("latest_manifest_version"),
        "latest_stable": check.get("latest_stable"),
        "update_available": check.get("update_available"),
        "version_comparison": check.get("version_comparison"),
        "artifact_status": check.get("artifact_status"),
        "signature_status": check.get("signature_status"),
        "next_safe_command": _manual_update_command(channel),
        "next_interactive_command": f"/更新 適用 {'安定版' if channel == 'stable' else 'ベータ版'} 確認",
        "quick_install_command": QUICK_INSTALL_COMMAND,
        "github_install_fallback_command": GITHUB_INSTALL_FALLBACK_COMMAND,
        "verified_install_command": VERIFIED_INSTALL_COMMAND,
        "verified_install_page": YONERAI_INSTALL_PAGE,
        "forced_update_enabled": FORCED_UPDATE_ENABLED,
        "auto_update_apply_enabled": AUTO_UPDATE_APPLY_ENABLED,
        "security_update": False,
        "critical_update": False,
        "update_policy": build_deferred_update_policy(update_available=bool(check.get("update_available"))),
        "actions_not_performed": [],
        "download_performed": False,
        "install_performed": False,
        "path_mutation": False,
        "remote_code_executed": False,
        "network_required": bool(confirmed and check.get("update_available")),
        "admin_required": False,
        "service_installed": False,
        "registry_modified": False,
        "local_script_path_printed": False,
        "google_token_stored": False,
        "provider_key_stored": False,
    }
    if not confirmed:
        base_report["actions_not_performed"] = [
            "no download",
            "no install",
            "no PATH mutation",
            "no remote execution",
            "no forced update",
            "no auto-apply update",
        ]
        base_report["message_ja"] = "更新を適用するには `/更新 適用 安定版 確認` または `/更新 適用 ベータ版 確認` を入力してください。"
        base_report["message_en"] = "Type `/update apply stable confirm` or `/update apply beta confirm` to apply manually."
        return base_report

    if check.get("update_available") is False:
        base_report.update(
            {
                "ok": True,
                "dry_run": False,
                "confirmation_required": False,
                "apply_state": "already_current",
                "actions_not_performed": [
                    "no download",
                    "no install",
                    "no PATH mutation",
                    "no remote execution",
                    "no forced update",
                    "no auto-apply update",
                ],
                "message_ja": "このチャンネルはすでに最新です。インストール処理は行いませんでした。",
                "message_en": "This channel is already current. No install action was run.",
            }
        )
        return base_report

    script = repo_root / "install.ps1"
    if not script.is_file():
        raise UpdateServiceError("local installer script is unavailable")
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        raise UpdateServiceError("PowerShell is required for manual update apply")

    run_env = dict(os.environ if env is None else env)
    if run_env.get("YONERAI_UPDATE_APPLY_TEST_MODE") == "1":
        base_report.update(
            {
                "ok": True,
                "dry_run": False,
                "confirmation_required": False,
                "apply_state": "test_mode_not_installed",
                "actions_not_performed": [
                    "test mode: no download",
                    "test mode: no install",
                    "no PATH mutation",
                    "no forced update",
                    "no auto-apply update",
                ],
                "message_ja": "テストモードのため、更新適用コマンドだけ検証し、実インストールは行いませんでした。",
                "message_en": "Test mode verified the update apply command without running a real install.",
            }
        )
        return base_report

    command = [
        shell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-Channel",
        channel,
        "-Repair",
        "-Execute",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            env=run_env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
    except subprocess.TimeoutExpired as exc:
        raise UpdateServiceError("manual update apply timed out") from exc
    except OSError as exc:
        raise UpdateServiceError("manual update apply could not start") from exc

    ok = completed.returncode == 0
    base_report.update(
        {
            "ok": ok,
            "dry_run": False,
            "confirmation_required": False,
            "apply_state": "completed" if ok else "failed",
            "installer_exit_code": completed.returncode,
            "install_performed": ok,
            "download_performed": ok,
            "remote_code_executed": False,
            "actions_not_performed": [
                "no PATH mutation",
                "no service install",
                "no registry modification",
                "no admin request",
                "no forced update",
                "no auto-apply update",
            ],
            "message_ja": "更新適用が完了しました。新しいターミナルで `yonerai` を起動してください。"
            if ok
            else "更新適用に失敗しました。`irm https://install.yonerai.com | iex` または `-Repair` で修復してください。",
            "message_en": "Update apply completed. Start `yonerai` in a new terminal."
            if ok
            else "Update apply failed. Try `irm https://install.yonerai.com | iex` or repair mode.",
        }
    )
    return base_report


def build_update_choice_report(*, repo_root: Path, current_version: str) -> dict[str, Any]:
    choices: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for channel, label_ja, label_en, command in (
        ("stable", "安定版", "Stable release", "yonerai update stable"),
        ("alpha", "ベータ版", "Beta build", "yonerai update beta"),
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
        "next_step_ja": "安定版なら `yonerai update stable`、ベータ版なら `yonerai update beta` を実行してください。",
        "next_step_en": "Run `yonerai update stable` for stable, or `yonerai update beta` for the beta build.",
        "forced_update_enabled": False,
        "auto_update_apply_enabled": False,
        "download_performed": False,
        "install_performed": False,
        "path_mutation": False,
        "remote_code_executed": False,
        "network_required": False,
    }


def _manual_update_command(channel: str) -> str:
    if channel == "alpha":
        return "yonerai update apply beta --yes"
    return "yonerai update apply stable --yes"


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
