from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.screens.native_run import format_native_run_compact
from yonerai_cli.screens.labels import _safe


def format_control_spine_callback(command: str, callbacks: Any, *, lang: str = "ja") -> str | None:
    mapping = {
        "/api": getattr(callbacks, "api_status", None),
        "/ping": getattr(callbacks, "ping_status", None),
        "/rate-limit": getattr(callbacks, "rate_limit_status", None),
        "/whoami": getattr(callbacks, "whoami", None),
        "/project": getattr(callbacks, "project_status", None),
        "/projects": getattr(callbacks, "project_status", None),
        "/sessions": getattr(callbacks, "session_status", None),
        "/audit": getattr(callbacks, "audit_status", None),
        "/run": getattr(callbacks, "native_run_status", None),
        "/worker": getattr(callbacks, "worker_status", None),
        "/capabilities": getattr(callbacks, "capability_list", None),
        "/modules": getattr(callbacks, "module_list", None),
    }
    callback = mapping.get(command)
    if callback is None:
        return None
    report = callback(lang)
    if report is None:
        return None
    if command in {"/run", "/worker", "/capabilities", "/modules"}:
        return format_native_run_compact(report, lang=lang)
    return format_control_spine_tui(report, lang=lang)


def format_staging_login_hint(*, lang: str = "ja") -> str:  # noqa: F811
    if lang != "ja":
        return (
            "Only alpha/staging Google login is available here.\n"
            "Try: /login\n"
            "Target: https://api-staging.yonerai.com\n"
            "Production login is unavailable in this build.\n"
            "No Google token storage, no refresh token storage, and no automatic private sync.\n"
        )
    return (
        "いま使えるのは α/staging の Google ログインだけです。\n"
        "試す: /ログイン または /login\n"
        "接続先: https://api-staging.yonerai.com\n"
        "正式ログインはこの build では使えません。\n"
        "Google token 保存なし、refresh token 保存なし、自動 private sync なし。\n"
    )


def format_login_flow_compact(report: dict[str, Any], *, lang: str = "ja") -> str:  # noqa: F811
    staging = report.get("staging") if isinstance(report.get("staging"), dict) else {}
    staging_available = bool(
        report.get("staging_login_available")
        or report.get("configured")
        or staging.get("configured")
        or report.get("staging_login")
    )
    if not staging_available:
        return format_staging_login_hint(lang=lang)

    linked_claim = report.get("staging_linked_claim") if isinstance(report.get("staging_linked_claim"), dict) else {}
    account = linked_claim.get("account") if isinstance(linked_claim.get("account"), dict) else {}
    bridge = report.get("cli_bridge") if isinstance(report.get("cli_bridge"), dict) else {}
    linked = bool(report.get("staging_linked"))
    auth_url = _safe(report.get("authorization_url") or bridge.get("browser_start_url") or "")
    expires_at = _safe(linked_claim.get("expires_at") or report.get("expires_at") or "unknown")
    email = _safe(account.get("email_redacted") or account.get("display_name") or "not linked")
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    error_message = _safe(error.get("message") or "")
    next_safe_command = _safe(report.get("next_safe_command") or "yonerai login")

    if lang != "ja":
        lines = ["Staging login"]
        if linked:
            lines.extend(
                (
                    "  state: linked",
                    f"  account: {email}",
                    f"  session_expires_at: {expires_at}",
                    "  next: type normally · /auth · /sync",
                    "  boundaries: no production login / no Google token storage / no private auto-sync",
                    "",
                )
            )
            return "\n".join(lines)
        lines.append("  state: waiting for browser login")
        if report.get("browser_opened"):
            lines.append("  browser: opened")
        elif auth_url:
            lines.append("  browser: open this URL")
            lines.append(f"  {auth_url}")
        else:
            lines.append("  browser: could not prepare the URL yet")
        if bridge.get("request_id"):
            lines.append(f"  request_id: {_safe(bridge.get('request_id'))}")
        if error_message:
            lines.append(f"  note: {error_message}")
        lines.append(f"  next: {next_safe_command}")
        lines.append("  boundaries: no production login / no Google token storage / no private auto-sync")
        lines.append("")
        return "\n".join(lines)

    lines = ["ログイン"]
    if linked:
        lines.extend(
            (
                "  状態: staging 連携済み",
                f"  アカウント: {email}",
                f"  セッション期限: {expires_at}",
                "  次: そのまま話す ・ /認証 ・ /同期",
                "  境界: 正式ログインなし / Google token保存なし / private自動syncなし",
                "",
            )
        )
        return "\n".join(lines)

    lines.append("  状態: staging ログイン待ち")
    if report.get("browser_opened"):
        lines.append("  ブラウザを開きました。認証した画面を完了してください。")
    elif auth_url:
        lines.append("  次のURLをブラウザで開いてください。")
        lines.append(f"  {auth_url}")
    else:
            lines.append("  ログインURLをまだ用意できていません。もう一度 `/ログイン` または `/login` を試してください。")
    if bridge.get("request_id"):
        lines.append(f"  リクエストID: {_safe(bridge.get('request_id'))}")
    if error_message:
        lines.append(f"  補足: {error_message}")
    lines.append(f"  次: {next_safe_command}")
    lines.append("  境界: 正式ログインなし / Google token保存なし / 自動 private syncなし")
    lines.append("")
    return "\n".join(lines)


