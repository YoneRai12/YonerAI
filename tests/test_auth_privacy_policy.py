from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
CORE_SRC = ROOT / "core" / "src"
for path in (CLIENTS_CLI, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def test_auth_status_is_contract_only_and_does_not_print_tokens(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.delenv("YONERAI_GOOGLE_OAUTH_CLIENT_ID", raising=False)

    assert cli.main(["auth", "status", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["schema_version"] == "yonerai-google-auth-contract/v0.1"
    assert report["configured"] is False
    assert report["production_login_enabled"] is False
    assert report["live_oauth_enabled"] is False
    assert report["client_secret_supported"] is False
    assert report["flow"]["scopes"] == ["openid", "email", "profile"]
    assert report["flow"]["pkce_required"] is True
    assert report["flow"]["state_required"] is True
    assert report["flow"]["loopback_redirect_only"] is True
    assert report["flow"]["embedded_webview_allowed"] is False
    assert report["token_printed"] is False
    assert "token=" not in serialized.lower()
    assert str(tmp_path) not in serialized


def test_auth_status_uses_staging_without_local_google_client_id(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    monkeypatch.delenv("YONERAI_GOOGLE_OAUTH_CLIENT_ID", raising=False)

    assert cli.main(["auth", "status", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["configured"] is False
    assert report["staging_login_available"] is True
    assert report["staging"]["origin"] == "https://api-staging.yonerai.com"
    assert report["next_safe_command"] == "yonerai login"
    assert report["error"] is None
    assert "YONERAI_GOOGLE_OAUTH_CLIENT_SECRET" not in serialized
    assert str(tmp_path) not in serialized


def test_auth_status_without_saved_session_stays_unauthenticated(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    monkeypatch.delenv("YONERAI_GOOGLE_OAUTH_CLIENT_ID", raising=False)

    assert cli.main(["auth", "status", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["staging_auth_state"] == "unauthenticated"
    assert report["staging_account"]["email_redacted"] == "not-linked"


def test_auth_status_localizes_staging_next_command(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    config_path.write_text(json.dumps({"language": "en"}), encoding="utf-8")
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    assert cli.main(["auth", "status", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["next_safe_command"] == "yonerai login"


def test_auth_status_pretty_uses_compact_japanese_staging_guidance(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.delenv("YONERAI_GOOGLE_OAUTH_CLIENT_ID", raising=False)

    assert cli.main(["auth", "status", "--pretty", "--lang", "ja"]) == 0
    output = capsys.readouterr().out

    assert "認証" in output
    assert "状態: 未ログイン / Google α-staging" in output
    assert "接続先: https://api-staging.yonerai.com" in output
    assert "/ログイン" in output
    assert "client secret" not in output.lower()
    assert str(tmp_path) not in output


def test_auth_status_pretty_shows_redacted_linked_account_without_raw_email(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services.auth_session_service import build_staging_auth_claim, save_staging_auth_claim

    config_path = tmp_path / "cli-config.json"
    save_staging_auth_claim(
        build_staging_auth_claim(
            origin="https://api-staging.yonerai.com",
            account={"email": "owner@example.com", "display_name": "Owner"},
        ),
        config_path=config_path,
    )
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    assert cli.main(["auth", "status", "--pretty", "--lang", "en"]) == 0
    output = capsys.readouterr().out

    assert "state: previously linked / Google alpha-staging" in output
    assert "account: o***@example.com" in output
    assert "backend_check: saved from a previous link." in output
    assert "owner@example.com" not in output
    assert str(tmp_path) not in output


def test_auth_status_pretty_uses_saved_session_wording_and_backend_verify_hint(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services.staging_session_service import save_staging_session

    config_path = tmp_path / "cli-config.json"
    save_staging_session(
        session_token="staging-session-token-1234567890",
        origin="https://api-staging.yonerai.com",
        account={"email": "owner@example.com", "display_name": "Owner"},
        config_path=config_path,
    )
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    assert cli.main(["auth", "status", "--pretty", "--lang", "ja"]) == 0
    output = capsys.readouterr().out

    assert "状態: 保存済みセッションあり / Google α-staging" in output
    assert "backend確認: まだしていません。`/アカウント`（英語: `/whoami`）で今の状態を確認します。" in output
    assert "次:" in output
    assert "/whoami" in output
    assert "同期 (/同期 / sync)" in output
    assert "owner@example.com" not in output
    assert str(tmp_path) not in output


def test_google_login_dry_run_requires_client_configuration_without_traceback(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.delenv("YONERAI_GOOGLE_OAUTH_CLIENT_ID", raising=False)

    assert cli.main(["auth", "google", "login", "--dry-run", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)

    assert report["dry_run"] is True
    assert report["live_oauth_started"] is False
    assert report["browser_opened"] is False
    assert report["token_printed"] is False
    assert report["error"]["code"] == "google_oauth_client_not_configured"
    assert "Traceback" not in json.dumps(report)


def test_google_login_dry_run_preserves_error_when_staging_is_ready(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    monkeypatch.delenv("YONERAI_GOOGLE_OAUTH_CLIENT_ID", raising=False)

    assert cli.main(["auth", "google", "login", "--dry-run", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["operation"] == "google_login_dry_run"
    assert report["configured"] is False
    assert report["error"]["code"] == "google_oauth_client_not_configured"
    assert "YONERAI_GOOGLE_OAUTH_CLIENT_SECRET" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_dry_run_accepts_loopback_pkce_contract(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_GOOGLE_OAUTH_CLIENT_ID", "fixture-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("YONERAI_GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:8765/oauth/google/callback")

    assert cli.main(["auth", "google", "login", "--dry-run", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["configured"] is True
    assert report["state_generated"] is True
    assert report["state_printed"] is False
    assert report["pkce_code_challenge_generated"] is True
    assert report["pkce_code_verifier_printed"] is False
    assert report["flow"]["redirect_valid"] is True
    assert report["flow"]["redirect_uri"].startswith("http://127.0.0.1:")
    assert report["storage"]["plain_text_token_storage_allowed"] is False
    assert "no live OAuth request" in report["actions_not_performed"]


def test_google_login_staging_requires_configured_allowlisted_origin(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.delenv("YONERAI_STAGING_AUTH_ORIGIN", raising=False)
    monkeypatch.delenv("YONERAI_OFFICIAL_API_STAGING_ORIGIN", raising=False)

    assert cli.main(["auth", "google", "login", "--staging", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["operation"] == "google_login_staging"
    assert report["configured"] is False
    assert report["production_login_enabled"] is False
    assert report["token_exchange_performed"] is False
    assert report["refresh_token_stored"] is False
    assert report["client_secret_required"] is False
    assert report["authorization_url"] is None
    assert report["error"]["code"] == "staging_auth_origin_not_configured"
    assert "YONERAI_GOOGLE_OAUTH_CLIENT_SECRET" not in serialized
    assert str(tmp_path) not in serialized


def test_login_alias_malformed_config_is_controlled_error(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "broken-config.json"
    config_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    assert cli.main(["login", "--json", "--config-path", str(config_path)]) == 2
    output = capsys.readouterr()

    assert "config could not be read as JSON" in output.err
    assert "Traceback" not in output.err
    assert str(tmp_path) not in output.err


def test_login_alias_short_default_uses_cli_bridge_without_tty_wait(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli.commands import auth as auth_command

    captured: dict[str, object] = {}

    def fake_build_staging_login_report(config_path: str | None, **kwargs: object) -> dict[str, object]:
        captured["config_path"] = config_path
        captured.update(kwargs)
        return {
            "ok": True,
            "operation": "google_login_staging",
            "configured": True,
            "authorization_url": "https://api-staging.yonerai.com/auth/google/start?cli_request_id=cli_fixture",
            "cli_bridge": {
                "network_called": True,
                "request_id": "cli_fixture",
                "browser_start_url": "https://api-staging.yonerai.com/auth/google/start?cli_request_id=cli_fixture",
            },
            "staging_linked": False,
            "staging_session_token_stored": False,
            "next_safe_command": "yonerai login",
        }

    monkeypatch.setattr(auth_command, "build_staging_login_report", fake_build_staging_login_report)
    monkeypatch.setattr(auth_command, "format_login_flow_compact", lambda report, *, lang: "bridge login ready")

    args = SimpleNamespace(
        staging=True,
        json=False,
        bridge=False,
        open_browser=False,
        wait_linked=False,
        config_path=str(tmp_path / "cli-config.json"),
        lang="ja",
        timeout_seconds=10.0,
        max_wait_seconds=120.0,
        poll_interval_seconds=2.0,
    )

    assert auth_command.handle_login_alias_command(args, print_json=lambda report: None) == 0
    output = capsys.readouterr().out

    assert captured["bridge"] is True
    assert captured["open_browser"] is False
    assert captured["wait_linked"] is False
    assert captured["config_path"] == str(tmp_path / "cli-config.json")
    assert "bridge login ready" in output


def test_google_login_staging_generates_public_safe_auth_url(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    assert cli.main(["auth", "google", "login", "--staging", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["operation"] == "google_login_staging"
    assert report["configured"] is True
    assert report["staging"]["origin"] == "https://api-staging.yonerai.com"
    assert report["authorization_url"] == "https://api-staging.yonerai.com/auth/google/start"
    assert report["state_generated"] is False
    assert report["state_printed_separately"] is False
    assert report["device_session_id_generated"] is False
    assert report["browser_opened"] is False
    assert report["live_oauth_started"] is False
    assert report["client_secret_required"] is False
    assert report["token_exchange_performed"] is False
    assert report["refresh_token_stored"] is False
    assert report["staging_api"]["network_fetch_default"] == "off"
    assert report["staging_api"]["network_fetch_when"] == "yonerai login or explicit --bridge/--poll-request-id"
    assert report["staging_api"]["redirect_policy"] == "reject_unexpected_host"
    assert any(endpoint["path"] == "/v1/account/me" for endpoint in report["staging_api"]["allowed_methods_and_paths"])
    assert any(endpoint["path"] == "/auth/cli/start" for endpoint in report["staging_api"]["allowed_methods_and_paths"])
    assert report["official_backend_called"] is False
    assert report["cli_bridge"]["network_called"] is False
    assert "YONERAI_GOOGLE_OAUTH_CLIENT_SECRET" not in serialized
    assert "refresh_token" in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_bridge_starts_cli_request_without_printing_tokens(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    calls: list[tuple[str, str]] = []

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        calls.append((method, url))
        assert body is None
        assert timeout == 7.0
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "expires_at": 12345,
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&redirect=true",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, timeout_seconds=7.0, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["official_backend_called"] is True
    assert report["authorization_url"] == (
        "https://api-staging.yonerai.com/auth/google/start?cli_request_id=cli_fixture_request&redirect=true"
    )
    assert report["cli_bridge"]["request_id"] == "cli_fixture_request"
    assert report["cli_bridge"]["start"]["poll_path"] == "/auth/cli/poll/cli_fixture_request"
    assert calls == [("POST", "https://api-staging.yonerai.com/auth/cli/start")]
    assert report["cli_bridge"]["start"]["staging_session_token_printed"] is False
    assert "ystg_cli" not in serialized
    assert "YONERAI_GOOGLE_OAUTH_CLIENT_SECRET" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_bridge_uses_returned_poll_url_without_printing_verifier(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    poll_verifier = "clipoll_testVerifier123"
    raw_poll_url = f"https://api-staging.yonerai.com/auth/cli/poll/cli_fixture_request?poll_verifier={poll_verifier}"
    calls: list[tuple[str, str]] = []

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        calls.append((method, url))
        if method == "POST":
            assert url == "https://api-staging.yonerai.com/auth/cli/start"
            return (
                200,
                {
                    "status": "created",
                    "request_id": "cli_fixture_request",
                    "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request",
                    "poll_path": "/auth/cli/poll/cli_fixture_request",
                    "poll_url": raw_poll_url,
                    "google_token_returned": False,
                    "refresh_token_returned": False,
                },
            )
        assert method == "GET"
        assert url == raw_poll_url
        return (
            200,
            {
                "status": "linked",
                "request_id": "cli_fixture_request",
                "session": {
                    "type": "yonerai_staging",
                    "token_field": "staging_session_token",
                    "staging_session_token": "ystg_cli_secret_placeholder",
                    "token_returned": False,
                    "bearer_authorization_supported": True,
                },
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    def account_transport(
        method: str,
        url: str,
        headers: dict[str, str],
        body: object,
        timeout: float,
    ) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        assert url == "https://api-staging.yonerai.com/v1/account/me"
        assert headers["Authorization"].startswith("Bearer ")
        return (
            200,
            {
                "account_id": "acct_fixture",
                "display_name": "Fixture",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(
        bridge=True,
        wait_linked=True,
        transport=transport,
        account_transport=account_transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["cli_bridge"]["start"]["poll_url"] == "https://api-staging.yonerai.com/auth/cli/poll/cli_fixture_request"
    assert report["cli_bridge"]["start"]["poll_url_received"] is True
    assert report["cli_bridge"]["start"]["poll_verifier_received"] is True
    assert report["cli_bridge"]["start"]["poll_verifier_printed"] is False
    assert calls == [
        ("POST", "https://api-staging.yonerai.com/auth/cli/start"),
        ("GET", raw_poll_url),
    ]
    assert poll_verifier not in serialized
    assert "ystg_cli_secret_placeholder" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_bridge_poll_redacts_session_placeholder(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        assert url == "https://api-staging.yonerai.com/auth/cli/poll/cli_fixture_request"
        return (
            200,
            {
                "status": "completed",
                "request_id": "cli_fixture_request",
                "staging_session_token": "ystg_cli_secret_placeholder",
                "google_token_returned": False,
                "refresh_token_returned": False,
                "replay_protected": True,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["official_backend_called"] is True
    assert report["error"] is None
    assert report["cli_bridge"]["poll_status"] == "completed"
    assert report["cli_bridge"]["staging_session_received"] is True
    assert report["staging_linked"] is False
    assert report["staging_linked_claim"] is None
    assert report["staging_claim_saved"] is False
    assert "ystg_cli_secret_placeholder" not in serialized
    assert "staging_session_token_printed" in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_accepts_nested_opaque_yonerai_session(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        assert url == "https://api-staging.yonerai.com/auth/cli/poll/cli_fixture_request"
        return (
            200,
            {
                "status": "linked",
                "request_id": "cli_fixture_request",
                "session": {
                    "type": "yonerai_staging",
                    "token_field": "staging_session_token",
                    "staging_session_token": "ystg_cli_secret_placeholder",
                    "token_returned": False,
                    "bearer_authorization_supported": True,
                },
                "google_token_returned": False,
                "refresh_token_returned": False,
                "auth_code_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["cli_bridge"]["poll_status"] == "linked"
    assert report["cli_bridge"]["staging_session_received"] is True
    assert report["cli_bridge"]["poll"]["session"]["token_field"] == "staging_session_token"
    assert report["cli_bridge"]["poll"]["session"]["opaque_session_available"] is True
    assert "ystg_cli_secret_placeholder" not in serialized
    assert "google_access_token_secret" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_accepts_opaque_session_token_return_metadata(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        return (
            200,
            {
                "status": "linked",
                "request_id": "cli_fixture_request",
                "session": {
                    "type": "yonerai_staging",
                    "token_field": "staging_session_token",
                    "staging_session_token": "ystg_cli_secret_placeholder",
                    "token_returned": True,
                    "bearer_authorization_supported": True,
                },
                "google_token_returned": False,
                "refresh_token_returned": False,
                "auth_code_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["cli_bridge"]["poll_status"] == "linked"
    assert report["cli_bridge"]["staging_session_received"] is True
    assert report["cli_bridge"]["poll"]["session"]["token_returned"] is False
    assert report["cli_bridge"]["poll"]["session"]["opaque_session_available"] is True
    assert "ystg_cli_secret_placeholder" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_accepts_nested_opaque_session_claim(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        return (
            200,
            {
                "status": "linked",
                "request_id": "cli_fixture_request",
                "session": {
                    "type": "yonerai_staging",
                    "token_field": "staging_session_claim",
                    "staging_session_claim": "ystg_cli_secret_placeholder",
                    "token_returned": True,
                    "bearer_authorization_supported": True,
                },
                "google_token_returned": False,
                "refresh_token_returned": False,
                "auth_code_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["cli_bridge"]["poll_status"] == "linked"
    assert report["cli_bridge"]["staging_session_received"] is True
    assert report["cli_bridge"]["poll"]["session"]["token_returned"] is False
    assert report["cli_bridge"]["poll"]["session"]["opaque_session_available"] is True
    assert "ystg_cli_secret_placeholder" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_session_save_does_not_double_hash_public_account_ref(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_session_service import save_staging_session

    public_ref = "staging-account-84c212c254ae65ca"
    claim = save_staging_session(
        session_token="ystg_fixture_session_1234567890",
        origin="https://api-staging.yonerai.com",
        account={"account_ref": public_ref, "display_name": "Fixture", "email_redacted": "f***@example.test"},
        config_path=tmp_path / "cli-config.json",
    )

    assert claim["account_id"] == public_ref


def test_staging_session_preserves_canonical_account_id_for_realtime_sync(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_session_service import save_staging_session

    canonical_account_id = "acct_contract_runtime_123"
    claim = save_staging_session(
        session_token="ystg_fixture_session_1234567890",
        origin="https://api-staging.yonerai.com",
        account={"account_id": canonical_account_id, "display_name": "Fixture"},
        config_path=tmp_path / "cli-config.json",
    )

    assert claim["account_id"] == canonical_account_id


def test_staging_bridge_rejects_sensitive_session_metadata_values(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    sensitive_values = (
        "access_token=leakmarker",
        "C:\\USERS\\Owner\\secret.txt",
        "http://10.0.0.5/runbook",
        "bad\nmetadata",
    )

    for index, value in enumerate(sensitive_values):
        field = ("type", "token_field", "expires_at", "type")[index]

        def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
            assert method == "GET"
            session = {
                "type": "yonerai_staging",
                "token_field": "staging_session_token",
                "staging_session_token": "ystg_cli_secret_placeholder",
                "token_returned": False,
                "bearer_authorization_supported": True,
            }
            session[field] = value
            return (
                200,
                {
                    "status": "linked",
                    "request_id": "cli_fixture_request",
                    "session": session,
                    "google_token_returned": False,
                    "refresh_token_returned": False,
                    "auth_code_returned": False,
                },
            )

        monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
        monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

        report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
        serialized = json.dumps(report, sort_keys=True)

        assert report["ok"] is False
        assert str(report["error"]["code"]).startswith("staging_bridge_session_")
        assert "leakmarker" not in serialized
        assert "C:\\USERS" not in serialized
        assert "10.0.0.5" not in serialized
        assert "ystg_cli_secret_placeholder" not in serialized
        assert str(tmp_path) not in serialized


def test_google_login_staging_rejects_mismatched_session_token_fields(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        return (
            200,
            {
                "status": "linked",
                "request_id": "cli_fixture_request",
                "staging_session_token": "ystg_cli_secret_placeholder_a",
                "session": {
                    "staging_session_token": "ystg_cli_secret_placeholder_b",
                    "token_returned": False,
                },
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_session_claim_invalid"
    assert report["staging_linked"] is False
    assert "ystg_cli_secret_placeholder_a" not in serialized
    assert "ystg_cli_secret_placeholder_b" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_rejects_empty_and_nonempty_session_token_mix(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        return (
            200,
            {
                "status": "linked",
                "request_id": "cli_fixture_request",
                "staging_session_token": "   ",
                "session": {
                    "staging_session_token": "ystg_cli_secret_placeholder",
                    "token_returned": False,
                },
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_session_claim_invalid"
    assert report["staging_linked"] is False
    assert "ystg_cli_secret_placeholder" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_bridge_rejects_sensitive_query_params_in_paths(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&access_token=leakmarker",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_browser_start_path_invalid"
    assert "leakmarker" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_bridge_rejects_semicolon_sensitive_query_params(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request;access_token=leakmarker",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_browser_start_path_invalid"
    assert "leakmarker" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_bridge_rejects_sensitive_fragment_params_in_paths(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request#refresh_token=leakmarker",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_browser_start_path_invalid"
    assert "leakmarker" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_bridge_rejects_sensitive_poll_path_params(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request",
                "poll_path": "/auth/cli/poll/cli_fixture_request?staging_session_token=leakmarker",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_poll_path_invalid"
    assert "leakmarker" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_bridge_rejects_sensitive_poll_url_params(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "poll_url": "https://api-staging.yonerai.com/auth/cli/poll/cli_fixture_request?staging_session_token=leakmarker",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_poll_url_invalid"
    assert "leakmarker" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_bridge_rejects_poll_url_wrong_origin(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "poll_url": "https://example.invalid/auth/cli/poll/cli_fixture_request?poll_verifier=clipoll_testVerifier123",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_poll_url_invalid"


def test_staging_bridge_rejects_unexpected_poll_url_query(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "poll_url": "https://api-staging.yonerai.com/auth/cli/poll/cli_fixture_request?poll_verifier=clipoll_testVerifier123&debug=true",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_poll_url_invalid"


def test_staging_bridge_rejects_poll_verifier_in_browser_url(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?poll_verifier=clipoll_testVerifier123",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "poll_url": "https://api-staging.yonerai.com/auth/cli/poll/cli_fixture_request?poll_verifier=clipoll_testVerifier123",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_browser_start_path_invalid"
    assert "clipoll_testVerifier123" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_bridge_rejects_nested_session_token_in_poll_response(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        return (
            200,
            {
                "status": "completed",
                "request_id": "cli_fixture_request",
                "account": {"staging_session_token": "nested_secret"},
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_token_return_forbidden"
    assert "nested_secret" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_bridge_rejects_object_session_claim_in_poll_response(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        return (
            200,
            {
                "status": "completed",
                "request_id": "cli_fixture_request",
                "staging_session_claim": {"access_token": "nested_secret"},
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_token_return_forbidden"
    assert "nested_secret" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_bridge_rejects_non_scalar_expires_at(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "expires_at": {"value": "not_a_public_scalar"},
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_expires_at_invalid"
    assert "not_a_public_scalar" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_waits_for_link_and_fetches_account_without_storing_tokens(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    poll_count = 0
    account_headers: list[dict[str, str]] = []

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        nonlocal poll_count
        if method == "POST":
            return (
                200,
                {
                    "status": "created",
                    "request_id": "cli_fixture_request",
                    "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&redirect=true",
                    "poll_path": "/auth/cli/poll/cli_fixture_request",
                    "google_token_returned": False,
                    "refresh_token_returned": False,
                },
            )
        poll_count += 1
        if poll_count == 1:
            return (
                200,
                {
                    "status": "pending",
                    "request_id": "cli_fixture_request",
                    "google_token_returned": False,
                    "refresh_token_returned": False,
                },
            )
        return (
            200,
            {
                "status": "completed",
                "request_id": "cli_fixture_request",
                "staging_session_token": "ystg_cli_secret_placeholder",
                "account": {"email": "owner@example.com", "display_name": "Owner"},
                "google_token_returned": False,
                "refresh_token_returned": False,
                "replay_protected": True,
            },
        )

    def account_transport(
        method: str,
        url: str,
        headers: dict[str, str],
        body: object,
        timeout: float,
    ) -> tuple[int, dict[str, object]]:
        account_headers.append(headers)
        assert method == "GET"
        assert url == "https://api-staging.yonerai.com/v1/account/me"
        assert headers["Authorization"] == "Bearer ystg_cli_secret_placeholder"
        return (
            200,
            {
                "ok": True,
                "account_id": "acct_owner_fixture",
                "display_name": "Owner",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(
        bridge=True,
        wait_linked=True,
        max_wait_seconds=2.0,
        poll_interval_seconds=0.25,
        transport=transport,
        account_transport=account_transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["staging_linked"] is True
    assert report["staging_session_token_stored"] is False
    assert report["cli_bridge"]["staging_session_received"] is True
    assert report["cli_bridge"]["account_me"]["ok"] is True
    assert report["staging_linked_claim"]["auth_state"] == "linked"
    assert report["staging_linked_claim"]["account"]["account_id"] == "acct_owner_fixture"
    assert report["staging_linked_claim"]["account"]["email_redacted"] == "not-linked"
    assert report["staging_linked_claim"]["storage"]["google_token_stored"] is False
    assert report["staging_linked_claim"]["storage"]["refresh_token_stored"] is False
    assert report["staging_linked_claim"]["storage"]["staging_session_token_stored"] is False
    assert account_headers
    assert "ystg_cli_secret_placeholder" not in serialized
    assert "owner@example.com" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_login_token_custody_scans_filesystem_config_and_ledger(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging
    from yonerai_cli.commands.auth import _persist_staging_claim_if_linked, _staging_session_handler
    from yonerai_cli.services.staging_session_service import load_staging_session_claim

    config_path = tmp_path / "cli-config.json"
    session_secret = "ystg_cli_secret_placeholder_custody"
    forbidden_values = (
        session_secret,
        "google_access_token_secret",
        "google_refresh_token_secret",
        "google_auth_code_secret",
    )

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        if method == "POST":
            return (
                200,
                {
                    "status": "created",
                    "request_id": "cli_fixture_request",
                    "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&redirect=true",
                    "poll_path": "/auth/cli/poll/cli_fixture_request",
                    "expires_at": "2099-06-06T00:30:00Z",
                    "google_token_returned": False,
                    "refresh_token_returned": False,
                },
            )
        return (
            200,
            {
                "status": "completed",
                "request_id": "cli_fixture_request",
                "staging_session_token": session_secret,
                "account": {"email": "owner@example.com", "display_name": "Owner"},
                "expires_at": "2099-06-06T00:30:00Z",
                "google_token_returned": False,
                "refresh_token_returned": False,
                "replay_protected": True,
            },
        )

    def account_transport(
        method: str,
        url: str,
        headers: dict[str, str],
        body: object,
        timeout: float,
    ) -> tuple[int, dict[str, object]]:
        assert headers["Authorization"] == f"Bearer {session_secret}"
        return (
            200,
            {
                "ok": True,
                "account": {"email": "owner@example.com", "display_name": "Owner"},
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(
        bridge=True,
        wait_linked=True,
        max_wait_seconds=2.0,
        poll_interval_seconds=0.25,
        transport=transport,
        account_transport=account_transport,
        session_claim_handler=_staging_session_handler(
            str(config_path),
            origin="https://api-staging.yonerai.com",
        ),
    )
    _persist_staging_claim_if_linked(report, config_path=str(config_path))
    ledger_path = tmp_path / "runs.jsonl"
    ledger_path.write_text(
        json.dumps(
            {
                "run_id": "run_custody_fixture",
                "auth_state": report.get("staging_linked_claim", {}).get("auth_state"),
                "session_hash": report.get("staging_session_storage", {}).get("session_hash"),
                "token_printed": False,
                "google_token_stored": False,
                "refresh_token_stored": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    assert report["ok"] is True
    assert report["staging_claim_saved"] is True
    saved_session_claim = load_staging_session_claim(config_path)
    assert saved_session_claim["redacted_email"] == "o***@example.com"
    assert saved_session_claim["display_name"] == "Owner"
    assert saved_session_claim["expires_at"] == "2099-06-06T00:30:00Z"
    for path in tmp_path.rglob("*"):
        if not path.is_file():
            continue
        data = path.read_bytes()
        for forbidden in forbidden_values:
            assert forbidden.encode("utf-8") not in data, path.name


def test_google_login_staging_retries_transient_poll_error(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging
    from yonerai_cli.staging_auth_bridge import StagingAuthBridgeError

    poll_count = 0

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        nonlocal poll_count
        if method == "POST":
            return (
                200,
                {
                    "status": "created",
                    "request_id": "cli_fixture_request",
                    "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&redirect=true",
                    "poll_path": "/auth/cli/poll/cli_fixture_request",
                    "google_token_returned": False,
                    "refresh_token_returned": False,
                },
            )
        poll_count += 1
        if poll_count == 1:
            raise StagingAuthBridgeError(
                "staging_bridge_poll_failed",
                "temporary staging error",
                status_code=503,
            )
        return (
            200,
            {
                "status": "completed",
                "request_id": "cli_fixture_request",
                "staging_session_token": "ystg_cli_secret_placeholder",
                "account": {"email": "owner@example.com", "display_name": "Owner"},
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    def account_transport(
        method: str,
        url: str,
        headers: dict[str, str],
        body: object,
        timeout: float,
    ) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "account": {"email": "owner@example.com", "display_name": "Owner"},
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(
        bridge=True,
        wait_linked=True,
        max_wait_seconds=2.0,
        poll_interval_seconds=0.25,
        transport=transport,
        account_transport=account_transport,
    )

    assert report["ok"] is True
    assert report["cli_bridge"]["poll_attempts"] == 2
    assert report["staging_linked"] is True


def test_google_login_staging_does_not_link_when_account_validation_fails(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        if method == "POST":
            return (
                200,
                {
                    "status": "created",
                    "request_id": "cli_fixture_request",
                    "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&redirect=true",
                    "poll_path": "/auth/cli/poll/cli_fixture_request",
                    "google_token_returned": False,
                    "refresh_token_returned": False,
                },
            )
        return (
            200,
            {
                "status": "linked",
                "request_id": "cli_fixture_request",
                "staging_session_token": "ystg_cli_secret_placeholder",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    def account_transport(
        method: str,
        url: str,
        headers: dict[str, str],
        body: object,
        timeout: float,
    ) -> tuple[int, dict[str, object]]:
        return (401, {"error": {"code": "expired"}, "google_token_returned": False, "refresh_token_returned": False})

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(
        bridge=True,
        wait_linked=True,
        transport=transport,
        account_transport=account_transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_account_validation_failed"
    assert report["staging_linked"] is False
    assert report["staging_linked_claim"] is None
    assert report["staging_session_token_stored"] is False
    assert "ystg_cli_secret_placeholder" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_does_not_link_without_cli_session(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        if method == "POST":
            return (
                200,
                {
                    "status": "created",
                    "request_id": "cli_fixture_request",
                    "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&redirect=true",
                    "poll_path": "/auth/cli/poll/cli_fixture_request",
                    "google_token_returned": False,
                    "refresh_token_returned": False,
                },
            )
        return (
            200,
            {
                "status": "linked",
                "linked": True,
                "request_id": "cli_fixture_request",
                "session": {
                    "type": "browser_cookie",
                    "token_returned": False,
                    "bearer_authorization_supported": True,
                    "cookie_name": "__Host-yonerai-staging",
                },
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(
        bridge=True,
        wait_linked=True,
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_cli_session_unavailable"
    assert report["cli_bridge"]["linked_without_cli_session"] is True
    assert report["cli_bridge"]["linked_without_session_claim"] is True
    assert report["cli_bridge"]["waited_until_linked"] is True
    assert report["cli_bridge"]["poll"]["session"]["token_returned"] is False
    assert report["cli_bridge"]["poll"]["session"]["bearer_authorization_supported"] is True
    assert report["staging_linked"] is False
    assert report["staging_linked_claim"] is None
    assert report["staging_session_token_stored"] is False
    assert "Traceback" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_browser_open_exception_falls_back(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&redirect=true",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    monkeypatch.setattr("yonerai_cli.auth_policy.webbrowser.open", lambda url: (_ for _ in ()).throw(RuntimeError("no browser")))

    report = build_google_login_staging(bridge=True, open_browser=True, transport=transport)

    assert report["ok"] is True
    assert report["browser_open_requested"] is True
    assert report["browser_opened"] is False
    assert report["authorization_url_printed"] is True


def test_staging_claim_keeps_common_display_name_characters_and_avoids_false_secret_hits() -> None:
    from yonerai_cli.services.auth_session_service import build_staging_auth_claim

    claim = build_staging_auth_claim(
        origin="https://api-staging.yonerai.com",
        account={"email": "secretary@example.com", "display_name": "Codey (Dev) & Team, Inc!"},
    )
    serialized = json.dumps(claim, sort_keys=True)

    assert claim["account"]["display_name"] == "Codey (Dev) & Team, Inc!"
    assert claim["account"]["email_redacted"] == "s***@example.com"
    assert "secretary@example.com" not in serialized


def test_google_login_staging_wait_link_fails_closed_when_not_completed(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        if method == "POST":
            return (
                200,
                {
                    "status": "created",
                    "request_id": "cli_fixture_request",
                    "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&redirect=true",
                    "poll_path": "/auth/cli/poll/cli_fixture_request",
                    "google_token_returned": False,
                    "refresh_token_returned": False,
                },
            )
        return (
            200,
            {
                "status": "pending",
                "request_id": "cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(
        bridge=True,
        wait_linked=True,
        max_wait_seconds=0.01,
        poll_interval_seconds=0.25,
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_link_not_completed"
    assert report["cli_bridge"]["waited_until_linked"] is False
    assert report["staging_session_token_stored"] is False
    assert "Traceback" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_auth_claim_storage_redacts_and_rejects_secret_material(tmp_path: Path) -> None:
    from yonerai_cli.services.auth_session_service import (
        build_staging_auth_claim,
        load_staging_auth_claim,
        save_staging_auth_claim,
        validate_staging_auth_claim,
    )

    config_path = tmp_path / "cli-config.json"
    claim = build_staging_auth_claim(
        origin="https://api-staging.yonerai.com",
        account={"email": "owner@example.com", "sub": "google-subject"},
    )
    saved = save_staging_auth_claim(claim, config_path=config_path)
    loaded = load_staging_auth_claim(config_path)
    serialized = json.dumps(loaded, sort_keys=True)

    assert saved["auth_state"] == "linked"
    assert loaded["account"]["email_redacted"] == "o***@example.com"
    assert loaded["account"]["raw_email_stored"] is False
    assert loaded["account"]["raw_subject_stored"] is False
    assert loaded["storage"]["staging_session_token_stored"] is False
    assert "owner@example.com" not in serialized
    assert "google-subject" not in serialized
    with pytest.raises(ValueError):
        validate_staging_auth_claim({"auth_state": "linked", "access_token": "secret"})


def test_staging_claim_save_failure_is_controlled_and_redacted(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.commands.auth import _persist_staging_claim_if_linked

    def fail_save(claim: dict[str, object], *, config_path: str | None = None) -> dict[str, object]:
        raise ValueError(f"cannot write {tmp_path / 'cli-config.json'}")

    monkeypatch.setattr("yonerai_cli.commands.auth.save_staging_auth_claim", fail_save)
    report: dict[str, object] = {
        "ok": True,
        "staging_linked": True,
        "staging_linked_claim": {"auth_state": "linked", "account": {"email_redacted": "o***@example.com"}},
    }

    _persist_staging_claim_if_linked(report, config_path=str(tmp_path / "cli-config.json"))
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["staging_linked"] is False
    assert report["staging_linked_claim"] is None
    assert report["staging_claim_saved"] is False
    assert report["error"]["code"] == "staging_claim_save_failed"  # type: ignore[index]
    assert report["error"]["private_path_printed"] is False  # type: ignore[index]
    assert "cannot write" not in serialized
    assert str(tmp_path) not in serialized


def test_auth_status_reads_saved_linked_staging_claim(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services.auth_session_service import build_staging_auth_claim, save_staging_auth_claim

    config_path = tmp_path / "cli-config.json"
    save_staging_auth_claim(
        build_staging_auth_claim(
            origin="https://api-staging.yonerai.com",
            account={"email": "owner@example.com", "display_name": "Owner"},
        ),
        config_path=config_path,
    )
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    assert cli.main(["auth", "status", "--json", "--config-path", str(config_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["staging_auth_state"] == "linked"
    assert report["staging_account"]["email_redacted"] == "o***@example.com"
    assert report["staging_session"]["storage"]["staging_session_token_stored"] is False
    assert "owner@example.com" not in serialized
    assert str(tmp_path) not in serialized


def test_auth_status_prefers_canonical_session_account_for_display(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services.auth_session_service import build_staging_auth_claim, save_staging_auth_claim
    from yonerai_cli.services.staging_session_service import save_staging_session

    config_path = tmp_path / "cli-config.json"
    save_staging_auth_claim(
        build_staging_auth_claim(
            origin="https://api-staging.yonerai.com",
            account={"account_ref": "staging-account-legacyhash", "display_name": "Owner"},
        ),
        config_path=config_path,
    )
    save_staging_session(
        session_token="ystg_session_fixture_123",
        origin="https://api-staging.yonerai.com",
        account={
            "account_id": "acct_google_canonical123",
            "email_redacted": "o***@example.com",
            "display_name": "Owner",
        },
        expires_at="2099-06-06T00:30:00Z",
        config_path=config_path,
    )
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    assert cli.main(["auth", "status", "--json", "--config-path", str(config_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["staging_auth_state"] == "linked"
    assert report["staging_account"]["account_id"] == "acct_google_canonical123"
    assert report["staging_session_claim"]["account_id"] == "acct_google_canonical123"
    assert report["staging_session"]["account"]["account_id"] == "acct_google_canonical123"
    assert "staging-account-legacyhash" not in serialized
    assert "ystg_session_fixture_123" not in serialized
    assert str(tmp_path) not in serialized


def test_auth_session_status_reads_safe_staging_session_without_printing_token(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services.staging_session_service import save_staging_session

    config_path = tmp_path / "cli-config.json"
    save_staging_session(
        session_token="ystg_session_fixture_123",
        origin="https://api-staging.yonerai.com",
        account={"email": "owner@example.com", "display_name": "Owner", "sub": "google-subject-private"},
        expires_at="2099-06-06T00:30:00Z",
        config_path=config_path,
    )
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))

    assert cli.main(["auth", "session", "status", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["auth_state"] == "linked"
    assert report["session_available"] is True
    assert report["redacted_email"] == "o***@example.com"
    assert report["token_printed"] is False
    assert report["google_access_token_stored"] is False
    assert report["google_refresh_token_stored"] is False
    assert report["plaintext_session_token_stored"] is False
    assert "ystg_session_fixture_123" not in serialized
    assert "owner@example.com" not in serialized
    assert str(tmp_path) not in serialized


def test_explicit_config_paths_do_not_share_staging_auth_sidecars(tmp_path: Path) -> None:
    from yonerai_cli.auth_policy import build_google_auth_status
    from yonerai_cli.services.auth_session_service import (
        build_staging_auth_claim,
        default_staging_auth_claim_path,
        save_staging_auth_claim,
    )
    from yonerai_cli.services.staging_session_service import (
        default_staging_session_claim_path,
        default_staging_session_secret_path,
        save_staging_session,
    )

    first_config = tmp_path / "first.json"
    second_config = tmp_path / "second.json"
    save_staging_auth_claim(
        build_staging_auth_claim(
            origin="https://api-staging.yonerai.com",
            account={"email": "owner@example.com", "display_name": "Owner", "sub": "google-subject-private"},
        ),
        config_path=first_config,
    )
    save_staging_session(
        session_token="ystg_session_fixture_123",
        origin="https://api-staging.yonerai.com",
        account={"email": "owner@example.com", "display_name": "Owner"},
        expires_at="2099-06-06T00:30:00Z",
        config_path=first_config,
    )

    assert default_staging_auth_claim_path(first_config).name == "first.staging-auth-claim.json"
    assert default_staging_session_claim_path(first_config).name == "first.staging-session-claim.json"
    assert default_staging_session_secret_path(first_config).name == "first.staging-session-token.dpapi"

    first = build_google_auth_status({}, claim_path=str(first_config))
    second = build_google_auth_status({}, claim_path=str(second_config))

    assert first["staging_auth_state"] == "linked"
    assert second["staging_auth_state"] == "unauthenticated"


def test_staging_session_loads_and_clears_legacy_sidecar_names(tmp_path: Path, monkeypatch) -> None:
    import base64

    from yonerai_cli.services import staging_session_service
    from yonerai_cli.services.staging_session_service import (
        build_staging_session_claim,
        clear_staging_session,
        default_staging_session_claim_path,
        legacy_staging_session_claim_path,
        legacy_staging_session_secret_path,
        load_staging_session_token,
    )

    config_path = tmp_path / "custom-cli-config.json"
    token = "ystg_session_fixture_legacy_123"
    claim = build_staging_session_claim(
        session_token=token,
        origin="https://api-staging.yonerai.com",
        account={"email": "owner@example.com", "display_name": "Owner"},
        expires_at="2099-06-06T00:30:00Z",
        storage_backend="windows_dpapi_file",
    )
    legacy_claim = legacy_staging_session_claim_path(config_path)
    legacy_secret = legacy_staging_session_secret_path(config_path)
    legacy_claim.write_text(json.dumps(claim, ensure_ascii=False), encoding="utf-8")
    legacy_secret.write_text("dpapi:v1:" + base64.b64encode(b"wrapped-secret").decode("ascii"), encoding="ascii")

    monkeypatch.setattr(staging_session_service, "_dpapi_unprotect", lambda _data: token.encode("utf-8"))

    loaded_token, loaded_claim = load_staging_session_token(config_path)
    assert loaded_token == token
    assert loaded_claim["auth_state"] == "linked"
    assert not default_staging_session_claim_path(config_path).exists()

    report = clear_staging_session(config_path)
    assert report["ok"] is True
    assert report["session_removed"] is True
    assert not legacy_claim.exists()
    assert not legacy_secret.exists()


def test_auth_logout_staging_clears_safe_session_without_printing_paths(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services.staging_session_service import save_staging_session

    config_path = tmp_path / "cli-config.json"
    save_staging_session(
        session_token="ystg_session_fixture_123",
        origin="https://api-staging.yonerai.com",
        account={"email": "owner@example.com", "display_name": "Owner"},
        expires_at="2099-06-06T00:30:00Z",
        config_path=config_path,
    )
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))

    assert cli.main(["auth", "logout", "--staging", "--json"]) == 0
    logout_report = json.loads(capsys.readouterr().out)
    assert logout_report["session_removed"] is True
    assert logout_report["token_printed"] is False

    assert cli.main(["auth", "session", "status", "--json"]) == 0
    status_report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(status_report, sort_keys=True)

    assert status_report["auth_state"] == "unauthenticated"
    assert status_report["session_available"] is False
    assert "ystg_session_fixture_123" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_session_rejects_case_insensitive_local_paths() -> None:
    from yonerai_cli.services.staging_session_service import build_staging_session_claim, validate_staging_session_claim

    claim = build_staging_session_claim(
        session_token="ystg_session_fixture_123",
        origin="https://api-staging.yonerai.com",
        account={"email": "owner@example.com", "display_name": "Owner"},
        expires_at="2099-06-06T00:30:00Z",
        storage_backend="memory_session_only",
    )
    claim["display_name"] = "/users/example/private"

    with pytest.raises(ValueError, match="local path"):
        validate_staging_session_claim(claim)


def test_auth_logout_staging_reports_delete_failure_safely(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services.staging_session_service import clear_staging_session, default_staging_session_claim_path

    config_path = tmp_path / "cli-config.json"
    claim_path = default_staging_session_claim_path(config_path)
    claim_path.write_text("{}", encoding="utf-8")

    def deny_unlink(self: Path) -> None:
        raise OSError("locked path should not be printed")

    monkeypatch.setattr(Path, "unlink", deny_unlink)
    report = clear_staging_session(config_path)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["session_removed"] is False
    assert report["error"]["code"] == "staging_session_clear_failed"  # type: ignore[index]
    assert report["error"]["local_path_printed"] is False  # type: ignore[index]
    assert str(tmp_path) not in serialized
    assert "locked path" not in serialized


def test_google_login_staging_bridge_fails_closed_on_token_return(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&redirect=true",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token": "must-not-print",
                "google_token_returned": True,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_token_return_forbidden"
    assert report["authorization_url_printed"] is False
    assert report["authorization_url"] is None
    assert "must-not-print" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_bridge_fails_closed_on_nested_token_return(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth/google/start?cli_request_id=cli_fixture_request&redirect=true",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
                "data": {"access_token": "nested-must-not-print"},
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_token_return_forbidden"
    assert report["authorization_url_printed"] is False
    assert report["authorization_url"] is None
    assert "nested-must-not-print" not in serialized
    assert str(tmp_path) not in serialized


@pytest.mark.parametrize(
    "metadata_value",
    [
        "staging_session_token=redacted",
        "session_token=redacted",
        "google_access_token=redacted",
        '"session_token": "redacted"',
        "'session_token': 'redacted'",
        "local_path=C:/Users/example/status.json",
        "local_path=/tmp/status.json",
        "local_path=/var/tmp/status.json",
        "local_path=/workspace/status.json",
    ],
)
def test_google_login_staging_bridge_rejects_token_named_session_metadata_values(
    metadata_value: str,
    tmp_path: Path,
    monkeypatch,
) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "pending",
                "request_id": "cli_fixture_request",
                "session": {
                    "type": metadata_value,
                    "token_field": metadata_value,
                    "token_returned": False,
                },
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_session_type_invalid"
    assert metadata_value not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_bridge_rejects_cross_origin_paths(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "https://evil.test/auth/google/start",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_browser_start_path_invalid"
    assert report["authorization_url_printed"] is False
    assert report["authorization_url"] is None
    assert "evil.test" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_bridge_rejects_backslash_paths(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/auth\\google\\start",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_browser_start_path_invalid"
    assert report["authorization_url_printed"] is False
    assert report["authorization_url"] is None
    assert "\\google" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_bridge_rejects_unexpected_relative_start_path(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "status": "created",
                "request_id": "cli_fixture_request",
                "browser_start_path": "/internal/debug",
                "poll_path": "/auth/cli/poll/cli_fixture_request",
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(bridge=True, transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_bridge_browser_start_path_invalid"
    assert report["authorization_url_printed"] is False
    assert report["authorization_url"] is None
    assert "/internal/debug" not in serialized
    assert str(tmp_path) not in serialized


def test_staging_bridge_transport_rejects_redirect_before_following() -> None:
    from yonerai_cli.staging_auth_bridge import StagingAuthBridgeError, _default_json_transport

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server callback name
            self.send_response(302)
            self.send_header("Location", "https://evil.test/auth/cli/start")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(StagingAuthBridgeError) as exc_info:
            _default_json_transport("POST", f"http://127.0.0.1:{server.server_port}/auth/cli/start", None, 2.0)
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert exc_info.value.code == "staging_bridge_redirect_forbidden"
    assert exc_info.value.status_code == 302


def test_staging_bridge_transport_preserves_http_error_with_non_json_body() -> None:
    from yonerai_cli.staging_auth_bridge import _default_json_transport

    class BadGatewayHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server callback name
            self.send_response(502)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>bad gateway</html>")

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), BadGatewayHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status_code, body = _default_json_transport(
            "POST",
            f"http://127.0.0.1:{server.server_port}/auth/cli/start",
            None,
            2.0,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert status_code == 502
    assert body == {}


def test_google_login_staging_allows_explicit_loopback_dev_origin(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "http://127.0.0.1:8787")
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ALLOW_LOCALHOST_DEV", "1")

    assert cli.main(["auth", "google", "login", "--staging", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["configured"] is True
    assert report["staging"]["origin"] == "http://127.0.0.1:8787"
    assert report["staging"]["localhost_dev_allowed"] is True
    assert report["authorization_url"] == "http://127.0.0.1:8787/auth/google/start"
    assert report["production_login_enabled"] is False
    assert report["token_exchange_performed"] is False
    assert "YONERAI_GOOGLE_OAUTH_CLIENT_SECRET" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_preserves_ipv6_loopback_dev_brackets(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "http://[::1]:8787")
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ALLOW_LOCALHOST_DEV", "1")

    assert cli.main(["auth", "google", "login", "--staging", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["staging"]["origin"] == "http://[::1]:8787"
    assert report["authorization_url"] == "http://[::1]:8787/auth/google/start"
    assert "http://::1:8787" not in serialized
    assert str(tmp_path) not in serialized


@pytest.mark.parametrize(
    "origin",
    [
        "http://api-staging.yonerai.com",
        "https://127.0.0.1",
        "https://10.0.0.5",
        "https://metadata.google.internal",
        "https://api-staging.yonerai.com.evil.test",
        "https://api-staging.yonerai.com/path",
        "https://user:pass@api-staging.yonerai.com",
    ],
)
def test_google_login_staging_rejects_disallowed_origins_without_echoing_value(
    origin: str,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", origin)

    assert cli.main(["auth", "google", "login", "--staging", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["configured"] is False
    assert report["staging"]["origin"] == "invalid_or_disallowed"
    assert report["authorization_url"] is None
    assert report["token_exchange_performed"] is False
    assert origin not in serialized
    assert "user:pass" not in serialized
    assert "10.0.0.5" not in serialized


def test_google_login_staging_rejects_malformed_port_without_traceback(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    origin = "https://api-staging.yonerai.com:bad"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", origin)

    assert cli.main(["auth", "google", "login", "--staging", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["configured"] is False
    assert report["staging"]["origin"] == "invalid_or_disallowed"
    assert report["authorization_url"] is None
    assert report["error"]["code"] == "staging_origin_invalid"
    assert origin not in serialized
    assert "Traceback" not in serialized
    assert str(tmp_path) not in serialized


def test_google_login_staging_rejects_malformed_redirect_port_without_printing_it(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli

    redirect_uri = "http://127.0.0.1:bad/oauth/google/callback"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    monkeypatch.setenv("YONERAI_GOOGLE_OAUTH_REDIRECT_URI", redirect_uri)

    assert cli.main(["auth", "google", "login", "--staging", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["configured"] is False
    assert report["authorization_url"] is None
    assert report["flow"]["redirect_valid"] is False
    assert report["flow"]["redirect_uri"] == "http://127.0.0.1:8765/oauth/google/callback"
    assert report["error"]["code"] == "redirect_uri_invalid"
    assert redirect_uri not in serialized
    assert "Traceback" not in serialized
    assert str(tmp_path) not in serialized


def test_google_staging_redirect_validation_rejects_unexpected_host() -> None:
    from yonerai_cli.auth_policy import validate_staging_redirect_location

    accepted = validate_staging_redirect_location(
        "https://api-staging.yonerai.com/v1/auth/google/callback",
        "https://api-staging.yonerai.com",
    )
    rejected = validate_staging_redirect_location(
        "https://evil.test/v1/auth/google/callback",
        "https://api-staging.yonerai.com",
    )

    assert accepted["valid"] is True
    assert accepted["actual_host"] == "api-staging.yonerai.com"
    assert rejected["valid"] is False
    assert rejected["reason"] == "redirect_host_not_allowed"
    assert rejected["actual_host"] == "redacted"


def test_google_staging_redirect_validation_accepts_explicit_localhost_dev() -> None:
    from yonerai_cli.auth_policy import validate_staging_redirect_location

    accepted = validate_staging_redirect_location(
        "http://127.0.0.1:8787/v1/auth/google/callback",
        "http://127.0.0.1:8787",
        env={"YONERAI_STAGING_AUTH_ALLOW_LOCALHOST_DEV": "1"},
    )
    rejected = validate_staging_redirect_location(
        "http://127.0.0.1:8788/v1/auth/google/callback",
        "http://127.0.0.1:8787",
        env={"YONERAI_STAGING_AUTH_ALLOW_LOCALHOST_DEV": "1"},
    )

    assert accepted["valid"] is True
    assert accepted["actual_host"] == "127.0.0.1"
    assert rejected["valid"] is False
    assert rejected["actual_host"] == "redacted"


def test_google_staging_redirect_validation_accepts_ipv6_loopback_dev() -> None:
    from yonerai_cli.auth_policy import validate_staging_redirect_location

    accepted = validate_staging_redirect_location(
        "http://[::1]:8787/v1/auth/google/callback",
        "http://[::1]:8787",
        env={"YONERAI_STAGING_AUTH_ALLOW_LOCALHOST_DEV": "1"},
    )

    assert accepted["valid"] is True
    assert accepted["actual_host"] == "::1"


def test_google_login_requires_staging_or_dry_run_flag(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))

    assert cli.main(["auth", "google", "login", "--json"]) == 2
    stderr = capsys.readouterr().err

    assert "--dry-run" in stderr
    assert "--staging" in stderr
    assert str(tmp_path) not in stderr


def test_google_login_rejects_non_loopback_redirect(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_GOOGLE_OAUTH_CLIENT_ID", "fixture-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("YONERAI_GOOGLE_OAUTH_REDIRECT_URI", "https://yonerai.com/oauth/google/callback")

    assert cli.main(["auth", "google", "login", "--dry-run", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)

    assert report["configured"] is False
    assert report["flow"]["loopback_redirect_only"] is True
    assert report["flow"]["redirect_valid"] is False
    assert report["error"]["code"] == "redirect_uri_must_be_loopback_http"


@pytest.mark.parametrize(
    "redirect_uri",
    [
        "http://user:pass@127.0.0.1:8765/oauth/google/callback",
        "http://127.0.0.1:8765/oauth/google/callback?code=secret",
        "http://127.0.0.1:8765/oauth/google/callback#token",
    ],
)
def test_google_login_rejects_loopback_redirect_with_unsafe_components(
    redirect_uri: str,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_GOOGLE_OAUTH_CLIENT_ID", "fixture-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("YONERAI_GOOGLE_OAUTH_REDIRECT_URI", redirect_uri)

    assert cli.main(["auth", "google", "login", "--dry-run", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report)

    assert report["configured"] is False
    assert report["flow"]["redirect_valid"] is False
    assert report["flow"]["redirect_uri"] == "http://127.0.0.1:8765/oauth/google/callback"
    assert report["error"]["code"] == "redirect_uri_must_not_include_credentials_query_or_fragment"
    assert "user:pass" not in serialized
    assert "code=secret" not in serialized
    assert "#token" not in serialized


def test_google_login_without_dry_run_is_rejected(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["auth", "google", "login"]) == 2
    captured = capsys.readouterr()

    assert "requires --dry-run" in captured.err
    assert "Traceback" not in captured.err


def test_privacy_status_keeps_openai_shared_traffic_disabled(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))

    assert cli.main(["config", "set", "openai_data_sharing", "on", "--json"]) == 0
    capsys.readouterr()
    assert cli.main(["privacy", "status", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["data_sharing"]["openai_shared_traffic_requested"] is True
    assert report["data_sharing"]["openai_shared_traffic_enabled"] is False
    assert report["data_sharing"]["requires_explicit_opt_in"] is True
    assert report["private_content_exclusion"]["active"] is True
    assert "workspace-local file content" in report["private_content_exclusion"]["excluded"]
    assert report["ledger"]["shared_traffic_flag_recorded"] is True
    assert report["ledger"]["default_shared_traffic"] is False
    assert report["quota"]["free_usage_claimed"] is False
    assert "no OpenAI shared traffic enabled" in report["actions_not_performed"]


def test_auto_runtime_records_shared_traffic_disabled_in_report_and_ledger() -> None:
    from ora_core.execution import InMemoryRunLedger, build_auto_runtime_report

    report = build_auto_runtime_report("hello", ledger=InMemoryRunLedger())
    event_names = [event["name"] for event in report["run"]["events"]]

    assert report["shared_traffic"]["enabled"] is False
    assert report["shared_traffic"]["private_content_excluded"] is True
    assert "shared_traffic_policy" in event_names
    assert report["boundaries"]["provider_key_output"] is False

def test_google_login_staging_manual_poll_fails_when_linked_without_cli_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from yonerai_cli.auth_policy import build_google_login_staging

    def transport(method: str, url: str, body: object, timeout: float) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        assert url.endswith("/auth/cli/poll/cli_fixture_request")
        return (
            200,
            {
                "status": "linked",
                "linked": True,
                "request_id": "cli_fixture_request",
                "session": {
                    "token_returned": False,
                    "bearer_authorization_supported": True,
                    "browser_cookie_session_present": True,
                },
                "google_token_returned": False,
                "refresh_token_returned": False,
            },
        )

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    report = build_google_login_staging(poll_request_id="cli_fixture_request", transport=transport)
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_cli_session_unavailable"
    assert report["cli_bridge"]["linked_without_cli_session"] is True
    assert report["cli_bridge"]["linked_without_session_claim"] is True
    assert report["cli_bridge"]["poll"]["session"]["token_returned"] is False
    assert report["staging_linked"] is False
    assert report["staging_linked_claim"] is None
    assert report["staging_session_token_stored"] is False
    assert "Traceback" not in serialized
    assert str(tmp_path) not in serialized
