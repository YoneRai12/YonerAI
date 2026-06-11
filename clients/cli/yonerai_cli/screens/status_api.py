from __future__ import annotations

from typing import Any

from yonerai_cli.screens.labels import _safe


def _format_status_check(report: dict[str, Any], *, lang: str) -> str:
    releases = report.get("releases") if isinstance(report.get("releases"), dict) else {}
    install = report.get("install") if isinstance(report.get("install"), dict) else {}
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    if lang == "ja":
        return "\n".join(
            (
                "状態",
                f"  status: {_safe(report.get('status') or 'unknown')}",
                f"  component数: {_safe(report.get('component_count') or 0)}",
                f"  最新安定版: {_safe(releases.get('latest_stable') or 'unknown')}",
                f"  最新ベータ版: {_safe(releases.get('latest_alpha') or 'unknown')}",
                f"  install command: {_safe(install.get('install_command') or 'none')}",
                f"  source: {_safe(source.get('kind') or 'fixture')}",
                f"  private_runtime_details_included: {_safe(report.get('private_runtime_details_included'))}",
                "  status.yonerai.com: contract/fixture reader only",
                "  本番AWS/Oracle: 含まれていません",
                "",
            )
        )
    return "\n".join(
        (
            "Status",
            f"  status: {_safe(report.get('status') or 'unknown')}",
            f"  components: {_safe(report.get('component_count') or 0)}",
            f"  latest_stable: {_safe(releases.get('latest_stable') or 'unknown')}",
            f"  latest_beta: {_safe(releases.get('latest_alpha') or 'unknown')}",
            f"  install_command: {_safe(install.get('install_command') or 'none')}",
            f"  source: {_safe(source.get('kind') or 'fixture')}",
            f"  private_runtime_details_included: {_safe(report.get('private_runtime_details_included'))}",
            "  status.yonerai.com: contract/fixture reader only",
            "  production AWS/Oracle: not included",
            "",
        )
    )


def _format_api_status(report: dict[str, Any], *, lang: str) -> str:
    rate_state = report.get("rate_limit_state") if isinstance(report.get("rate_limit_state"), dict) else {}
    if lang == "ja":
        return "\n".join(
            (
                "公式API",
                f"  設定済み: {_safe(report.get('official_api_configured'))}",
                f"  endpoint: {_safe(report.get('endpoint_url') or 'not_configured')}",
                f"  auth_state: {_safe(report.get('auth_state') or 'dry_run')}",
                f"  rate_limit: {_safe(rate_state.get('policy_state') or 'contract_only')}",
                f"  private content exclusion: {_safe(report.get('private_content_exclusion'))}",
                f"  OpenAI shared traffic: {_safe(report.get('shared_traffic_enabled'))}",
                f"  production_backend_included: {_safe(report.get('production_backend_included'))}",
                f"  official backend: {'included' if report.get('production_backend_included') else 'not included'}",
                "  try: yonerai api status --pretty --lang ja",
                "",
            )
        )
    return "\n".join(
        (
            "Official API",
            f"  configured: {_safe(report.get('official_api_configured'))}",
            f"  endpoint_url: {_safe(report.get('endpoint_url') or 'not_configured')}",
            f"  auth_state: {_safe(report.get('auth_state') or 'dry_run')}",
            f"  rate_limit: {_safe(rate_state.get('policy_state') or 'contract_only')}",
            f"  private_content_exclusion: {_safe(report.get('private_content_exclusion'))}",
            f"  shared_traffic_enabled: {_safe(report.get('shared_traffic_enabled'))}",
            f"  production_backend_included: {_safe(report.get('production_backend_included'))}",
            f"  official backend: {'included' if report.get('production_backend_included') else 'not included'}",
            "  try: yonerai api status --pretty",
            "",
        )
    )


def _format_api_unavailable(lang: str) -> str:
    if lang == "ja":
        return "公式API状態はこのビルドでは表示できません。\n"
    return "Official API status is unavailable in this build.\n"
