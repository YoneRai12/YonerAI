from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


def _print_start_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> None:
    from yonerai_cli.first_run import format_first_run_pretty

    print(format_first_run_pretty(report, lang=lang, color=color))


def _print_doctor_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> None:
    print(_format_doctor_pretty(report, lang=lang, color=color))


def _format_doctor_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> str:
    if lang == "ja":
        title = "YonerAI 診断"
        sections = _doctor_sections_ja(report)
    else:
        title = "YonerAI doctor"
        sections = _doctor_sections_en(report)
    if report["errors"]:
        error_title = "エラー" if lang == "ja" else "Errors"
        sections = (*sections, CliSection(error_title, tuple(CliRow("error", error, "fail") for error in report["errors"])))
    return render_report(title, sections, color=color)


def _print_status_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> None:
    print(_format_status_pretty(report, lang=lang, color=color))


def _format_status_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> str:
    manifest = report["manifest"]
    boundaries = report["boundaries"]
    status_api_section = _status_api_section(report)
    if lang == "ja":
        sections = (
            CliSection(
                "公開デモ",
                (
                    CliRow("デモ", "利用可能", "ok"),
                    CliRow("Quickstart", "利用可能", "ok"),
                    CliRow("認証情報", "不要", "ok"),
                ),
            ),
            CliSection(
                "配布準備",
                (
                    CliRow("マニフェスト", "有効" if manifest["contract_valid"] else "無効", "ok" if manifest["contract_valid"] else "fail"),
                    CliRow("インストール準備", "完了" if manifest["install_ready"] else "未完了", "ok" if manifest["install_ready"] else "warn"),
                    CliRow("ネットワークインストーラー", "未実装", "ok"),
                ),
            ),
            CliSection(
                "境界",
                (
                    CliRow("Official Managed Cloud", "外部/契約のみ", "ok"),
                    CliRow("Live Discord", "不要", "ok"),
                    CliRow("永続メモリ", "不要", "ok" if not boundaries["persistent_memory_required"] else "fail"),
                ),
            ),
        )
        if status_api_section is not None:
            sections = (*sections, status_api_section)
        return render_report("YonerAI 状態", sections, color=color)

    sections = (
        CliSection(
            "Public demo",
            (
                CliRow("demo", "available", "ok"),
                CliRow("quickstart", "available", "ok"),
                CliRow("credentials", "not required", "ok"),
            ),
        ),
        CliSection(
            "Distribution readiness",
            (
                CliRow("manifest", "valid" if manifest["contract_valid"] else "invalid", "ok" if manifest["contract_valid"] else "fail"),
                CliRow("install_ready", manifest["install_ready"], "ok" if manifest["install_ready"] else "warn"),
                CliRow("network_installer", "not implemented", "ok"),
            ),
        ),
        CliSection(
            "Boundaries",
            (
                CliRow("official_cloud", "external/contract-only", "ok"),
                CliRow("live_discord", "not required", "ok"),
                CliRow("persistent_memory", "not required", "ok" if not boundaries["persistent_memory_required"] else "fail"),
            ),
        ),
    )
    official_status = report.get("official_status")
    if isinstance(official_status, dict):
        components = official_status.get("components") if isinstance(official_status.get("components"), list) else []
        component_rows = tuple(
            CliRow(
                str(component.get("component")),
                str(component.get("status")),
                "ok" if component.get("network_required") is False else "warn",
                note=component.get("degraded_reason"),
            )
            for component in components
            if isinstance(component, dict)
        )
        sections = (
            *sections,
            CliSection(
                "Official status contract",
                component_rows
                or (
                    CliRow("components", "none", "warn"),
                ),
            ),
        )
    if status_api_section is not None:
        sections = (*sections, status_api_section)
    return render_report("YonerAI status", sections, color=color)