def format_control_spine_compact(report: dict[str, Any], *, lang: str = "ja") -> str:  # noqa: F811
    operation = str(report.get("operation") or "control_spine")
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    skew = report.get("contract_skew") if isinstance(report.get("contract_skew"), dict) else {}
    lines = [_compact_title(operation, lang)]

    if operation == "whoami":
        account = report.get("account") if isinstance(report.get("account"), dict) else {}
        linked_claim_account = report.get("linked_claim_account") if isinstance(report.get("linked_claim_account"), dict) else {}
        auth_state = str(report.get("auth_state") or ("linked" if report.get("ok") else "unauthenticated"))
        lines.append(f"  {_compact_state_label(report, lang)}")
        if account:
            lines.append(f"  {_compact_label('アカウント', 'account', lang)}: {_compact_account_label(account, lang=lang)}")
        elif linked_claim_account:
            lines.append(f"  {_compact_label('アカウント', 'account', lang)}: {_compact_account_label(linked_claim_account, lang=lang)}")
        if auth_state in {"linked", "expired", "revoked"}:
            lines.append(
                f"  {_compact_label('セッション期限', 'session_expires_at', lang)}: "
                f"{_safe(report.get('session_expires_at') or ('未連携' if lang == 'ja' else 'not linked'))}"
            )
        if auth_state == "linked":
            lines.append(f"  {_compact_next_label(lang)}: {_interactive_commands(lang, 'yonerai sessions', 'yonerai logout')}")
        elif auth_state in {"expired", "revoked"}:
            lines.append("  再ログイン: /ログイン (/login)" if lang == "ja" else "  relogin: /login (/ログイン)")
            lines.append(f"  {_compact_next_label(lang)}: {_interactive_next_command('yonerai login', lang=lang)}")
        else:
            lines.append("  まだクラウド連携していません。" if lang == "ja" else "  cloud account is not linked yet.")
            if not error:
                lines.append(f"  {_compact_next_label(lang)}: {_interactive_next_command('yonerai login', lang=lang)}")
    elif operation == "session_list":
        sessions = report.get("sessions") if isinstance(report.get("sessions"), list) else []
        lines.append(f"  {_compact_state_label(report, lang)}")
        lines.append(
            f"  {_compact_label('件数', 'count', lang)}: {len(sessions)} / "
            f"{_compact_label('接続先', 'backend', lang)}: {_safe(report.get('backend_url') or 'not_configured')}"
        )
        if sessions:
            current = next((session for session in sessions if isinstance(session, dict) and session.get("current")), None)
            if isinstance(current, dict):
                lines.append(f"  {_compact_label('現在', 'current', lang)}: {_compact_session_summary(current, lang)}")
            others = [
                _compact_session_summary(session, lang)
                for session in sessions
                if isinstance(session, dict) and not session.get("current")
            ]
            for index, summary in enumerate(others[:2], start=1):
                lines.append(f"  {_compact_label(f'他{index}', f'other_{index}', lang)}: {summary}")
        lines.append(f"  {_compact_next_label(lang)}: {_interactive_commands(lang, 'yonerai revoke <session_id>', 'yonerai logout')}")
    elif operation == "session_revoke":
        session = report.get("session") if isinstance(report.get("session"), dict) else {}
        result_label = "削除して無効化" if report.get("revoked") and lang == "ja" else "revoked" if report.get("revoked") else "未完了" if lang == "ja" else "not completed"
        lines.append(f"  {_compact_label('結果', 'result', lang)}: {result_label}")
        lines.append(
            f"  {_compact_label('対象', 'target', lang)}: "
            f"{_safe(report.get('requested_session_id') or session.get('session_id') or 'unknown')}"
        )
        if session:
            lines.append(f"  {_compact_label('状態', 'state', lang)}: {_compact_session_summary(session, lang)}")
        lines.append(f"  {_compact_next_label(lang)}: {_interactive_next_command('yonerai sessions', lang=lang)}")
    elif operation == "staging_logout":
        logout_label = (
            "ローカルの staging セッションを削除しました"
            if report.get("session_removed") and lang == "ja"
            else "cleared local staging session"
            if report.get("session_removed")
            else "何も削除していません"
            if lang == "ja"
            else "nothing to clear"
        )
        lines.append(f"  {_compact_label('状態', 'state', lang)}: {logout_label}")
        lines.append(f"  {_compact_next_label(lang)}: {_interactive_next_command('yonerai login', lang=lang)}")
    elif operation == "project_list":
        projects = report.get("projects") if isinstance(report.get("projects"), list) else []
        lines.append(f"  {_compact_state_label(report, lang)}")
        current = report.get("current_project") if isinstance(report.get("current_project"), dict) else {}
        if current:
            lines.append(f"  {_compact_label('現在', 'current', lang)}: {_compact_project_summary(current, lang)}")
        for index, project in enumerate(projects[:3], start=1):
            if isinstance(project, dict):
                lines.append(f"  {_compact_label(f'候補{index}', f'project_{index}', lang)}: {_compact_project_summary(project, lang)}")
        lines.append(f"  {_compact_next_label(lang)}: {_interactive_next_command('yonerai projects use <project_id>', lang=lang)}")
    elif operation in {"project_current", "project_use"}:
        project = report.get("project") if isinstance(report.get("project"), dict) else {}
        lines.append(f"  {_compact_state_label(report, lang)}")
        if project:
            lines.append(f"  {_compact_label('プロジェクト', 'project', lang)}: {_compact_project_summary(project, lang)}")
        if report.get("requested_project_id"):
            lines.append(f"  {_compact_label('入力', 'requested', lang)}: {_safe(report.get('requested_project_id'))}")
        lines.append(f"  {_compact_next_label(lang)}: {_interactive_commands(lang, 'yonerai projects', 'yonerai whoami')}")
    elif operation == "api_ping":
        ping = report.get("ping") if isinstance(report.get("ping"), dict) else {}
        lines.append(f"  {_compact_state_label(report, lang)}")
        lines.append(f"  {_compact_label('応答', 'response', lang)}: {_safe(ping.get('message') or 'pong')}")
        lines.append(f"  {_compact_label('接続先', 'backend', lang)}: {_safe(report.get('backend_url') or 'not_configured')}")
        lines.append(f"  {_compact_next_label(lang)}: {_interactive_commands(lang, 'yonerai whoami', 'yonerai rate-limit')}")
    elif operation == "api_rate_limit":
        rate = report.get("rate_limit") if isinstance(report.get("rate_limit"), dict) else {}
        body = rate.get("body") if isinstance(rate.get("body"), dict) else {}
        lines.append(f"  {_compact_state_label(report, lang)}")
        lines.append(
            f"  {_compact_label('スコープ', 'scope', lang)}: {_safe(body.get('scope') or 'unknown')} / "
            f"{_compact_label('許可', 'allowed', lang)}: {_yes_no(body.get('allowed'), lang=lang)}"
        )
        lines.append(
            f"  {_compact_label('超過', 'quota', lang)}: {_yes_no(body.get('quota_exceeded'), lang=lang)} / "
            f"{_compact_label('ヘッダー', 'headers', lang)}: {', '.join(str(item) for item in report.get('rate_limit_headers_present', [])[:3]) or 'none'}"
        )
        lines.append(f"  {_compact_next_label(lang)}: {_interactive_commands(lang, 'yonerai ping', 'yonerai update')}")
    elif operation == "api_status":
        lines.append(f"  {_compact_state_label(report, lang)}")
        lines.append(f"  {_compact_label('接続先', 'backend', lang)}: {_safe(report.get('backend_url') or 'not_configured')}")
        auth_label = "staging 連携済み" if report.get("account_linked") and lang == "ja" else "linked" if report.get("account_linked") else "未ログイン" if lang == "ja" else "not linked"
        lines.append(f"  {_compact_label('認証', 'auth', lang)}: {auth_label}")
        lines.append(f"  {_compact_next_label(lang)}: {_interactive_commands(lang, 'yonerai login', 'yonerai whoami')}")
    elif operation == "audit_list":
        events = report.get("events") if isinstance(report.get("events"), list) else []
        lines.append(f"  {_compact_state_label(report, lang)}")
        lines.append(f"  {_compact_label('件数', 'count', lang)}: {len(events)}")
        for index, event in enumerate(events[:3], start=1):
            if isinstance(event, dict):
                lines.append(
                    f"  {_compact_label(f'項目{index}', f'item_{index}', lang)}: "
                    f"{_safe(event.get('summary') or event.get('event_type') or 'event')}"
                )
        lines.append(f"  {_compact_next_label(lang)}: {_interactive_next_command('yonerai auth status', lang=lang)}")
    else:
        return format_control_spine_tui(report, lang=lang)

    if error:
        lines.append(f"  {_compact_label('補足', 'note', lang)}: {_safe(_error_message(error, lang))}")
        lines.append(
            f"  {_compact_next_label(lang)}: "
            f"{_safe(_interactive_next_command(str(error.get('next_safe_command') or 'yonerai login'), lang=lang))}"
        )
    if skew and skew.get("skew_detected"):
        lines.append(f"  {_compact_label('互換警告', 'contract_warning', lang)}: {_safe(_contract_skew_message(skew, lang))}")
    lines.append(f"  {_compact_label('境界', 'boundaries', lang)}: {_compact_boundary_line(lang)}")
    lines.append("")
    return "\n".join(lines)


def format_control_spine_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    operation = str(report.get("operation") or "control_spine")
    sections: list[CliSection] = [_status_section(report, lang=lang)]

    account = report.get("account") if isinstance(report.get("account"), dict) else {}
    if account:
        sections.append(
            CliSection(
                _label("アカウント", "Account", lang),
                (
                    CliRow("account_id", account.get("account_id"), "ok"),
                    CliRow("display_name", account.get("display_name"), "ok"),
                    CliRow("email", account.get("email_redacted"), "ok"),
                    CliRow("raw_email_stored", account.get("raw_email_stored"), "fail" if account.get("raw_email_stored") else "ok"),
                ),
            )
        )

    control = report.get("control_spine") if isinstance(report.get("control_spine"), dict) else {}
    if control:
        sections.append(CliSection("Control Spine", tuple(CliRow(key, value, "ok") for key, value in control.items())))

    skew = report.get("contract_skew") if isinstance(report.get("contract_skew"), dict) else {}
    if skew:
        sections.append(
            CliSection(
                _label("契約バージョン", "Contract version", lang),
                (
                    CliRow("api_version", skew.get("api_version"), "ok"),
                    CliRow("min_cli_version", skew.get("min_cli_version"), "ok"),
                    CliRow("current_cli_version", skew.get("current_cli_version"), "ok"),
                    CliRow("skew_detected", skew.get("skew_detected"), "warn" if skew.get("skew_detected") else "ok"),
                    CliRow("next_action", _contract_skew_message(skew, lang), "warn" if skew.get("skew_detected") else "ok"),
                ),
            )
        )

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
                    CliRow(
                        str(project.get("project_id")),
                        _project_summary(project, lang),
                        "ok" if project.get("current") else "warn",
                    )
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
                    CliRow(
                        str(session.get("session_id")),
                        _session_summary(session, lang),
                        "ok" if session.get("current") else "warn",
                    )
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
                _label("しないこと", "Non-actions", lang),
                tuple(CliRow(f"boundary_{idx}", action, "ok") for idx, action in enumerate(actions[:8], start=1)),
            )
        )

    return render_report(_title(operation, lang), tuple(sections), color=color)


