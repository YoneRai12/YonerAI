from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.screens.labels import _safe, _yes_no


def format_memory_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> str:
    if report.get("operation") == "status":
        if lang == "ja":
            rows = (
                CliRow("記憶件数", report.get("record_count", 0), "ok"),
                CliRow("クラウド同期", "オフ", "ok"),
                CliRow("local-to-cloud既定", "無効", "ok"),
                CliRow("raw prompt保存", report.get("raw_prompt_persisted"), "fail" if report.get("raw_prompt_persisted") else "ok"),
                CliRow("ローカルpath出力", report.get("store_path_output"), "fail" if report.get("store_path_output") else "ok"),
            )
            return render_report("YonerAI 記憶境界", (CliSection("状態", rows),), color=color)
        rows = (
            CliRow("records", report.get("record_count", 0), "ok"),
            CliRow("cloud_sync_enabled", report.get("cloud_sync_enabled"), "warn" if report.get("cloud_sync_enabled") else "ok"),
            CliRow(
                "local_to_cloud_default",
                report.get("local_to_cloud_enabled_by_default"),
                "fail" if report.get("local_to_cloud_enabled_by_default") else "ok",
            ),
            CliRow("raw_prompt_persisted", report.get("raw_prompt_persisted"), "fail" if report.get("raw_prompt_persisted") else "ok"),
            CliRow("store_path_output", report.get("store_path_output"), "fail" if report.get("store_path_output") else "ok"),
        )
        return render_report("YonerAI memory boundary", (CliSection("Status", rows),), color=color)
    if report.get("operation") == "sync_preview":
        decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
        title = "YonerAI 記憶同期プレビュー" if lang == "ja" else "YonerAI memory sync preview"
        section_title = "判定" if lang == "ja" else "Decision"
        rows = (
            CliRow("direction", report.get("direction"), "ok"),
            CliRow(
                "decision",
                decision.get("state", "unknown"),
                "warn" if decision.get("state") == "approval_required" else ("fail" if decision.get("state") == "blocked" else "ok"),
            ),
            CliRow("reason", decision.get("reason", "none"), "ok"),
            CliRow("sync_allowed", report.get("sync_allowed"), "warn" if not report.get("sync_allowed") else "ok"),
            CliRow("sync_performed", report.get("sync_performed"), "fail" if report.get("sync_performed") else "ok"),
        )
        return render_report(title, (CliSection(section_title, rows),), color=color)
    if report.get("operation") == "list":
        rows = tuple(CliRow(record["memory_id"], record.get("redacted_summary", "[redacted]"), "ok") for record in report["records"]) or (
            CliRow("records", "none", "warn"),
        )
        title = "YonerAI ローカル記憶" if lang == "ja" else "YonerAI local memory"
        section = "記憶" if lang == "ja" else "Records"
        return render_report(title, (CliSection(section, rows),), color=color)
    rows = (
        CliRow("operation", report.get("operation", "unknown"), "ok" if report.get("ok") else "fail"),
        CliRow("ok", report.get("ok"), "ok" if report.get("ok") else "fail"),
        CliRow("cloud_synced", report.get("cloud_synced", False), "fail" if report.get("cloud_synced") else "ok"),
    )
    title = "YonerAI ローカル記憶" if lang == "ja" else "YonerAI local memory"
    section = "ローカルのみ" if lang == "ja" else "Local-only"
    return render_report(title, (CliSection(section, rows),), color=color)


def _format_memory_status(report: dict[str, Any], *, lang: str) -> str:
    counts = report.get("counts_by_scope") if isinstance(report.get("counts_by_scope"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    if lang == "ja":
        lines = [
            "記憶",
            f"  ローカル記憶: {'利用可能' if report.get('ok') else '利用不可'}",
            f"  active件数: {_safe(report.get('record_count') or 0)}",
            f"  local -> cloud自動同期: {'オン' if report.get('local_to_cloud_enabled_by_default') else 'オフ'}",
            f"  cloud同期: {'オン' if report.get('cloud_sync_enabled') else 'オフ'}",
            f"  raw prompt保存: {'オン' if report.get('raw_prompt_persisted') else 'オフ'}",
            f"  local path出力: {'オン' if report.get('local_absolute_path_persisted') else 'オフ'}",
            "  scope別:",
        ]
        for key in ("session", "local_private", "shared_preference", "project", "procedural", "cloud_account"):
            lines.append(f"    - {key}: {_safe(counts.get(key, 0))}")
        lines.extend(
            [
                "  試す: yonerai memory add \"note\" --scope local --pretty",
                "  同期preview: yonerai memory sync preview --direction local-to-cloud --pretty",
                "  実行しないこと:",
            ]
        )
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Memory",
            f"  available: {bool(report.get('ok'))}",
            f"  active_records: {_safe(report.get('record_count') or 0)}",
            f"  local_to_cloud_enabled_by_default: {bool(report.get('local_to_cloud_enabled_by_default'))}",
            f"  cloud_sync_enabled: {bool(report.get('cloud_sync_enabled'))}",
            f"  raw_prompt_persisted: {bool(report.get('raw_prompt_persisted'))}",
            f"  local_absolute_path_persisted: {bool(report.get('local_absolute_path_persisted'))}",
            "  try: yonerai memory add \"note\" --scope local --pretty",
            "  sync preview: yonerai memory sync preview --direction local-to-cloud --pretty",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "",
        )
    )

