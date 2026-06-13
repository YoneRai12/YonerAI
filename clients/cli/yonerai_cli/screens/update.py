from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.screens.labels import _safe, _value_label, _yes_no


def format_install_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    if report.get("schema_version") == "yonerai-install-status/v0.1":
        return format_install_status_pretty(report, color=color)
    manifest = report["manifest"]
    non_actions = report["non_actions"]
    errors = tuple(CliRow("error", error, "fail") for error in manifest["errors"])
    sections = (
        CliSection(
            "Dry-run plan",
            (
                CliRow("dry_run", report["dry_run"], "ok" if report["dry_run"] else "fail"),
                CliRow("target_category", report["target_category"], "ok"),
                CliRow("manifest_contract_valid", manifest["contract_valid"], "ok" if manifest["contract_valid"] else "fail"),
                CliRow("install_ready", manifest["install_ready"], "ok" if manifest["install_ready"] else "warn"),
                CliRow("artifact_count", manifest["artifact_count"], "ok" if manifest["artifact_count"] else "fail"),
            ),
        ),
        CliSection(
            "Signature",
            (
                CliRow("signature_state", manifest["signature_state"], "ok" if manifest["signature_state"] == "signed" else "warn"),
                CliRow("signature_verified", manifest["signature_verified"], "ok" if manifest["signature_verified"] else "warn"),
                CliRow(
                    "placeholder_non_production",
                    manifest["placeholder_non_production"],
                    "warn" if manifest["placeholder_non_production"] else "ok",
                ),
                CliRow(
                    "verification_required_before_real_install",
                    manifest["verification_required_before_real_install"],
                    "warn" if manifest["verification_required_before_real_install"] else "ok",
                ),
            ),
        ),
        CliSection("Non-actions", tuple(CliRow(name, value, "ok" if value else "fail") for name, value in non_actions.items())),
        CliSection(
            "Execution boundary",
            (
                CliRow("download_performed", report["download_performed"], "fail" if report["download_performed"] else "ok"),
                CliRow("install_performed", report["install_performed"], "fail" if report["install_performed"] else "ok"),
                CliRow("path_mutation", report["path_mutation"], "fail" if report["path_mutation"] else "ok"),
                CliRow("remote_code_executed", report["remote_code_executed"], "fail" if report["remote_code_executed"] else "ok"),
            ),
        ),
    )
    if errors:
        sections = (*sections, CliSection("Errors", errors))
    return render_report("YonerAI install plan", sections, color=color)


def format_install_status_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    source = report["source_policy"]
    signature = report["signature_status"]
    non_actions = report["non_actions"]
    rows = (
        CliRow("channel", _display_channel(report.get("channel"), lang="en"), "ok"),
        CliRow("selected_version", report["selected_version"], "ok"),
        CliRow("install_script_source", source["install_script_source"], "ok"),
        CliRow("artifact_source", source["artifact_source"], "ok"),
        CliRow(
            "yonerai.com_installer_bytes",
            source["yonerai_com_serves_install_script"],
            "fail" if source["yonerai_com_serves_install_script"] else "ok",
        ),
        CliRow(
            "yonerai.com_manifest_or_zip",
            source["yonerai_com_serves_manifest_or_zip"],
            "fail" if source["yonerai_com_serves_manifest_or_zip"] else "ok",
        ),
        CliRow("local_file_source_allowed", source["local_file_source_allowed"], "fail" if source["local_file_source_allowed"] else "ok"),
        CliRow("signature_state", signature["state"], "ok" if signature["state"] == "signed" else "warn"),
        CliRow("production_trust_store", signature["production_trust_store_included"], "fail" if signature["production_trust_store_included"] else "ok"),
    )
    command_rows = tuple(CliRow(name, value, "ok") for name, value in report["recommended_commands"].items())
    sections = (
        CliSection("Install source", rows),
        CliSection("Recommended commands", command_rows),
        CliSection("Non-actions", tuple(CliRow(name, value, "ok" if value else "fail") for name, value in non_actions.items())),
    )
    return render_report("YonerAI install status", sections, color=color)


