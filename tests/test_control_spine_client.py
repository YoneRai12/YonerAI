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
                        "min_cli_version": "0.8.0",
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


def test_rate_limit_drops_known_private_operational_metadata(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services.control_spine_service import build_control_spine_rate_limit_report

    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        assert url.endswith("/v1/rate-limit")
        return (
            200,
            {
                "allowed": True,
                "scope": "anonymous",
                "fallback_reason": "within_quota",
                "quota_exceeded": False,
                "control_spine": {
                    "contract_version": "yonerai.control-spine.v0.1",
                    "scopes": [
                        {"name": "profile:read", "enabled_by_default": True, "summary": "read profile"},
                        {"name": "agent:run", "enabled_by_default": True, "summary": "requires gate"},
                    ],
                },
                "cost_guard": {
                    "secrets_lifecycle": {"google_client_secret": {"storage": "aws_secrets_manager_reference_only"}},
                    "notification_channel": "yonerai_staging_alerts_sns_topic",
                },
            },
            {"X-YonerAI-RateLimit-Scope": "anonymous"},
        )

    report = build_control_spine_rate_limit_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(tmp_path / "cli-config.json"),
        transport=transport,
        timeout_seconds=3.0,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is True
    assert report["rate_limit"]["body"]["scope"] == "anonymous"
    assert "cost_guard" not in serialized
    assert "google_client_secret" not in serialized
    assert "yonerai_staging_alerts_sns_topic" not in serialized
    agent_scope = next(scope for scope in report["scopes"] if scope["name"] == "agent:run")
    assert agent_scope["enabled_by_default"] is False
    assert agent_scope["requires_threat_model"] is True


def test_rate_limit_public_sanitizer_handles_null_and_bad_scope_shapes(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services.control_spine_service import build_control_spine_rate_limit_report

    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        assert url.endswith("/v1/rate-limit")
        return (
            200,
            {
                "allowed": True,
                "scope": "anonymous",
                "fallback_reason": "within_quota",
                "quota_exceeded": False,
                "control_spine": {
                    "contract_version": "yonerai.control-spine.v0.1",
                    "admin_scopes_disabled": None,
                    "session_scopes": None,
                    "scopes": [
                        {"name": None, "enabled_by_default": True, "summary": "missing name"},
                        {"name": 123, "enabled_by_default": True, "summary": "bad name"},
                        {"name": "profile:read", "enabled_by_default": True, "summary": "read profile"},
                    ],
                },
            },
            {"X-YonerAI-RateLimit-Scope": "anonymous"},
        )

    report = build_control_spine_rate_limit_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(tmp_path / "cli-config.json"),
        transport=transport,
        timeout_seconds=3.0,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is True
    control = report["rate_limit"]["body"]["control_spine"]
    assert control["admin_scopes_disabled"] == []
    assert control["session_scopes"] == []
    assert [scope["name"] for scope in control["scopes"]] == [
        "scope:redacted",
        "scope:redacted",
        "profile:read",
    ]
    assert "Traceback" not in serialized
    assert str(tmp_path) not in serialized


def test_rate_limit_rejects_unexpected_token_fields(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services.control_spine_service import build_control_spine_rate_limit_report

    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        assert url.endswith("/v1/rate-limit")
        return 200, {"allowed": True, "scope": "anonymous", "access_token": "must-not-print"}, {}

    report = build_control_spine_rate_limit_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(tmp_path / "cli-config.json"),
        transport=transport,
        timeout_seconds=3.0,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "control_spine_private_payload_rejected"
    assert "must-not-print" not in serialized
    assert str(tmp_path) not in serialized


def test_status_rejects_generic_session_token_payload(tmp_path: Path, monkeypatch) -> None:
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
            return 200, {"status": "ok", "session_token": "must-not-print"}, {}
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
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["backend_status"]["ok"] is False
    assert report["backend_status"]["error"]["code"] == "control_spine_private_payload_rejected"
    assert "must-not-print" not in serialized
    assert str(tmp_path) not in serialized


def test_rate_limit_rejects_generic_token_payload(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services.control_spine_service import build_control_spine_rate_limit_report

    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        assert url.endswith("/v1/rate-limit")
        return 200, {"allowed": True, "scope": "anonymous", "token": "must-not-print"}, {}

    report = build_control_spine_rate_limit_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(tmp_path / "cli-config.json"),
        transport=transport,
        timeout_seconds=3.0,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "control_spine_private_payload_rejected"
    assert "must-not-print" not in serialized
    assert str(tmp_path) not in serialized


def test_status_rejects_https_private_endpoint_payload(tmp_path: Path, monkeypatch) -> None:
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
            return 200, {"status": "ok", "runbook": "https://10.0.0.5/runbook"}, {}
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
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["backend_status"]["ok"] is False
    assert report["backend_status"]["error"]["code"] == "control_spine_private_payload_rejected"
    assert "10.0.0.5" not in serialized
    assert str(tmp_path) not in serialized


def test_status_rejects_172_private_endpoint_payload(tmp_path: Path, monkeypatch) -> None:
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
            return 200, {"status": "ok", "runbook": "http://172.20.1.5/runbook"}, {}
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
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["backend_status"]["ok"] is False
    assert report["backend_status"]["error"]["code"] == "control_spine_private_payload_rejected"
    assert "172.20.1.5" not in serialized
    assert str(tmp_path) not in serialized


def test_error_detail_rejects_bearer_secret_text(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services.control_spine_service import build_control_spine_ping_report

    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        return 400, {"detail": {"reason": "Bearer must-not-print-secret"}}, {}

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


def test_whoami_accepts_contract_account_id_after_sanitizing(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services.control_spine_service import build_whoami_report
    from yonerai_cli.services.staging_session_service import load_staging_session_claim, save_staging_session

    config_path = tmp_path / "cli-config.json"
    session_value = "opaque-session-value-123456789"
    raw_account_id = "acct_contract_visible_123"
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
        assert url == "https://api-staging.yonerai.com/v1/whoami"
        return (
            200,
            {
                "account": {
                    "account_id": raw_account_id,
                    "email": "owner@example.test",
                    "display_name": "Owner",
                }
            },
            {"X-YonerAI-RateLimit-Scope": "staging"},
        )

    report = build_whoami_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is True
    assert report["account"]["account_id"] == raw_account_id
    assert report["account"]["account_ref"].startswith("staging-account-")
    assert report["account"]["email_redacted"] == "o***@example.test"
    assert report["staging_session_claim_updated"] is True
    assert report["staging_session_account_id"] == raw_account_id
    updated_claim = load_staging_session_claim(config_path=str(config_path))
    assert updated_claim["account_id"] == raw_account_id
    assert session_value not in serialized
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
        assert url == "https://api-staging.yonerai.com/v1/whoami"
        assert headers["Authorization"] == f"Bearer {session_value}"
        return (
            200,
            {
                "account": {
                    "email": "owner@example.test",
                    "display_name": "Owner",
                    "account_id": "acct_contract_safe_ref_123",
                    "sub": "google-subject",
                }
            },
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
    assert report["account"]["account_id"] == "acct_contract_safe_ref_123"
    assert report["account"]["email_redacted"] == "o***@example.test"
    assert str(report["account"]["account_ref"]).startswith("staging-account-")
    assert session_value not in serialized
    assert "google-subject" not in serialized
    assert str(tmp_path) not in serialized


def test_whoami_falls_back_to_account_me_when_new_endpoint_missing(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services.control_spine_service import build_whoami_report
    from yonerai_cli.services.staging_session_service import save_staging_session

    config_path = tmp_path / "cli-config.json"
    session_value = "opaque-session-value-123456789"
    calls: list[str] = []
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
        assert headers["Authorization"] == f"Bearer {session_value}"
        calls.append(url)
        if url.endswith("/v1/whoami"):
            return 404, {"detail": {"reason": "not_found"}}, {"X-YonerAI-RateLimit-Scope": "staging"}
        assert url == "https://api-staging.yonerai.com/v1/account/me"
        return (
            200,
            {"account": {"email": "owner@example.test", "display_name": "Owner"}},
            {"X-YonerAI-RateLimit-Scope": "staging"},
        )

    report = build_whoami_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is True
    assert calls == [
        "https://api-staging.yonerai.com/v1/whoami",
        "https://api-staging.yonerai.com/v1/account/me",
    ]
    assert report["account"]["email_redacted"] == "o***@example.test"
    assert session_value not in serialized
    assert str(tmp_path) not in serialized


def test_whoami_fallback_uses_top_level_saved_session_account(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services.control_spine_service import build_whoami_report
    from yonerai_cli.services.staging_session_service import save_staging_session

    config_path = tmp_path / "cli-config.json"
    save_staging_session(
        session_token="opaque-session-value-123456789",
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
        return 503, {"error": {"code": "temporary_unavailable"}}, {"X-YonerAI-RateLimit-Scope": "staging"}

    report = build_whoami_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is False
    assert report["account_linked"] is True
    assert report["linked_claim_account"]["display_name"] == "Owner"  # type: ignore[index]
    assert report["linked_claim_account"]["email_redacted"] == "o***@example.test"  # type: ignore[index]
    assert "opaque-session-value" not in serialized
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
    assert "/ログイン" in rendered
    assert "Traceback" not in serialized
    assert str(tmp_path) not in serialized


def test_localized_session_expired_message_is_case_insensitive() -> None:
    from yonerai_cli.cli import _localized_cli_error

    rendered = _localized_cli_error("Saved Session Expired", [])

    assert "yonerai login" in rendered
    assert "期限" in rendered
    assert "Saved Session Expired" not in rendered


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
    assert "/更新" in rendered
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


def test_public_cli_control_spine_commands_do_not_default_to_staging_origin(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))
    monkeypatch.delenv("YONERAI_STAGING_AUTH_ORIGIN", raising=False)
    monkeypatch.delenv("YONERAI_OFFICIAL_API_STAGING_ORIGIN", raising=False)

    assert cli.main(["whoami", "--json"]) == 1
    whoami = json.loads(capsys.readouterr().out)
    assert whoami["backend_url"] == "not_configured"
    assert whoami["staging_origin_configured"] is False
    assert whoami["official_backend_called"] is False
    assert whoami["error"]["code"] == "staging_origin_not_configured"

    assert cli.main(["project", "list", "--json"]) == 1
    projects = json.loads(capsys.readouterr().out)
    assert projects["backend_url"] == "not_configured"
    assert projects["staging_origin_configured"] is False
    assert projects["official_backend_called"] is False
    assert projects["error"]["code"] == "staging_origin_not_configured"

    assert cli.main(["audit", "list", "--json"]) == 1
    audit = json.loads(capsys.readouterr().out)
    assert audit["backend_url"] == "not_configured"
    assert audit["staging_origin_configured"] is False
    assert audit["official_backend_called"] is False
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
    assert report["staging_login_available"] is True


def test_format_login_flow_compact_uses_staging_report_without_legacy_flag() -> None:
    from yonerai_cli.screens.control_spine import format_login_flow_compact

    report = {
        "ok": True,
        "configured": True,
        "staging": {
            "configured": True,
            "origin": "https://api-staging.yonerai.com",
        },
        "authorization_url": "https://api-staging.yonerai.com/auth/google/start",
        "browser_opened": False,
        "next_safe_command": "yonerai login",
        "cli_bridge": {},
    }

    rendered = format_login_flow_compact(report, lang="ja")

    assert "ステージング Google ログインだけ利用できます。" not in rendered
    assert "次のURLをブラウザで開いてください。" in rendered
    assert "https://api-staging.yonerai.com/auth/google/start" in rendered


def test_format_control_spine_compact_keeps_short_user_facing_output() -> None:
    from yonerai_cli.screens.control_spine import format_control_spine_compact

    report = {
        "ok": True,
        "operation": "whoami",
        "account": {"email_redacted": "o***@example.test"},
        "session_expires_at": "2030-01-01T00:00:00Z",
    }

    rendered = format_control_spine_compact(report, lang="ja")

    assert "アカウント" in rendered
    assert "o***@example.test" in rendered
    assert "/セッション" in rendered
    assert "/ログアウト" in rendered
    assert "staging のみ" in rendered
    assert "Control Spine" not in rendered


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


def test_interactive_ping_does_not_inject_staging_origin_when_env_is_missing(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.services import control_spine_callbacks

    monkeypatch.delenv("YONERAI_STAGING_AUTH_ORIGIN", raising=False)
    monkeypatch.delenv("YONERAI_OFFICIAL_API_STAGING_ORIGIN", raising=False)

    seen: dict[str, object] = {}

    def fake_build_ping_report(*, config, env, claim_path, transport=None, timeout_seconds=10.0):  # type: ignore[no-untyped-def]
        seen["env"] = dict(env)
        seen["claim_path"] = claim_path
        return {
            "ok": False,
            "operation": "api_ping",
            "backend_url": env.get("YONERAI_STAGING_AUTH_ORIGIN", "not_configured"),
            "staging_origin_configured": "YONERAI_STAGING_AUTH_ORIGIN" in env,
        }

    monkeypatch.setattr(control_spine_callbacks, "build_control_spine_ping_report", fake_build_ping_report)

    report = control_spine_callbacks.interactive_ping_status("ja", config_path=str(tmp_path / "cli-config.json"))

    assert report is not None
    assert report["backend_url"] == "not_configured"
    assert report["staging_origin_configured"] is False
    assert seen["claim_path"] == str(tmp_path / "cli-config.json")
    assert isinstance(seen["env"], dict)
    assert "YONERAI_STAGING_AUTH_ORIGIN" not in seen["env"]


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



def test_control_spine_ignores_invalid_saved_session_origin(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.commands import api as api_command
    from yonerai_cli.services import control_spine_service

    def fail_transport(*_args: object, **_kwargs: object) -> tuple[int, dict[str, object], dict[str, str]]:
        raise AssertionError("invalid origin must not call transport")

    monkeypatch.delenv("YONERAI_STAGING_AUTH_ORIGIN", raising=False)
    monkeypatch.delenv("YONERAI_OFFICIAL_API_STAGING_ORIGIN", raising=False)
    monkeypatch.setattr(
        control_spine_service,
        "load_staging_session_token",
        lambda _path: ("opaque-session-value-123456789", {"auth_state": "linked", "origin": "configured"}),
    )
    monkeypatch.setattr(
        api_command,
        "load_staging_session_token",
        lambda _path: ("opaque-session-value-123456789", {"auth_state": "linked", "origin": "configured"}),
    )

    context = control_spine_service.build_control_spine_context(config={}, env={}, claim_path=str(tmp_path / "cli.json"))
    report = control_spine_service.build_control_spine_status_report(
        config={},
        env={},
        claim_path=str(tmp_path / "cli.json"),
        transport=fail_transport,
    )

    assert context["origin_configured"] is False
    assert context["origin"] == "not_configured"
    assert context["session_origin_mismatch"] is False
    assert context["session_schema_mismatch"] is False
    assert report["ok"] is True
    assert report["error"]["code"] == "staging_origin_not_configured"
    assert api_command._control_spine_origin_configured(SimpleNamespace(config_path=str(tmp_path / "cli.json"))) is False


def test_staging_session_claim_preserves_allowlisted_origin() -> None:
    from yonerai_cli.services.staging_session_service import build_staging_session_claim, validate_staging_session_claim

    claim = build_staging_session_claim(
        session_token="opaque-session-value-123456789",
        origin="https://api-staging.yonerai.com/",
        account={"email": "owner@example.com", "display_name": "Owner"},
        storage_backend="memory_session_only",
    )
    loaded = validate_staging_session_claim(claim)

    assert claim["origin"] == "https://api-staging.yonerai.com"
    assert loaded["origin"] == "https://api-staging.yonerai.com"

def test_control_spine_slash_commands_are_visible() -> None:
    from yonerai_cli.tui.aliases import canonical_command
    from yonerai_cli.tui.keymap import slash_command_words

    words = slash_command_words("ja")

    assert canonical_command("/ログイン") == "/login"
    assert canonical_command("/loguin") == "/login"
    assert canonical_command("/ローカルLLM") == "/local-llm"
    assert canonical_command("/ローカルllm") == "/local-llm"
    assert canonical_command("/更新") == "/update"
    assert canonical_command("/アカウント") == "/whoami"
    assert canonical_command("/プロジェクト") == "/project"
    assert canonical_command("/セッション") == "/sessions"
    assert canonical_command("/疎通") == "/ping"
    assert canonical_command("/監査") == "/audit"
    assert "/ログイン" in words
    assert "/アカウント" in words
    assert "/プロジェクト" in words
    assert "/セッション" in words
    assert "/疎通" in words
    assert "/監査" in words

def test_whoami_401_token_reason_preserves_auth_guidance_without_printing_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
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
        assert url == "https://api-staging.yonerai.com/v1/whoami"
        assert headers["Authorization"] == f"Bearer {session_value}"
        assert body is None
        return (
            401,
            {"detail": {"reason": "invalid_token", "state": "token_expired"}},
            {"X-YonerAI-RateLimit-Scope": "staging"},
        )

    report = build_whoami_report(
        config={},
        env={"YONERAI_STAGING_AUTH_ORIGIN": "https://api-staging.yonerai.com"},
        claim_path=str(config_path),
        transport=transport,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is False
    assert report["backend_status_code"] == 401
    assert report["error"]["code"] == "staging_session_rejected"
    assert report["error"]["next_safe_command"] == "yonerai login"
    assert report["error"]["repair_command"] == "yonerai logout && yonerai login"
    assert report["error"]["backend_reason"] == "auth_rejected"
    assert "invalid_token" not in serialized
    assert "token_expired" not in serialized
    assert session_value not in serialized
    assert str(tmp_path) not in serialized