def _format_sync_status(report: dict[str, Any], *, lang: str) -> str:
    cloud_link = report.get("cloud_link") if isinstance(report.get("cloud_link"), dict) else {}
    directions = report.get("directions") if isinstance(report.get("directions"), dict) else {}
    cloud_to_local = directions.get("cloud_to_local") if isinstance(directions.get("cloud_to_local"), dict) else {}
    local_to_cloud = directions.get("local_to_cloud") if isinstance(directions.get("local_to_cloud"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    if lang == "ja":
        lines = [
            "同期",
            f"  認証状態: {_safe(report.get('auth_state') or cloud_link.get('auth_state') or 'dry_run')}",
            "  cloud -> local: ログイン済み + 選択したcloud会話だけ同期downできます",
            f"    現在有効: {_yes_no(cloud_to_local.get('enabled_now'), lang='ja')}",
            "  local -> cloud: 初期値では無効。明示承認とaudit理由が必要です",
            f"    初期値有効: {_yes_no(local_to_cloud.get('enabled_by_default'), lang='ja')}",
            f"    明示承認必須: {_yes_no(local_to_cloud.get('requires_explicit_approval'), lang='ja')}",
            "  除外: private file / local memory / local node payload / provider keys",
            f"  共有トラフィック: {'オン' if report.get('shared_traffic_enabled') else 'オフ'}",
            "  public repo: contract/fixtureのみ。本番Official Cloud/Oracleには接続しません",
            "  試す: yonerai sync preview --direction cloud-to-local --json",
            "  実行しないこと:",
        ]
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Sync",
            f"  auth_state: {_safe(report.get('auth_state') or cloud_link.get('auth_state') or 'dry_run')}",
            f"  cloud_to_local_enabled: {bool(cloud_to_local.get('enabled_now'))}",
            f"  local_to_cloud_enabled_by_default: {bool(local_to_cloud.get('enabled_by_default'))}",
            f"  local_to_cloud_requires_approval: {bool(local_to_cloud.get('requires_explicit_approval'))}",
            "  excluded: private file, local memory, local node payload, provider keys",
            f"  shared_traffic_enabled: {bool(report.get('shared_traffic_enabled'))}",
            "  public_repo: contract/fixture only; no production Official Cloud or Oracle call",
            "  try: yonerai sync preview --direction cloud-to-local --json",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "",
        )
    )

def _format_sync_unavailable(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "同期状態はこのビルドでは契約表示のみです。",
                "  cloud -> local: 本番cloud同期は未実装です",
                "  local -> cloud: 初期値では無効。自動uploadはしません",
                "  private/local memory/file/local node payload/provider keysは送信しません",
                "",
            )
        )
    return "\n".join(
        (
            "Sync status is contract display only in this build.",
            "  cloud -> local: production cloud sync is not implemented",
            "  local -> cloud: disabled by default; no automatic upload",
            "  private/local memory/file/local node payload/provider keys are not sent",
            "",
        )
    )

def _format_memory_unavailable(lang: str) -> str:
    if lang == "ja":
        return "記憶状態はこのビルドでは利用できません。\n"
    return "Memory status is unavailable in this build.\n"

def _memory_action_help(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "記憶操作",
                "  /記憶 add <内容>",
                "  /記憶 list",
                "  /記憶 forget <memory_id>",
                "  /記憶 sync preview cloud-to-local",
                "  /記憶 sync preview local-to-cloud",
                "",
            )
        )
    return "Memory actions: /memory add <text>, /memory list, /memory forget <memory_id>, /memory sync preview local-to-cloud\n"

