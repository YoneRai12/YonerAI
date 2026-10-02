from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
CORE_SRC = ROOT / "core" / "src"
for path in (CLIENTS_CLI, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


ORIGIN = "https://api-staging.yonerai.com"
RATE_HEADERS = {
    "X-YonerAI-RateLimit-Scope": "anonymous",
    "X-YonerAI-RateLimit-Limit": "60",
    "X-YonerAI-RateLimit-Remaining": "59",
    "X-YonerAI-RateLimit-Reset": "2026-06-06T00:00:00Z",
    "X-YonerAI-RateLimit-Reason": "within_quota",
}


def _save_linked_claim(tmp_path: Path) -> str:
    from yonerai_cli.services.auth_session_service import build_staging_auth_claim, save_staging_auth_claim

    claim_path = tmp_path / "staging-auth-claim.json"
    claim = build_staging_auth_claim(
        origin=ORIGIN,
        expires_at="2026-06-06T00:30:00Z",
        account={"email": "owner@example.com", "display_name": "Owner", "sub": "google-subject-private"},
    )
    save_staging_auth_claim(claim, claim_path=claim_path)
    return str(claim_path)


def _save_linked_claim_and_session(tmp_path: Path) -> str:
    from yonerai_cli.services.staging_session_service import save_staging_session

    claim_path = Path(_save_linked_claim(tmp_path))
    save_staging_session(
        session_token="ystg_session_fixture_123",
        origin=ORIGIN,
        account={"email": "owner@example.com", "display_name": "Owner", "sub": "google-subject-private"},
        expires_at="2099-06-06T00:30:00Z",
        config_path=claim_path,
    )
    return str(claim_path)


def _status_payload() -> dict[str, object]:
    return {
        "contract_version": "yonerai.status.feed.v0.2",
        "official_api_contract_version": "yonerai.official.api.v1.skeleton",
        "status": "not_production",
        "production": False,
        "private_runtime_details_included": False,
        "user_message_en": "Public CLI does not receive client_secret or refresh_token values.",
    }


def _rate_limit_payload() -> dict[str, object]:
    return {
        "allowed": True,
        "scope": "anonymous",
        "fallback_reason": "within_quota",
        "quota_exceeded": False,
        "conversation_sync": {
            "mode": "staging",
            "cloud_to_local": "preview_available",
            "local_to_cloud": "approval_required",
            "shared_traffic": "off",
        },
        "shared_traffic": "off",
    }


def test_staging_sync_status_reads_public_status_without_secret_false_positive(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_sync_service import build_staging_sync_status

    calls: list[tuple[str, str]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        calls.append((method, url))
        if url.endswith("/v1/status"):
            return 200, _status_payload(), RATE_HEADERS
        if url.endswith("/v1/rate-limit"):
            return 200, _rate_limit_payload(), RATE_HEADERS
        raise AssertionError(url)

    report = build_staging_sync_status(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        claim_path=_save_linked_claim(tmp_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["official_backend_called"] is True
    assert report["rate_limit"]["conversation_sync"]["cloud_to_local"] == "preview_available"
    assert report["directions"]["local_to_cloud"]["staging_state"] == "approval_required"
    assert ("GET", f"{ORIGIN}/v1/status") in calls
    assert "owner@example.com" not in serialized
    assert "google-subject-private" not in serialized


def test_staging_conversations_fail_closed_when_session_claim_is_not_stored(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_sync_service import build_staging_conversations_report

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        raise AssertionError("conversation API must not be called without a safe staging session")

    report = build_staging_conversations_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        claim_path=_save_linked_claim(tmp_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_session_required"
    assert report["conversations"] == []
    assert "Authorization" not in serialized
    assert "owner@example.com" not in serialized


def test_staging_conversations_reject_private_response_fields(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_sync_service import build_staging_conversations_report

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        return (
            200,
            {
                "conversations": [
                    {
                        "cloud_conversation_id": "cloud-1",
                        "title": "safe title",
                        "selected_by_user": True,
                        "raw_body": "private text must not be in the public fixture",
                    }
                ]
            },
            RATE_HEADERS,
        )

    report = build_staging_conversations_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        claim_path=_save_linked_claim_and_session(tmp_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_conversations_private_fields"
    assert report["error"]["token_printed"] is False


def test_staging_conversations_reject_case_insensitive_local_paths(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_sync_service import build_staging_conversations_report

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        assert headers["Authorization"] == "Bearer ystg_session_fixture_123"
        return (
            200,
            {
                "conversations": [
                    {
                        "cloud_conversation_id": "cloud-1",
                        "title": "/users/example/private",
                        "selected_by_user": True,
                    }
                ]
            },
            RATE_HEADERS,
        )

    report = build_staging_conversations_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        claim_path=_save_linked_claim_and_session(tmp_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "staging_sync_private_payload_rejected"
    assert report["error"]["local_path_printed"] is False


def test_staging_conversations_use_safe_session_without_printing_token(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_sync_service import build_staging_conversations_report

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        assert method == "GET"
        assert url == f"{ORIGIN}/v1/conversations"
        assert headers["Authorization"] == "Bearer ystg_session_fixture_123"
        return (
            200,
            {
                "conversations": [
                    {"cloud_conversation_id": "cloud-1", "title": "safe title", "selected_by_user": True},
                    {"cloud_conversation_id": "cloud-2", "title": "other safe title", "selected_by_user": False},
                ]
            },
            RATE_HEADERS,
        )

    report = build_staging_conversations_report(
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        claim_path=_save_linked_claim_and_session(tmp_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["staging_session_available"] is True
    assert report["selected_count"] == 1
    assert report["conversations"][0]["raw_body_included"] is False
    assert "ystg_session_fixture_123" not in serialized
    assert "Authorization" not in serialized
    assert "owner@example.com" not in serialized


def test_staging_conversation_show_uses_safe_session_summary_only(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_sync_service import build_staging_conversation_show_report

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        assert method == "GET"
        assert url == f"{ORIGIN}/v1/conversations/cloud-1"
        assert headers["Authorization"] == "Bearer ystg_session_fixture_123"
        return (
            200,
            {
                "conversation": {
                    "cloud_conversation_id": "cloud-1",
                    "title": "safe title",
                    "summary": "redacted summary only",
                    "selected_by_user": True,
                    "message_count": 3,
                    "updated_at": "2026-06-06T00:00:00Z",
                }
            },
            RATE_HEADERS,
        )

    report = build_staging_conversation_show_report(
        conversation_id="cloud-1",
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        claim_path=_save_linked_claim_and_session(tmp_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["conversation"]["summary"] == "redacted summary only"
    assert report["conversation"]["raw_body_included"] is False
    assert "ystg_session_fixture_123" not in serialized
    assert "Authorization" not in serialized


def test_staging_sync_preview_cloud_to_local_requires_account_session(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_sync_service import build_staging_sync_preview_report

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        raise AssertionError("cloud-to-local preview must not call staging API without a safe staging session")

    report = build_staging_sync_preview_report(
        direction="cloud-to-local",
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        claim_path=_save_linked_claim(tmp_path),
        transport=transport,
    )

    assert report["ok"] is False
    assert report["decision"]["state"] == "blocked"
    assert report["decision"]["reason"] == "staging_session_required"
    assert report["sync_performed"] is False
    assert report["private_content_exclusion"]["private_file_content_excluded"] is True


def test_staging_sync_preview_local_to_cloud_is_approval_only_without_backend(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_sync_service import build_staging_sync_preview_report

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        raise AssertionError("local-to-cloud preview must not call the staging backend")

    report = build_staging_sync_preview_report(
        direction="local-to-cloud",
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        claim_path=_save_linked_claim(tmp_path),
        transport=transport,
    )

    assert report["ok"] is True
    assert report["decision"]["state"] == "approval_required"
    assert report["decision"]["requires_explicit_approval"] is True
    assert report["official_backend_called"] is False
    assert report["sync_performed"] is False


def test_staging_sync_preview_cloud_to_local_uses_session_without_uploading_private_content(tmp_path: Path) -> None:
    from yonerai_cli.services.staging_sync_service import build_staging_sync_preview_report

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
        assert method == "POST"
        assert url == f"{ORIGIN}/v1/sync/preview"
        assert headers["Authorization"] == "Bearer ystg_session_fixture_123"
        assert body is not None
        assert body["direction"] == "cloud_to_local"
        assert body["contains_private_content"] is False
        assert body["audit_reason"] == "public_cli_sync_preview"
        return (
            200,
            {
                "ok": True,
                "decision": {
                    "state": "allowed",
                    "reason": "cloud_to_local_preview_available",
                    "requires_explicit_approval": False,
                    "private_content_excluded": True,
                },
                "private_content_exclusion": {
                    "raw_prompt_excluded": True,
                    "private_file_content_excluded": True,
                    "local_memory_excluded": True,
                    "local_node_payload_excluded": True,
                    "provider_keys_excluded": True,
                    "local_absolute_paths_excluded": True,
                    "openai_shared_traffic_excluded": True,
                },
            },
            RATE_HEADERS,
        )

    report = build_staging_sync_preview_report(
        direction="cloud-to-local",
        env={"YONERAI_STAGING_AUTH_ORIGIN": ORIGIN},
        claim_path=_save_linked_claim_and_session(tmp_path),
        transport=transport,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ok"] is True
    assert report["decision"]["state"] == "allowed"
    assert report["sync_performed"] is False
    assert report["approval_recorded"] is False
    assert report["private_content_exclusion"]["private_file_content_excluded"] is True
    assert "ystg_session_fixture_123" not in serialized
    assert "Authorization" not in serialized


def test_cloud_slash_alias_opens_sync_screen() -> None:
    from yonerai_cli.tui.aliases import canonical_command

    assert canonical_command("/クラウド") == "/sync"
    assert canonical_command("/同期") == "/sync"


def test_scripted_chat_accepts_japanese_sync_slash_command(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{CLIENTS_CLI}{os.pathsep}{CORE_SRC}"
    env["YONERAI_CLI_CONFIG_PATH"] = str(tmp_path / "config.json")
    completed = subprocess.run(
        [sys.executable, "-m", "yonerai_cli", "chat", "--script", "--lang", "ja", "--color", "never"],
        input="/同期\n/終了\n",
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=env,
        check=False,
    )
    diagnostic = f"stdout={completed.stdout!r}\nstderr={completed.stderr!r}"

    assert completed.returncode == 0, diagnostic
    assert "同期" in completed.stdout
    assert "local -> cloud" in completed.stdout
    assert "不明なコマンド" not in completed.stdout