def format_control_spine_tui(report: dict[str, Any], *, lang: str = "ja") -> str:  # noqa: F811
    account = report.get("account") if isinstance(report.get("account"), dict) else {}
    linked_claim_account = report.get("linked_claim_account") if isinstance(report.get("linked_claim_account"), dict) else {}
    scopes = report.get("scopes") if isinstance(report.get("scopes"), list) else []
    scope_names = [_safe(scope.get("name")) for scope in scopes[:4] if isinstance(scope, dict) and scope.get("name")]
    account_candidates = (
        account.get("email_redacted"),
        account.get("display_name"),
        linked_claim_account.get("email_redacted"),
        linked_claim_account.get("display_name"),
    )
    account_label = "not-linked"
    for candidate in account_candidates:
        text = _safe(candidate)
        if text and text != "not-linked":
            account_label = text
            break
    if lang != "ja":
        lines = [
            "Auth / API",
            f"  backend: {_safe(report.get('backend_url') or 'not_configured')}",
            f"  state: {'linked' if report.get('account_linked') else 'not linked'} (staging only)",
            f"  account: {account_label}",
            f"  session_expires_at: {_safe(report.get('session_expires_at') or 'not-linked')}",
            f"  scopes: {', '.join(scope_names) if scope_names else 'not-fetched'}",
            "  boundaries: no production login / shared traffic off / private upload disabled",
        ]
        error = report.get("error") if isinstance(report.get("error"), dict) else {}
        if error:
            lines.append(f"  note: {_safe(_error_message(error, lang))}")
            if error.get("next_safe_command"):
                lines.append(f"  next: {_safe(error.get('next_safe_command'))}")
        skew = report.get("contract_skew") if isinstance(report.get("contract_skew"), dict) else {}
        if skew and skew.get("skew_detected"):
            lines.append(f"  contract_warning: {_safe(_contract_skew_message(skew, lang))}")
        lines.append("  next: /whoami /login")
        lines.append("")
        return "\n".join(lines)

    lines = [
        "認証 / API",
        f"  接続先: {_safe(report.get('backend_url') or 'not_configured')}",
        f"  状態: {'staging 連携済み' if report.get('account_linked') else '未ログイン'}",
        f"  アカウント: {account_label}",
        f"  セッション期限: {_safe(report.get('session_expires_at') or '未連携')}",
        f"  スコープ: {', '.join(scope_names) if scope_names else '未取得'}",
        "  境界: 正式ログインなし / OpenAI共有オフ / private upload無効",
    ]
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        lines.append(f"  補足: {_safe(_error_message(error, lang))}")
        if error.get("next_safe_command"):
            lines.append(f"  次に試す: {_safe(error.get('next_safe_command'))}")
    skew = report.get("contract_skew") if isinstance(report.get("contract_skew"), dict) else {}
    if skew and skew.get("skew_detected"):
        lines.append(f"  互換警告: {_safe(_contract_skew_message(skew, lang))}")
    lines.append("  次: /アカウント /ログイン")
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
        CliRow("session_expires_at", report.get("session_expires_at") or "not-linked", "ok" if report.get("session_expires_at") else "warn"),
        CliRow("session_available", report.get("staging_session_available"), "ok" if report.get("staging_session_available") else "warn"),
        CliRow("production_login_enabled", report.get("production_login_enabled"), "fail" if report.get("production_login_enabled") else "ok"),
        CliRow("shared_traffic_enabled", report.get("shared_traffic_enabled"), "fail" if report.get("shared_traffic_enabled") else "ok"),
        CliRow("local_private_upload_enabled", report.get("local_private_upload_enabled"), "fail" if report.get("local_private_upload_enabled") else "ok"),
    ]
    if "backend_status_code" in report:
        rows.append(CliRow("backend_status_code", report.get("backend_status_code"), "ok" if report.get("ok") else "warn"))
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        rows.append(CliRow("error", error.get("code"), "fail"))
        rows.append(CliRow("message", _error_message(error, lang), "warn"))
        rows.append(CliRow("next_action", error.get("next_safe_command") or "yonerai login", "warn"))
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
        "session_revoke": "YonerAI セッション削除",
        "audit_list": "YonerAI 監査",
    }.get(operation, "YonerAI control spine")


def _label(ja: str, en: str, lang: str) -> str:
    return ja if lang == "ja" else en


def _scope_summary(scope: dict[str, Any], lang: str) -> str:
    state = "有効" if scope.get("enabled_by_default") else "無効"
    if lang != "ja":
        state = "enabled" if scope.get("enabled_by_default") else "disabled"
    if scope.get("requires_threat_model"):
        reason = "脅威モデルゲート必須" if lang == "ja" else "requires threat-model gate"
        return f"{state} - {reason} - {_safe(scope.get('summary') or '')}"
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
    current = "現在" if session.get("current") else "他"
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


def _error_message(error: dict[str, Any], lang: str) -> object:
    if lang == "ja" and error.get("code") == "staging_auth_required":
        return "staging セッションが未ログインまたは期限切れです。`/ログイン` または `/login` を使ってください。"
    if lang == "ja" and error.get("code") == "staging_origin_not_configured":
        return "ログイン先が未設定です。`/ログイン` または `/login` を使う前に staging 接続先を確認してください。"
    return error.get("message")


def _contract_skew_message(skew: dict[str, Any], lang: str) -> str:
    if not skew.get("skew_detected"):
        return "互換あり" if lang == "ja" else "ok"
    if lang == "ja":
        return "CLI が staging API の必要バージョンより古い可能性があります。`/更新` または `/update` を確認してください。"
    return str(skew.get("warning") or "Run `/update`.")


def _compact_title(operation: str, lang: str) -> str:
    if lang == "ja":
        return {
            "whoami": "アカウント",
            "session_list": "セッション",
            "session_revoke": "セッション削除",
            "staging_logout": "ログアウト",
            "project_list": "プロジェクト",
            "project_current": "現在のプロジェクト",
            "project_use": "プロジェクト選択",
            "api_ping": "API ping",
            "api_rate_limit": "レート制限",
            "api_status": "API 状態",
            "audit_list": "監査",
        }.get(operation, "Control Spine")
    return {
        "whoami": "Account",
        "session_list": "Sessions",
        "session_revoke": "Session revoke",
        "staging_logout": "Logout",
        "project_list": "Projects",
        "project_current": "Current project",
        "project_use": "Project selection",
        "api_ping": "API ping",
        "api_rate_limit": "Rate limit",
        "api_status": "API status",
        "audit_list": "Audit",
    }.get(operation, "Control Spine")


def _compact_label(ja: str, en: str, lang: str) -> str:
    return ja if lang == "ja" else en


def _compact_next_label(lang: str) -> str:
    return "次" if lang == "ja" else "next"


def _compact_boundary_line(lang: str) -> str:
    if lang == "ja":
        return "staging のみ / 正式ログインなし / Google token保存なし / OpenAI共有オフ / private upload無効"
    return "staging only / no production login / no Google token storage / shared traffic off / private upload disabled"


