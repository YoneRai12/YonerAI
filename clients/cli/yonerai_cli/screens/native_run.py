from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


def format_native_run_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    title = "YonerAI Native Run (alpha/staging)" if lang != "ja" else "YonerAI Native Run（α/staging）"
    sections = [_status_section(report, lang=lang)]
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    if run:
        sections.append(_run_section(run, lang=lang))
    provider_sharing = report.get("provider_sharing") if isinstance(report.get("provider_sharing"), dict) else {}
    if provider_sharing:
        sections.append(_provider_sharing_section(provider_sharing, lang=lang))
    context_preview = report.get("context_preview") if isinstance(report.get("context_preview"), dict) else {}
    if context_preview:
        sections.append(_context_preview_section(context_preview, lang=lang))
    result = report.get("result") if isinstance(report.get("result"), dict) else {}
    if result:
        sections.append(_result_section(result, lang=lang))
    events = report.get("events") if isinstance(report.get("events"), list) else []
    if events:
        sections.append(_events_section(events, lang=lang))
    worker = report.get("worker") if isinstance(report.get("worker"), dict) else {}
    if worker:
        sections.append(_worker_section(worker, lang=lang))
    capabilities = report.get("capabilities") if isinstance(report.get("capabilities"), list) else []
    if capabilities:
        sections.append(_capabilities_section(capabilities, lang=lang))
    modules = report.get("modules") if isinstance(report.get("modules"), list) else []
    if modules:
        sections.append(_modules_section(modules, lang=lang))
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        sections.append(_error_section(error, lang=lang))
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    if actions:
        sections.append(
            CliSection(
                _label("やっていないこと", "Non-actions", lang),
                tuple(CliRow(f"boundary_{idx}", item, "ok") for idx, item in enumerate(actions[:8], start=1)),
            )
        )
    return render_report(title, tuple(sections), color=color)


def format_native_run_compact(report: dict[str, Any], *, lang: str = "ja") -> str:
    operation = str(report.get("operation") or "native_run")
    lines = [_title(operation, lang)]
    state = "ok" if report.get("ok", True) else "blocked"
    if lang == "ja":
        state = "正常" if report.get("ok", True) else "止めました"
    lines.append(f"  {_label('状態', 'state', lang)}: {state}")
    lines.append(f"  {_label('接続先', 'backend', lang)}: {_safe(report.get('backend_url') or 'not_configured')}")
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    if run:
        lines.append(
            f"  run_id: {_safe(run.get('run_id'))} / "
            f"{_label('状態', 'status', lang)}: {_safe(run.get('status') or 'unknown')}"
        )
    result = report.get("result") if isinstance(report.get("result"), dict) else {}
    if result:
        lines.append(f"  {_label('結果', 'result', lang)}: {_safe(result.get('result_summary') or 'not_ready')}")
    events = report.get("events") if isinstance(report.get("events"), list) else []
    if events:
        lines.append(f"  {_label('イベント', 'events', lang)}: {len(events)}")
        for event in events[:3]:
            if isinstance(event, dict):
                lines.append(f"  - {_safe(event.get('status') or event.get('type') or 'event')}: {_safe(event.get('summary'))}")
    worker = report.get("worker") if isinstance(report.get("worker"), dict) else {}
    if worker:
        lines.append(
            f"  {_label('ワーカー', 'worker', lang)}: "
            f"{_safe(worker.get('official_execution_worker') or 'unknown')} / "
            f"{_safe(worker.get('worker_delivery') or 'outbound_polling_only')}"
        )
    capabilities = report.get("capabilities") if isinstance(report.get("capabilities"), list) else []
    if capabilities:
        names = ", ".join(_safe(item.get("capability_id")) for item in capabilities[:4] if isinstance(item, dict))
        lines.append(f"  {_label('能力', 'capabilities', lang)}: {names}")
    modules = report.get("modules") if isinstance(report.get("modules"), list) else []
    if modules:
        names = ", ".join(_safe(item.get("module_id")) for item in modules[:4] if isinstance(item, dict))
        lines.append(f"  {_label('モジュール', 'modules', lang)}: {names}")
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        lines.append(f"  {_label('理由', 'reason', lang)}: {_error_message(error, lang=lang)}")
        if error.get("next_safe_command"):
            lines.append(f"  {_label('次に試す', 'next', lang)}: {_interactive_next(str(error.get('next_safe_command')), lang=lang)}")
    lines.append(f"  {_label('境界', 'boundaries', lang)}: {_boundary_line(lang)}")
    lines.append("")
    return "\n".join(lines)


