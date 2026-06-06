from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

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
    assert report["next_safe_command"] == "yonerai auth google login --staging --bridge --pretty --lang ja"
    assert report["error"] is None
    assert "YONERAI_GOOGLE_OAUTH_CLIENT_SECRET" not in serialized
    assert str(tmp_path) not in serialized


def test_auth_status_localizes_staging_next_command(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    config_path.write_text(json.dumps({"language": "en"}), encoding="utf-8")
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    assert cli.main(["auth", "status", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["next_safe_command"] == "yonerai auth google login --staging --bridge --pretty --lang en"


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
    assert report["staging_api"]["network_fetch_when"] == "explicit --bridge or --poll-request-id only"
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
    assert report["cli_bridge"]["poll_status"] == "completed"
    assert report["cli_bridge"]["staging_session_received"] is True
    assert report["cli_bridge"]["poll"]["linked_identity"] == "staging_session_claim_received"
    assert "ystg_cli_secret_placeholder" not in serialized
    assert "staging_session_token_printed" in serialized
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
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["staging_linked"] is True
    assert report["staging_session_token_stored"] is False
    assert report["cli_bridge"]["staging_session_received"] is True
    assert report["cli_bridge"]["account_me"]["ok"] is True
    assert report["staging_linked_claim"]["auth_state"] == "linked"
    assert report["staging_linked_claim"]["account"]["email_redacted"] == "o***@example.com"
    assert report["staging_linked_claim"]["storage"]["google_token_stored"] is False
    assert report["staging_linked_claim"]["storage"]["refresh_token_stored"] is False
    assert report["staging_linked_claim"]["storage"]["staging_session_token_stored"] is False
    assert account_headers
    assert "ystg_cli_secret_placeholder" not in serialized
    assert "owner@example.com" not in serialized
    assert str(tmp_path) not in serialized


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
