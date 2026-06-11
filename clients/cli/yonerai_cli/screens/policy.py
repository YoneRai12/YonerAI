from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


def format_policy_status_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    policies = report.get("policies") if isinstance(report.get("policies"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    schema = report.get("policy_schema") if isinstance(report.get("policy_schema"), dict) else {}

    if lang == "ja":
        title = "YonerAI ポリシー状態"
        provider_title = "提供元とモデル"
        permission_title = "権限と安全"
        runtime_title = "実行境界"
        update_memory_title = "更新と記憶"
        schema_title = "ポリシー構造"
        non_action_title = "実行しないこと"
        provider_label = "提供元"
        live_label = "外部live接続"
        key_label = "キー保存/表示"
        model_label = "モデル"
        pricing_label = "有料/共有通信"
        approval_label = "承認"
        file_label = "ファイル"
        tools_label = "ツール"
        shell_label = "任意shell"
        runtime_label = "公開runtime"
        cloud_label = "公式cloud"
        oracle_label = "official Oracle"
        discord_label = "live Discord"
        update_label = "更新"
        auto_update_label = "自動適用"
        memory_label = "記憶"
        sync_label = "local->cloud"
        cloud_escape_label = "cloud escape"
        configurable_label = "設定で変えられる"
        fixed_disabled_label = "固定で無効"
        future_label = "将来候補"
    else:
        title = "YonerAI policy status"
        provider_title = "Provider and model"
        permission_title = "Permission and safety"
        runtime_title = "Runtime boundaries"
        update_memory_title = "Update and memory"
        schema_title = "Policy structure"
        non_action_title = "Non-actions"
        provider_label = "provider"
        live_label = "live external"
        key_label = "key storage/output"
        model_label = "model"
        pricing_label = "paid/shared traffic"
        approval_label = "approval"
        file_label = "file access"
        tools_label = "tools"
        shell_label = "arbitrary shell"
        runtime_label = "public runtime"
        cloud_label = "official cloud"
        oracle_label = "official Oracle"
        discord_label = "live Discord"
        update_label = "update"
        auto_update_label = "auto apply"
        memory_label = "memory"
        sync_label = "local->cloud"
        cloud_escape_label = "cloud escape"
        configurable_label = "configurable"
        fixed_disabled_label = "fixed disabled"
        future_label = "future"

    provider = _policy(policies, "provider")
    model = _policy(policies, "model")
    pricing = _policy(policies, "pricing")
    permission = _policy(policies, "permission")
    runtime = _policy(policies, "runtime")
    update = _policy(policies, "update")
    memory = _policy(policies, "memory_sync")
    cloud_escape = _policy(policies, "cloud_escape")

    provider_rows = (
        CliRow(provider_label, f"{provider.get('preference')} (default={provider.get('default_provider')})", "ok"),
        CliRow(live_label, provider.get("live_external_provider_enabled"), "warn" if provider.get("live_external_provider_enabled") else "ok"),
        CliRow(key_label, "disabled", "ok"),
        CliRow(model_label, f"{model.get('preference')} / configurable={model.get('configurable')}", "ok"),
        CliRow(pricing_label, f"paid_default={pricing.get('paid_provider_calls_default')} shared={pricing.get('shared_traffic_enabled')}", "warn" if pricing.get("shared_traffic_enabled") else "ok"),
    )
    permission_rows = (
        CliRow(approval_label, permission.get("approval_mode"), "ok"),
        CliRow(file_label, permission.get("file_access_mode"), "ok"),
        CliRow(tools_label, permission.get("tools_mode"), "ok"),
        CliRow(shell_label, permission.get("arbitrary_shell_execution"), "fail" if permission.get("arbitrary_shell_execution") else "ok"),
    )
    runtime_rows = (
        CliRow(runtime_label, runtime.get("public_runtime"), "ok"),
        CliRow(cloud_label, runtime.get("official_cloud_runtime_in_public_repo"), "fail" if runtime.get("official_cloud_runtime_in_public_repo") else "ok"),
        CliRow(oracle_label, runtime.get("production_oracle_in_public_repo"), "fail" if runtime.get("production_oracle_in_public_repo") else "ok"),
        CliRow(discord_label, runtime.get("live_discord_enabled"), "fail" if runtime.get("live_discord_enabled") else "ok"),
        CliRow(cloud_escape_label, cloud_escape.get("candidate_scope"), "warn"),
    )
    update_memory_rows = (
        CliRow(update_label, f"{update.get('check_mode')} / {update.get('plan_mode')}", "ok"),
        CliRow(auto_update_label, update.get("auto_apply_enabled"), "fail" if update.get("auto_apply_enabled") else "ok"),
        CliRow(memory_label, f"enabled={memory.get('memory_enabled')} scope={memory.get('default_scope')}", "ok" if memory.get("memory_enabled") else "warn"),
        CliRow(sync_label, "approval_required", "ok"),
    )
    schema_rows = (
        CliRow(configurable_label, _csv(summary.get("configurable")), "ok"),
        CliRow(fixed_disabled_label, _csv(summary.get("fixed_disabled")), "ok"),
        CliRow(future_label, _csv(_future_policy_items(schema)), "warn"),
    )
    non_actions = tuple(CliRow("boundary", value, "ok") for value in report.get("actions_not_performed", ()))

    return render_report(
        title,
        (
            CliSection(provider_title, provider_rows),
            CliSection(permission_title, permission_rows),
            CliSection(runtime_title, runtime_rows),
            CliSection(update_memory_title, update_memory_rows),
            CliSection(schema_title, schema_rows),
            CliSection(non_action_title, non_actions),
        ),
        color=color,
    )


def _policy(policies: dict[str, Any], key: str) -> dict[str, Any]:
    value = policies.get(key)
    return value if isinstance(value, dict) else {}


def _future_policy_items(schema: dict[str, Any]) -> tuple[str, ...]:
    policy_types = schema.get("policy_types") if isinstance(schema.get("policy_types"), dict) else {}
    items: list[str] = []
    for policy_name, definition in policy_types.items():
        if not isinstance(definition, dict):
            continue
        future = definition.get("future")
        if not isinstance(future, list):
            continue
        for value in future:
            items.append(f"{policy_name}.{value}")
    return tuple(items)


def _csv(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) if value else "none"
    if value is None:
        return "none"
    return str(value)