def _compact_state_label(report: dict[str, Any], lang: str) -> str:
    if report.get("ok"):
        return "状態: 利用可能" if lang == "ja" else "state: available"
    auth_state = str(report.get("auth_state") or "")
    if auth_state in {"expired", "revoked", "unauthenticated"}:
        mapping = {
            "expired": "期限切れ",
            "revoked": "削除済み",
            "unauthenticated": "未ログイン",
        }
        if lang == "ja":
            return f"状態: {mapping.get(auth_state, '未ログイン')}"
        return f"state: {auth_state}"
    return "状態: 要確認" if lang == "ja" else "state: needs attention"


def _compact_account_label(account: dict[str, Any], *, lang: str) -> str:
    value = _safe(account.get("email_redacted") or account.get("display_name") or "not-linked")
    if value == "not-linked":
        return "未連携" if lang == "ja" else "not linked"
    return value


def _compact_project_summary(project: dict[str, Any], lang: str) -> str:
    name = _safe(project.get("name") or project.get("project_id") or "unknown")
    project_id = _safe(project.get("project_id") or "unknown")
    current = "現在" if project.get("current") else "候補"
    if lang != "ja":
        current = "current" if project.get("current") else "available"
    return f"{name} ({project_id}, {current})"


def _compact_session_summary(session: dict[str, Any], lang: str) -> str:
    session_id = _safe(session.get("session_id") or "unknown")
    status = _safe(session.get("status") or "unknown")
    expires_at = _safe(session.get("expires_at") or "unknown")
    current = "現在" if session.get("current") else "他"
    if lang != "ja":
        current = "current" if session.get("current") else "other"
    return f"{session_id} / {status} / {current} / expires={expires_at}"


def _yes_no(value: object, *, lang: str) -> str:
    if lang == "ja":
        return "はい" if value else "いいえ"
    return "yes" if value else "no"


# Final clean overrides for interactive Control Spine UX.
def format_staging_login_hint(*, lang: str = "ja") -> str:  # noqa: F811
    if lang == "ja":
        return (
            "ログイン\n"
            "  ここで使えるのは α/staging の Google ログインだけです。\n"
            "  試す: /ログイン (/login)\n"
            "  接続先: https://api-staging.yonerai.com\n"
            "  本番ログインはこのビルドでは使えません。\n"
            "  境界: Google token保存なし / refresh token保存なし / private自動同期なし\n"
        )
    return (
        "Login\n"
        "  Only alpha/staging Google login is available here.\n"
        "  Try: /login\n"
        "  Target: https://api-staging.yonerai.com\n"
        "  Production login is unavailable in this build.\n"
        "  Boundaries: no Google token storage / no refresh token storage / no private auto-sync\n"
    )


def format_login_flow_compact(report: dict[str, Any], *, lang: str = "ja") -> str:  # noqa: F811
    staging = report.get("staging") if isinstance(report.get("staging"), dict) else {}
    staging_available = bool(
        report.get("staging_login_available")
        or report.get("configured")
        or staging.get("configured")
        or report.get("staging_login")
    )
    if not staging_available:
        return format_staging_login_hint(lang=lang)

    linked_claim = report.get("staging_linked_claim") if isinstance(report.get("staging_linked_claim"), dict) else {}
    account = linked_claim.get("account") if isinstance(linked_claim.get("account"), dict) else {}
    bridge = report.get("cli_bridge") if isinstance(report.get("cli_bridge"), dict) else {}
    linked = bool(report.get("staging_linked"))
    auth_url = _safe(report.get("authorization_url") or bridge.get("browser_start_url") or "")
    expires_at = _safe(linked_claim.get("expires_at") or report.get("expires_at") or "unknown")
    email = _safe(account.get("email_redacted") or account.get("display_name") or "not linked")
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    error_message = _safe(error.get("message") or "")
    next_safe_command = _safe(
        _interactive_next_command(str(report.get("next_safe_command") or "yonerai login"), lang=lang)
    )

    if lang == "ja":
        lines = ["ログイン"]
        if linked:
            lines.extend(
                (
                    "  状態: staging 連携済み",
                    f"  アカウント: {email}",
                    f"  セッション期限: {expires_at}",
                    "  次: そのまま話す /認証 (/auth) /同期 (/sync)",
                    "  境界: stagingのみ / Google token保存なし / refresh token保存なし / private自動同期なし",
                    "",
                )
            )
            return "\n".join(lines)
        lines.append("  状態: staging ログイン待ち")
        if report.get("browser_opened"):
            lines.append("  ブラウザを開きました。表示された画面で続けてください。")
        elif auth_url:
            lines.append("  次の URL をブラウザで開いてください。")
            lines.append(f"  {auth_url}")
        else:
            lines.append("  ログイン URL をまだ用意できていません。もう一度 `/ログイン` または `/login` を試してください。")
        if bridge.get("request_id"):
            lines.append(f"  request_id: {_safe(bridge.get('request_id'))}")
        if error_message:
            lines.append(f"  注意: {error_message}")
        lines.append(f"  次: {next_safe_command}")
        lines.append("  境界: stagingのみ / Google token保存なし / refresh token保存なし / private自動同期なし")
        lines.append("")
        return "\n".join(lines)

    lines = ["Staging login"]
    if linked:
        lines.extend(
            (
                "  state: linked",
                f"  account: {email}",
                f"  session_expires_at: {expires_at}",
                "  next: talk normally /auth /sync",
                "  boundaries: staging only / no Google token storage / no refresh token storage / no private auto-sync",
                "",
            )
        )
        return "\n".join(lines)
    lines.append("  state: waiting for browser login")
    if report.get("browser_opened"):
        lines.append("  browser: opened")
    elif auth_url:
        lines.append("  browser: open this URL")
        lines.append(f"  {auth_url}")
    else:
        lines.append("  browser: login URL is not ready yet")
    if bridge.get("request_id"):
        lines.append(f"  request_id: {_safe(bridge.get('request_id'))}")
    if error_message:
        lines.append(f"  note: {error_message}")
    lines.append(f"  next: {next_safe_command}")
    lines.append("  boundaries: staging only / no Google token storage / no refresh token storage / no private auto-sync")
    lines.append("")
    return "\n".join(lines)


def _error_message(error: dict[str, Any], lang: str) -> object:  # noqa: F811
    code = str(error.get("code") or "")
    if lang == "ja":
        if code == "staging_auth_required":
            return "staging セッションが未ログイン、または期限切れです。`/ログイン` または `/login` を使ってください。"
        if code == "staging_origin_not_configured":
            return "staging 接続先が未設定です。`/ログイン` の前に接続先を確認してください。"
    return error.get("message")


def _contract_skew_message(skew: dict[str, Any], lang: str) -> str:  # noqa: F811
    if not skew.get("skew_detected"):
        return "正常" if lang == "ja" else "ok"
    if lang == "ja":
        return "CLI が staging API の最低バージョン条件を満たしていない可能性があります。`/更新` または `/update` を確認してください。"
    return str(skew.get("warning") or "Check `/update`.")


