from __future__ import annotations

from collections.abc import Mapping

from yonerai_cli.auth_policy import build_google_auth_status, build_privacy_status
from yonerai_cli.screens.labels import _safe, _value_label, _yes_no


DEFAULT_STAGING_ORIGIN = "https://api-staging.yonerai.com"


def format_auth_status_report(report: Mapping[str, object], *, lang: str = "ja") -> str:
    staging = report.get("staging") if isinstance(report.get("staging"), dict) else {}
    session_claim = report.get("staging_session_claim") if isinstance(report.get("staging_session_claim"), dict) else {}
    staging_session = report.get("staging_session") if isinstance(report.get("staging_session"), dict) else {}
    linked_claim = report.get("staging_linked_claim") if isinstance(report.get("staging_linked_claim"), dict) else {}
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    session_state = str(session_claim.get("auth_state") or "unauthenticated")
    saved_claim_state = str(staging_session.get("auth_state") or "unauthenticated")

    raw_state = str(
        report.get("staging_auth_state")
        or session_state
        or saved_claim_state
        or "unauthenticated"
    )
    auth_state = _auth_state_label(
        raw_state,
        lang=lang,
        session_state=session_state,
        saved_claim_state=saved_claim_state,
    )
    account_label = _friendly_auth_account_label(report, lang=lang)
    expires_fallback = "不明" if lang == "ja" else "unknown"
    if raw_state == "unauthenticated":
        expires_fallback = "未連携" if lang == "ja" else "not linked"
    expires_at = _safe(
        session_claim.get("expires_at")
        or linked_claim.get("expires_at")
        or staging_session.get("expires_at")
        or expires_fallback
    )
    staging_origin = _friendly_staging_origin(
        staging=staging,
        session_claim=session_claim,
        staging_session=staging_session,
        linked_claim=linked_claim,
    )
    error_code = str(error.get("code") or "") if error else ""
    staging_label = _friendly_staging_label(
        staging_ready=bool(staging.get("configured")),
        error_code=error_code,
        lang=lang,
    )
    next_command = _safe(_friendly_next_command(raw_state, report=report, lang=lang))
    note = _friendly_auth_note(
        raw_state=raw_state,
        error_code=error_code,
        error_message=_safe(error.get("message") or "") if error else "",
        lang=lang,
    )
    if raw_state == "unauthenticated" and not error_code:
        note = ""
    backend_check = _friendly_backend_check(
        raw_state=raw_state,
        session_state=session_state,
        saved_claim_state=saved_claim_state,
        lang=lang,
    )

    if lang == "ja":
        lines = ["認証", f"  状態: {auth_state} / Google α-staging", f"  アカウント: {account_label}"]
        if raw_state in {"linked", "expired", "revoked"}:
            lines.append(f"  セッション期限: {expires_at}")
        if raw_state in {"unauthenticated", "pending"}:
            lines.append(f"  接続先: {staging_origin}")
        if backend_check:
            lines.append(f"  backend確認: {backend_check}")
        lines.append("  本番: 使えません")
        lines.append(f"  次: {next_command}")
        lines.append("  境界: token保存なし / refresh保存なし / private自動アップロードなし")
        if raw_state in {"expired", "revoked"}:
            lines.append("  再ログイン: `/ログイン` （英語: `/login`）")
        elif raw_state == "unauthenticated":
            lines.append("  案内: `/ログイン` （英語: `/login`）でブラウザ連携を始めます。")
        if note and raw_state not in {"unauthenticated", "expired", "revoked"}:
            lines.append(f"  補足: {note}")
        lines.append("")
        return "\n".join(lines)

    lines = ["Auth", f"  state: {auth_state} / Google alpha-staging", f"  account: {account_label}"]
    if raw_state in {"linked", "expired", "revoked"}:
        lines.append(f"  session_expires_at: {expires_at}")
    if raw_state in {"unauthenticated", "pending"}:
        lines.append(f"  staging_origin: {staging_origin}")
    if backend_check:
        lines.append(f"  backend_check: {backend_check}")
    lines.append("  production: unavailable")
    lines.append(f"  next: {next_command}")
    lines.append("  boundaries: no Google token storage / no refresh token storage / no private auto-upload")
    if raw_state in {"expired", "revoked"}:
        lines.append("  relogin: `/login` (Japanese: `/ログイン`)")
    elif raw_state == "unauthenticated":
        lines.append("  guide: use `/login` (Japanese: `/ログイン`) to start browser sign-in")
    if note and raw_state not in {"unauthenticated", "expired", "revoked"}:
        lines.append(f"  note: {note}")
    lines.append("")
    return "\n".join(lines)