def _status_section(report: dict[str, Any], *, lang: str) -> CliSection:
    return CliSection(
        _label("状態", "Status", lang),
        (
            CliRow("ok", report.get("ok", True), "ok" if report.get("ok", True) else "fail"),
            CliRow("operation", report.get("operation"), "ok"),
            CliRow("backend", report.get("backend_url"), "ok"),
            CliRow("staging_only", report.get("staging_only"), "ok"),
            CliRow("account_linked", report.get("account_linked"), "ok" if report.get("account_linked") else "warn"),
            CliRow("session_available", report.get("session_available"), "ok" if report.get("session_available") else "warn"),
            CliRow("production_cloud_runtime_enabled", report.get("production_cloud_runtime_enabled"), "fail" if report.get("production_cloud_runtime_enabled") else "ok"),
            CliRow("raw_private_file_bytes_sent", report.get("raw_private_file_bytes_sent"), "fail" if report.get("raw_private_file_bytes_sent") else "ok"),
        ),
    )


def _run_section(run: dict[str, Any], *, lang: str) -> CliSection:
    return CliSection(
        _label("実行", "Run", lang),
        (
            CliRow("run_id", run.get("run_id"), "ok"),
            CliRow("status", run.get("status"), _status_level(str(run.get("status") or ""))),
            CliRow("project_id", run.get("project_id"), "ok"),
            CliRow("module_id", run.get("module_id"), "ok"),
            CliRow("capability", ", ".join(str(item) for item in run.get("capability_requirements", [])), "ok"),
            CliRow("privacy_class", run.get("privacy_class"), "ok"),
            CliRow("worker_delivery", run.get("worker_delivery"), "ok"),
            CliRow("provider_call_enabled", run.get("provider_call_enabled"), "fail" if run.get("provider_call_enabled") else "ok"),
        ),
    )


def _provider_sharing_section(provider_sharing: dict[str, Any], *, lang: str) -> CliSection:
    return CliSection(
        _label("Provider sharing", "Provider sharing", lang),
        (
            CliRow("conversation_id", provider_sharing.get("conversation_id"), "ok" if provider_sharing.get("conversation_id") else "warn"),
            CliRow("sync_policy", provider_sharing.get("sync_policy"), "ok"),
            CliRow("provider_data_policy", provider_sharing.get("provider_data_policy"), "warn" if provider_sharing.get("openai_shared_traffic_enabled") else "ok"),
            CliRow("consent_state", provider_sharing.get("consent_state"), "ok" if provider_sharing.get("consent_state") == "enabled" else "warn"),
            CliRow("openai_shared_traffic_enabled", provider_sharing.get("openai_shared_traffic_enabled"), "warn" if provider_sharing.get("openai_shared_traffic_enabled") else "ok"),
            CliRow("raw_body_included", provider_sharing.get("raw_body_included"), "fail" if provider_sharing.get("raw_body_included") else "ok"),
            CliRow("provider_key_included", provider_sharing.get("provider_key_included"), "fail" if provider_sharing.get("provider_key_included") else "ok"),
            CliRow("google_token_included", provider_sharing.get("google_token_included"), "fail" if provider_sharing.get("google_token_included") else "ok"),
        ),
    )