def _status_api_section(report: dict[str, Any]) -> CliSection | None:
    status_api = report.get("status_api")
    if not isinstance(status_api, dict):
        return None
    releases = status_api.get("releases") if isinstance(status_api.get("releases"), dict) else {}
    return CliSection(
        "Status API bridge",
        (
            CliRow("schema_version", status_api.get("schema_version"), "ok"),
            CliRow("status", status_api.get("status"), "warn"),
            CliRow("component_count", status_api.get("component_count"), "ok"),
            CliRow("latest_stable", releases.get("latest_stable"), "ok"),
            CliRow("latest_alpha", releases.get("latest_alpha"), "ok"),
            CliRow(
                "production_backend_included",
                status_api.get("production_backend_included"),
                "fail" if status_api.get("production_backend_included") else "ok",
            ),
            CliRow(
                "private_runtime_details_included",
                status_api.get("private_runtime_details_included"),
                "fail" if status_api.get("private_runtime_details_included") else "ok",
            ),
        ),
    )


def _doctor_sections_en(report: dict[str, Any]) -> tuple[CliSection, ...]:
    python_report = report["python"]
    cli_report = report["cli"]
    manifest_report = report["manifest"]
    boundaries = report["boundaries"]
    redaction_check = report["system_checks"]["redaction_self_check"]
    mcp_check = report["system_checks"]["mcp_deny_policy"]
    provider_rows = _provider_setup_rows(report, lang="en")
    provider_e2e_rows = _provider_runtime_e2e_rows(report, lang="en")
    hybrid_wire_rows = _hybrid_wire_contract_rows(report, lang="en")
    node_relay_rows = _hybrid_node_relay_contract_rows(report, lang="en")
    relay_rows = _relay_status_rows(report, lang="en")
    oracle_rows = _oracle_stub_rows(report)
    auto_runtime_rows = _auto_runtime_rows(report)
    install_update_rows = _install_update_rows(report, lang="en")
    return (
        CliSection(
            "Setup",
            (
                CliRow("overall", "ready for public demo" if report["ok"] else "needs attention", "ok" if report["ok"] else "fail"),
                CliRow("python", python_report["version"], "ok" if python_report["supported"] else "fail"),
                CliRow("cli_import", cli_report["import_ok"], "ok" if cli_report["import_ok"] else "fail"),
                CliRow("package_version", cli_report["package_version"], "ok"),
                CliRow("repo_version", cli_report["repo_version"] or "unknown", "ok" if cli_report["repo_version"] else "warn"),
                CliRow("demo", "available" if cli_report["demo_command_available"] else "missing", "ok" if cli_report["demo_command_available"] else "fail"),
                CliRow(
                    "quickstart",
                    "available" if cli_report["quickstart_alias_available"] else "missing",
                    "ok" if cli_report["quickstart_alias_available"] else "fail",
                ),
            ),
        ),
        CliSection(
            "Manifest",
            (
                CliRow("manifest_example_valid", manifest_report["contract_valid"], "ok" if manifest_report["contract_valid"] else "fail"),
                CliRow("manifest_install_ready", manifest_report["install_ready"], "ok" if manifest_report["install_ready"] else "warn"),
                CliRow("signature_state", manifest_report["signature_state"], "ok" if manifest_report["signature_state"] == "signed" else "warn"),
                CliRow("non_production_reason", manifest_report["non_production_reason"] or "none", "warn" if manifest_report["non_production_reason"] else "ok"),
            ),
        ),
        CliSection(
            "Diagnostics",
            (
                CliRow("redaction_self_check", redaction_check["status"], "ok" if redaction_check["ok"] else "fail"),
                CliRow("mcp_deny_policy", mcp_check["status"], "ok" if mcp_check["ok"] else "fail"),
            ),
        ),
        CliSection("Hybrid Wire Contract", hybrid_wire_rows),
        CliSection("Hybrid Node/Relay", node_relay_rows),
        CliSection("Relay local-dev", relay_rows),
        CliSection("Oracle stub", oracle_rows),
        CliSection("Auto runtime", auto_runtime_rows),
        CliSection("Provider runtime", provider_rows),
        CliSection("Provider runtime E2E fixtures", provider_e2e_rows),
        CliSection("Install/update", install_update_rows),
        CliSection(
            "Boundaries",
            (
                CliRow("network_required", boundaries["network_required"], "fail" if boundaries["network_required"] else "ok"),
                CliRow("credentials_required_for_demo", report["credentials"]["required_for_demo"], "fail" if report["credentials"]["required_for_demo"] else "ok"),
                CliRow("official_cloud_runtime", "external/contract-only", "ok"),
                CliRow("live_discord", "not required", "ok" if not boundaries["live_discord_required"] else "fail"),
                CliRow("network_installer", "not implemented", "ok"),
                CliRow("production_features", "not included", "ok"),
                CliRow("install_mutation", boundaries["install_mutation"], "fail" if boundaries["install_mutation"] else "ok"),
                CliRow("path_mutation", boundaries["path_mutation"], "fail" if boundaries["path_mutation"] else "ok"),
            ),
        ),
    )