def _format_auth_status(config: dict[str, object], *, lang: str) -> str:
    report = build_google_auth_status(config, claim_path=str(config.get("_runtime_config_path") or "") or None)
    return format_auth_status_report(report, lang=lang)


def _auth_state_label(
    value: object,
    *,
    lang: str,
    session_state: str = "unauthenticated",
    saved_claim_state: str = "unauthenticated",
) -> str:
    state = str(value or "unauthenticated")
    if lang == "ja":
        if state == "linked" and session_state == "linked":
            return "保存済みセッションあり"
        if state == "linked" and saved_claim_state == "linked":
            return "前回の連携記録あり"
        return {
            "pending": "ログイン待ち",
            "expired": "期限切れ",
            "revoked": "取り消し済み",
            "unauthenticated": "未ログイン",
        }.get(state, state)
    if state == "linked" and session_state == "linked":
        return "saved staging session"
    if state == "linked" and saved_claim_state == "linked":
        return "previously linked"
    return {
        "pending": "waiting for login (staging only)",
        "expired": "expired (staging only)",
        "revoked": "revoked (staging only)",
        "unauthenticated": "not linked (staging only)",
    }.get(state, f"{state} (staging only)")


def _friendly_auth_account_label(report: Mapping[str, object], *, lang: str) -> str:
    for candidate in (
        report.get("staging_account"),
        report.get("staging_session_claim"),
        report.get("staging_linked_claim"),
        report.get("staging_session"),
    ):
        if isinstance(candidate, Mapping):
            email = str(candidate.get("email_redacted") or candidate.get("redacted_email") or "").strip()
            if email and email != "not-linked":
                return _safe(email)
            display_name = str(candidate.get("display_name") or "").strip()
            if display_name and display_name != "not-linked":
                if display_name == "linked staging account":
                    return "保存済みアカウント" if lang == "ja" else "saved staging account"
                return _safe(display_name)
            account = candidate.get("account")
            if isinstance(account, Mapping):
                nested_email = str(account.get("email_redacted") or account.get("redacted_email") or "").strip()
                if nested_email and nested_email != "not-linked":
                    return _safe(nested_email)
                nested_display_name = str(account.get("display_name") or "").strip()
                if nested_display_name and nested_display_name != "not-linked":
                    if nested_display_name == "linked staging account":
                        return "保存済みアカウント" if lang == "ja" else "saved staging account"
                    return _safe(nested_display_name)
    return "未連携" if lang == "ja" else "not linked"


def _friendly_staging_origin(
    *,
    staging: Mapping[str, object],
    session_claim: Mapping[str, object],
    staging_session: Mapping[str, object],
    linked_claim: Mapping[str, object],
) -> str:
    for candidate in (
        staging.get("origin"),
        session_claim.get("origin"),
        linked_claim.get("origin"),
        staging_session.get("origin"),
    ):
        value = str(candidate or "").strip()
        if value and value not in {"not_configured", "invalid_or_disallowed", "configured"}:
            return _safe(value)
    return DEFAULT_STAGING_ORIGIN


def _friendly_staging_label(*, staging_ready: bool, error_code: str, lang: str) -> str:
    if staging_ready:
        return "簡単ログイン可 (既定の staging 接続先)" if lang == "ja" else "available (staging)"
    if error_code.startswith("staging_origin_") and error_code != "staging_auth_origin_not_configured":
        return (
            "設定値が不正です。allowlisted HTTPS host に戻してください"
            if lang == "ja"
            else "configured value is invalid; use an allowlisted HTTPS host"
        )
    return "簡単ログイン可 (既定の staging 接続先)" if lang == "ja" else "available (staging)"