def _context_preview_section(context_preview: dict[str, Any], *, lang: str) -> CliSection:
    excluded = context_preview.get("excluded_data_categories") if isinstance(context_preview.get("excluded_data_categories"), list) else []
    return CliSection(
        _label("Context preview", "Context preview", lang),
        (
            CliRow("current_message_included", context_preview.get("current_message_included"), "warn" if context_preview.get("current_message_included") else "ok"),
            CliRow("prior_message_count", context_preview.get("prior_message_count"), "ok"),
            CliRow("full_history_included", context_preview.get("full_history_included"), "fail" if context_preview.get("full_history_included") else "ok"),
            CliRow("estimated_tokens", context_preview.get("estimated_tokens"), "ok"),
            CliRow("reserved_token_budget", context_preview.get("reserved_token_budget"), "ok"),
            CliRow("excluded", ", ".join(str(item) for item in excluded[:8]), "ok"),
        ),
    )


def _result_section(result: dict[str, Any], *, lang: str) -> CliSection:
    return CliSection(
        _label("結果", "Result", lang),
        (
            CliRow("run_id", result.get("run_id"), "ok"),
            CliRow("status", result.get("status"), _status_level(str(result.get("status") or ""))),
            CliRow("result_ref", result.get("result_ref"), "ok" if result.get("result_ref") else "warn"),
            CliRow("result_summary", result.get("result_summary"), "ok" if result.get("result_summary") not in {None, "not_ready"} else "warn"),
            CliRow("raw_chain_of_thought_included", result.get("raw_chain_of_thought_included"), "fail" if result.get("raw_chain_of_thought_included") else "ok"),
        ),
    )


def _events_section(events: list[Any], *, lang: str) -> CliSection:
    rows = []
    for index, event in enumerate(events[:8], start=1):
        if isinstance(event, dict):
            rows.append(
                CliRow(
                    f"event_{index}",
                    f"{_safe(event.get('status') or event.get('type'))}: {_safe(event.get('summary'))}",
                    _status_level(str(event.get("status") or "")),
                )
            )
    return CliSection(_label("イベント", "Events", lang), tuple(rows))


def _worker_section(worker: dict[str, Any], *, lang: str) -> CliSection:
    return CliSection(
        _label("ワーカー", "Worker", lang),
        (
            CliRow("official_execution_worker", worker.get("official_execution_worker"), "warn"),
            CliRow("queue", worker.get("queue"), "ok"),
            CliRow("queued_runs", worker.get("queued_runs"), "ok"),
            CliRow("claimed_runs", worker.get("claimed_runs"), "ok"),
            CliRow("completed_runs", worker.get("completed_runs"), "ok"),
            CliRow("worker_delivery", worker.get("worker_delivery"), "ok"),
            CliRow("inbound_owner_pc_ports_required", worker.get("inbound_owner_pc_ports_required"), "fail" if worker.get("inbound_owner_pc_ports_required") else "ok"),
            CliRow("raw_local_content_included", worker.get("raw_local_content_included"), "fail" if worker.get("raw_local_content_included") else "ok"),
        ),
    )


def _capabilities_section(capabilities: list[Any], *, lang: str) -> CliSection:
    rows = []
    for index, capability in enumerate(capabilities[:12], start=1):
        if isinstance(capability, dict):
            rows.append(
                CliRow(
                    f"capability_{index}",
                    f"{_safe(capability.get('capability_id'))} / {_safe(capability.get('privacy_class'))} / worker={capability.get('requires_worker')}",
                    "ok",
                )
            )
    return CliSection(_label("能力", "Capabilities", lang), tuple(rows))


def _modules_section(modules: list[Any], *, lang: str) -> CliSection:
    rows = []
    for index, module in enumerate(modules[:12], start=1):
        if isinstance(module, dict):
            rows.append(
                CliRow(
                    f"module_{index}",
                    f"{_safe(module.get('module_id'))} / {_safe(module.get('api_surface'))} / public={module.get('public_exposure')}",
                    "ok" if module.get("public_exposure") else "warn",
                )
            )
    return CliSection(_label("モジュール", "Modules", lang), tuple(rows))