def _doctor_sections_ja(report: dict[str, Any]) -> tuple[CliSection, ...]:
    python_report = report["python"]
    cli_report = report["cli"]
    manifest_report = report["manifest"]
    boundaries = report["boundaries"]
    redaction_check = report["system_checks"]["redaction_self_check"]
    mcp_check = report["system_checks"]["mcp_deny_policy"]
    provider_rows = _provider_setup_rows(report, lang="ja")
    provider_e2e_rows = _provider_runtime_e2e_rows(report, lang="ja")
    hybrid_wire_rows = _hybrid_wire_contract_rows(report, lang="ja")
    node_relay_rows = _hybrid_node_relay_contract_rows(report, lang="ja")
    relay_rows = _relay_status_rows(report, lang="ja")
    oracle_rows = _oracle_stub_rows(report)
    auto_runtime_rows = _auto_runtime_rows(report)
    install_update_rows = _install_update_rows(report, lang="ja")
    return (
        CliSection(
            "セットアップ",
            (
                CliRow("全体", "公開デモ実行可能" if report["ok"] else "確認が必要", "ok" if report["ok"] else "fail"),
                CliRow("Python", python_report["version"], "ok" if python_report["supported"] else "fail"),
                CliRow("CLI import", "成功" if cli_report["import_ok"] else "失敗", "ok" if cli_report["import_ok"] else "fail"),
                CliRow("CLI package", cli_report["package_version"], "ok"),
                CliRow("Repo version", cli_report["repo_version"] or "unknown", "ok" if cli_report["repo_version"] else "warn"),
                CliRow("デモ", "利用可能" if cli_report["demo_command_available"] else "未検出", "ok" if cli_report["demo_command_available"] else "fail"),
                CliRow(
                    "Quickstart",
                    "利用可能" if cli_report["quickstart_alias_available"] else "未検出",
                    "ok" if cli_report["quickstart_alias_available"] else "fail",
                ),
            ),
        ),
        CliSection(
            "マニフェスト",
            (
                CliRow("マニフェスト", "有効" if manifest_report["contract_valid"] else "無効", "ok" if manifest_report["contract_valid"] else "fail"),
                CliRow("インストール準備", "完了" if manifest_report["install_ready"] else "未完了", "ok" if manifest_report["install_ready"] else "warn"),
                CliRow("署名状態", manifest_report["signature_state"], "ok" if manifest_report["signature_state"] == "signed" else "warn"),
                CliRow("非本番理由", manifest_report["non_production_reason"] or "なし", "warn" if manifest_report["non_production_reason"] else "ok"),
            ),
        ),
        CliSection(
            "診断",
            (
                CliRow("Redaction self-check", "成功" if redaction_check["ok"] else "失敗", "ok" if redaction_check["ok"] else "fail"),
                CliRow("MCP deny policy", "成功" if mcp_check["ok"] else "失敗", "ok" if mcp_check["ok"] else "fail"),
            ),
        ),
        CliSection("Hybrid Wire Contract", hybrid_wire_rows),
        CliSection("Hybrid Node/Relay", node_relay_rows),
        CliSection("Relay local-dev", relay_rows),
        CliSection("Oracle stub", oracle_rows),
        CliSection("Auto runtime", auto_runtime_rows),
        CliSection("プロバイダー実行環境", provider_rows),
        CliSection("プロバイダー実行環境 E2E フィクスチャ", provider_e2e_rows),
        CliSection("インストール/更新", install_update_rows),
        CliSection(
            "境界",
            (
                CliRow("ネットワーク", "不要" if not boundaries["network_required"] else "必要", "ok" if not boundaries["network_required"] else "fail"),
                CliRow("認証情報", "不要" if not report["credentials"]["required_for_demo"] else "必要", "ok" if not report["credentials"]["required_for_demo"] else "fail"),
                CliRow("Official Managed Cloud", "外部/契約のみ", "ok"),
                CliRow("Live Discord", "不要" if not boundaries["live_discord_required"] else "必要", "ok" if not boundaries["live_discord_required"] else "fail"),
                CliRow("ネットワークインストーラー", "未実装", "ok"),
                CliRow("本番機能", "含まれません", "ok"),
                CliRow("インストール変更", "なし" if not boundaries["install_mutation"] else "あり", "ok" if not boundaries["install_mutation"] else "fail"),
                CliRow("PATH変更", "なし" if not boundaries["path_mutation"] else "あり", "ok" if not boundaries["path_mutation"] else "fail"),
            ),
        ),
    )


