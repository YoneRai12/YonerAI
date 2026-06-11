from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.screens.labels import _safe, _yes_no


def format_control_spine_callback(command: str, callbacks: Any, *, lang: str = "ja") -> str | None:
    mapping = {
        "/api": getattr(callbacks, "api_status", None),
        "/project": getattr(callbacks, "project_status", None),
        "/sessions": getattr(callbacks, "session_status", None),
        "/audit": getattr(callbacks, "audit_status", None),
    }
    callback = mapping.get(command)
    if callback is None:
        return None
    return format_control_spine_tui(callback(lang), lang=lang)


def format_staging_login_hint(*, lang: str = "ja") -> str:
    if lang != "ja":
        return (
            "Only staging Google login is available.\n"
            "Try: yonerai login --bridge --open-browser --wait-linked --pretty --lang ja\n"
            "No production login, Google token storage, or private data sync is performed.\n"
        )
    return (
        "ステージング Google ログインだけ利用できます。\n"
        "次に試す: yonerai login --bridge --open-browser --wait-linked --pretty --lang ja\n"
        "本番ログイン、Google token 保存、非公開データ同期は行いません。\n"
    )


def format_control_spine_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    operation = str(report.get("operation") or "control_spine")
    sections: list[CliSection] = [_status_section(report, lang=lang)]

    account = report.get("account") if isinstance(report.get("account"), dict) else {}
    if account:
        sections.append(
            CliSection(
                _label("アカウント", "Account", lang),
                (
                    CliRow("account_ref", account.get("account_ref"), "ok"),
                    CliRow("display_name", account.get("display_name"), "ok"),
                    CliRow("email", account.get("email_redacted"), "ok"),
                    CliRow(
                        "raw_email_stored",
                        account.get("raw_email_stored"),
                        "fail" if account.get("raw_email_stored") else "ok",
                    ),
                ),
            )
        )

    control = report.get("control_spine") if isinstance(report.get("control_spine"), dict) else {}
    if control:
        sections.append(CliSection("Control Spine", tuple(CliRow(key, value, "ok") for key, value in control.items())))

    scopes = report.get("scopes") if isinstance(report.get("scopes"), list) else []
    if scopes:
        sections.append(
            CliSection(
                _label("スコープ", "Scopes", lang),
                tuple(
                    CliRow(
                        str(scope.get("name") or "scope"),
                        _scope_summary(scope, lang),
                        "ok" if scope.get("enabled_by_default") else "warn",
                    )
                    for scope in scopes
                    if isinstance(scope, dict)
                ),
            )
        )

    rate = report.get("rate_limit") if isinstance(report.get("rate_limit"), dict) else {}
    if rate:
        sections.append(_rate_limit_section(rate, lang=lang))

    projects = report.get("projects") if isinstance(report.get("projects"), list) else []
    if projects:
        sections.append(
            CliSection(
                _label("プロジェクト", "Projects", lang),
                tuple(
                    CliRow(str(project.get("project_id")), _project_summary(project, lang), "ok" if project.get("current") else "warn")
                    for project in projects
                    if isinstance(project, dict)
                ),
            )
        )
    project = report.get("project") if isinstance(report.get("project"), dict) else {}
    if project:
        sections.append(CliSection(_label("現在のプロジェクト", "Current project", lang), _project_rows(project)))

    sessions = report.get("sessions") if isinstance(report.get("sessions"), list) else []
    if sessions:
        sections.append(
            CliSection(
                _label("セッション", "Sessions", lang),
                tuple(
                    CliRow(str(session.get("session_id")), _session_summary(session, lang), "ok" if session.get("current") else "warn")
                    for session in sessions
                    if isinstance(session, dict)
                ),
            )
        )
    session = report.get("session") if isinstance(report.get("session"), dict) else {}
    if session:
        sections.append(CliSection(_label("セッション操作", "Session action", lang), _session_rows(session, report)))

    events = report.get("events") if isinstance(report.get("events"), list) else []
    if events:
        sections.append(
            CliSection(
                _label("監査", "Audit", lang),
                tuple(
                    CliRow(str(event.get("event_id")), _safe(event.get("summary") or event.get("event_type")), "ok")
                    for event in events
                    if isinstance(event, dict)
                ),
            )
        )

    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    if actions:
        sections.append(
            CliSection(
                _label("実行しないこと", "Non-actions", lang),
                tuple(CliRow(f"boundary_{idx}", action, "ok") for idx, action in enumerate(actions[:8], start=1)),
            )
        )

    return render_report(_title(operation, lang), tuple(sections), color=color)