def _error_section(error: dict[str, Any], *, lang: str) -> CliSection:
    return CliSection(
        _label("注意", "Note", lang),
        (
            CliRow("code", error.get("code"), "fail"),
            CliRow("message", _error_message(error, lang=lang), "warn"),
            CliRow("next_safe_command", _interactive_next(str(error.get("next_safe_command") or "yonerai login"), lang=lang), "ok"),
            CliRow("token_printed", error.get("token_printed"), "fail" if error.get("token_printed") else "ok"),
            CliRow("local_path_printed", error.get("local_path_printed"), "fail" if error.get("local_path_printed") else "ok"),
        ),
    )


def _title(operation: str, lang: str) -> str:
    if lang != "ja":
        return {
            "native_run_submit": "Native Run submit",
            "native_run_status": "Native Run status",
            "native_run_events": "Native Run events",
            "native_run_result": "Native Run result",
            "native_run_cancel": "Native Run cancel",
            "worker_status": "Worker status",
            "capability_list": "Capabilities",
            "module_list": "Modules",
        }.get(operation, "Native Run")
    return {
        "native_run_submit": "Native Run 送信",
        "native_run_status": "Native Run 状態",
        "native_run_events": "Native Run イベント",
        "native_run_result": "Native Run 結果",
        "native_run_cancel": "Native Run キャンセル",
        "worker_status": "ワーカー状態",
        "capability_list": "能力一覧",
        "module_list": "モジュール一覧",
    }.get(operation, "Native Run")


def _label(ja: str, en: str, lang: str) -> str:
    return ja if lang == "ja" else en


def _safe(value: object) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        return "none"
    lowered = text.lower()
    if any(marker in lowered for marker in ("access_token", "refresh_token", "client_secret", "authorization_code", "c:\\users", "/users/", "/home/", "/root/")):
        return "redacted"
    return text[:240]


def _status_level(status: str) -> str:
    normalized = status.lower()
    if normalized in {"completed", "run_created", "queued", "worker_claimed", "running", "event"}:
        return "ok"
    if normalized in {"canceled", "expired", "approval_required"}:
        return "warn"
    if normalized in {"failed", "error", "denied"}:
        return "fail"
    return "warn"


def _error_message(error: dict[str, Any], *, lang: str) -> str:
    code = str(error.get("code") or "")
    if lang == "ja":
        if code == "staging_auth_required":
            return "stagingログインが必要です。`yonerai login` でログインしてください。"
        if code == "native_run_prompt_rejected":
            return "入力に秘密情報またはローカルパスらしき文字列があるため送信しません。"
        if code == "native_run_private_payload_rejected":
            return "staging APIの応答に公開できない情報が含まれていたため表示しません。"
        if code == "native_run_unreachable":
            return "staging APIに接続できませんでした。ネットワークまたはbackend状態を確認してください。"
    return _safe(error.get("message") or code or "needs attention")


def _interactive_next(command: str, *, lang: str) -> str:
    mapping = {
        "yonerai login": ("/ログイン (/login)", "/login (/ログイン)"),
        "yonerai run submit \"hello\"": ("/実行 hello (/run submit hello)", "/run submit hello (/実行 hello)"),
        "yonerai run status <run_id>": ("/実行 状態 <run_id> (/run status <run_id>)", "/run status <run_id> (/実行 状態 <run_id>)"),
        "yonerai run events <run_id>": ("/実行 イベント <run_id> (/run events <run_id>)", "/run events <run_id> (/実行 イベント <run_id>)"),
        "yonerai run result <run_id>": ("/実行 結果 <run_id> (/run result <run_id>)", "/run result <run_id> (/実行 結果 <run_id>)"),
    }
    ja, en = mapping.get(command, (command, command))
    return ja if lang == "ja" else en


def _boundary_line(lang: str) -> str:
    if lang == "ja":
        return "α/stagingのみ / 本番クラウドではない / token保存なし / 秘密・ローカルファイル送信なし"
    return "alpha/staging only / not production cloud / no token storage / no private local file upload"
