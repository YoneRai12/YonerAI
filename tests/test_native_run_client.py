from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
if str(CLIENTS_CLI) not in sys.path:
    sys.path.insert(0, str(CLIENTS_CLI))


def _linked_context() -> dict[str, Any]:
    return {
        "origin": "https://api-staging.yonerai.com",
        "origin_configured": True,
        "auth_state": "linked",
        "account_linked": True,
        "session_available": True,
        "session_token": "opaque-yonerai-session",
        "session_claim": {"expires_at": "2026-06-30T00:00:00Z"},
    }


def _unauthenticated_context() -> dict[str, Any]:
    return {
        "origin": "https://api-staging.yonerai.com",
        "origin_configured": True,
        "auth_state": "unauthenticated",
        "account_linked": False,
        "session_available": False,
        "session_token": None,
        "session_claim": {},
    }


def _install_context(monkeypatch, context: dict[str, Any]) -> None:
    from yonerai_cli.services import native_run_service

    monkeypatch.setattr(native_run_service, "build_control_spine_context", lambda **_kwargs: dict(context))


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str], dict[str, object] | None, float]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: dict[str, object] | None,
        timeout_seconds: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        self.calls.append((method, url, headers, body, timeout_seconds))
        rate_headers = {"X-YonerAI-RateLimit-Remaining": "42"}
        if method == "POST" and "/v1/conversations/" in url and url.endswith("/messages"):
            assert body is not None
            assert body["privacy_class"] == "synthetic"
            assert body["role"] == "user"
            assert body["body_on_aws_acknowledged"] is True
            assert "message_text" in body
            return (201, {"message": {"message_body_included": False}}, rate_headers)
        if method == "POST" and "/v1/conversations/" in url and url.endswith("/provider-consent/preview"):
            assert body is not None
            assert "audit_reason" in body
            return (200, {"allowed": True}, rate_headers)
        if method == "POST" and "/v1/conversations/" in url and url.endswith("/provider-consent/approve"):
            assert body is not None
            assert body["explicit_provider_consent"] is True
            assert body["consent_copy_acknowledged"] is True
            return (200, {"provider_traffic_allowed": True}, rate_headers)
        if method == "GET" and "/v1/conversations/" in url and url.endswith("/context-package/manifest"):
            return (200, {"context_manifest": {"raw_content_included": False, "included_message_count": 1}}, rate_headers)
        if method == "POST" and url.endswith("/v1/runs"):
            assert body is not None
            assert body["files"] == []
            input_payload = body["input"]
            assert isinstance(input_payload, dict)
            assert input_payload["raw_file_bytes_included"] is False
            assert input_payload["local_absolute_paths_included"] is False
            provider_body_on_aws = body.get("provider_data_policy") == "openai_shared_explicit"
            if provider_body_on_aws:
                assert body["privacy_class"] == "synthetic"
                assert body["approval_state"] == "staging_auto_approved_metadata_only"
                assert body["body_boundary"] == "body_on_aws"
                assert str(body["conversation_id"]).startswith("cloud-conv-")
                assert body["sync_policy"] == "cloud_to_local"
                assert body["body_on_aws"] is True
                assert body["body_ref"]["message_body_included"] is False
                assert body["message_body_included"] is False
                assert input_payload["kind"] == "cloud_conversation_ref"
                assert input_payload["body_boundary"] == "body_on_aws"
                assert input_payload["body_source"] == "aws_conversation_body"
                assert input_payload["body_ref"]["message_body_included"] is False
                assert input_payload["body_ref"]["plaintext_value_included"] is False
                assert input_payload["message_body_included"] is False
                assert input_payload["plaintext_value_included"] is False
                assert input_payload["current_message_included"] is True
                assert input_payload["local_private_memory_included"] is False
                assert input_payload["provider_keys_included"] is False
                assert input_payload["google_tokens_included"] is False
            else:
                assert body["privacy_class"] == "metadata_only"
                assert body["approval_state"] == "staging_auto_approved_metadata_only"
                assert body["body_boundary"] == "metadata_only"
            conversation = body.get("conversation")
            if conversation is not None:
                assert isinstance(conversation, dict)
                assert conversation["message_body_included"] is False
                assert conversation["raw_body_included"] is False
                assert conversation["provider_keys_included"] is False
            provider_sharing = body.get("provider_sharing")
            assert isinstance(provider_sharing, dict)
            assert provider_sharing["raw_body_included"] is False
            assert provider_sharing["provider_key_included"] is False
            assert provider_sharing["google_token_included"] is False
            context_preview = body.get("context_preview")
            assert isinstance(context_preview, dict)
            assert context_preview["full_history_included"] is False
            return (
                202,
                {
                    "contract_version": "yonerai.native-run.v1.staging",
                    "provider_call_enabled": False,
                    "raw_private_content_logged": False,
                    "run": _run_payload(status="queued"),
                    "queue": {
                        "backend": "staging-internal",
                        "status": "queued",
                        "worker_delivery": "outbound_polling_only",
                    },
                },
                rate_headers,
            )
        if method == "GET" and url.endswith("/v1/runs/run_123"):
            return (200, {"run": _run_payload(status="completed", result_summary="hello result")}, rate_headers)
        if method == "GET" and url.endswith("/v1/runs/run_123/events"):
            return (
                200,
                {
                    "events": [
                        {
                            "event_id": "evt_1",
                            "run_id": "run_123",
                            "type": "status",
                            "status": "worker_claimed",
                            "summary": "Worker picked up the staging run.",
                        }
                    ]
                },
                rate_headers,
            )
        if method == "POST" and url.endswith("/v1/runs/run_123/cancel"):
            return (
                200,
                {
                    "run": _run_payload(status="canceled"),
                    "cancellation": {"status": "accepted", "reason": "owner requested"},
                },
                rate_headers,
            )
        if method == "GET" and url.endswith("/v1/status"):
            return (
                200,
                {
                    "status_snapshot": {
                        "official_execution_worker": "online",
                        "queue": "ready",
                        "queued_runs": 1,
                        "claimed_runs": 0,
                        "completed_runs": 3,
                        "worker_delivery": "outbound_polling_only",
                        "raw_local_content_included": False,
                    }
                },
                rate_headers,
            )
        if method == "GET" and url.endswith("/v1/capabilities"):
            return (
                200,
                {
                    "contract_version": "yonerai.capability-manifest.v1.staging",
                    "capabilities": [
                        {
                            "capability_id": "run.echo",
                            "module_id": "run.core",
                            "privacy_class": "metadata_only",
                            "requires_worker": True,
                        }
                    ],
                },
                rate_headers,
            )
        if method == "GET" and url.endswith("/v1/modules"):
            return (
                200,
                {
                    "contract_version": "yonerai.module-manifest.v1.staging",
                    "modules": [
                        {
                            "module_id": "run.core",
                            "capabilities": ["run.echo"],
                            "api_surface": "public",
                            "public_exposure": True,
                        }
                    ],
                },
                rate_headers,
            )
        raise AssertionError(f"unexpected request: {method} {url}")