def format_control_spine_tui(report: dict[str, Any], *, lang: str = "ja") -> str:
    if lang != "ja":
        return format_control_spine_pretty(report, lang="en", color="never")

    lines = [
        _title(str(report.get("operation") or "control_spine"), lang),
        f"  接続先: {_safe(report.get('backend_url') or 'not_configured')}",
        f"  ステージング専用: {_yes_no(report.get('staging_only'), lang='ja')}",
        f"  アカウント: {'リンク済み' if report.get('account_linked') else '未リンク'}",
        f"  セッション: {'利用可能' if report.get('staging_session_available') else '未保存'}",
        f"  production backend: {'enabled' if report.get('production_backend_enabled') else 'disabled'}",
        f"  本番ログイン: {'有効' if report.get('production_login_enabled') else '無効'}",
        f"  OpenAI共有トラフィック: {'オン' if report.get('shared_traffic_enabled') else 'オフ'}",
        f"  ローカル非公開アップロード: {'オン' if report.get('local_private_upload_enabled') else 'オフ'}",
    ]
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        lines.append(f"  注意: {_safe(error.get('code'))} - {_safe(error.get('message'))}")
    account = report.get("account") if isinstance(report.get("account"), dict) else {}
    if account:
        lines.append(f"  表示名: {_safe(account.get('display_name'))}")
        lines.append(f"  メール: {_safe(account.get('email_redacted'))}")
    scopes = report.get("scopes") if isinstance(report.get("scopes"), list) else []
    if scopes:
        lines.append("  スコープ:")
        for scope in scopes[:8]:
            if isinstance(scope, dict):
                state = "有効" if scope.get("enabled_by_default") else "無効"
                lines.append(f"    - {_safe(scope.get('name'))}: {state}")
    lines.append("  次に試す: yonerai whoami --pretty --lang ja")
    lines.append("")
    return "\n".join(lines)


def _status_section(report: dict[str, Any], *, lang: str) -> CliSection:
    rows = [
        CliRow("operation", report.get("operation"), "ok"),
        CliRow("ok", report.get("ok"), "ok" if report.get("ok") else "fail"),
        CliRow("backend", report.get("backend_url") or "not_configured", "ok" if report.get("staging_origin_configured") else "warn"),
        CliRow("staging_only", report.get("staging_only"), "ok"),
        CliRow("account_linked", report.get("account_linked"), "ok" if report.get("account_linked") else "warn"),
        CliRow("auth_state", report.get("auth_state"), "ok" if report.get("auth_state") == "linked" else "warn"),
        CliRow(
            "session_available",
            report.get("staging_session_available"),
            "ok" if report.get("staging_session_available") else "warn",
        ),
        CliRow(
            "production_login_enabled",
            report.get("production_login_enabled"),
            "fail" if report.get("production_login_enabled") else "ok",
        ),
        CliRow(
            "shared_traffic_enabled",
            report.get("shared_traffic_enabled"),
            "fail" if report.get("shared_traffic_enabled") else "ok",
        ),
        CliRow(
            "local_private_upload_enabled",
            report.get("local_private_upload_enabled"),
            "fail" if report.get("local_private_upload_enabled") else "ok",
        ),
    ]
    if "backend_status_code" in report:
        rows.append(CliRow("backend_status_code", report.get("backend_status_code"), "ok" if report.get("ok") else "warn"))
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        rows.append(CliRow("error", error.get("code"), "fail"))
        rows.append(CliRow("message", error.get("message"), "warn"))
    return CliSection(_label("状態", "Status", lang), tuple(rows))