def format_update_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    if report.get("schema_version") == "yonerai-update-choice/v0.1":
        return format_update_choice_pretty(report)
    if report.get("schema_version") == "yonerai-update-apply/v0.1":
        return _format_update_apply_pretty(report, color=color)
    if report.get("schema_version") == "yonerai-update-check/v0.1":
        return format_update_check_pretty(report, color=color)
    manifest = report["manifest"]
    signature = report["signature_status"]
    non_actions = report["non_actions"]
    selected = report["selected_artifact"] or {}
    update_policy = report.get("update_policy") if isinstance(report.get("update_policy"), dict) else {}
    errors = tuple(CliRow("error", error, "fail") for error in manifest["errors"])
    warnings = tuple(CliRow("warning", warning, "warn") for warning in report["warnings"])
    sections = (
        CliSection(
            "Dry-run update plan",
            (
                CliRow("dry_run", report["dry_run"], "ok" if report["dry_run"] else "fail"),
                CliRow("current_version", report["current_version"], "ok"),
                CliRow("target_version", report["target_version"], "ok" if report["target_version"] else "fail"),
                CliRow("latest_stable", report.get("latest_stable", "unknown"), "ok"),
                CliRow("channel", _display_channel(report.get("channel"), lang="en"), "ok" if report.get("channel") else "fail"),
                CliRow("update_available", report["update_available"], "warn" if report["update_available"] else "ok"),
                CliRow("security_update", bool(report.get("security_update")), "warn" if report.get("security_update") else "ok"),
                CliRow("critical_update", bool(report.get("critical_update")), "fail" if report.get("critical_update") else "ok"),
                CliRow("version_comparison", report["version_comparison"], _update_version_comparison_level(report)),
                CliRow("rollback_plan_available", report["rollback_plan_available"], "ok" if report["rollback_plan_available"] else "warn"),
            ),
        ),
        CliSection(
            "Install/update UX",
            (
                CliRow("quick_install_command", report.get("quick_install_command", "unavailable"), "ok"),
                CliRow("github_install_fallback_command", report.get("github_install_fallback_command", "unavailable"), "ok"),
                CliRow("verified_install_page", report.get("verified_install_page", "unavailable"), "ok"),
                CliRow("forced_update_enabled", bool(report.get("forced_update_enabled")), "fail" if report.get("forced_update_enabled") else "ok"),
                CliRow("auto_update_apply_enabled", bool(report.get("auto_update_apply_enabled")), "fail" if report.get("auto_update_apply_enabled") else "ok"),
                CliRow(
                    "basic_local_mock_chat_allowed",
                    bool(update_policy.get("basic_local_mock_chat_allowed", True)),
                    "ok" if update_policy.get("basic_local_mock_chat_allowed", True) else "fail",
                ),
            ),
        ),
        CliSection(
            "Manifest",
            (
                CliRow("contract_valid", manifest["contract_valid"], "ok" if manifest["contract_valid"] else "fail"),
                CliRow("install_ready", manifest["install_ready"], "ok" if manifest["install_ready"] else "warn"),
                CliRow("artifact_count", manifest["artifact_count"], "ok" if manifest["artifact_count"] else "fail"),
                CliRow("selected_artifact", selected.get("artifact_id", "none"), "ok" if selected else "fail"),
                CliRow("artifact_filename", selected.get("actual_filename", "none"), "ok" if selected.get("filename_matches") else "fail"),
                CliRow("sha256_present", report["sha256_present"], "ok" if report["sha256_present"] else "fail"),
            ),
        ),
        CliSection(
            "Signature",
            (
                CliRow("signature_state", signature["state"], "ok" if signature["state"] == "signed" else "warn"),
                CliRow("signature_verified", signature["verified"], "ok" if signature["verified"] else "warn"),
                CliRow("placeholder_non_production", signature["placeholder_non_production"], "warn" if signature["placeholder_non_production"] else "ok"),
                CliRow(
                    "verification_required_before_real_update",
                    signature["verification_required_before_real_update"],
                    "warn" if signature["verification_required_before_real_update"] else "ok",
                ),
            ),
        ),
        CliSection("Non-actions", tuple(CliRow(name, value, "ok" if value else "fail") for name, value in non_actions.items())),
        CliSection(
            "Execution boundary",
            (
                CliRow("download_performed", report["download_performed"], "fail" if report["download_performed"] else "ok"),
                CliRow("install_performed", report["install_performed"], "fail" if report["install_performed"] else "ok"),
                CliRow("path_mutation", report["path_mutation"], "fail" if report["path_mutation"] else "ok"),
                CliRow("remote_code_executed", report["remote_code_executed"], "fail" if report["remote_code_executed"] else "ok"),
            ),
        ),
    )
    if warnings:
        sections = (*sections, CliSection("Warnings", warnings))
    if errors:
        sections = (*sections, CliSection("Errors", errors))
    return render_report("YonerAI update plan", sections, color=color)