def _run_payload(*, status: str, result_summary: str | None = None) -> dict[str, object]:
    return {
        "run_id": "run_123",
        "project_id": "personal-staging",
        "module_id": "run.core",
        "capability_requirements": ["run.echo"],
        "privacy_class": "metadata_only",
        "approval_state": "staging_auto_approved_metadata_only",
        "status": status,
        "result_ref": "result:run_123" if result_summary else None,
        "result_summary": result_summary,
        "provider_call_enabled": False,
        "raw_local_content_included": False,
        "worker_delivery": "outbound_polling_only",
    }


def test_native_run_submit_requires_staging_login(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    _install_context(monkeypatch, _unauthenticated_context())
    report = build_native_run_submit_report("hello", config={}, env={}, claim_path=None)
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_auth_required"
    assert report["official_backend_called"] is False
    assert "opaque-yonerai-session" not in serialized
    assert "refresh-token-value" not in serialized
    assert "access-token-value" not in serialized
    assert "authorization-code-value" not in serialized


def test_native_run_submit_sends_metadata_only_request(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    _install_context(monkeypatch, _linked_context())
    transport = FakeTransport()
    report = build_native_run_submit_report("hello", config={}, env={}, claim_path=None, transport=transport)

    assert report["ok"] is True
    assert report["run"]["run_id"] == "run_123"
    assert report["run"]["privacy_class"] == "metadata_only"
    assert report["provider_call_enabled"] is False
    assert transport.calls[0][0] == "POST"
    assert transport.calls[0][1] == "https://api-staging.yonerai.com/v1/runs"
    assert transport.calls[0][2]["Authorization"] == "Bearer opaque-yonerai-session"


def test_native_run_submit_marks_saved_session_rejected_on_backend_401(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    _install_context(monkeypatch, _linked_context())

    def transport(
        method: str,
        url: str,
        headers: dict[str, str],
        body: dict[str, object] | None,
        timeout_seconds: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        assert method == "POST"
        assert url == "https://api-staging.yonerai.com/v1/runs"
        assert headers["Authorization"] == "Bearer opaque-yonerai-session"
        assert body is not None
        return (
            401,
            {"detail": {"reason": "missing_auth"}},
            {"X-YonerAI-RateLimit-Remaining": "41"},
        )

    report = build_native_run_submit_report("hello", config={}, env={}, claim_path=None, transport=transport)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_session_rejected"
    assert report["error"]["backend_reason"] == "missing_auth"
    assert report["error"]["repair_command"] == "yonerai logout && yonerai login"
    assert report["auth_state"] == "staging_session_rejected"
    assert report["account_linked"] is False
    assert report["session_available"] is False
    assert report["staging_session_rejected"] is True
    assert report["session_repair_action"] == "yonerai logout && yonerai login"


def test_native_run_submit_preserves_approval_required_as_policy_error(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    _install_context(monkeypatch, _linked_context())

    def transport(
        method: str,
        url: str,
        headers: dict[str, str],
        body: dict[str, object] | None,
        timeout_seconds: float,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        assert method == "POST"
        assert url == "https://api-staging.yonerai.com/v1/runs"
        assert headers["Authorization"] == "Bearer opaque-yonerai-session"
        assert body is not None
        return (
            403,
            {"detail": {"reason": "approval_required"}},
            {"X-YonerAI-RateLimit-Remaining": "40"},
        )

    report = build_native_run_submit_report("hello", config={}, env={}, claim_path=None, transport=transport)

    assert report["ok"] is False
    assert report["error"]["code"] == "approval_required"
    assert report["account_linked"] is True
    assert report["session_available"] is True
    assert "staging_session_rejected" not in report


def test_native_run_submit_rejects_local_only_before_backend(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    _install_context(monkeypatch, _linked_context())
    transport = FakeTransport()
    report = build_native_run_submit_report(
        "hello",
        conversation_id="local-conv-1",
        sync_policy="local_only",
        config={},
        env={},
        claim_path=None,
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "local_only_official_worker_rejected"
    assert report["official_backend_called"] is False
    assert report["conversation_policy"]["execution"]["official_worker_allowed"] is False
    assert transport.calls == []


def test_native_run_submit_uses_default_conversation_policy_store_for_local_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from yonerai_cli.services.conversation_sync_policy_service import build_conversation_policy_set_report
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    config_path = tmp_path / "cli-config.json"
    build_conversation_policy_set_report("local-conv-stored", "local_only", config_path=config_path)
    _install_context(monkeypatch, _linked_context())
    transport = FakeTransport()

    report = build_native_run_submit_report(
        "hello",
        conversation_id="local-conv-stored",
        config={},
        env={},
        claim_path=str(config_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "local_only_official_worker_rejected"
    assert report["conversation_policy"]["sync_policy"] == "local_only"
    assert report["conversation_policy"]["memory"]["reason"] == "local_only_memory_stays_local"
    assert report["official_backend_called"] is False
    assert transport.calls == []


def test_native_run_output_shows_conversation_policy_and_memory_boundary(monkeypatch) -> None:
    from yonerai_cli.screens.native_run import format_native_run_compact, format_native_run_pretty
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    _install_context(monkeypatch, _linked_context())
    report = build_native_run_submit_report(
        "hello",
        conversation_id="local-conv-1",
        sync_policy="local_only",
        config={},
        env={},
        claim_path=None,
        transport=FakeTransport(),
    )

    pretty = format_native_run_pretty(report, lang="ja", color="never")
    compact = format_native_run_compact(report, lang="ja")

    assert "会話ポリシー境界" in pretty
    assert "execution.official_worker_allowed" in pretty
    assert "memory.memory_scope" in pretty
    assert "local_private" in pretty
    assert "local_only_memory_stays_local" in pretty
    assert "会話ポリシー" in compact
    assert "記憶" in compact
    assert "local_private" in compact


def test_native_run_submit_sends_cloud_to_local_conversation_metadata(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    _install_context(monkeypatch, _linked_context())
    transport = FakeTransport()
    report = build_native_run_submit_report(
        "hello",
        conversation_id="cloud-conv-1",
        conversation_origin="cloud",
        sync_policy="cloud_to_local",
        config={},
        env={},
        claim_path=None,
        transport=transport,
    )

    request_body = next(call[3] for call in transport.calls if call[1].endswith("/v1/runs"))
    assert report["ok"] is True
    assert report["conversation_policy"]["sync_policy"] == "cloud_to_local"
    assert request_body is not None
    assert request_body["conversation"]["conversation_id"] == "cloud-conv-1"
    assert request_body["conversation"]["message_body_included"] is False
    assert request_body["conversation"]["local_private_memory_included"] is False


def test_native_run_submit_uses_default_conversation_policy_store_for_cloud_origin(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from yonerai_cli.services.conversation_sync_policy_service import build_conversation_policy_set_report
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    config_path = tmp_path / "cli-config.json"
    build_conversation_policy_set_report(
        "cloud-conv-stored",
        "cloud_to_local",
        origin="cloud",
        config_path=config_path,
    )
    _install_context(monkeypatch, _linked_context())
    transport = FakeTransport()

    report = build_native_run_submit_report(
        "hello",
        conversation_id="cloud-conv-stored",
        config={},
        env={},
        claim_path=str(config_path),
        transport=transport,
    )

    request_body = next(call[3] for call in transport.calls if call[1].endswith("/v1/runs"))
    assert report["ok"] is True
    assert report["conversation_policy"]["sync_policy"] == "cloud_to_local"
    assert report["conversation_policy"]["memory"]["inherits_conversation_policy"] is True
    assert request_body is not None
    assert request_body["conversation_id"] == "cloud-conv-stored"
    assert request_body["sync_policy"] == "cloud_to_local"
    assert request_body["conversation"]["local_private_memory_included"] is False


def test_native_run_submit_requires_provider_sharing_consent(monkeypatch, tmp_path: Path) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    _install_context(monkeypatch, _linked_context())
    transport = FakeTransport()
    report = build_native_run_submit_report(
        "hello",
        conversation_id="cloud-conv-2",
        conversation_origin="cloud",
        sync_policy="cloud_to_local",
        provider_data_policy="openai_shared_explicit",
        provider_sharing_store=str(tmp_path / "provider-sharing.json"),
        config={},
        env={},
        claim_path=None,
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "provider_sharing_consent_required"
    assert report["official_backend_called"] is False
    assert transport.calls == []


def test_native_run_submit_sends_provider_context_only_after_consent(monkeypatch, tmp_path: Path) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_submit_report
    from yonerai_cli.services.provider_sharing_service import build_provider_sharing_enable_report

    _install_context(monkeypatch, _linked_context())
    store = tmp_path / "provider-sharing.json"
    build_provider_sharing_enable_report("cloud-conv-3", confirm=True, store_path=store)
    transport = FakeTransport()

    report = build_native_run_submit_report(
        "hello",
        conversation_id="cloud-conv-3",
        conversation_origin="cloud",
        sync_policy="cloud_to_local",
        provider_data_policy="openai_shared_explicit",
        provider_sharing_store=str(store),
        config={},
        env={},
        claim_path=None,
        transport=transport,
    )

    request_body = next(call[3] for call in transport.calls if call[1].endswith("/v1/runs"))
    assert report["ok"] is True
    assert report["provider_sharing"]["openai_shared_traffic_enabled"] is True
    assert report["openai_shared_traffic_enabled"] is False
    assert report["openai_shared_traffic_sent"] is False
    assert report["context_preview"]["current_message_included"] is True
    assert request_body is not None
    assert request_body["provider_data_policy"] == "openai_shared_explicit"
    assert request_body["privacy_class"] == "synthetic"
    assert request_body["body_boundary"] == "body_on_aws"
    assert request_body["conversation_id"] == "cloud-conv-3"
    assert request_body["sync_policy"] == "cloud_to_local"
    assert request_body["body_on_aws"] is True
    assert request_body["body_ref"]["message_body_included"] is False
    assert request_body["message_body_included"] is False
    assert request_body["input"]["kind"] == "cloud_conversation_ref"
    assert request_body["input"]["body_boundary"] == "body_on_aws"
    assert request_body["input"]["body_source"] == "aws_conversation_body"
    assert request_body["input"]["body_ref"]["message_body_included"] is False
    assert request_body["input"]["current_message_included"] is True
    assert request_body["provider_sharing"]["openai_shared_traffic_enabled"] is True
    assert request_body["provider_sharing"]["raw_body_included"] is False
    assert request_body["context_preview"]["full_history_included"] is False


def test_native_run_submit_rejects_local_only_openai_policy_before_backend(monkeypatch, tmp_path: Path) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_submit_report

    _install_context(monkeypatch, _linked_context())
    transport = FakeTransport()
    report = build_native_run_submit_report(
        "hello",
        conversation_id="local-conv-2",
        sync_policy="local_only",
        provider_data_policy="openai_shared_explicit",
        provider_sharing_store=str(tmp_path / "provider-sharing.json"),
        config={},
        env={},
        claim_path=None,
        transport=transport,
    )

    assert report["ok"] is False
    assert report["official_backend_called"] is False
    assert report["error"]["code"] in {"local_only_official_worker_rejected", "local_only_provider_sharing_rejected"}
    assert transport.calls == []


def test_native_run_submit_rejects_secret_like_prompt_as_report(monkeypatch, tmp_path: Path) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_submit_report
    from yonerai_cli.services.provider_sharing_service import build_provider_sharing_enable_report

    _install_context(monkeypatch, _linked_context())
    store = tmp_path / "provider-sharing.json"
    build_provider_sharing_enable_report("cloud-conv-secret", confirm=True, store_path=store)
    transport = FakeTransport()

    report = build_native_run_submit_report(
        "password=secret",
        conversation_id="cloud-conv-secret",
        conversation_origin="cloud",
        sync_policy="cloud_to_local",
        provider_data_policy="openai_shared_explicit",
        provider_sharing_store=str(store),
        config={},
        env={},
        claim_path=None,
        transport=transport,
    )

    assert report["ok"] is False
    assert report["official_backend_called"] is False
    assert report["error"]["code"] == "native_run_prompt_rejected"
    assert report["provider_sharing"]["raw_body_included"] is False
    assert transport.calls == []


def test_native_run_replaces_legacy_configured_origin(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import build_worker_status_report

    context = _unauthenticated_context()
    context["origin"] = "configured"
    context["origin_configured"] = True
    _install_context(monkeypatch, context)
    transport = FakeTransport()

    report = build_worker_status_report(config={}, env={}, claim_path=None, transport=transport)

    assert report["ok"] is True
    assert report["backend_url"] == "https://api-staging.yonerai.com"
    assert report["origin_invalid_replaced"] is True
    assert transport.calls[0][1] == "https://api-staging.yonerai.com/v1/status"


def test_native_run_status_events_result_cancel(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import (
        build_native_run_cancel_report,
        build_native_run_events_report,
        build_native_run_result_report,
        build_native_run_status_report,
    )

    _install_context(monkeypatch, _linked_context())
    transport = FakeTransport()

    status = build_native_run_status_report("run_123", config={}, env={}, claim_path=None, transport=transport)
    events = build_native_run_events_report("run_123", config={}, env={}, claim_path=None, transport=transport)
    result = build_native_run_result_report("run_123", config={}, env={}, claim_path=None, transport=transport)
    cancel = build_native_run_cancel_report("run_123", config={}, env={}, claim_path=None, transport=transport)

    assert status["run"]["status"] == "completed"
    assert events["events"][0]["status"] == "worker_claimed"
    assert result["result"]["result_summary"] == "hello result"
    assert result["result"]["raw_chain_of_thought_included"] is False
    assert cancel["run"]["status"] == "canceled"


def test_worker_capability_and_module_reports(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import (
        build_capability_list_report,
        build_module_list_report,
        build_worker_status_report,
    )

    _install_context(monkeypatch, _unauthenticated_context())
    transport = FakeTransport()

    worker = build_worker_status_report(config={}, env={}, claim_path=None, transport=transport)
    capabilities = build_capability_list_report(config={}, env={}, claim_path=None, transport=transport)
    modules = build_module_list_report(config={}, env={}, claim_path=None, transport=transport)

    assert worker["worker"]["official_execution_worker"] == "online"
    assert capabilities["capabilities"][0]["capability_id"] == "run.echo"
    assert modules["modules"][0]["module_id"] == "run.core"
    assert all(call[2] == {} for call in transport.calls)


def test_worker_status_reads_owner_worker_without_rejecting_safe_secret_policy_words(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import build_worker_status_report

    _install_context(monkeypatch, _unauthenticated_context())

    def status_transport(_method, _url, _headers, _body, _timeout):
        return (
            200,
            {
                "auth": {
                    "staging_oauth": {
                        "client_secret_rotation_required": True,
                        "refresh_token_storage_enabled": False,
                    }
                },
                "owner_worker": {
                    "status": "not_configured",
                    "connectivity": "outbound_polling_only",
                    "raw_local_content_included": False,
                    "inbound_owner_pc_ports_required": False,
                },
            },
            {},
        )

    report = build_worker_status_report(config={}, env={}, claim_path=None, transport=status_transport)

    assert report["ok"] is True
    assert report["worker"]["official_execution_worker"] == "not_configured"
    assert report["worker"]["worker_delivery"] == "outbound_polling_only"


def test_native_run_rejects_private_payload_from_status_source(monkeypatch) -> None:
    from yonerai_cli.services.native_run_service import build_native_run_events_report

    _install_context(monkeypatch, _linked_context())

    def private_transport(_method, _url, _headers, _body, _timeout):
        return (
            200,
            {"events": [{"summary": "see http://10.0.0.5/runbook", "access_token": "secret"}]},
            {},
        )

    report = build_native_run_events_report(
        "run_123",
        config={},
        env={},
        claim_path=None,
        transport=private_transport,
    )

    serialized = json.dumps(report, ensure_ascii=False)
    assert report["ok"] is False
    assert report["error"]["code"] == "native_run_private_payload_rejected"
    assert "10.0.0.5" not in serialized
    assert "secret" not in serialized


def test_native_run_public_safety_allows_false_token_flags_but_rejects_values() -> None:
    from yonerai_cli.services.native_run_service import NativeRunServiceError, _assert_public_safe_payload

    _assert_public_safe_payload(
        {
            "google_token_included": False,
            "refresh_token_stored": False,
            "provider_key_printed": False,
            "context_manifest": {"raw_content_included": False},
        }
    )
    with pytest.raises(NativeRunServiceError):
        _assert_public_safe_payload({"google_token_included": "actual-token-like-value"})


def test_native_run_cli_commands_and_tui_aliases(monkeypatch, capsys) -> None:
    from yonerai_cli import cli
    from yonerai_cli.commands import native_run as native_run_command
    from yonerai_cli.screens.control_spine import format_control_spine_callback
    from yonerai_cli.tui.aliases import canonical_command

    monkeypatch.setattr(
        native_run_command,
        "build_native_run_report",
        lambda _args: {"ok": True, "operation": "native_run_submit", "run": _run_payload(status="queued")},
    )

    assert cli.main(["run", "submit", "hello", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["operation"] == "native_run_submit"
    assert output["run"]["run_id"] == "run_123"

    assert canonical_command("/実行") == "/run"
    assert canonical_command("/Run") == "/run"
    text = format_control_spine_callback(
        "/run",
        SimpleNamespace(native_run_status=lambda _lang: {"ok": True, "operation": "native_run_help"}),
        lang="ja",
    )
    assert text is not None
    assert "Native Run" in text
