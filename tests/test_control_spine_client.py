from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
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
        if url.endswith("/v1/health"):
            return (
                200,
                {
                    "status": "ok",
                    "api_version": "yonerai.control-spine.v0.1",
                    "min_cli_version": "0.20.0-alpha.1",
                    "control_spine": {"mode": "staging"},
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
                            {"name": "agent:run", "enabled_by_default": True, "summary": "dogfood agent run disabled"},
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
    assert [scope["name"] for scope in report["scopes"]] == ["profile:read", "session:revoke", "agent:run", "admin:*"]
    agent_scope = next(scope for scope in report["scopes"] if scope["name"] == "agent:run")
    admin_scope = next(scope for scope in report["scopes"] if scope["name"] == "admin:*")
    assert agent_scope["enabled_by_default"] is False
    assert agent_scope["requires_threat_model"] is True
    assert admin_scope["requires_threat_model"] is True
    assert report["contract_skew"]["skew_detected"] is False
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


def test_expired_session_mid_command_has_guided_japanese_relogin(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.screens.control_spine import format_control_spine_pretty
    from yonerai_cli.services.control_spine_service import build_whoami_report
    from yonerai_cli.services.staging_session_service import save_staging_session

    config_path = tmp_path / "cli-config.json"
    save_staging_session(
        session_token="opaque-session-value-123456789",
        origin="https://api-staging.yonerai.com",
        account={"email": "owner@example.test", "display_name": "Owner"},
        expires_at="2000-01-01T00:00:00Z",
        config_path=config_path,
    )

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        raise AssertionError("expired local session must not call staging backend")

    report = build_whoami_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(config_path),
        transport=transport,
    )
    rendered = format_control_spine_pretty(report, lang="ja", color="never")
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True) + rendered

    assert report["ok"] is False
    assert report["auth_state"] == "expired"
    assert report["error"]["code"] == "staging_auth_required"
    assert "yonerai login" in rendered
    assert "Traceback" not in serialized
    assert str(tmp_path) not in serialized


def test_contract_skew_warns_when_backend_requires_newer_cli(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.screens.control_spine import format_control_spine_pretty
    from yonerai_cli.services.control_spine_service import build_control_spine_status_report

    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        if url.endswith("/v1/status"):
            return 200, {"status": "not_production", "control_spine": {"mode": "staging"}}, {}
        if url.endswith("/v1/health"):
            return 200, {"api_version": "yonerai.control-spine.v0.2", "min_cli_version": "99.0.0"}, {}
        if url.endswith("/v1/rate-limit"):
            return 200, {"scope": "staging", "allowed": True, "quota_exceeded": False}, {}
        raise AssertionError(url)

    report = build_control_spine_status_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(tmp_path / "cli-config.json"),
        transport=transport,
    )
    rendered = format_control_spine_pretty(report, lang="ja", color="never")
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True) + rendered

    assert report["ok"] is True
    assert report["contract_skew"]["skew_detected"] is True
    assert "yonerai update check" in rendered
    assert str(tmp_path) not in serialized


def test_contract_skew_missing_health_fields_is_debug_only(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.screens.control_spine import format_control_spine_pretty
    from yonerai_cli.services.control_spine_service import build_control_spine_status_report

    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        if url.endswith("/v1/status"):
            return 200, {"status": "not_production", "control_spine": {"mode": "staging"}}, {}
        if url.endswith("/v1/health"):
            return 200, {"status": "ok"}, {}
        if url.endswith("/v1/rate-limit"):
            return 200, {"scope": "staging", "allowed": True, "quota_exceeded": False}, {}
        raise AssertionError(url)

    report = build_control_spine_status_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(tmp_path / "cli-config.json"),
        transport=transport,
    )
    rendered = format_control_spine_pretty(report, lang="ja", color="never")

    assert report["ok"] is True
    assert report["contract_skew"]["skew_detected"] is False
    assert report["contract_skew"]["warning"] is None
    assert report["contract_skew"]["missing_fields"] == ["api_version", "min_cli_version"]
    assert report["contract_skew"]["missing_field_policy"] == "debug_only_no_user_warning"
    assert "yonerai update check" not in rendered


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


def test_login_alias_no_staging_is_controlled_error(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))

    assert cli.main(["login", "--no-staging", "--json"]) == 2
    output = capsys.readouterr()

    assert "ステージングログイン" in output.err
    assert str(tmp_path) not in output.err


def test_revoke_session_invalid_id_is_controlled_error(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services.staging_session_service import save_staging_session

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    save_staging_session(
        session_token="opaque-session-value-123456789",
        origin="https://api-staging.yonerai.com",
        account={"email": "owner@example.test", "display_name": "Owner"},
        config_path=config_path,
    )

    assert cli.main(["auth", "revoke-session", "bad session id", "--json"]) == 2
    output = capsys.readouterr()

    assert "セッションID" in output.err
    assert "Traceback" not in output.err
    assert str(tmp_path) not in output.err


def test_control_spine_callback_returns_none_when_api_status_unavailable() -> None:
    from yonerai_cli.screens.control_spine import format_control_spine_callback

    callbacks = SimpleNamespace(api_status=lambda _lang: None)

    assert format_control_spine_callback("/api", callbacks, lang="ja") is None


def test_interactive_callbacks_honor_custom_config_path(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services import control_spine_callbacks

    seen: dict[str, object] = {}

    def fake_whoami(_lang: str, *, config_path: str | None = None) -> dict[str, object]:
        seen["config_path"] = config_path
        return {"ok": True, "operation": "whoami"}

    monkeypatch.setattr(control_spine_callbacks, "interactive_whoami", fake_whoami)

    callbacks = cli._interactive_callbacks(str(tmp_path / "custom-config.json"))
    assert callbacks.whoami is not None
    assert callbacks.whoami("ja")["operation"] == "whoami"
    assert seen["config_path"] == str(tmp_path / "custom-config.json")


def test_control_spine_context_handles_missing_session_claim(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services import control_spine_service

    monkeypatch.setattr(control_spine_service, "load_staging_session_token", lambda _path: (None, None))

    context = control_spine_service.build_control_spine_context(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(tmp_path / "cli-config.json"),
    )

    assert context["auth_state"] == "unauthenticated"
    assert context["session_claim"] == {}


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