def _memory_cloud_preview_disabled(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "cloud -> local memory preview: オフ",
                "  設定で無効です。同期previewは実行しません。",
                "  変更: /設定 記憶 cloud-preview オン",
                "",
            )
        )
    return "\n".join(
        (
            "cloud-to-local memory preview is off",
            "  The preview callback was not executed.",
            "  Change: /settings memory cloud-preview on",
            "",
        )
    )

def _memory_write_disabled(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "記憶: オフ",
                "  記憶が無効なため、新しい記憶は保存しません。",
                "  変更: /設定 記憶 オン",
                "",
            )
        )
    return "\n".join(
        (
            "Memory is off",
            "  New memory records are not saved while memory is disabled.",
            "  Change: /settings memory on",
            "",
        )
    )

def _format_memory_action_report(report: dict[str, Any], *, lang: str) -> str:
    operation = str(report.get("operation") or "unknown")
    if operation == "add":
        record = report.get("record") if isinstance(report.get("record"), dict) else {}
        if lang == "ja":
            return "\n".join(
                (
                    "記憶を追加しました",
                    f"  memory_id: {_safe(record.get('memory_id') or 'none')}",
                    f"  scope: {_safe(record.get('scope') or 'unknown')}",
                    f"  sync_policy: {_safe(record.get('sync_policy') or 'unknown')}",
                    f"  summary: {_safe(record.get('redacted_summary') or '')}",
                    "  cloud同期: なし",
                    "  raw prompt保存: なし",
                    "",
                )
            )
        return "\n".join(
            (
                "Memory added",
                f"  memory_id: {_safe(record.get('memory_id') or 'none')}",
                f"  scope: {_safe(record.get('scope') or 'unknown')}",
                f"  sync_policy: {_safe(record.get('sync_policy') or 'unknown')}",
                f"  summary: {_safe(record.get('redacted_summary') or '')}",
                "  cloud_sync: false",
                "  raw_prompt_persisted: false",
                "",
            )
        )
    if operation == "list":
        records = report.get("records") if isinstance(report.get("records"), list) else []
        lines = ["記憶一覧" if lang == "ja" else "Memory list", f"  count: {_safe(report.get('count') or 0)}"]
        if not records:
            lines.append("  記憶はまだありません" if lang == "ja" else "  no memory records")
        for record in records[:10]:
            if isinstance(record, dict):
                lines.append(f"  - {_safe(record.get('memory_id') or 'mem_unknown')}: {_safe(record.get('redacted_summary') or '')}")
        lines.append("")
        return "\n".join(lines)
    if operation == "forget":
        if lang == "ja":
            return "\n".join(
                (
                    "記憶を忘却しました" if report.get("forgotten") else "記憶が見つかりませんでした",
                    f"  memory_id: {_safe(report.get('memory_id') or 'none')}",
                    "  cloud同期: なし",
                    "",
                )
            )
        return "\n".join(
            (
                "Memory forgotten" if report.get("forgotten") else "Memory not found",
                f"  memory_id: {_safe(report.get('memory_id') or 'none')}",
                "  cloud_sync: false",
                "",
            )
        )
    if operation == "sync_preview":
        decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
        actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
        if lang == "ja":
            lines = [
                "記憶同期プレビュー",
                f"  direction: {_safe(report.get('direction') or 'unknown')}",
                f"  decision: {_safe(decision.get('state') or 'unknown')}",
                f"  reason: {_safe(decision.get('reason') or 'none')}",
                f"  explicit approval required: {_yes_no(decision.get('requires_explicit_approval'), lang='ja')}",
                "  local private memory: cloudへ自動同期しません",
                "  sync_performed: なし",
                "  実行しないこと:",
            ]
            for action in actions[:8]:
                lines.append(f"    - {_safe(action)}")
            lines.append("")
            return "\n".join(lines)
        return "\n".join(
            (
                "Memory sync preview",
                f"  direction: {_safe(report.get('direction') or 'unknown')}",
                f"  decision: {_safe(decision.get('state') or 'unknown')}",
                f"  reason: {_safe(decision.get('reason') or 'none')}",
                f"  requires_explicit_approval: {bool(decision.get('requires_explicit_approval'))}",
                "  local_private_memory: never uploads automatically",
                "  sync_performed: false",
                "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
                "",
            )
        )
    return _memory_action_help(lang)
