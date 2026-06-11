from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
for path in (CLIENTS_CLI,):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def test_control_spine_status_reads_scopes_without_tokens(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services.control_spine_service import build_control_spine_status_report

    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        assert method == "GET"
        assert body is None
        assert headers == {}
        assert timeout == 3.0
        if url.endswith("/v1/status"):
            return (
                200,
                {
                    "status": "not_production",
                    "control_spine": {
                        "status": "not_production",
                        "mode": "staging",
                        "sessions": "active_expired_revoked_suspended",
                        "revoke": "staging_available",
                        "projects": "personal_staging",
                        "audit": "sanitized_metadata_only",
                        "admin_scope": "disabled_by_default",
                        "shared_traffic": "off",
                    },
                },
                {"X-YonerAI-RateLimit-Scope": "staging"},
            )
        if url.endswith("/v1/rate-limit"):
            return (
                200,
                {
                    "scope": "staging",
                    "allowed": True,
                    "quota_exceeded": False,
                    "control_spine": {
                        "contract_version": "yonerai.control-spine.v0.1",
                        "scopes": [
                            {"name": "profile:read", "enabled_by_default": True, "summary": "read profile"},
                            {"name": "session:revoke", "enabled_by_default": True, "summary": "revoke sessions"},
                            {"name": "admin:*", "enabled_by_default": False, "summary": "admin disabled"},
                        ],
                    },
                },
                {
                    "X-YonerAI-RateLimit-Scope": "staging",
                    "X-YonerAI-RateLimit-Limit": "60",
                    "X-YonerAI-RateLimit-Remaining": "59",
                },
            )
        raise AssertionError(url)

    report = build_control_spine_status_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(tmp_path / "cli-config.json"),
        transport=transport,
        timeout_seconds=3.0,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is True
    assert report["staging_only"] is True
    assert report["production_backend_enabled"] is False
    assert report["shared_traffic_enabled"] is False
    assert report["control_spine"]["mode"] == "staging"
    assert [scope["name"] for scope in report["scopes"]] == ["profile:read", "session:revoke", "admin:*"]
    assert "access_token" not in serialized
    assert "refresh_token" in serialized
    assert str(tmp_path) not in serialized


def test_whoami_uses_saved_staging_session_without_printing_it(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.screens.control_spine import format_control_spine_pretty
    from yonerai_cli.services.control_spine_service import build_whoami_report
    from yonerai_cli.services.staging_session_service import save_staging_session

    config_path = tmp_path / "cli-config.json"
    session_value = "opaque-session-value-123456789"
    save_staging_session(
        session_token=session_value,
        origin="https://api-staging.yonerai.com",
        account={"email": "owner@example.test", "display_name": "Owner"},
        config_path=config_path,
    )

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        assert method == "GET"
        assert url == "https://api-staging.yonerai.com/v1/account/me"
        assert headers["Authorization"] == f"Bearer {session_value}"
        return (
            200,
            {"account": {"email": "owner@example.test", "display_name": "Owner", "sub": "google-subject"}},
            {"X-YonerAI-RateLimit-Scope": "staging"},
        )

    report = build_whoami_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(config_path),
        transport=transport,
    )
    rendered = format_control_spine_pretty(report, lang="ja", color="never")
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True) + rendered

    assert report["ok"] is True
    assert report["account"]["email_redacted"] == "o***@example.test"
    assert session_value not in serialized
    assert "google-subject" not in serialized
    assert str(tmp_path) not in serialized


def test_control_spine_rejects_private_or_token_payload(tmp_path: Path) -> None:
    from yonerai_cli.services.control_spine_service import build_control_spine_ping_report

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        return 200, {"status": "ok", "access_token": "must-not-print"}, {}

    report = build_control_spine_ping_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(tmp_path / "cli-config.json"),
        transport=transport,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "control_spine_private_payload_rejected"
    assert "must-not-print" not in serialized
    assert str(tmp_path) not in serialized


def test_public_cli_control_spine_commands_fail_closed_without_origin(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.delenv("YONERAI_STAGING_AUTH_ORIGIN", raising=False)
    monkeypatch.delenv("YONERAI_OFFICIAL_API_STAGING_ORIGIN", raising=False)

    assert cli.main(["whoami", "--json"]) == 1
    whoami = json.loads(capsys.readouterr().out)
    assert whoami["error"]["code"] == "staging_origin_not_configured"

    assert cli.main(["project", "list", "--json"]) == 1
    projects = json.loads(capsys.readouterr().out)
    assert projects["error"]["code"] == "staging_origin_not_configured"

    assert cli.main(["audit", "list", "--json"]) == 1
    audit = json.loads(capsys.readouterr().out)
    assert audit["error"]["code"] == "staging_origin_not_configured"

    serialized = json.dumps([whoami, projects, audit], sort_keys=True)
    assert str(tmp_path) not in serialized


def test_login_alias_prints_staging_url_without_network(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    assert cli.main(["login", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["operation"] == "google_login_staging"
    assert report["authorization_url"] == "https://api-staging.yonerai.com/auth/google/start"
    assert report["official_backend_called"] is False
    assert report["production_login_enabled"] is False
    assert report["token_printed"] is False


def test_control_spine_slash_commands_are_visible() -> None:
    from yonerai_cli.tui.aliases import canonical_command
    from yonerai_cli.tui.keymap import slash_command_words

    words = slash_command_words("ja")

    assert canonical_command("/ログイン") == "/login"
    assert canonical_command("/プロジェクト") == "/project"
    assert canonical_command("/セッション") == "/sessions"
    assert canonical_command("/監査") == "/audit"
    assert "/ログイン" in words
    assert "/プロジェクト" in words
    assert "/セッション" in words
    assert "/監査" in words