def _interactive_next_command(value: str, *, lang: str) -> str:  # noqa: F811
    mapping = {
        "yonerai login": "/ログイン (/login)" if lang == "ja" else "/login (/ログイン)",
        "yonerai whoami": "/アカウント (/whoami)" if lang == "ja" else "/whoami (/アカウント)",
        "yonerai sessions": "/セッション (/sessions)" if lang == "ja" else "/sessions (/セッション)",
        "yonerai logout": "/ログアウト (/logout)" if lang == "ja" else "/logout (/ログアウト)",
        "yonerai revoke <session_id>": "/取り消し <session_id> (/revoke <session_id>)" if lang == "ja" else "/revoke <session_id> (/取り消し <session_id>)",
        "yonerai projects": "/プロジェクト (/projects)" if lang == "ja" else "/projects (/プロジェクト)",
        "yonerai projects current": "/プロジェクト 現在 (/projects current)" if lang == "ja" else "/projects current (/プロジェクト 現在)",
        "yonerai projects use <project_id>": "/プロジェクト 使う <project_id> (/projects use <project_id>)" if lang == "ja" else "/projects use <project_id> (/プロジェクト 使う <project_id>)",
        "yonerai ping": "/疎通 (/ping)" if lang == "ja" else "/ping (/疎通)",
        "yonerai rate-limit": "/レート (/rate-limit)" if lang == "ja" else "/rate-limit (/レート)",
        "yonerai update": "/更新 (/update)" if lang == "ja" else "/update (/更新)",
        "yonerai update stable": "/更新 安定版 (/update stable)" if lang == "ja" else "/update stable (/更新 安定版)",
        "yonerai update alpha": "/更新 ベータ版 (/update beta)" if lang == "ja" else "/update beta (/更新 ベータ版)",
        "yonerai update beta": "/更新 ベータ版 (/update beta)" if lang == "ja" else "/update beta (/更新 ベータ版)",
        "yonerai update apply stable --yes": "/更新 適用 安定版 確認 (/update apply stable confirm)" if lang == "ja" else "/update apply stable confirm (/更新 適用 安定版 確認)",
        "yonerai update apply beta --yes": "/更新 適用 ベータ版 確認 (/update apply beta confirm)" if lang == "ja" else "/update apply beta confirm (/更新 適用 ベータ版 確認)",
        "yonerai auth status": "/認証 (/auth)" if lang == "ja" else "/auth (/認証)",
    }
    return mapping.get(value, value)


def _interactive_commands(lang: str, *commands: str) -> str:  # noqa: F811
    return " / ".join(_interactive_next_command(command, lang=lang) for command in commands)


def format_control_spine_tui(report: dict[str, Any], *, lang: str = "ja") -> str:  # noqa: F811
    operation = str(report.get("operation") or "control_spine")
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    backend = _safe(report.get("backend_url") or "https://api-staging.yonerai.com")
    skew = report.get("contract_skew") if isinstance(report.get("contract_skew"), dict) else {}

    if lang != "ja":
        return format_control_spine_compact(report, lang=lang)

    title_map = {
        "whoami": "アカウント",
        "session_list": "セッション",
        "session_revoke": "セッション取り消し",
        "staging_logout": "ログアウト",
        "project_list": "プロジェクト",
        "project_current": "プロジェクト",
        "project_use": "プロジェクト",
        "api_ping": "疎通確認",
        "api_rate_limit": "レート制限",
        "api_status": "認証 / API",
        "audit_list": "監査",
    }
    lines = [title_map.get(operation, "Control Spine")]

    if operation == "whoami":
        account = report.get("account") if isinstance(report.get("account"), dict) else {}
        email = _safe(account.get("email_redacted") or account.get("display_name") or "未連携")
        auth_state = _safe(report.get("auth_state") or ("linked" if report.get("ok") else "unauthenticated"))
        lines.extend(
            (
                f"  状態: {auth_state}",
                f"  アカウント: {email}",
                f"  セッション期限: {_safe(report.get('session_expires_at') or '未連携')}",
                f"  次: {_interactive_commands(lang, 'yonerai sessions', 'yonerai logout') if report.get('ok') else _interactive_next_command('yonerai login', lang=lang)}",
            )
        )
    elif operation == "session_list":
        sessions = report.get("sessions") if isinstance(report.get("sessions"), list) else []
        lines.append(f"  件数: {len(sessions)}")
        for session in sessions[:3]:
            if isinstance(session, dict):
                lines.append(f"  - {_compact_session_summary(session, lang)}")
        lines.append(f"  次: {_interactive_commands(lang, 'yonerai revoke <session_id>', 'yonerai logout')}")
    elif operation in {"project_list", "project_current", "project_use"}:
        project = report.get("project") if isinstance(report.get("project"), dict) else {}
        current_project = report.get("current_project") if isinstance(report.get("current_project"), dict) else {}
        chosen = project or current_project
        if chosen:
            lines.append(f"  現在: {_compact_project_summary(chosen, lang)}")
        projects = report.get("projects") if isinstance(report.get("projects"), list) else []
        for item in projects[:3]:
            if isinstance(item, dict):
                lines.append(f"  - {_compact_project_summary(item, lang)}")
        lines.append(f"  次: {_interactive_commands(lang, 'yonerai projects', 'yonerai whoami')}")
    elif operation == "api_ping":
        ping = report.get("ping") if isinstance(report.get("ping"), dict) else {}
        lines.extend(
            (
                f"  応答: {_safe(ping.get('message') or 'pong')}",
                f"  接続先: {backend}",
                f"  次: {_interactive_commands(lang, 'yonerai whoami', 'yonerai rate-limit')}",
            )
        )
    elif operation == "api_rate_limit":
        rate = report.get("rate_limit") if isinstance(report.get("rate_limit"), dict) else {}
        body = rate.get("body") if isinstance(rate.get("body"), dict) else {}
        lines.extend(
            (
                f"  scope: {_safe(body.get('scope') or 'unknown')}",
                f"  allowed: {_yes_no(body.get('allowed'), lang=lang)}",
                f"  quota_exceeded: {_yes_no(body.get('quota_exceeded'), lang=lang)}",
                f"  次: {_interactive_commands(lang, 'yonerai ping', 'yonerai update')}",
            )
        )
    elif operation == "api_status":
        account_linked = "staging 連携済み" if report.get("account_linked") else "未ログイン"
        scopes = report.get("scopes") if isinstance(report.get("scopes"), list) else []
        scope_names = ", ".join(
            _safe(scope.get("name")) for scope in scopes[:4] if isinstance(scope, dict) and scope.get("name")
        ) or "未取得"
        lines.extend(
            (
                f"  接続先: {backend}",
                f"  状態: {account_linked}",
                f"  scopes: {scope_names}",
                f"  次: {_interactive_commands(lang, 'yonerai whoami', 'yonerai login')}",
            )
        )
    elif operation == "audit_list":
        events = report.get("events") if isinstance(report.get("events"), list) else []
        lines.append(f"  件数: {len(events)}")
        for event in events[:3]:
            if isinstance(event, dict):
                lines.append(f"  - {_safe(event.get('summary') or event.get('event_type') or 'event')}")
        lines.append(f"  次: {_interactive_next_command('yonerai auth status', lang=lang)}")
    else:
        lines.extend(
            (
                f"  接続先: {backend}",
                f"  次: {_interactive_commands(lang, 'yonerai login', 'yonerai whoami')}",
            )
        )

    if error:
        lines.append(f"  注意: {_safe(_error_message(error, lang))}")
        if error.get("next_safe_command"):
            lines.append(f"  次: {_safe(_interactive_next_command(str(error.get('next_safe_command')), lang=lang))}")
    if skew.get("skew_detected"):
        lines.append(f"  契約差分: {_safe(_contract_skew_message(skew, lang))}")
    lines.append("  境界: shared trafficオフ / private upload無効 / 本番ログイン無効")
    lines.append("")
    return "\n".join(lines)


# Clean UTF-8 overrides for interactive Control Spine surfaces.
def format_staging_login_hint(*, lang: str = "ja") -> str:  # noqa: F811
    if lang != "ja":
        return (
            "Only alpha/staging Google login is available here.\n"
            "Try: /login (Japanese: /ログイン)\n"
            "Target: https://api-staging.yonerai.com\n"
            "Production login is unavailable in this build.\n"
            "No Google token storage, no refresh token storage, and no automatic private sync.\n"
        )
    return (
        "ここで使えるのは α/staging の Google ログインだけです。\n"
        "試す: /ログイン （英語: /login）\n"
        "接続先: https://api-staging.yonerai.com\n"
        "本番ログインはこの build では使えません。\n"
        "Google token / refresh token は保存しません。private 自動同期もしません。\n"
    )