def _format_update_apply_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    artifact = report.get("artifact_status") if isinstance(report.get("artifact_status"), dict) else {}
    signature = report.get("signature_status") if isinstance(report.get("signature_status"), dict) else {}
    sections = (
        CliSection(
            "Manual update apply",
            (
                CliRow("ok", report.get("ok"), "ok" if report.get("ok") else "warn"),
                CliRow("channel", _display_channel(report.get("channel"), lang="en"), "ok"),
                CliRow("current_version", report.get("current_version"), "ok"),
                CliRow("target_version", report.get("latest_manifest_version"), "ok"),
                CliRow("update_available", report.get("update_available"), "warn" if report.get("update_available") else "ok"),
                CliRow("confirmation_required", report.get("confirmation_required"), "warn" if report.get("confirmation_required") else "ok"),
                CliRow("apply_state", report.get("apply_state", "not_started"), "ok" if report.get("ok") else "warn"),
                CliRow("next_safe_command", report.get("next_safe_command"), "ok"),
            ),
        ),
        CliSection(
            "Artifact and trust",
            (
                CliRow("artifact", artifact.get("actual_filename") or artifact.get("selected_artifact") or "none", "ok"),
                CliRow("sha256_present", artifact.get("sha256_present"), "ok" if artifact.get("sha256_present") else "fail"),
                CliRow("signature_state", signature.get("state"), "warn" if signature.get("state") != "signed" else "ok"),
                CliRow("signature_verified", signature.get("verified"), "warn" if not signature.get("verified") else "ok"),
            ),
        ),
        CliSection(
            "Execution boundary",
            (
                CliRow("manual_apply", report.get("manual_apply"), "ok"),
                CliRow("forced_update_enabled", report.get("forced_update_enabled"), "fail" if report.get("forced_update_enabled") else "ok"),
                CliRow("auto_update_apply_enabled", report.get("auto_update_apply_enabled"), "fail" if report.get("auto_update_apply_enabled") else "ok"),
                CliRow("path_mutation", report.get("path_mutation"), "fail" if report.get("path_mutation") else "ok"),
                CliRow("admin_required", report.get("admin_required"), "fail" if report.get("admin_required") else "ok"),
                CliRow("service_installed", report.get("service_installed"), "fail" if report.get("service_installed") else "ok"),
                CliRow("registry_modified", report.get("registry_modified"), "fail" if report.get("registry_modified") else "ok"),
            ),
        ),
        CliSection(
            "Next",
            (
                CliRow("message", report.get("message_en") or report.get("message_ja"), "ok" if report.get("ok") else "warn"),
                CliRow("interactive_command", report.get("next_interactive_command"), "ok"),
            ),
        ),
    )
    return render_report("YonerAI update apply", sections, color=color)


