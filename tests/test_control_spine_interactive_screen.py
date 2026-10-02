from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
for path in (CLIENTS_CLI,):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def test_login_flow_compact_prefers_slash_guidance_in_japanese() -> None:
    from yonerai_cli.screens.control_spine_interactive import format_login_flow_compact

    report = {
        "ok": True,
        "configured": True,
        "staging": {"configured": True, "origin": "https://api-staging.yonerai.com"},
        "authorization_url": "https://api-staging.yonerai.com/auth/google/start",
        "browser_opened": False,
        "next_safe_command": "yonerai login",
        "cli_bridge": {},
    }

    rendered = format_login_flow_compact(report, lang="ja")

    assert "ログイン" in rendered
    assert "/ログイン" in rendered
    assert "login" in rendered
    assert "yonerai login" not in rendered
    assert "次のURL" in rendered
    assert "https://api-staging.yonerai.com/auth/google/start" in rendered


def test_control_spine_tui_prefers_slash_commands_in_japanese() -> None:
    from yonerai_cli.screens.control_spine_interactive import format_control_spine_tui

    report = {
        "ok": False,
        "operation": "api_status",
        "backend_url": "https://api-staging.yonerai.com",
        "account_linked": False,
        "error": {
            "code": "staging_auth_required",
            "message": "Staging login is required or the saved session expired.",
            "next_safe_command": "yonerai login",
        },
    }

    rendered = format_control_spine_tui(report, lang="ja")

    assert "ログイン" in rendered
    assert "/ログイン" in rendered
    assert "login" in rendered
    assert "/アカウント" not in rendered
    assert "whoami" not in rendered
    assert "yonerai login" not in rendered


def test_control_spine_tui_does_not_duplicate_next_action_for_auth_error() -> None:
    from yonerai_cli.screens.control_spine_interactive import format_control_spine_tui

    report = {
        "ok": False,
        "operation": "api_status",
        "backend_url": "https://api-staging.yonerai.com",
        "account_linked": False,
        "error": {
            "code": "staging_auth_required",
            "message": "Staging login is required or the saved session expired.",
            "next_safe_command": "yonerai login",
        },
    }

    rendered = format_control_spine_tui(report, lang="ja")

    assert rendered.count("  次: ") == 1
    assert "/ログイン (/login)" in rendered


def test_control_spine_tui_marks_auth_required_with_saved_session_as_expired() -> None:
    from yonerai_cli.screens.control_spine_interactive import format_control_spine_tui

    report = {
        "ok": False,
        "operation": "whoami",
        "auth_state": "linked",
        "session_expires_at": "2030-01-01T00:00:00Z",
        "account": {"email_redacted": "o***@example.com"},
        "error": {
            "code": "staging_auth_required",
            "message": "Staging login is required or the saved session expired.",
            "next_safe_command": "yonerai login",
        },
    }

    rendered = format_control_spine_tui(report, lang="ja")

    assert "状態: 期限切れ" in rendered
    assert "状態: staging 連携済み" not in rendered


def test_control_spine_tui_ping_does_not_fake_pong_when_request_failed() -> None:
    from yonerai_cli.screens.control_spine_interactive import format_control_spine_tui

    report = {
        "ok": False,
        "operation": "api_ping",
        "backend_url": "https://api-staging.yonerai.com",
        "error": {
            "code": "staging_auth_required",
            "message": "Staging login is required or the saved session expired.",
            "next_safe_command": "yonerai login",
        },
    }

    rendered = format_control_spine_tui(report, lang="ja")

    assert "応答: 未実行" in rendered
    assert "応答: pong" not in rendered