def _friendly_auth_note(
    *,
    raw_state: str,
    error_code: str,
    error_message: str,
    lang: str,
) -> str:
    if raw_state == "unauthenticated":
        return (
            "まだクラウド連携していません。`/ログイン`（英語: `/login`）でブラウザ連携を始められます。"
            if lang == "ja"
            else "Your cloud account is not linked yet. Use `/login` (Japanese: `/ログイン`) to start browser sign-in."
        )
    if raw_state == "linked":
        return ""
    if error_code == "google_oauth_client_not_configured":
        return (
            "この CLI に Google client secret は保存しません。ログイン処理は staging 側で完了します。"
            if lang == "ja"
            else "This CLI does not keep a Google client secret. Sign-in is completed on the staging side."
        )
    if error_code == "staging_auth_origin_not_configured":
        return (
            f"環境変数は通常不要です。既定では {DEFAULT_STAGING_ORIGIN} を使います。"
            if lang == "ja"
            else f"You do not need env vars unless you want a different staging target. The default is {DEFAULT_STAGING_ORIGIN}."
        )
    if error_code.startswith("staging_origin_"):
        return (
            "staging 接続先が不正です。allowlisted HTTPS host に戻してください。"
            if lang == "ja"
            else "The current staging origin setting is invalid. Replace it with an allowlisted HTTPS host."
        )
    return error_message


def _friendly_next_command(raw_state: str, *, report: Mapping[str, object], lang: str) -> str:
    if raw_state == "linked":
        return (
            "アカウント (/アカウント / whoami) ・ 同期 (/同期 / sync) ・ そのまま話す"
            if lang == "ja"
            else "account (/whoami / アカウント) · sync (/sync / 同期) · talk normally"
        )
    if raw_state in {"expired", "revoked", "unauthenticated"}:
        return "/ログイン ・ /login" if lang == "ja" else "/login"
    return str(report.get("next_safe_command") or ("/login" if lang != "ja" else "/ログイン ・ /login"))


def _friendly_backend_check(
    *,
    raw_state: str,
    session_state: str,
    saved_claim_state: str,
    lang: str,
) -> str:
    if raw_state != "linked":
        return ""
    if session_state == "linked":
        return (
            "まだしていません。`/アカウント`（英語: `/whoami`）で今の状態を確認します。"
            if lang == "ja"
            else "not checked yet. Use `/whoami` (Japanese: `/アカウント`) to verify now."
        )
    if saved_claim_state == "linked":
        return (
            "前回の連携記録です。`/アカウント`（英語: `/whoami`）で今の状態を確認します。"
            if lang == "ja"
            else "saved from a previous link. Use `/whoami` (Japanese: `/アカウント`) to verify now."
        )
    return ""


def _format_privacy_status(config: dict[str, object], *, lang: str) -> str:
    report = build_privacy_status(config)
    sharing = report.get("data_sharing") if isinstance(report.get("data_sharing"), dict) else {}
    exclusion = report.get("private_content_exclusion") if isinstance(report.get("private_content_exclusion"), dict) else {}
    ledger = report.get("ledger") if isinstance(report.get("ledger"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    excluded = exclusion.get("excluded") if isinstance(exclusion.get("excluded"), list) else []
    if lang == "ja":
        lines = [
            "プライバシー",
            f"  OpenAI共有トラフィック: {'オン' if sharing.get('openai_shared_traffic_enabled') else 'オフ'}",
            f"  ユーザー opt-in 必須: {_yes_no(sharing.get('requires_explicit_opt_in'), lang='ja')}",
            "  local→cloud自動同期なし: はい",
            f"  private/local 除外: {_yes_no(exclusion.get('active'), lang='ja')}",
            f"  ledger shared_traffic 既定: {_value_label(bool(ledger.get('default_shared_traffic')), lang='ja')}",
            f"  raw prompt 保存: {_value_label(bool(ledger.get('raw_prompt_persisted')), lang='ja')}",
            "  除外するもの:",
        ]
        for item in excluded[:6]:
            lines.append(f"    - {_safe(item)}")
        lines.append("  しないこと:")
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Privacy",
            f"  openai_shared_traffic_enabled: {bool(sharing.get('openai_shared_traffic_enabled'))}",
            f"  requires_explicit_opt_in: {bool(sharing.get('requires_explicit_opt_in'))}",
            "  local_to_cloud_auto_sync_disabled: True",
            f"  private_content_exclusion_active: {bool(exclusion.get('active'))}",
            f"  ledger_default_shared_traffic: {bool(ledger.get('default_shared_traffic'))}",
            f"  raw_prompt_persisted: {bool(ledger.get('raw_prompt_persisted'))}",
            "  excluded: " + ", ".join(_safe(item) for item in excluded[:6]),
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "",
        )
    )