def format_update_choice_pretty(report: dict[str, Any]) -> str:
    choices = report.get("choices") if isinstance(report.get("choices"), list) else []
    lines = [
        "YonerAI 更新",
        f"  現在のバージョン: {_safe(report.get('current_version') or '不明')}",
        "  どちらを確認しますか？",
        "",
    ]
    for index, choice in enumerate(choices, start=1):
        if not isinstance(choice, dict):
            continue
        label = _safe(choice.get("label_ja") or choice.get("label_en") or choice.get("id") or f"choice-{index}")
        command = _safe(choice.get("command") or "")
        latest = _safe(choice.get("latest_version") or "不明")
        available = "利用可" if choice.get("available") else "確認不可"
        update_available = "更新あり" if choice.get("update_available") else "更新なし"
        signature = _safe(choice.get("signature_state") or "不明")
        lines.extend(
            [
                f"  {index}. {label}",
                f"     コマンド: {command}",
                f"     最新: {latest} / {update_available} / {available}",
                f"     署名/信頼: {signature}",
            ]
        )
        if choice.get("error"):
            lines.append(f"     エラー: {_safe(choice.get('error'))}")
    lines.extend(
        [
            "",
            f"  次: {_safe(report.get('next_step_ja') or '/更新 安定版 または /更新 ベータ版')}",
            "  ここではダウンロード、インストール、PATH変更、自動適用は行いません。",
            "  実際のインストール確認は表示された安全な次のコマンドで進めます。",
            "",
        ]
    )
    return "\n".join(lines)


def format_update_check_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    artifact = report.get("artifact_status") if isinstance(report.get("artifact_status"), dict) else {}
    signature = report.get("signature_status") if isinstance(report.get("signature_status"), dict) else {}
    update_policy = report.get("update_policy") if isinstance(report.get("update_policy"), dict) else {}
    warnings = tuple(CliRow("warning", warning, "warn") for warning in report.get("warnings", []))
    sections = (
        CliSection(
            "Update check",
            (
                CliRow("dry_run", report["dry_run"], "ok" if report["dry_run"] else "fail"),
                CliRow("current_version", report["current_version"], "ok"),
                CliRow("latest_manifest_version", report["latest_manifest_version"], "ok"),
                CliRow("latest_stable", report.get("latest_stable", "unknown"), "ok"),
                CliRow("channel", _display_channel(report.get("channel"), lang="en"), "ok" if report.get("channel") else "fail"),
                CliRow("update_available", report["update_available"], "warn" if report["update_available"] else "ok"),
                CliRow("security_update", bool(report.get("security_update")), "warn" if report.get("security_update") else "ok"),
                CliRow("critical_update", bool(report.get("critical_update")), "fail" if report.get("critical_update") else "ok"),
                CliRow("version_comparison", report["version_comparison"], _update_version_comparison_level(report)),
                CliRow("next_safe_command", report["next_safe_command"], "ok"),
            ),
        ),
        CliSection(
            "Install/update UX",
            (
                CliRow("quick_install_command", report.get("quick_install_command", "unavailable"), "ok"),
                CliRow("github_install_fallback_command", report.get("github_install_fallback_command", "unavailable"), "ok"),
                CliRow("verified_install_page", report.get("verified_install_page", "unavailable"), "ok"),
                CliRow("forced_update_enabled", bool(report.get("forced_update_enabled")), "fail" if report.get("forced_update_enabled") else "ok"),
                CliRow("auto_update_apply_enabled", bool(report.get("auto_update_apply_enabled")), "fail" if report.get("auto_update_apply_enabled") else "ok"),
                CliRow(
                    "basic_local_mock_chat_allowed",
                    bool(update_policy.get("basic_local_mock_chat_allowed", True)),
                    "ok" if update_policy.get("basic_local_mock_chat_allowed", True) else "fail",
                ),
            ),
        ),
        CliSection(
            "Artifact",
            (
                CliRow("selected_artifact", artifact.get("selected_artifact") or "none", "ok" if artifact.get("selected_artifact") else "warn"),
                CliRow("artifact_filename", artifact.get("actual_filename") or "none", "ok" if artifact.get("filename_matches") else "fail"),
                CliRow("filename_matches", artifact.get("filename_matches"), "ok" if artifact.get("filename_matches") else "fail"),
                CliRow("sha256_present", artifact.get("sha256_present"), "ok" if artifact.get("sha256_present") else "fail"),
            ),
        ),
        CliSection(
            "Signature",
            (
                CliRow("signature_state", signature.get("state"), "ok" if signature.get("state") == "signed" else "warn"),
                CliRow("signature_verified", signature.get("verified"), "ok" if signature.get("verified") else "warn"),
                CliRow(
                    "verification_required_before_real_update",
                    signature.get("verification_required_before_real_update"),
                    "warn" if signature.get("verification_required_before_real_update") else "ok",
                ),
            ),
        ),
        CliSection("Non-actions", tuple(CliRow(name, True, "ok") for name in report.get("actions_not_performed", []))),
        CliSection(
            "Execution boundary",
            (
                CliRow("download_performed", report["download_performed"], "fail" if report["download_performed"] else "ok"),
                CliRow("install_performed", report["install_performed"], "fail" if report["install_performed"] else "ok"),
                CliRow("path_mutation", report["path_mutation"], "fail" if report["path_mutation"] else "ok"),
                CliRow("remote_code_executed", report["remote_code_executed"], "fail" if report["remote_code_executed"] else "ok"),
                CliRow("network_required", report["network_required"], "warn" if report["network_required"] else "ok"),
            ),
        ),
    )
    if warnings:
        sections = (*sections, CliSection("Warnings", warnings))
    return render_report("YonerAI update check", sections, color=color)