def _install_update_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    install_update = report.get("install_update")
    if not isinstance(install_update, dict):
        unavailable = "利用不可" if lang == "ja" else "unavailable"
        return (CliRow("status", unavailable, "warn"),)
    if lang == "ja":
        return (
            CliRow("最新stable", install_update.get("latest_stable", "unknown"), "ok"),
            CliRow("Quick install", install_update.get("quick_install_command", "unavailable"), "ok"),
            CliRow("Verified install", install_update.get("verified_install_page", "unavailable"), "ok"),
            CliRow(
                "強制更新",
                "なし" if not install_update.get("forced_update_enabled") else "あり",
                "ok" if not install_update.get("forced_update_enabled") else "fail",
            ),
            CliRow(
                "自動適用",
                "なし" if not install_update.get("auto_update_apply_enabled") else "あり",
                "ok" if not install_update.get("auto_update_apply_enabled") else "fail",
            ),
            CliRow("本番インストーラー", "未完了", "warn"),
        )
    return (
        CliRow("latest_stable", install_update.get("latest_stable", "unknown"), "ok"),
        CliRow("quick_install", install_update.get("quick_install_command", "unavailable"), "ok"),
        CliRow("verified_install", install_update.get("verified_install_page", "unavailable"), "ok"),
        CliRow(
            "forced_update_enabled",
            bool(install_update.get("forced_update_enabled")),
            "fail" if install_update.get("forced_update_enabled") else "ok",
        ),
        CliRow(
            "auto_update_apply_enabled",
            bool(install_update.get("auto_update_apply_enabled")),
            "fail" if install_update.get("auto_update_apply_enabled") else "ok",
        ),
        CliRow("production_installer", "not ready", "warn"),
    )


def _oracle_stub_rows(report: dict[str, Any]) -> tuple[CliRow, ...]:
    oracle = report.get("oracle_stub")
    if not isinstance(oracle, dict):
        return (CliRow("status", "unavailable", "warn"),)
    return (
        CliRow("status", oracle.get("status", "unknown"), "ok" if oracle.get("ok") else "fail"),
        CliRow("schema", oracle.get("schema_version", "unknown"), "ok"),
        CliRow("queue_available", oracle.get("queue_available", False), "ok" if oracle.get("queue_available") else "warn"),
        CliRow(
            "deterministic_fixture",
            oracle.get("deterministic_fixture_result", False),
            "ok" if oracle.get("deterministic_fixture_result") else "warn",
        ),
        CliRow(
            "network_required",
            oracle.get("network_required", False),
            "fail" if oracle.get("network_required") else "ok",
        ),
        CliRow(
            "production_oracle_used",
            oracle.get("production_oracle_used", False),
            "fail" if oracle.get("production_oracle_used") else "ok",
        ),
        CliRow(
            "official_cloud_runtime",
            oracle.get("official_cloud_runtime_implemented", False),
            "fail" if oracle.get("official_cloud_runtime_implemented") else "ok",
        ),
    )


