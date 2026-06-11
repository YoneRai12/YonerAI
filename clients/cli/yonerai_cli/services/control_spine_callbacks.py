from __future__ import annotations

import os
from typing import Any

from yonerai_cli.services.control_spine_service import (
    build_audit_report,
    build_control_spine_status_report,
    build_project_report,
    build_session_report,
    build_whoami_report,
    load_config_for_control_spine,
)


def interactive_api_status(_lang: str) -> dict[str, Any] | None:
    if not (os.environ.get("YONERAI_STAGING_AUTH_ORIGIN") or os.environ.get("YONERAI_OFFICIAL_API_STAGING_ORIGIN")):
        return None
    return build_control_spine_status_report(config=load_config_for_control_spine(None), env=os.environ)


def interactive_whoami(_lang: str) -> dict[str, Any]:
    return build_whoami_report(config=load_config_for_control_spine(None), env=os.environ)


def interactive_project_status(_lang: str) -> dict[str, Any]:
    return build_project_report("current", config=load_config_for_control_spine(None), env=os.environ)


def interactive_session_status(_lang: str) -> dict[str, Any]:
    return build_session_report("list", config=load_config_for_control_spine(None), env=os.environ)


def interactive_audit_status(_lang: str) -> dict[str, Any]:
    return build_audit_report(config=load_config_for_control_spine(None), env=os.environ)