def format_login_flow_compact(report: dict[str, Any], *, lang: str = "ja") -> str:  # noqa: F811
    staging = report.get("staging") if isinstance(report.get("staging"), dict) else {}
    staging_available = bool(
        report.get("staging_login_available")
        or report.get("configured")
        or staging.get("configured")
        or report.get("staging_login")
    )
    if not staging_available:
        return format_staging_login_hint(lang=lang)

    linked_claim = report.get("staging_linked_claim") if isinstance(report.get("staging_linked_claim"), dict) else {}
    account = linked_claim.get("account") if isinstance(linked_claim.get("account"), dict) else {}
    bridge = report.get("cli_bridge") if isinstance(report.get("cli_bridge"), dict) else {}
    linked = bool(report.get("staging_linked"))
    auth_url = _safe(report.get("authorization_url") or bridge.get("browser_start_url") or "")
    expires_at = _safe(linked_claim.get("expires_at") or report.get("expires_at") or "unknown")
    email = _safe(account.get("email_redacted") or account.get("display_name") or "not linked")
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    error_message = _safe(error.get("message") or "")
    next_safe_command = _safe(_interactive_next_command(str(report.get("next_safe_command") or "yonerai login"), lang=lang))

    if lang != "ja":
        lines = ["Staging login"]
        if linked:
            lines.extend(
                (
                    "  state: linked",
                    f"  account: {email}",
                    f"  session_expires_at: {expires_at}",
                    "  next: type normally · /auth · /sync",
                    "  boundaries: staging only / no Google token storage / no private auto-sync",
                    "",
                )
            )
            return "\n".join(lines)
        lines.append("  state: waiting for browser login")
        if report.get("browser_opened"):
            lines.append("  browser: opened")
        elif auth_url:
            lines.append("  browser: open this URL")
            lines.append(f"  {auth_url}")
        else:
            lines.append("  browser: login URL is not ready yet")
        if bridge.get("request_id"):
            lines.append(f"  request_id: {_safe(bridge.get('request_id'))}")
        if error_message:
            lines.append(f"  note: {error_message}")
        lines.append(f"  next: {next_safe_command}")
        lines.append("  boundaries: staging only / no Google token storage / no private auto-sync")
        lines.append("")
        return "\n".join(lines)

    lines = ["ログイン"]
    if linked:
        lines.extend(
            (
                "  状態: staging 連携済み",
                f"  アカウント: {email}",
                f"  セッション期限: {expires_at}",
                "  次: そのまま話す ・ /認証 ・ /同期",
                "  境界: staging のみ / Google token保存なし / refresh token保存なし / private自動同期なし",
                "",
            )
        )
        return "\n".join(lines)

    lines.append("  状態: staging ログイン待ち")
    if report.get("browser_opened"):
        lines.append("  ブラウザを開きました。表示された画面で続けてください。")
    elif auth_url:
        lines.append("  次のURLをブラウザで開いてください。")
        lines.append(f"  {auth_url}")
    else:
            lines.append("  ログインURLをまだ用意できていません。もう一度 `/ログイン` を試してください。")
    if bridge.get("request_id"):
        lines.append(f"  リクエストID: {_safe(bridge.get('request_id'))}")
    if error_message:
        lines.append(f"  補足: {error_message}")
    lines.append(f"  次: {next_safe_command}")
    lines.append("  境界: staging のみ / Google token保存なし / refresh token保存なし / private自動同期なし")
    lines.append("")
    return "\n".join(lines)


def format_control_spine_compact(report: dict[str, Any], *, lang: str = "ja") -> str:  # noqa: F811
    operation = str(report.get("operation") or "control_spine")
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    skew = report.get("contract_skew") if isinstance(report.get("contract_skew"), dict) else {}
    lines = [_compact_title(operation, lang)]

    if operation == "whoami":
        account = report.get("account") if isinstance(report.get("account"), dict) else {}
        linked_claim_account = report.get("linked_claim_account") if isinstance(report.get("linked_claim_account"), dict) else {}
        auth_state = str(report.get("auth_state") or ("linked" if report.get("ok") else "unauthenticated"))
        lines.append(f"  {_compact_state_label(report, lang)}")
        if account:
            lines.append(f"  {_compact_label('アカウント', 'account', lang)}: {_compact_account_label(account, lang=lang)}")
        elif linked_claim_account:
            lines.append(f"  {_compact_label('アカウント', 'account', lang)}: {_compact_account_label(linked_claim_account, lang=lang)}")
        if auth_state in {"linked", "expired", "revoked"}:
            lines.append(
                f"  {_compact_label('セッション期限', 'session_expires_at', lang)}: "
                f"{_safe(report.get('session_expires_at') or ('未連携' if lang == 'ja' else 'not linked'))}"
            )
        if auth_state == "linked":
            lines.append(f"  {_compact_next_label(lang)}: /セッション ・ /ログアウト")
        elif auth_state in {'expired', 'revoked'}:
            lines.append("  再ログイン: /ログイン" if lang == "ja" else "  relogin: /login")
            lines.append(f"  {_compact_next_label(lang)}: /ログイン")
        else:
            lines.append("  まだクラウド連携していません。" if lang == "ja" else "  cloud account is not linked yet.")
            if not error:
                lines.append(f"  {_compact_next_label(lang)}: /ログイン")
    elif operation == "session_list":
        sessions = report.get("sessions") if isinstance(report.get("sessions"), list) else []
        lines.append(f"  {_compact_state_label(report, lang)}")
        lines.append(
            f"  {_compact_label('件数', 'count', lang)}: {len(sessions)} / "
            f"{_compact_label('接続先', 'backend', lang)}: {_safe(report.get('backend_url') or 'not_configured')}"
        )
        if sessions:
            current = next((session for session in sessions if isinstance(session, dict) and session.get("current")), None)
            if isinstance(current, dict):
                lines.append(f"  {_compact_label('現在', 'current', lang)}: {_compact_session_summary(current, lang)}")
            others = [
                _compact_session_summary(session, lang)
                for session in sessions
                if isinstance(session, dict) and not session.get("current")
            ]
            for index, summary in enumerate(others[:2], start=1):
                lines.append(f"  {_compact_label(f'他{index}', f'other_{index}', lang)}: {summary}")
        lines.append(f"  {_compact_next_label(lang)}: /取り消し <session_id> ・ /ログアウト")
    elif operation == "session_revoke":
        session = report.get("session") if isinstance(report.get("session"), dict) else {}
        result_label = "取り消して無効化" if report.get("revoked") and lang == "ja" else "revoked" if report.get("revoked") else "未完了" if lang == "ja" else "not completed"
        lines.append(f"  {_compact_label('結果', 'result', lang)}: {result_label}")
        lines.append(
            f"  {_compact_label('対象', 'target', lang)}: "
            f"{_safe(report.get('requested_session_id') or session.get('session_id') or 'unknown')}"
        )
        if session:
            lines.append(f"  {_compact_label('状態', 'state', lang)}: {_compact_session_summary(session, lang)}")
        lines.append(f"  {_compact_next_label(lang)}: /セッション")
    elif operation == "staging_logout":
        logout_label = (
            "ローカルの staging セッションを消しました"
            if report.get("session_removed") and lang == "ja"
            else "cleared local staging session"
            if report.get("session_removed")
            else "何も消していません"
            if lang == "ja"
            else "nothing to clear"
        )
        lines.append(f"  {_compact_label('状態', 'state', lang)}: {logout_label}")
        lines.append(f"  {_compact_next_label(lang)}: /ログイン")
    elif operation == "project_list":
        projects = report.get("projects") if isinstance(report.get("projects"), list) else []
        lines.append(f"  {_compact_state_label(report, lang)}")
        current = report.get("current_project") if isinstance(report.get("current_project"), dict) else {}
        if current:
            lines.append(f"  {_compact_label('現在', 'current', lang)}: {_compact_project_summary(current, lang)}")
        for index, project in enumerate(projects[:3], start=1):
            if isinstance(project, dict):
                lines.append(f"  {_compact_label(f'候補{index}', f'project_{index}', lang)}: {_compact_project_summary(project, lang)}")
        lines.append(f"  {_compact_next_label(lang)}: /プロジェクト ・ /アカウント")
    elif operation in {"project_current", "project_use"}:
        project = report.get("project") if isinstance(report.get("project"), dict) else {}
        lines.append(f"  {_compact_state_label(report, lang)}")
        if project:
            lines.append(f"  {_compact_label('プロジェクト', 'project', lang)}: {_compact_project_summary(project, lang)}")
        if report.get("requested_project_id"):
            lines.append(f"  {_compact_label('入力', 'requested', lang)}: {_safe(report.get('requested_project_id'))}")
        lines.append(f"  {_compact_next_label(lang)}: /プロジェクト ・ /アカウント")
    elif operation == "api_ping":
        ping = report.get("ping") if isinstance(report.get("ping"), dict) else {}
        lines.append(f"  {_compact_state_label(report, lang)}")
        lines.append(f"  {_compact_label('応答', 'response', lang)}: {_safe(ping.get('message') or 'pong')}")
        lines.append(f"  {_compact_label('接続先', 'backend', lang)}: {_safe(report.get('backend_url') or 'not_configured')}")
        lines.append(f"  {_compact_next_label(lang)}: /アカウント ・ /レート")
    elif operation == "api_rate_limit":
        rate = report.get("rate_limit") if isinstance(report.get("rate_limit"), dict) else {}
        body = rate.get("body") if isinstance(rate.get("body"), dict) else {}
        lines.append(f"  {_compact_state_label(report, lang)}")
        lines.append(
            f"  {_compact_label('スコープ', 'scope', lang)}: {_safe(body.get('scope') or 'unknown')} / "
            f"{_compact_label('許可', 'allowed', lang)}: {_yes_no(body.get('allowed'), lang=lang)}"
        )
        lines.append(
            f"  {_compact_label('上限超過', 'quota', lang)}: {_yes_no(body.get('quota_exceeded'), lang=lang)} / "
            f"{_compact_label('ヘッダー', 'headers', lang)}: {', '.join(str(item) for item in report.get('rate_limit_headers_present', [])[:3]) or 'none'}"
        )
        lines.append(f"  {_compact_next_label(lang)}: /疎通 ・ /更新")
    elif operation == "api_status":
        lines.append(f"  {_compact_state_label(report, lang)}")
        lines.append(f"  {_compact_label('接続先', 'backend', lang)}: {_safe(report.get('backend_url') or 'not_configured')}")
        auth_label = "staging 連携済み" if report.get("account_linked") and lang == "ja" else "linked" if report.get("account_linked") else "未ログイン" if lang == "ja" else "not linked"
        lines.append(f"  {_compact_label('認証', 'auth', lang)}: {auth_label}")
        lines.append(f"  {_compact_next_label(lang)}: /ログイン ・ /アカウント")
    elif operation == "audit_list":
        events = report.get("events") if isinstance(report.get("events"), list) else []
        lines.append(f"  {_compact_state_label(report, lang)}")
        lines.append(f"  {_compact_label('件数', 'count', lang)}: {len(events)}")
        for index, event in enumerate(events[:3], start=1):
            if isinstance(event, dict):
                lines.append(
                    f"  {_compact_label(f'監査{index}', f'item_{index}', lang)}: "
                    f"{_safe(event.get('summary') or event.get('event_type') or 'event')}"
                )
        lines.append(f"  {_compact_next_label(lang)}: /認証")
    else:
        return format_control_spine_tui(report, lang=lang)

    if error:
        lines.append(f"  {_compact_label('補足', 'note', lang)}: {_safe(_error_message(error, lang))}")
        lines.append(
            f"  {_compact_next_label(lang)}: {_safe(_interactive_next_command(str(error.get('next_safe_command') or 'yonerai login'), lang=lang))}"
        )
    if skew and skew.get("skew_detected"):
        lines.append(f"  {_compact_label('契約差分', 'contract_warning', lang)}: {_safe(_contract_skew_message(skew, lang))}")
    lines.append(f"  {_compact_label('境界', 'boundaries', lang)}: {_compact_boundary_line(lang)}")
    lines.append("")
    return "\n".join(lines)