def _auto_runtime_rows(report: dict[str, Any]) -> tuple[CliRow, ...]:
    auto_runtime = report.get("auto_runtime")
    if not isinstance(auto_runtime, dict):
        return (CliRow("status", "unavailable", "warn"),)
    routes = auto_runtime.get("routes")
    route_count = len(routes) if isinstance(routes, list) else 0
    return (
        CliRow("status", auto_runtime.get("status", "unknown"), "ok" if auto_runtime.get("ok") else "fail"),
        CliRow("schema", auto_runtime.get("schema_version", "unknown"), "ok"),
        CliRow("command", auto_runtime.get("command", "yonerai ask --auto --json"), "ok"),
        CliRow("routes", route_count, "ok" if route_count >= 5 else "warn"),
        CliRow("mock_provider_default", auto_runtime.get("mock_provider_default"), "ok"),
        CliRow("local_llm_loopback_only", auto_runtime.get("local_llm_loopback_only"), "ok"),
        CliRow(
            "live_external_provider_default",
            auto_runtime.get("live_external_provider_default"),
            "fail" if auto_runtime.get("live_external_provider_default") else "ok",
        ),
        CliRow(
            "reviewer_plan",
            auto_runtime.get("reviewer_plan_supported"),
            "ok" if auto_runtime.get("reviewer_plan_supported") else "warn",
        ),
    )


def _hybrid_wire_contract_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    hybrid = report.get("hybrid_wire_contract")
    if not isinstance(hybrid, dict):
        unavailable = "利用不可" if lang == "ja" else "unavailable"
        return (CliRow("status", unavailable, "warn"),)
    trust_states = hybrid.get("trust_states")
    trust_state_count = len(trust_states) if isinstance(trust_states, list) else 0
    required_count = _hybrid_required_trust_state_count(hybrid)
    posture_states = hybrid.get("node_posture_states")
    posture_state_count = len(posture_states) if isinstance(posture_states, list) else 0
    required_posture_count = _hybrid_required_node_posture_state_count(hybrid)
    capabilities = hybrid.get("capabilities")
    capability_count = len(capabilities) if isinstance(capabilities, list) else 0
    extension_boundary = hybrid.get("extension_boundary")
    extension_boundary_count = len(extension_boundary) if isinstance(extension_boundary, list) else 0
    orchestration_stub = hybrid.get("official_orchestration_stub")
    orchestration_response = {}
    if isinstance(orchestration_stub, dict):
        response_value = orchestration_stub.get("response")
        if isinstance(response_value, dict):
            orchestration_response = response_value
    route_alignment = hybrid.get("route_orchestration_alignment")
    if not isinstance(route_alignment, dict):
        route_alignment = {}
    status_ok = "正常" if lang == "ja" else "ok"
    status_fail = "失敗" if lang == "ja" else "fail"
    route_alignment_status = route_alignment.get("status")
    route_alignment_value = status_ok if route_alignment_status == "ok" else status_fail
    route_alignment_level = "ok" if route_alignment_status == "ok" else "fail"
    not_implemented = "未実装" if lang == "ja" else "not implemented"
    implemented = "実装済み" if lang == "ja" else "implemented"
    return (
        CliRow("status", status_ok if hybrid.get("ok") else status_fail, "ok" if hybrid.get("ok") else "fail"),
        CliRow("schema", hybrid.get("schema_version", "unknown"), "ok"),
        CliRow("test_fixture_only", hybrid.get("test_fixture_only"), "ok" if hybrid.get("test_fixture_only") else "warn"),
        CliRow("capabilities", capability_count, "ok" if capability_count else "warn"),
        CliRow("trust_states", trust_state_count, "ok" if trust_state_count >= required_count else "warn"),
        CliRow("extension_boundary", extension_boundary_count, "ok" if extension_boundary_count else "warn"),
        CliRow(
            "node_posture_states",
            posture_state_count,
            "ok" if posture_state_count >= required_posture_count else "warn",
        ),
        CliRow(
            "route_preview_fixture",
            hybrid.get("route_preview_fixture_supported"),
            "ok" if hybrid.get("route_preview_fixture_supported") else "warn",
        ),
        CliRow(
            "orchestration_response",
            orchestration_response.get("schema_name", "missing"),
            "ok" if orchestration_response.get("schema_name") == "OfficialOrchestrationStubResponse" else "warn",
        ),
        CliRow(
            "cloud_contract_candidate",
            orchestration_response.get("route_strategy", "missing"),
            "ok" if orchestration_response.get("route_strategy") == "cloud_contract_candidate" else "warn",
        ),
        CliRow(
            "route_orchestration_alignment",
            route_alignment_value,
            route_alignment_level,
        ),
        CliRow("network_required", hybrid.get("network_required"), "fail" if hybrid.get("network_required") else "ok"),
        CliRow(
            "official_cloud_runtime",
            not_implemented if not hybrid.get("official_cloud_runtime_implemented") else implemented,
            "ok" if not hybrid.get("official_cloud_runtime_implemented") else "fail",
        ),
    )


