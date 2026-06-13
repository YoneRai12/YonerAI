from __future__ import annotations

from typing import Any

from yonerai_cli.screens.labels import _safe

_DEFAULT_BACKEND = "https://api-staging.yonerai.com"


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
    }
    callback = mapping.get(command)
    if callback is None:
        return None
    report = callback(lang)
    if report is None:
        return None
    return format_control_spine_tui(report, lang=lang)


def format_staging_login_hint(*, lang: str = "ja") -> str:
    if lang == "ja":
        return (
            "ログイン\n"
            "  ここで使えるのは α/staging の Google ログインだけです。\n"
            "  試す: /ログイン (/login)\n"
            f"  接続先: {_DEFAULT_BACKEND}\n"
            "  本番ログインはこの build では使えません。\n"
            "  境界: Google token保存なし / refresh token保存なし / private自動アップロードなし\n"
        )
    return (
        "Login\n"
        "  Only alpha/staging Google login is available here.\n"
        "  Try: /login\n"
        f"  Target: {_DEFAULT_BACKEND}\n"
        "  Production login is unavailable in this build.\n"
        "  Boundaries: no Google token storage / no refresh token storage / no private auto-upload\n"
    )


def format_login_flow_compact(report: dict[str, Any], *, lang: str = "ja") -> str:
    staging = report.get("staging") if isinstance(report.get("staging"), dict) else {}
    bridge = report.get("cli_bridge") if isinstance(report.get("cli_bridge"), dict) else {}
    linked_claim = report.get("staging_linked_claim") if isinstance(report.get("staging_linked_claim"), dict) else {}
    account = linked_claim.get("account") if isinstance(linked_claim.get("account"), dict) else {}
    staging_available = bool(
        report.get("staging_login_available")
        or report.get("configured")
        or staging.get("configured")
        or report.get("staging_login")
    )
    if not staging_available:
        return format_staging_login_hint(lang=lang)

    linked = bool(report.get("staging_linked"))
    auth_url = _safe(report.get("authorization_url") or bridge.get("browser_start_url") or "")
    expires_at = _safe(linked_claim.get("expires_at") or report.get("expires_at") or "unknown")
    account_label = _safe(account.get("email_redacted") or account.get("display_name") or "not linked")
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    error_message = _safe(error.get("message") or "")
    next_safe_command = _safe(_interactive_next_command(str(report.get("next_safe_command") or "yonerai login"), lang=lang))

    if lang != "ja":
        lines = ["Staging login"]
        if linked:
            lines.extend(
                (
                    "  state: linked",
                    f"  account: {account_label}",
                    f"  session_expires_at: {expires_at}",
                    "  next: type normally · /auth · /sync",
                    "  boundaries: staging only / no Google token storage / no refresh token storage / no private auto-upload",
                    "",
                )
            )
            return "\n".join(lines)
        lines.append("  state: waiting for browser login")
        if report.get("browser_opened"):
            lines.append("  browser: opened")
        elif auth_url:
            lines.append("  next URL: open this in your browser")
            lines.append(f"  {auth_url}")
        else:
            lines.append("  browser URL is not ready yet")
        if error_message:
            lines.append(f"  note: {error_message}")
        lines.append(f"  next: {next_safe_command}")
        lines.append("  boundaries: staging only / no Google token storage / no refresh token storage / no private auto-upload")
        lines.append("")
        return "\n".join(lines)

    lines = ["ログイン"]
    if linked:
        lines.extend(
            (
                "  状態: staging 連携済み",
                f"  アカウント: {account_label}",
                f"  セッション期限: {expires_at}",
                "  次: そのまま話す ・ /認証 (/auth) ・ /同期 (/sync)",
                "  境界: stagingのみ / Google token保存なし / refresh token保存なし / private自動アップロードなし",
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
        lines.append("  ログインURLをまだ用意できていません。もう一度 /ログイン (/login) を試してください。")
    if error_message:
        lines.append(f"  注意: {error_message}")
    lines.append(f"  次: {next_safe_command}")
    lines.append("  境界: stagingのみ / Google token保存なし / refresh token保存なし / private自動アップロードなし")
    lines.append("")
    return "\n".join(lines)


def format_control_spine_tui(report: dict[str, Any], *, lang: str = "ja") -> str:
    return _format_control_spine_tui_ja(report) if lang == "ja" else _format_control_spine_tui_en(report)


def _format_control_spine_tui_ja(report: dict[str, Any]) -> str:
    operation = str(report.get("operation") or "control_spine")
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    backend = _safe(report.get("backend_url") or _DEFAULT_BACKEND)
    skew = report.get("contract_skew") if isinstance(report.get("contract_skew"), dict) else {}
    lines = [_title_ja(operation)]
    next_hint: str | None = None

    if operation == "whoami":
        account = report.get("account") if isinstance(report.get("account"), dict) else {}
        email = _safe(account.get("email_redacted") or account.get("display_name") or "未連携")
        auth_state = _ja_auth_state(report)
        lines.extend(
            (
                f"  状態: {auth_state}",
                f"  アカウント: {email}",
                f"  セッション期限: {_safe(report.get('session_expires_at') or '未連携')}",
            )
        )
        next_hint = _interactive_commands("ja", "yonerai sessions", "yonerai logout") if report.get("ok") else _interactive_next_command("yonerai login", lang="ja")
    elif operation == "session_list":
        sessions = report.get("sessions") if isinstance(report.get("sessions"), list) else []
        lines.append(f"  件数: {len(sessions)}")
        for session in sessions[:3]:
            if isinstance(session, dict):
                lines.append(f"  - {_session_summary(session, lang='ja')}")
        next_hint = _interactive_commands("ja", "yonerai revoke <session_id>", "yonerai logout")
    elif operation in {"project_list", "project_current", "project_use"}:
        project = report.get("project") if isinstance(report.get("project"), dict) else {}
        current_project = report.get("current_project") if isinstance(report.get("current_project"), dict) else {}
        chosen = project or current_project
        if chosen:
            lines.append(f"  現在: {_project_summary(chosen, lang='ja')}")
        projects = report.get("projects") if isinstance(report.get("projects"), list) else []
        for item in projects[:3]:
            if isinstance(item, dict):
                lines.append(f"  - {_project_summary(item, lang='ja')}")
        next_hint = _interactive_commands("ja", "yonerai projects", "yonerai whoami")
    elif operation == "api_ping":
        ping = report.get("ping") if isinstance(report.get("ping"), dict) else {}
        ping_message = _safe(ping.get("message") or ("pong" if report.get("ok") else "未実行"))
        lines.extend((f"  応答: {ping_message}", f"  接続先: {backend}"))
        next_hint = _interactive_commands("ja", "yonerai whoami", "yonerai rate-limit")
    elif operation == "api_rate_limit":
        rate = report.get("rate_limit") if isinstance(report.get("rate_limit"), dict) else {}
        body = rate.get("body") if isinstance(rate.get("body"), dict) else {}
        lines.extend(
            (
                f"  scope: {_safe(body.get('scope') or 'unknown')}",
                f"  allowed: {_yes_no(body.get('allowed'), lang='ja')}",
                f"  quota_exceeded: {_yes_no(body.get('quota_exceeded'), lang='ja')}",
            )
        )
        next_hint = _interactive_commands("ja", "yonerai ping", "yonerai update")
    elif operation == "api_status":
        scopes = report.get("scopes") if isinstance(report.get("scopes"), list) else []
        scope_names = ", ".join(
            _safe(scope.get("name")) for scope in scopes[:4] if isinstance(scope, dict) and scope.get("name")
        ) or "未取得"
        lines.extend(
            (
                f"  接続先: {backend}",
                f"  状態: {'staging 連携済み' if report.get('account_linked') else '未ログイン'}",
                f"  scopes: {scope_names}",
            )
        )
        next_hint = _interactive_commands("ja", "yonerai whoami", "yonerai login")
    elif operation == "audit_list":
        events = report.get("events") if isinstance(report.get("events"), list) else []
        lines.append(f"  件数: {len(events)}")
        for event in events[:3]:
            if isinstance(event, dict):
                lines.append(f"  - {_safe(event.get('summary') or event.get('event_type') or 'event')}")
        next_hint = _interactive_next_command("yonerai auth status", lang="ja")
    else:
        lines.append(f"  接続先: {backend}")
        next_hint = _interactive_commands("ja", "yonerai login", "yonerai whoami")

    if error:
        lines.append(f"  注意: {_ja_error_message(error)}")
        if error.get("next_safe_command"):
            next_hint = _safe(_interactive_next_command(str(error.get('next_safe_command')), lang="ja"))
    if next_hint:
        lines.append(f"  次: {next_hint}")
    if skew.get("skew_detected"):
        lines.append(f"  契約差分: {_contract_skew_message(skew, 'ja')}")
    lines.append("  境界: shared trafficオフ / private upload無効 / 本番ログイン無効")
    lines.append("")
    return "\n".join(lines)


def _format_control_spine_tui_en(report: dict[str, Any]) -> str:
    operation = str(report.get("operation") or "control_spine")
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    backend = _safe(report.get("backend_url") or _DEFAULT_BACKEND)
    skew = report.get("contract_skew") if isinstance(report.get("contract_skew"), dict) else {}
    lines = [_title_en(operation)]

    if operation == "whoami":
        account = report.get("account") if isinstance(report.get("account"), dict) else {}
        lines.extend(
            (
                f"  state: {_effective_auth_state(report)}",
                f"  account: {_safe(account.get('email_redacted') or account.get('display_name') or 'not linked')}",
                f"  session_expires_at: {_safe(report.get('session_expires_at') or 'not linked')}",
            )
        )
    else:
        lines.append(f"  backend: {backend}")

    if error:
        lines.append(f"  note: {_safe(error.get('message') or 'needs attention')}")
    if skew.get("skew_detected"):
        lines.append(f"  contract_warning: {_contract_skew_message(skew, 'en')}")
    lines.append(f"  next: {_interactive_commands('en', 'yonerai login', 'yonerai whoami')}")
    lines.append("  boundaries: shared traffic off / private upload disabled / production login unavailable")
    lines.append("")
    return "\n".join(lines)


def _interactive_next_command(value: str, *, lang: str) -> str:
    mapping = {
        "yonerai login": ("/ログイン (/login)", "/login (/ログイン)"),
        "yonerai whoami": ("/アカウント (/whoami)", "/whoami (/アカウント)"),
        "yonerai sessions": ("/セッション (/sessions)", "/sessions (/セッション)"),
        "yonerai logout": ("/ログアウト (/logout)", "/logout (/ログアウト)"),
        "yonerai revoke <session_id>": ("/取り消し <session_id> (/revoke <session_id>)", "/revoke <session_id> (/取り消し <session_id>)"),
        "yonerai projects": ("/プロジェクト (/projects)", "/projects (/プロジェクト)"),
        "yonerai projects current": ("/プロジェクト 現在 (/projects current)", "/projects current (/プロジェクト 現在)"),
        "yonerai projects use <project_id>": ("/プロジェクト 使う <project_id> (/projects use <project_id>)", "/projects use <project_id> (/プロジェクト 使う <project_id>)"),
        "yonerai ping": ("/疎通 (/ping)", "/ping (/疎通)"),
        "yonerai rate-limit": ("/レート (/rate-limit)", "/rate-limit (/レート)"),
        "yonerai update": ("/更新 (/update)", "/update (/更新)"),
        "yonerai update stable": ("/更新 安定版 (/update stable)", "/update stable (/更新 安定版)"),
        "yonerai update alpha": ("/更新 ベータ版 (/update beta)", "/update beta (/更新 ベータ版)"),
        "yonerai update beta": ("/更新 ベータ版 (/update beta)", "/update beta (/更新 ベータ版)"),
        "yonerai update apply stable --yes": ("/更新 適用 安定版 確認 (/update apply stable confirm)", "/update apply stable confirm (/更新 適用 安定版 確認)"),
        "yonerai update apply beta --yes": ("/更新 適用 ベータ版 確認 (/update apply beta confirm)", "/update apply beta confirm (/更新 適用 ベータ版 確認)"),
        "yonerai auth status": ("/認証 (/auth)", "/auth (/認証)"),
    }
    ja, en = mapping.get(value, (value, value))
    return ja if lang == "ja" else en


def _interactive_commands(lang: str, *commands: str) -> str:
    separator = " ・ " if lang == "ja" else " · "
    return separator.join(_interactive_next_command(command, lang=lang) for command in commands)


def _ja_error_message(error: dict[str, Any]) -> str:
    code = str(error.get("code") or "")
    if code == "staging_auth_required":
        return "staging セッションが未ログイン、または期限切れです。/ログイン (/login) を使ってください。"
    if code == "staging_origin_not_configured":
        return "staging 接続先が未設定です。/ログイン の前に接続先を確認してください。"
    return _safe(error.get("message") or "要確認")


def _contract_skew_message(skew: dict[str, Any], lang: str) -> str:
    if not skew.get("skew_detected"):
        return "ok" if lang != "ja" else "正常"
    if lang == "ja":
        return "CLI と staging API の契約差分があります。/更新 (/update) を確認してください。"
    return _safe(skew.get("warning") or "Check /update.")


def _title_ja(operation: str) -> str:
    return {
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
    }.get(operation, "Control Spine")


def _title_en(operation: str) -> str:
    return {
        "whoami": "Account",
        "session_list": "Sessions",
        "session_revoke": "Session revoke",
        "staging_logout": "Logout",
        "project_list": "Projects",
        "project_current": "Project",
        "project_use": "Project",
        "api_ping": "Ping",
        "api_rate_limit": "Rate limit",
        "api_status": "Auth / API",
        "audit_list": "Audit",
    }.get(operation, "Control Spine")


def _ja_auth_state(report: dict[str, Any]) -> str:
    return {
        "linked": "staging 連携済み",
        "expired": "期限切れ",
        "revoked": "取り消し済み",
        "pending": "待機中",
        "unauthenticated": "未ログイン",
    }.get(_effective_auth_state(report), "未ログイン")


def _effective_auth_state(report: dict[str, Any]) -> str:
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    state = str(report.get("auth_state") or ("linked" if report.get("ok") else "unauthenticated"))
    if error.get("code") != "staging_auth_required":
        return state
    if state in {"expired", "revoked", "pending"}:
        return state
    if report.get("session_expires_at"):
        return "expired"
    return "unauthenticated"


def _project_summary(project: dict[str, Any], *, lang: str) -> str:
    name = _safe(project.get("name") or project.get("project_id") or "unknown")
    project_id = _safe(project.get("project_id") or "unknown")
    state = "現在" if project.get("current") else "利用可"
    if lang != "ja":
        state = "current" if project.get("current") else "available"
    return f"{name} ({project_id}, {state})"


def _session_summary(session: dict[str, Any], *, lang: str) -> str:
    session_id = _safe(session.get("session_id") or "unknown")
    status = _safe(session.get("status") or "unknown")
    expires_at = _safe(session.get("expires_at") or "unknown")
    role = "現在" if session.get("current") else "別"
    if lang != "ja":
        role = "current" if session.get("current") else "other"
    return f"{session_id} / {status} / {role} / expires={expires_at}"


def _yes_no(value: object, *, lang: str) -> str:
    if lang == "ja":
        return "はい" if value else "いいえ"
    return "yes" if value else "no"
