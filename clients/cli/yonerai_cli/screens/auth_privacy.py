from __future__ import annotations

from yonerai_cli.auth_policy import build_google_auth_status, build_privacy_status
from yonerai_cli.screens.labels import _safe, _value_label, _yes_no


def _format_auth_status(config: dict[str, object], *, lang: str) -> str:
    report = build_google_auth_status(config)
    flow = report.get("flow") if isinstance(report.get("flow"), dict) else {}
    storage = report.get("storage") if isinstance(report.get("storage"), dict) else {}
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    if lang == "ja":
        lines = [
            "認証",
            f"  Google認証: {'設定あり' if report.get('configured') else '未設定'}",
            "  状態: ドライラン契約のみ。本番Googleログインはまだ有効にしていません",
            f"  ループバックredirectのみ: {_yes_no(flow.get('loopback_redirect_only'), lang='ja')}",
            f"  PKCE必須: {_yes_no(flow.get('pkce_required'), lang='ja')}",
            f"  state必須: {_yes_no(flow.get('state_required'), lang='ja')}",
            f"  embedded webview: {'禁止' if not flow.get('embedded_webview_allowed') else '許可'}",
            f"  token保存: {_safe(storage.get('refresh_token_storage') or 'disabled_by_default')}",
            "  次に試す: yonerai auth google login --dry-run --pretty --lang ja",
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
            "  mode: dry-run contract only; production Google login is disabled",
            f"  loopback_redirect_only: {bool(flow.get('loopback_redirect_only'))}",
            f"  pkce_required: {bool(flow.get('pkce_required'))}",
            f"  state_required: {bool(flow.get('state_required'))}",
            f"  token_storage: {_safe(storage.get('refresh_token_storage') or 'disabled_by_default')}",
            "  next: yonerai auth google login --dry-run --pretty",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "",
        )
    )


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
            f"  ユーザーopt-in必要: {_yes_no(sharing.get('requires_explicit_opt_in'), lang='ja')}",
            f"  private/local内容の除外: {_yes_no(exclusion.get('active'), lang='ja')}",
            f"  ledger shared_traffic既定値: {_value_label(bool(ledger.get('default_shared_traffic')), lang='ja')}",
            f"  raw prompt保存: {_value_label(bool(ledger.get('raw_prompt_persisted')), lang='ja')}",
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
