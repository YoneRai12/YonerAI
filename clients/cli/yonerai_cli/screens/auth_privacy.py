from __future__ import annotations

from collections.abc import Mapping

from yonerai_cli.auth_policy import build_google_auth_status, build_privacy_status
from yonerai_cli.screens.labels import _safe, _value_label, _yes_no


def _format_auth_status(config: dict[str, object], *, lang: str) -> str:
    report = build_google_auth_status(config, claim_path=str(config.get("_runtime_config_path") or "") or None)
    flow = report.get("flow") if isinstance(report.get("flow"), dict) else {}
    storage = report.get("storage") if isinstance(report.get("storage"), dict) else {}
    staging = report.get("staging") if isinstance(report.get("staging"), dict) else {}
    staging_session = report.get("staging_session") if isinstance(report.get("staging_session"), dict) else {}
    staging_account = staging_session.get("account") if isinstance(staging_session.get("account"), dict) else {}
    session_claim = report.get("staging_session_claim") if isinstance(report.get("staging_session_claim"), dict) else {}
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    if lang == "ja":
        lines = [
            "認証",
            f"  Google認証: {'設定あり' if report.get('configured') else '未設定'}",
            "  状態: ステージング契約のみ。本番 Google ログインは未実装です",
            "  本番Googleログインはまだ有効にしていません",
            f"  ループバック redirect のみ: {_yes_no(flow.get('loopback_redirect_only'), lang='ja')}",
            f"  PKCE 必須: {_yes_no(flow.get('pkce_required'), lang='ja')}",
            f"  state 必須: {_yes_no(flow.get('state_required'), lang='ja')}",
            f"  embedded webview: {'禁止' if not flow.get('embedded_webview_allowed') else '許可'}",
            f"  token 保存: {_safe(storage.get('refresh_token_storage') or 'disabled_by_default')}",
            f"  staging ログイン: {'利用可能' if staging.get('configured') else '未設定'}",
            f"  staging origin: {_safe(staging.get('origin') or 'not_configured')}",
            f"  staging 認証状態: {_safe(staging_session.get('auth_state') or 'unauthenticated')}",
            f"  staging session: {'利用可能' if session_claim.get('session_available') else '未保存'}",
            f"  session 保存方式: {_safe(session_claim.get('storage_backend') or 'none')}",
            f"  linked account: {_safe(_staging_account_label(staging_account, session_claim))}",
            "  account sync: オフ。cloud -> local は選択・認証後の preview のみ。local -> cloud は既定で無効です",
            "  local/private upload: 無効。private file / local memory / local node payload は送信しません",
            f"  次に試す: {_safe(report.get('next_safe_command') or 'yonerai login')}",
        ]
        if error:
            lines.append(f"  補足: {_safe(error.get('message') or error.get('code'))}")
        lines.append("  実行しないこと:")
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Auth",
            f"  google_auth: {'configured' if report.get('configured') else 'not configured'}",
            "  mode: staging contract only; official Google login is disabled",
            f"  loopback_redirect_only: {bool(flow.get('loopback_redirect_only'))}",
            f"  pkce_required: {bool(flow.get('pkce_required'))}",
            f"  state_required: {bool(flow.get('state_required'))}",
            f"  token_storage: {_safe(storage.get('refresh_token_storage') or 'disabled_by_default')}",
            f"  staging_login: {'available' if staging.get('configured') else 'not configured'}",
            f"  staging_origin: {_safe(staging.get('origin') or 'not_configured')}",
            f"  staging_auth_state: {_safe(staging_session.get('auth_state') or 'unauthenticated')}",
            f"  staging_session: {'available' if session_claim.get('session_available') else 'not stored'}",
            f"  session_storage: {_safe(session_claim.get('storage_backend') or 'none')}",
            f"  linked_account: {_safe(_staging_account_label(staging_account, session_claim))}",
            "  account_sync: off; cloud-to-local is preview-only after selection/auth, local-to-cloud is disabled by default",
            "  local_private_upload: disabled; private files, local memory, and local node payloads are excluded",
            f"  next: {_safe(report.get('next_safe_command') or 'yonerai login')}",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "",
        )
    )


def _staging_account_label(account: Mapping[str, object], session_claim: Mapping[str, object] | None = None) -> object:
    email = account.get("email_redacted")
    if email and email != "not-linked":
        return email
    if session_claim is not None:
        session_email = session_claim.get("redacted_email")
        if session_email and session_email != "not-linked":
            return session_email
        if session_claim.get("display_name") and session_claim.get("display_name") != "not-linked":
            return session_claim.get("display_name")
    return account.get("display_name") or "not-linked"


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
            f"  private/local内容の除外: {_yes_no(exclusion.get('active'), lang='ja')}",
            f"  ledger shared_traffic 既定値: {_value_label(bool(ledger.get('default_shared_traffic')), lang='ja')}",
            f"  raw prompt 保存: {_value_label(bool(ledger.get('raw_prompt_persisted')), lang='ja')}",
            "  共有しない内容:",
        ]
        for item in excluded[:6]:
            lines.append(f"    - {_safe(item)}")
        lines.append("  実行しないこと:")
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Privacy",
            f"  openai_shared_traffic_enabled: {bool(sharing.get('openai_shared_traffic_enabled'))}",
            f"  requires_explicit_opt_in: {bool(sharing.get('requires_explicit_opt_in'))}",
            f"  private_content_exclusion_active: {bool(exclusion.get('active'))}",
            f"  ledger_default_shared_traffic: {bool(ledger.get('default_shared_traffic'))}",
            f"  raw_prompt_persisted: {bool(ledger.get('raw_prompt_persisted'))}",
            "  excluded: " + ", ".join(_safe(item) for item in excluded[:6]),
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "",
        )
    )