def _hybrid_required_trust_state_count(hybrid: dict[str, Any]) -> int:
    required_count = hybrid.get("required_trust_state_count")
    if isinstance(required_count, int) and required_count > 0:
        return required_count
    required_states = hybrid.get("required_trust_states")
    if isinstance(required_states, list) and required_states:
        return len(required_states)
    trust_states = hybrid.get("trust_states")
    return len(trust_states) if isinstance(trust_states, list) else 1


def _hybrid_required_node_posture_state_count(hybrid: dict[str, Any]) -> int:
    required_count = hybrid.get("required_node_posture_state_count")
    if isinstance(required_count, int) and required_count > 0:
        return required_count
    required_states = hybrid.get("required_node_posture_states")
    if isinstance(required_states, list) and required_states:
        return len(required_states)
    posture_states = hybrid.get("node_posture_states")
    return len(posture_states) if isinstance(posture_states, list) else 1


def _hybrid_node_relay_contract_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    contract = report.get("hybrid_node_relay_contract")
    if not isinstance(contract, dict):
        unavailable = "利用不可" if lang == "ja" else "unavailable"
        return (CliRow("status", unavailable, "warn"),)
    is_ok = bool(contract.get("ok"))
    status_ok = "正常" if lang == "ja" else "ok"
    needs_attention = "確認が必要" if lang == "ja" else "needs attention"
    not_implemented = "未実装" if lang == "ja" else "not implemented"
    implemented = "実装済み" if lang == "ja" else "implemented"
    schema_version = contract.get("schema_version", "unknown")
    schema_status = "fail" if schema_version == "unknown" else "ok"
    scope = contract.get("public_repo_scope", "unknown")
    scope_status = "fail" if scope == "unknown" else "ok"
    return (
        CliRow("status", status_ok if is_ok else needs_attention, "ok" if is_ok else "fail"),
        CliRow("schema", schema_version, schema_status),
        CliRow("scope", scope, scope_status),
        CliRow(
            "official_cloud_runtime",
            not_implemented if not contract.get("official_cloud_runtime_implemented") else implemented,
            "ok" if not contract.get("official_cloud_runtime_implemented") else "fail",
        ),
        CliRow("production_oracle", contract.get("production_oracle_used"), "fail" if contract.get("production_oracle_used") else "ok"),
        CliRow("network_required", contract.get("network_required"), "fail" if contract.get("network_required") else "ok"),
    )


