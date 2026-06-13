from __future__ import annotations

import os
from typing import Any

from yonerai_cli.services.control_spine_service import (
    build_audit_report,
    build_control_spine_ping_report,
    build_control_spine_status_report,
    build_control_spine_rate_limit_report,
    build_project_report,
    build_session_report,
    build_whoami_report,
    load_config_for_control_spine,
)
from yonerai_cli.services.staging_session_service import clear_staging_session


def _interactive_env() -> dict[str, str]:
    return dict(os.environ)


def interactive_runtime_env() -> dict[str, str]:
    return _interactive_env()


def interactive_api_status(_lang: str, *, config_path: str | None = None) -> dict[str, Any] | None:
    return build_control_spine_status_report(
        config=load_config_for_control_spine(config_path),
        env=_interactive_env(),
        claim_path=config_path,
    )


def interactive_rate_limit_status(_lang: str, *, config_path: str | None = None) -> dict[str, Any] | None:
    report = build_control_spine_rate_limit_report(
        config=load_config_for_control_spine(config_path),
        env=_interactive_env(),
        claim_path=config_path,
    )
    if not report.get("staging_origin_configured"):
        report["ok"] = True
        report.pop("error", None)
        report["rate_limit"] = {
            "ok": True,
            "official_backend_called": False,
            "status_code": None,
            "body": {
                "allowed": True,
                "scope": "anonymous",
                "quota_exceeded": False,
                "fallback_reason": "local_fixture_without_staging_origin",
            },
            "rate_limit_headers_present": [],
        }
        report["scopes"] = []
    return report


def interactive_ping_status(_lang: str, *, config_path: str | None = None) -> dict[str, Any] | None:
    return build_control_spine_ping_report(
        config=load_config_for_control_spine(config_path),
        env=_interactive_env(),
        claim_path=config_path,
    )


def interactive_whoami(_lang: str, *, config_path: str | None = None) -> dict[str, Any]:
    return build_whoami_report(
        config=load_config_for_control_spine(config_path),
        env=_interactive_env(),
        claim_path=config_path,
    )


def interactive_project_status(_lang: str, *, config_path: str | None = None) -> dict[str, Any]:
    return build_project_report(
        "list",
        config=load_config_for_control_spine(config_path),
        env=_interactive_env(),
        claim_path=config_path,
    )


def interactive_session_status(_lang: str, *, config_path: str | None = None) -> dict[str, Any]:
    return build_session_report(
        "list",
        config=load_config_for_control_spine(config_path),
        env=_interactive_env(),
        claim_path=config_path,
    )


def interactive_audit_status(_lang: str, *, config_path: str | None = None) -> dict[str, Any]:
    return build_audit_report(
        config=load_config_for_control_spine(config_path),
        env=_interactive_env(),
        claim_path=config_path,
    )


def interactive_logout(_lang: str, *, config_path: str | None = None) -> dict[str, Any]:
    return clear_staging_session(config_path)


def interactive_session_revoke(
    _lang: str,
    session_id: str,
    *,
    config_path: str | None = None,
) -> dict[str, Any]:
    return build_session_report(
        "revoke",
        session_id=session_id,
        config=load_config_for_control_spine(config_path),
        env=_interactive_env(),
        claim_path=config_path,
    )