def _update_version_comparison_level(report: dict[str, Any]) -> str:
    comparison = report["version_comparison"]
    if comparison == "target_older":
        return "warn"
    if comparison == "unknown":
        return "fail"
    return "ok" if report["ok"] else "warn"


def _display_channel(channel: Any, *, lang: str) -> str:
    value = str(channel or "").strip()
    if lang == "ja":
        if value == "stable":
            return "安定版"
        if value == "alpha":
            return "ベータ版"
        return _safe(value or "不明")
    if value == "alpha":
        return "beta"
    return _safe(value or "unknown")


def _interactive_update_command(value: Any, *, lang: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "/更新" if lang == "ja" else "/update"
    if text.startswith("/"):
        return _safe(text)
    normalized = " ".join(text.split()).lower()
    if lang == "ja":
        mapping = (
            ("yonerai update apply stable", "/更新 適用 安定版 確認 (/update apply stable confirm)"),
            ("yonerai update apply alpha", "/更新 適用 ベータ版 確認 (/update apply beta confirm)"),
            ("yonerai update apply beta", "/更新 適用 ベータ版 確認 (/update apply beta confirm)"),
            ("yonerai update stable", "/更新 安定版 (/update stable)"),
            ("yonerai update alpha", "/更新 ベータ版 (/update beta)"),
            ("yonerai update beta", "/更新 ベータ版 (/update beta)"),
            ("yonerai update check", "/更新 (/update)"),
            ("yonerai update plan", "/更新 (/update)"),
            ("yonerai update", "/更新 (/update)"),
        )
    else:
        mapping = (
            ("yonerai update apply stable", "/update apply stable confirm (/更新 適用 安定版 確認)"),
            ("yonerai update apply alpha", "/update apply beta confirm (/更新 適用 ベータ版 確認)"),
            ("yonerai update apply beta", "/update apply beta confirm (/更新 適用 ベータ版 確認)"),
            ("yonerai update stable", "/update stable (/更新 安定版)"),
            ("yonerai update alpha", "/update beta (/更新 ベータ版)"),
            ("yonerai update beta", "/update beta (/更新 ベータ版)"),
            ("yonerai update check", "/update (/更新)"),
            ("yonerai update plan", "/update (/更新)"),
            ("yonerai update", "/update (/更新)"),
        )
    for prefix, replacement in mapping:
        if normalized.startswith(prefix):
            return replacement
    return _safe(text)


def _format_update_check(report: dict[str, Any], *, lang: str) -> str:
    if report.get("schema_version") == "yonerai-update-choice/v0.1":
        return format_update_choice_pretty(report)
    artifact = report.get("artifact_status") if isinstance(report.get("artifact_status"), dict) else {}
    signature = report.get("signature_status") if isinstance(report.get("signature_status"), dict) else {}
    policy = report.get("update_policy") if isinstance(report.get("update_policy"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    if lang == "ja":
        if report.get("schema_version") == "yonerai-update-apply/v0.1":
            lines = [
                "更新適用",
                f"  チャンネル: {_display_channel(report.get('channel'), lang='ja')}",
                f"  現在のバージョン: {_safe(report.get('current_version') or '不明')}",
                f"  対象バージョン: {_safe(report.get('latest_manifest_version') or '不明')}",
                f"  状態: {_safe(report.get('apply_state') or '未実行')}",
                f"  確認が必要: {_yes_no(bool(report.get('confirmation_required')), lang='ja')}",
                f"  次: {_interactive_update_command(report.get('next_interactive_command') or report.get('next_safe_command'), lang='ja')}",
                f"  説明: {_safe(report.get('message_ja') or '')}",
                "  自動適用なし / 強制サイレント更新なし / PATH変更なし",
                "",
            ]
            return "\n".join(lines)
        lines = [
            "更新確認",
            f"  現在のバージョン: {_safe(report.get('current_version') or '不明')}",
            f"  チャンネル: {_display_channel(report.get('channel'), lang='ja')}",
            f"  最新安定版: {_safe(report.get('latest_stable') or report.get('latest_manifest_version') or '不明')}",
            f"  最新: {_safe(report.get('latest_manifest_version') or report.get('latest_stable') or '不明')}",
            f"  更新: {_value_label(bool(report.get('update_available')), lang='ja')}",
            f"  trust: {_safe(signature.get('state') or '不明')} / sha256={'あり' if artifact.get('sha256_present') else 'なし'}",
            f"  artifact: {_safe(artifact.get('actual_filename') or artifact.get('selected_artifact') or '未選択')}",
            f"  強制更新: {'あり' if report.get('forced_update_enabled') else 'なし'}",
            f"  自動適用: {'あり' if report.get('auto_update_apply_enabled') else 'なし'}",
            f"  セキュリティ更新: {'あり' if report.get('security_update') else 'なし'}",
            f"  クリティカル更新: {'あり' if report.get('critical_update') else 'なし'}",
            f"  次: {_interactive_update_command(report.get('next_safe_command'), lang='ja')}",
            f"  Quick install: {_safe(report.get('quick_install_command') or '不明')}",
            f"  Verified install: {_safe(report.get('verified_install_page') or 'https://yonerai.com/install')}",
            f"  基本ローカルmockチャット: {'利用可' if policy.get('basic_local_mock_chat_allowed', True) else '制限'}",
            "  実行しなかったこと:",
        ]
        visible_actions = actions[:4]
        for action in visible_actions:
            lines.append(f"    - {_safe(action)}")
        if not any("forced update" in str(action).lower() for action in visible_actions):
            lines.append("    - no forced update")
        if warnings:
            lines.append("  注意:")
            for warning in warnings[:3]:
                lines.append(f"    - {_safe(warning)}")
        lines.append("")
        return "\n".join(lines)
    if report.get("schema_version") == "yonerai-update-apply/v0.1":
        return "\n".join(
            (
                "Update apply",
                f"  channel: {_display_channel(report.get('channel'), lang='en')}",
                f"  current_version: {_safe(report.get('current_version') or 'unknown')}",
                f"  target_version: {_safe(report.get('latest_manifest_version') or 'unknown')}",
                f"  update_available: {bool(report.get('update_available'))}",
                f"  confirmation_required: {bool(report.get('confirmation_required'))}",
                f"  apply_state: {_safe(report.get('apply_state') or 'not_started')}",
                f"  next_safe_command: {_interactive_update_command(report.get('next_safe_command'), lang='en')}",
                f"  interactive_command: {_interactive_update_command(report.get('next_interactive_command'), lang='en')}",
                f"  message: {_safe(report.get('message_en') or '')}",
                "  no auto-apply / no forced silent update / no PATH mutation / no admin request",
                "",
            )
        )
    return "\n".join(
        (
            "Update check",
            f"  current_version: {_safe(report.get('current_version') or 'unknown')}",
            f"  latest_manifest_version: {_safe(report.get('latest_manifest_version') or 'unknown')}",
            f"  latest_stable: {_safe(report.get('latest_stable') or 'unknown')}",
            f"  channel: {_display_channel(report.get('channel'), lang='en')}",
            f"  update_available: {bool(report.get('update_available'))}",
            f"  version_comparison: {_safe(report.get('version_comparison') or 'unknown')}",
            f"  selected_artifact: {_safe(artifact.get('actual_filename') or artifact.get('selected_artifact') or 'none')}",
            f"  sha256_present: {bool(artifact.get('sha256_present'))}",
            f"  signature: {_safe(signature.get('state') or 'unknown')} verified={bool(signature.get('verified'))}",
            f"  rollback_plan_available: {bool(report.get('rollback_plan_available'))}",
            f"  next_safe_command: {_interactive_update_command(report.get('next_safe_command'), lang='en')}",
            f"  quick_install_command: {_safe(report.get('quick_install_command') or 'unknown')}",
            f"  github_install_fallback_command: {_safe(report.get('github_install_fallback_command') or 'unknown')}",
            f"  verified_install_page: {_safe(report.get('verified_install_page') or 'https://yonerai.com/install')}",
            f"  security_update: {bool(report.get('security_update'))}",
            f"  critical_update: {bool(report.get('critical_update'))}",
            f"  forced_update_enabled: {bool(report.get('forced_update_enabled'))}",
            f"  auto_update_apply_enabled: {bool(report.get('auto_update_apply_enabled'))}",
            f"  active_session_behavior: {_safe(policy.get('active_session_behavior') or 'warn_only_do_not_interrupt')}",
            f"  next_startup_behavior: {_safe(policy.get('next_startup_behavior') or 'show_update_screen_first_only_if_critical')}",
            f"  basic_local_mock_chat_allowed: {bool(policy.get('basic_local_mock_chat_allowed', True))}",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions),
            "",
        )
    )

def _format_update_error(exc: Exception, *, lang: str) -> str:
    message = _safe(str(exc) or exc.__class__.__name__)
    if lang == "ja":
        return f"更新確認に失敗しました: {message}\n"
    return f"Update check failed: {message}\n"

def _format_update_notice(report: dict[str, Any] | None, lang: str, *, phase: str) -> str | None:
    if report is None:
        return None
    policy = report.get("update_policy") if isinstance(report.get("update_policy"), dict) else {}
    if lang == "ja":
        title = "起動時の更新通知" if phase == "startup" else "タスク後の更新通知"
        return "\n".join(
            (
                title,
                f"  current: {_safe(report.get('current_version') or 'unknown')}",
                f"  latest_stable: {_safe(report.get('latest_stable') or report.get('latest_manifest_version') or 'unknown')}",
                f"  update_available: {_value_label(bool(report.get('update_available')), lang='ja')}",
                f"  critical_update: {_value_label(bool(report.get('critical_update')), lang='ja')}",
                f"  behavior: {_safe(policy.get('active_session_behavior') or 'warn_only_do_not_interrupt')}",
                f"  次: {_interactive_update_command(report.get('next_safe_command'), lang='ja')}",
                "  自動適用なし / 強制サイレント更新なし / ローカルmock chatは継続できます",
                "",
            )
        )
    title = "Startup update notice" if phase == "startup" else "Post-task update notice"
    return "\n".join(
        (
            title,
            f"  current: {_safe(report.get('current_version') or 'unknown')}",
            f"  latest_stable: {_safe(report.get('latest_stable') or report.get('latest_manifest_version') or 'unknown')}",
            f"  update_available: {bool(report.get('update_available'))}",
            f"  critical_update: {bool(report.get('critical_update'))}",
            f"  behavior: {_safe(policy.get('active_session_behavior') or 'warn_only_do_not_interrupt')}",
            f"  next: {_interactive_update_command(report.get('next_safe_command'), lang='en')}",
            "  no auto-apply / no forced silent update / local mock chat remains available",
            "",
        )
    )

def _update_unavailable(lang: str) -> str:
    if lang == "ja":
        return "更新確認はこのビルドでは利用できません。`/更新` を試してください。\n"
    return "Update check is unavailable in this build. Try `/update`.\n"