def _rate_limit_section(rate: dict[str, Any], *, lang: str) -> CliSection:
    rate_body = rate.get("body") if isinstance(rate.get("body"), dict) else {}
    return CliSection(
        _label("レート制限", "Rate limit", lang),
        (
            CliRow("status_code", rate.get("status_code"), "ok" if rate.get("ok") else "warn"),
            CliRow("scope", rate_body.get("scope") or "unknown", "ok"),
            CliRow("allowed", rate_body.get("allowed"), "ok" if rate_body.get("allowed") else "warn"),
            CliRow("quota_exceeded", rate_body.get("quota_exceeded"), "warn" if rate_body.get("quota_exceeded") else "ok"),
            CliRow("headers", ", ".join(str(item) for item in rate.get("rate_limit_headers_present", [])), "ok"),
        ),
    )


def _title(operation: str, lang: str) -> str:
    if lang != "ja":
        return {
            "whoami": "YonerAI account",
            "api_ping": "YonerAI API ping",
            "api_status": "YonerAI API status",
            "api_rate_limit": "YonerAI API rate limit",
            "project_list": "YonerAI projects",
            "project_current": "YonerAI current project",
            "project_use": "YonerAI project selection",
            "session_list": "YonerAI sessions",
            "session_revoke": "YonerAI session revoke",
            "audit_list": "YonerAI audit",
        }.get(operation, "YonerAI control spine")
    return {
        "whoami": "YonerAI アカウント",
        "api_ping": "YonerAI API ping",
        "api_status": "YonerAI API 状態",
        "api_rate_limit": "YonerAI API レート制限",
        "project_list": "YonerAI プロジェクト",
        "project_current": "YonerAI 現在のプロジェクト",
        "project_use": "YonerAI プロジェクト選択",
        "session_list": "YonerAI セッション",
        "session_revoke": "YonerAI セッション取り消し",
        "audit_list": "YonerAI 監査",
    }.get(operation, "YonerAI control spine")


def _label(ja: str, en: str, lang: str) -> str:
    return ja if lang == "ja" else en


def _scope_summary(scope: dict[str, Any], lang: str) -> str:
    state = "有効" if scope.get("enabled_by_default") else "無効"
    if lang != "ja":
        state = "enabled" if scope.get("enabled_by_default") else "disabled"
    return f"{state} - {_safe(scope.get('summary') or '')}"


def _project_summary(project: dict[str, Any], lang: str) -> str:
    current = "現在" if project.get("current") else "利用可能"
    if lang != "ja":
        current = "current" if project.get("current") else "available"
    return f"{_safe(project.get('name'))} ({current})"


def _project_rows(project: dict[str, Any]) -> tuple[CliRow, ...]:
    return (
        CliRow("project_id", project.get("project_id"), "ok"),
        CliRow("name", project.get("name"), "ok"),
        CliRow("current", project.get("current"), "ok" if project.get("current") else "warn"),
        CliRow("billing_enabled", project.get("billing_enabled"), "fail" if project.get("billing_enabled") else "ok"),
        CliRow("scopes", ", ".join(str(scope) for scope in project.get("scopes", [])), "ok"),
    )


def _session_summary(session: dict[str, Any], lang: str) -> str:
    current = "現在" if session.get("current") else "別セッション"
    if lang != "ja":
        current = "current" if session.get("current") else "other"
    return f"{_safe(session.get('status'))} / {current} / expires={_safe(session.get('expires_at') or 'unknown')}"


def _session_rows(session: dict[str, Any], report: dict[str, Any]) -> tuple[CliRow, ...]:
    return (
        CliRow("session_id", session.get("session_id"), "ok"),
        CliRow("status", session.get("status"), "ok"),
        CliRow("revoked", report.get("revoked", False), "ok" if report.get("revoked") else "warn"),
        CliRow("token_included", session.get("token_included"), "fail" if session.get("token_included") else "ok"),
    )