def format_control_spine_tui(report: dict[str, Any], *, lang: str = "ja") -> str:  # noqa: F811
    account = report.get("account") if isinstance(report.get("account"), dict) else {}
    linked_claim_account = report.get("linked_claim_account") if isinstance(report.get("linked_claim_account"), dict) else {}
    scopes = report.get("scopes") if isinstance(report.get("scopes"), list) else []
    scope_names = [_safe(scope.get("name")) for scope in scopes[:4] if isinstance(scope, dict) and scope.get("name")]
    account_candidates = (
        account.get("email_redacted"),
        account.get("display_name"),
        linked_claim_account.get("email_redacted"),
        linked_claim_account.get("display_name"),
    )
    account_label = "未連携" if lang == "ja" else "not linked"
    for candidate in account_candidates:
        text = _safe(candidate)
        if text and text not in {"not-linked", "None", "未連携"}:
            account_label = text
            break

    operation = str(report.get("operation") or "control_spine")

    if operation == "staging_logout":
        error = report.get("error") if isinstance(report.get("error"), dict) else {}
        removed = bool(report.get("session_removed"))
        if lang != "ja":
            lines = [
                "Logout",
                f"  state: {'cleared local staging session' if removed else 'nothing to clear'}",
                "  boundaries: staging only / no Google token storage / no private auto-sync",
                "  next: /login · /whoami · /sessions",
            ]
            if error:
                lines.append(f"  note: {_safe(_error_message(error, lang))}")
            lines.append("")
            return "\n".join(lines)
        lines = [
            "ログアウト",
            f"  状態: {'ローカルの staging セッションを削除しました' if removed else '削除する staging セッションはありません'}",
            "  境界: staging のみ / Google token保存なし / refresh token保存なし / private自動同期なし",
            "  次: /ログイン ・ /アカウント ・ /セッション",
        ]
        if error:
            lines.append(f"  補足: {_safe(_error_message(error, lang))}")
        lines.append("")
        return "\n".join(lines)

    if lang != "ja":
        lines = [
            "Auth / API",
            f"  backend: {_safe(report.get('backend_url') or 'not_configured')}",
            f"  state: {'linked' if report.get('account_linked') else 'not linked'} (staging only)",
            f"  account: {account_label}",
            f"  session_expires_at: {_safe(report.get('session_expires_at') or 'not-linked')}",
            f"  scopes: {', '.join(scope_names) if scope_names else 'not-fetched'}",
            "  boundaries: no production login / shared traffic off / private upload disabled",
        ]
        error = report.get("error") if isinstance(report.get("error"), dict) else {}
        if error:
            lines.append(f"  note: {_safe(_error_message(error, lang))}")
            if error.get("next_safe_command"):
                lines.append(f"  next: {_safe(_interactive_next_command(str(error.get('next_safe_command')), lang=lang))}")
        skew = report.get("contract_skew") if isinstance(report.get("contract_skew"), dict) else {}
        if skew and skew.get("skew_detected"):
            lines.append(f"  contract_warning: {_safe(_contract_skew_message(skew, lang))}")
        lines.append("  next: /whoami · /login · /sessions")
        lines.append("")
        return "\n".join(lines)

    lines = [
        "認証 / API",
        f"  接続先: {_safe(report.get('backend_url') or 'not_configured')}",
        f"  状態: {'staging 連携済み' if report.get('account_linked') else '未ログイン'}",
        f"  アカウント: {account_label}",
        f"  セッション期限: {_safe(report.get('session_expires_at') or '未連携')}",
        f"  スコープ: {', '.join(scope_names) if scope_names else '未取得'}",
        "  境界: staging のみ / OpenAI共有オフ / private upload無効",
    ]
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        lines.append(f"  補足: {_safe(_error_message(error, lang))}")
        if error.get("next_safe_command"):
            lines.append(f"  次に試す: {_safe(_interactive_next_command(str(error.get('next_safe_command')), lang=lang))}")
    skew = report.get("contract_skew") if isinstance(report.get("contract_skew"), dict) else {}
    if skew and skew.get("skew_detected"):
        lines.append(f"  契約差分: {_safe(_contract_skew_message(skew, lang))}")
    lines.append("  次: /アカウント ・ /ログイン ・ /セッション")
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
        CliRow("session_expires_at", report.get("session_expires_at") or "not-linked", "ok" if report.get("session_expires_at") else "warn"),
        CliRow("session_available", report.get("staging_session_available"), "ok" if report.get("staging_session_available") else "warn"),
        CliRow("production_login_enabled", report.get("production_login_enabled"), "fail" if report.get("production_login_enabled") else "ok"),
        CliRow("shared_traffic_enabled", report.get("shared_traffic_enabled"), "fail" if report.get("shared_traffic_enabled") else "ok"),
        CliRow("local_private_upload_enabled", report.get("local_private_upload_enabled"), "fail" if report.get("local_private_upload_enabled") else "ok"),
    ]
    if "backend_status_code" in report:
        rows.append(CliRow("backend_status_code", report.get("backend_status_code"), "ok" if report.get("ok") else "warn"))
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    if error:
        rows.append(CliRow("error", error.get("code"), "fail"))
        rows.append(CliRow("message", _error_message(error, lang), "warn"))
        rows.append(CliRow("next_action", error.get("next_safe_command") or "yonerai login", "warn"))
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
    if scope.get("requires_threat_model"):
        reason = "脅威モデル審査が必要" if lang == "ja" else "requires threat-model gate"
        return f"{state} - {reason} - {_safe(scope.get('summary') or '')}"
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
    current = "現在" if session.get("current") else "他"
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