def _relay_status_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    relay_status = report.get("relay_status")
    if not isinstance(relay_status, dict):
        unavailable = "利用不可" if lang == "ja" else "unavailable"
        return (CliRow("status", unavailable, "warn"),)
    relay = relay_status.get("relay")
    relay = relay if isinstance(relay, dict) else {}
    is_ok = bool(relay_status.get("ok"))
    status_ok = "正常" if lang == "ja" else "ok"
    needs_attention = "確認が必要" if lang == "ja" else "needs attention"
    schema_version = relay_status.get("schema_version", "unknown")
    mode = relay_status.get("mode", "unknown")
    return (
        CliRow("status", status_ok if is_ok else needs_attention, "ok" if is_ok else "fail"),
        CliRow("schema", schema_version, "fail" if schema_version == "unknown" else "ok"),
        CliRow("mode", mode, "fail" if mode == "unknown" else "ok"),
        CliRow("loopback_only", relay.get("loopback_only"), "ok" if relay.get("loopback_only") else "fail"),
        CliRow("process_started", relay.get("process_started"), "fail" if relay.get("process_started") else "ok"),
        CliRow("public_exposure_allowed", relay.get("public_exposure_allowed"), "fail" if relay.get("public_exposure_allowed") else "ok"),
        CliRow("message_body_persisted", relay.get("message_body_persisted"), "fail" if relay.get("message_body_persisted") else "ok"),
    )


def _provider_setup_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    provider_setup = report.get("providers") if isinstance(report.get("providers"), dict) else {}
    providers = provider_setup.get("providers") if isinstance(provider_setup, dict) else []
    rows: list[CliRow] = []
    for provider in providers if isinstance(providers, list) else []:
        if not isinstance(provider, dict):
            continue
        provider_id = str(provider.get("provider_id") or "unknown")
        blockers = provider.get("setup_blockers")
        blocker_text = ", ".join(str(blocker) for blocker in blockers) if isinstance(blockers, list) else ""
        value = str(provider.get("setup_status") or "unknown")
        if blocker_text:
            value = f"{value}; {blocker_text}"
        rows.append(CliRow(provider_id, value, _provider_setup_level(str(provider.get("setup_status") or "unknown"))))
    fallback_name = "プロバイダー" if lang == "ja" else "providers"
    fallback_value = "利用不可" if lang == "ja" else "unavailable"
    return tuple(rows) or (CliRow(fallback_name, fallback_value, "warn"),)


def _provider_runtime_e2e_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    fixtures = report.get("provider_runtime_e2e_fixtures")
    if not isinstance(fixtures, dict):
        fixtures = {}
    status_value = fixtures.get("status", "unknown")
    openai_value = fixtures.get("openai_compatible", "unknown")
    local_llm_value = fixtures.get("local_llm", "unknown")
    ledger_value = fixtures.get("run_ledger", "unknown")
    external_network_value = fixtures.get("external_network_call_performed", "unknown")
    return (
        CliRow("status" if lang == "en" else "状態", status_value, _fixture_value_status(status_value, expected="covered_by_local_tests")),
        CliRow("openai_compatible", openai_value, _fixture_value_status(openai_value)),
        CliRow("local_llm", local_llm_value, _fixture_value_status(local_llm_value)),
        CliRow("run_ledger", ledger_value, _fixture_value_status(ledger_value)),
        CliRow(
            "external_network_call_performed" if lang == "en" else "外部ネットワーク通信",
            external_network_value,
            "ok" if external_network_value is False else "fail",
        ),
    )


def _fixture_value_status(value: object, *, expected: object | None = None) -> str:
    if expected is not None:
        if value == expected:
            return "ok"
        return "fail" if value == "unknown" else "warn"
    return "fail" if value == "unknown" else "ok"


def _provider_setup_level(setup_status: str) -> str:
    if setup_status in {"ready", "live_ready"}:
        return "ok"
    if setup_status in {"disabled", "live_opt_in_required", "missing_configuration"}:
        return "warn"
    return "fail"


def _bool_text(value: object) -> str:
    return "true" if value is True else "false" if value is False else str(value)


def _nested_dict(value: object, key: str) -> object:
    if not isinstance(value, dict):
        return None
    return value.get(key)
