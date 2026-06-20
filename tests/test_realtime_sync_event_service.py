from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
if str(CLIENTS_CLI) not in sys.path:
    sys.path.insert(0, str(CLIENTS_CLI))


def _event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schema_version": "yonerai.realtime_sync.v1",
        "event_id": "evt_public_001",
        "account_id": "acct_public_001",
        "conversation_id": "conv_public_001",
        "message_id": "msg_public_001",
        "event_type": "message_created",
        "origin": "web",
        "sync_policy": "cloud_to_local",
        "cursor": "cursor_public_001",
        "sequence": 1,
        "idempotency_key": "sync_public_001",
        "created_at": "2026-06-20T00:00:00Z",
        "projection_version": 1,
        "body_ref": {
            "kind": "aws_message_body",
            "href": "/v1/conversations/conv_public_001/messages/msg_public_001",
            "body_included": False,
        },
        "provider_consent_ref": {"state": "off", "conversation_id": "conv_public_001"},
        "audit_ref": {"kind": "metadata_only", "audit_id": "aud_public_001"},
        "reason": "cloud conversation selected by linked account",
    }
    event.update(overrides)
    return event


def test_valid_cloud_to_local_sync_event_allows_aws_body_fetch_only_after_validation() -> None:
    from yonerai_cli.services.realtime_sync_event_service import validate_realtime_sync_event

    report = validate_realtime_sync_event(_event(), linked_account_id="acct_public_001")

    assert report["ok"] is True
    assert report["body_fetch_allowed"] is True
    assert report["body_fetch_reason"] == "cloud_to_local_metadata_validated"
    assert report["raw_body_included"] is False
    assert report["provider_consent_separate"] is True
    assert report["approval_authority_from_projection"] is False


def test_local_only_or_local_origin_never_fetches_cloud_body() -> None:
    from yonerai_cli.services.realtime_sync_event_service import validate_realtime_sync_event

    report = validate_realtime_sync_event(
        _event(origin="local", sync_policy="local_only"),
        linked_account_id="acct_public_001",
    )

    assert report["body_fetch_allowed"] is False
    assert report["body_fetch_reason"] == "local_origin_or_local_only_never_fetches_cloud_body"
    assert report["local_private_memory_projected"] is False


def test_projection_stale_pauses_body_fetch_until_repair() -> None:
    from yonerai_cli.services.realtime_sync_event_service import validate_realtime_sync_event

    report = validate_realtime_sync_event(
        _event(event_type="projection_stale", sync_policy="cloud_to_local"),
        linked_account_id="acct_public_001",
    )

    assert report["body_fetch_allowed"] is False
    assert report["body_fetch_reason"] == "projection_paused_or_stale"


def test_duplicate_event_or_idempotency_key_is_ignored() -> None:
    from yonerai_cli.services.realtime_sync_event_service import validate_realtime_sync_event

    duplicate_event = validate_realtime_sync_event(
        _event(),
        linked_account_id="acct_public_001",
        seen_event_ids=("evt_public_001",),
    )
    duplicate_idempotency = validate_realtime_sync_event(
        _event(event_id="evt_public_002"),
        linked_account_id="acct_public_001",
        seen_idempotency_keys=("sync_public_001",),
    )

    assert duplicate_event["body_fetch_allowed"] is False
    assert duplicate_event["body_fetch_reason"] == "duplicate_event_ignored"
    assert duplicate_idempotency["body_fetch_allowed"] is False
    assert duplicate_idempotency["body_fetch_reason"] == "duplicate_idempotency_key_ignored"


def test_account_mismatch_rejects_before_body_fetch() -> None:
    from yonerai_cli.services.realtime_sync_event_service import build_realtime_sync_event_validation_report

    report = build_realtime_sync_event_validation_report(_event(), linked_account_id="acct_other")

    assert report["ok"] is False
    assert report["body_fetch_allowed"] is False
    assert report["error"]["code"] == "sync_event_account_mismatch"


def test_raw_body_projection_is_rejected() -> None:
    from yonerai_cli.services.realtime_sync_event_service import build_realtime_sync_event_validation_report

    event = _event(body_ref={"kind": "aws_message_body", "href": "/v1/conversations/conv/messages/msg", "body_included": True})
    report = build_realtime_sync_event_validation_report(event, linked_account_id="acct_public_001")

    assert report["ok"] is False
    assert report["body_fetch_allowed"] is False
    assert report["error"]["code"] == "sync_event_body_included_rejected"
    assert report["raw_body_included"] is False


def test_token_like_text_is_rejected_without_printing_it() -> None:
    from yonerai_cli.services.realtime_sync_event_service import build_realtime_sync_event_validation_report

    report = build_realtime_sync_event_validation_report(
        _event(reason="refresh_token should never be projected"),
        linked_account_id="acct_public_001",
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "sync_event_private_payload_rejected"
    assert report["error"]["token_printed"] is False


def test_local_path_or_internal_endpoint_is_rejected() -> None:
    from yonerai_cli.services.realtime_sync_event_service import build_realtime_sync_event_validation_report

    path_report = build_realtime_sync_event_validation_report(
        _event(reason="C:\\Users\\owner\\secret.txt"),
        linked_account_id="acct_public_001",
    )
    endpoint_report = build_realtime_sync_event_validation_report(
        _event(reason="http://10.0.0.5/runbook"),
        linked_account_id="acct_public_001",
    )

    assert path_report["ok"] is False
    assert path_report["error"]["local_path_printed"] is False
    assert endpoint_report["ok"] is False
    assert endpoint_report["error"]["private_runtime_detail_printed"] is False


def test_body_ref_path_traversal_or_query_is_rejected() -> None:
    from yonerai_cli.services.realtime_sync_event_service import build_realtime_sync_event_validation_report

    traversal = build_realtime_sync_event_validation_report(
        _event(body_ref={"kind": "aws_message_body", "href": "/v1/conversations/../admin", "body_included": False}),
        linked_account_id="acct_public_001",
    )
    query = build_realtime_sync_event_validation_report(
        _event(body_ref={"kind": "aws_message_body", "href": "/v1/conversations/conv/messages/msg?debug=1", "body_included": False}),
        linked_account_id="acct_public_001",
    )

    assert traversal["ok"] is False
    assert traversal["error"]["code"] == "sync_event_body_ref_invalid"
    assert query["ok"] is False
    assert query["error"]["code"] == "sync_event_body_ref_invalid"


def test_unknown_private_fields_are_rejected() -> None:
    from yonerai_cli.services.realtime_sync_event_service import build_realtime_sync_event_validation_report

    report = build_realtime_sync_event_validation_report(
        _event(raw_audit={"debug": "not public"}),
        linked_account_id="acct_public_001",
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "sync_event_private_fields"