def _error_message(error: dict[str, Any], lang: str) -> object:
    if lang == "ja" and error.get("code") == "staging_auth_required":
        return "staging セッションの再ログインが必要です。`/ログイン` を実行してください。"
    if lang == "ja" and error.get("code") == "staging_origin_not_configured":
        return "staging 接続先が未設定です。`/ログイン` の前に接続先を確認してください。"
    return error.get("message")


def _contract_skew_message(skew: dict[str, Any], lang: str) -> str:
    if not skew.get("skew_detected"):
        return "問題なし" if lang == "ja" else "ok"
    if lang == "ja":
        return "CLI と staging API の契約バージョン差があります。`/更新` を確認してください。"
    return str(skew.get("warning") or "Check `/update`.")


def _interactive_next_command(value: str, *, lang: str) -> str:
    mapping = {
        "yonerai login": "/ログイン (/login)" if lang == "ja" else "/login (/ログイン)",
        "yonerai whoami": "/アカウント (/whoami)" if lang == "ja" else "/whoami (/アカウント)",
        "yonerai sessions": "/セッション (/sessions)" if lang == "ja" else "/sessions (/セッション)",
        "yonerai logout": "/ログアウト (/logout)" if lang == "ja" else "/logout (/ログアウト)",
        "yonerai revoke <session_id>": "/取り消し <session_id> (/revoke <session_id>)" if lang == "ja" else "/revoke <session_id> (/取り消し <session_id>)",
        "yonerai projects": "/プロジェクト (/projects)" if lang == "ja" else "/projects (/プロジェクト)",
        "yonerai projects current": "/プロジェクト 現在 (/projects current)" if lang == "ja" else "/projects current (/プロジェクト 現在)",
        "yonerai projects use <project_id>": "/プロジェクト 使う <project_id> (/projects use <project_id>)" if lang == "ja" else "/projects use <project_id> (/プロジェクト 使う <project_id>)",
        "yonerai ping": "/疎通 (/ping)" if lang == "ja" else "/ping (/疎通)",
        "yonerai rate-limit": "/レート (/rate-limit)" if lang == "ja" else "/rate-limit (/レート)",
        "yonerai update": "/更新 (/update)" if lang == "ja" else "/update (/更新)",
        "yonerai update stable": "/更新 安定版 (/update stable)" if lang == "ja" else "/update stable (/更新 安定版)",
        "yonerai update alpha": "/更新 ベータ版 (/update beta)" if lang == "ja" else "/update beta (/更新 ベータ版)",
        "yonerai update beta": "/更新 ベータ版 (/update beta)" if lang == "ja" else "/update beta (/更新 ベータ版)",
        "yonerai update apply stable --yes": "/更新 適用 安定版 確認 (/update apply stable confirm)" if lang == "ja" else "/update apply stable confirm (/更新 適用 安定版 確認)",
        "yonerai update apply beta --yes": "/更新 適用 ベータ版 確認 (/update apply beta confirm)" if lang == "ja" else "/update apply beta confirm (/更新 適用 ベータ版 確認)",
        "yonerai auth status": "/認証 (/auth)" if lang == "ja" else "/auth (/認証)",
    }
    return mapping.get(value, value)


def _interactive_commands(lang: str, *commands: str) -> str:
    separator = " ・ " if lang == "ja" else " / "
    return separator.join(_interactive_next_command(command, lang=lang) for command in commands)


def _compact_title(operation: str, lang: str) -> str:
    if lang == "ja":
        return {
            "whoami": "アカウント",
            "session_list": "セッション",
            "session_revoke": "セッション取り消し",
            "staging_logout": "ログアウト",
            "project_list": "プロジェクト",
            "project_current": "現在のプロジェクト",
            "project_use": "プロジェクト選択",
            "api_ping": "API ping",
            "api_rate_limit": "レート制限",
            "api_status": "API 状態",
            "audit_list": "監査",
        }.get(operation, "Control Spine")
    return {
        "whoami": "Account",
        "session_list": "Sessions",
        "session_revoke": "Session revoke",
        "staging_logout": "Logout",
        "project_list": "Projects",
        "project_current": "Current project",
        "project_use": "Project selection",
        "api_ping": "API ping",
        "api_rate_limit": "Rate limit",
        "api_status": "API status",
        "audit_list": "Audit",
    }.get(operation, "Control Spine")


def _compact_label(ja: str, en: str, lang: str) -> str:
    return ja if lang == "ja" else en


def _compact_next_label(lang: str) -> str:
    return "次" if lang == "ja" else "next"


def _compact_boundary_line(lang: str) -> str:
    if lang == "ja":
        return "staging のみ / 本番ログインなし / Google token保存なし / OpenAI共有オフ / private upload無効"
    return "staging only / no production login / no Google token storage / shared traffic off / private upload disabled"


def _compact_state_label(report: dict[str, Any], lang: str) -> str:
    if report.get("ok"):
        return "状態: 利用可能" if lang == "ja" else "state: available"
    auth_state = str(report.get("auth_state") or "")
    if auth_state in {"expired", "revoked", "unauthenticated"}:
        mapping = {
            "expired": "期限切れ",
            "revoked": "取り消し済み",
            "unauthenticated": "未ログイン",
        }
        if lang == "ja":
            return f"状態: {mapping.get(auth_state, '未ログイン')}"
        return f"state: {auth_state}"
    return "状態: 要確認" if lang == "ja" else "state: needs attention"


def _compact_account_label(account: dict[str, Any], *, lang: str) -> str:
    value = _safe(account.get("email_redacted") or account.get("display_name") or "not-linked")
    if value == "not-linked":
        return "未連携" if lang == "ja" else "not linked"
    return value


def _compact_project_summary(project: dict[str, Any], lang: str) -> str:
    name = _safe(project.get("name") or project.get("project_id") or "unknown")
    project_id = _safe(project.get("project_id") or "unknown")
    current = "現在" if project.get("current") else "候補"
    if lang != "ja":
        current = "current" if project.get("current") else "available"
    return f"{name} ({project_id}, {current})"


def _compact_session_summary(session: dict[str, Any], lang: str) -> str:
    session_id = _safe(session.get("session_id") or "unknown")
    status = _safe(session.get("status") or "unknown")
    expires_at = _safe(session.get("expires_at") or "unknown")
    current = "現在" if session.get("current") else "他"
    if lang != "ja":
        current = "current" if session.get("current") else "other"
    return f"{session_id} / {status} / {current} / expires={expires_at}"


def _yes_no(value: object, *, lang: str) -> str:
    if lang == "ja":
        return "はい" if value else "いいえ"
    return "yes" if value else "no"
