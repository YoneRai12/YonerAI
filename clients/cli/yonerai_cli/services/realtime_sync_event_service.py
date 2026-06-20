from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any


REALTIME_SYNC_SCHEMA_VERSION = "yonerai.realtime_sync.v1"
EVENT_TYPES = {
    "conversation_created",
    "conversation_updated",
    "message_created",
    "message_updated",
    "message_deleted",
    "policy_changed",
    "cursor_checkpoint",
    "projection_stale",
}
ORIGINS = {"web", "cloud", "cli", "local"}
SYNC_POLICIES = {"local_only", "cloud_to_local", "bidirectional_explicit", "paused"}
BODY_REF_KINDS = {"aws_message_body", "none"}
SYNC_EVENT_FIXTURES = {
    "valid",
    "local-only",
    "projection-stale",
    "duplicate",
    "account-mismatch",
    "raw-body",
    "private-token",
    "private-path",
    "bad-body-ref",
}
ALLOWED_FIELDS = {
    "schema_version",
    "event_id",
    "account_id",
    "conversation_id",
    "message_id",
    "event_type",
    "origin",
    "sync_policy",
    "cursor",
    "sequence",
    "idempotency_key",
    "created_at",
    "projection_version",
    "body_ref",
    "provider_consent_ref",
    "audit_ref",
    "reason",
}
REQUIRED_FIELDS = {
    "schema_version",
    "event_id",
    "account_id",
    "conversation_id",
    "event_type",
    "origin",
    "sync_policy",
    "cursor",
    "idempotency_key",
    "created_at",
    "projection_version",
}
PUBLIC_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")


class RealtimeSyncEventError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_safe_error(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "token_printed": False,
            "local_path_printed": False,
            "raw_body_printed": False,
            "private_runtime_detail_printed": False,
        }


def build_realtime_sync_event_fixture(name: str = "valid") -> dict[str, object]:
    if name not in SYNC_EVENT_FIXTURES:
        raise RealtimeSyncEventError("sync_event_fixture_invalid", "Realtime sync event fixture is not supported.")
    event: dict[str, object] = {
        "schema_version": REALTIME_SYNC_SCHEMA_VERSION,
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
    if name == "local-only":
        event.update({"origin": "local", "sync_policy": "local_only"})
    elif name == "projection-stale":
        event.update({"event_type": "projection_stale"})
    elif name == "duplicate":
        event.update({"event_id": "evt_duplicate_001", "idempotency_key": "sync_duplicate_001"})
    elif name == "account-mismatch":
        event.update({"account_id": "acct_other"})
    elif name == "raw-body":
        event["body_ref"] = {
            "kind": "aws_message_body",
            "href": "/v1/conversations/conv_public_001/messages/msg_public_001",
            "body_included": True,
        }
    elif name == "private-token":
        event["reason"] = "refresh_token must not be projected"
    elif name == "private-path":
        event["reason"] = "C:\\Users\\owner\\secret.txt"
    elif name == "bad-body-ref":
        event["body_ref"] = {
            "kind": "aws_message_body",
            "href": "/v1/conversations/../admin",
            "body_included": False,
        }
    return event


def validate_realtime_sync_event(
    event: Mapping[str, object],
    *,
    linked_account_id: str | None = None,
    seen_event_ids: Iterable[str] = (),
    seen_idempotency_keys: Iterable[str] = (),
) -> dict[str, object]:
    """Validate a body-free realtime sync event before any AWS body fetch."""

    _assert_mapping(event)
    _assert_no_unknown_fields(event)
    _assert_required_fields(event)
    _assert_public_safe_payload(event)

    schema_version = _required_text(event, "schema_version")
    if schema_version != REALTIME_SYNC_SCHEMA_VERSION:
        raise RealtimeSyncEventError("sync_event_schema_mismatch", "Realtime sync event schema is not supported.")

    event_type = _enum_text(event, "event_type", EVENT_TYPES, code="sync_event_type_invalid")
    origin = _enum_text(event, "origin", ORIGINS, code="sync_event_origin_invalid")
    sync_policy = _enum_text(event, "sync_policy", SYNC_POLICIES, code="sync_event_policy_invalid")
    event_id = _public_id(event, "event_id")
    account_id = _public_id(event, "account_id")
    conversation_id = _public_id(event, "conversation_id")
    message_id = _optional_public_id(event, "message_id")
    cursor = _required_text(event, "cursor")
    idempotency_key = _required_text(event, "idempotency_key")
    projection_version = event.get("projection_version")
    if not isinstance(projection_version, int) or projection_version < 1:
        raise RealtimeSyncEventError("sync_event_projection_version_invalid", "Realtime sync projection version is invalid.")

    if linked_account_id is not None and account_id != linked_account_id:
        raise RealtimeSyncEventError("sync_event_account_mismatch", "Realtime sync event account does not match the linked session.")

    body_ref = _body_ref(event.get("body_ref"))
    if sync_policy == "paused" or event_type == "projection_stale":
        body_fetch_allowed = False
        body_fetch_reason = "projection_paused_or_stale"
    elif sync_policy == "local_only" or origin in {"cli", "local"}:
        body_fetch_allowed = False
        body_fetch_reason = "local_origin_or_local_only_never_fetches_cloud_body"
    elif body_ref["kind"] == "aws_message_body" and body_ref["href"]:
        body_fetch_allowed = True
        body_fetch_reason = "cloud_to_local_metadata_validated"
    else:
        body_fetch_allowed = False
        body_fetch_reason = "no_aws_body_ref"

    duplicate_event = event_id in set(seen_event_ids)
    duplicate_idempotency_key = idempotency_key in set(seen_idempotency_keys)
    return {
        "schema_version": REALTIME_SYNC_SCHEMA_VERSION,
        "ok": True,
        "event_id": event_id,
        "account_id": account_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "event_type": event_type,
        "origin": origin,
        "sync_policy": sync_policy,
        "cursor": cursor,
        "idempotency_key": idempotency_key,
        "projection_version": projection_version,
        "body_ref": body_ref,
        "body_fetch_allowed": body_fetch_allowed and not duplicate_event and not duplicate_idempotency_key,
        "body_fetch_reason": "duplicate_event_ignored"
        if duplicate_event
        else "duplicate_idempotency_key_ignored"
        if duplicate_idempotency_key
        else body_fetch_reason,
        "duplicate_event": duplicate_event,
        "duplicate_idempotency_key": duplicate_idempotency_key,
        "raw_body_included": False,
        "provider_consent_separate": True,
        "approval_authority_from_projection": False,
        "local_private_memory_projected": False,
    }


def build_realtime_sync_event_validation_report(
    event: Mapping[str, object],
    *,
    linked_account_id: str | None = None,
    seen_event_ids: Iterable[str] = (),
    seen_idempotency_keys: Iterable[str] = (),
) -> dict[str, object]:
    try:
        return validate_realtime_sync_event(
            event,
            linked_account_id=linked_account_id,
            seen_event_ids=seen_event_ids,
            seen_idempotency_keys=seen_idempotency_keys,
        )
    except RealtimeSyncEventError as exc:
        return {
            "schema_version": REALTIME_SYNC_SCHEMA_VERSION,
            "ok": False,
            "error": exc.to_safe_error(),
            "body_fetch_allowed": False,
            "raw_body_included": False,
            "local_private_memory_projected": False,
        }


def _assert_mapping(event: object) -> None:
    if not isinstance(event, Mapping):
        raise RealtimeSyncEventError("sync_event_invalid", "Realtime sync event is invalid.")


def _assert_no_unknown_fields(event: Mapping[str, object]) -> None:
    unknown = set(event) - ALLOWED_FIELDS
    if unknown:
        raise RealtimeSyncEventError("sync_event_private_fields", "Realtime sync event contains non-public fields.")


def _assert_required_fields(event: Mapping[str, object]) -> None:
    missing = [field for field in sorted(REQUIRED_FIELDS) if field not in event]
    if missing:
        raise RealtimeSyncEventError("sync_event_missing_required_field", "Realtime sync event is missing required fields.")


def _required_text(event: Mapping[str, object], field: str) -> str:
    value = event.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RealtimeSyncEventError("sync_event_field_invalid", "Realtime sync event field is invalid.")
    text = value.strip()
    _assert_public_safe_text(text)
    return text


def _enum_text(event: Mapping[str, object], field: str, allowed: set[str], *, code: str) -> str:
    value = _required_text(event, field)
    if value not in allowed:
        raise RealtimeSyncEventError(code, "Realtime sync event enum value is invalid.")
    return value


def _public_id(event: Mapping[str, object], field: str) -> str:
    value = _required_text(event, field)
    if not PUBLIC_ID_RE.fullmatch(value):
        raise RealtimeSyncEventError("sync_event_id_invalid", "Realtime sync event id is invalid.")
    return value


def _optional_public_id(event: Mapping[str, object], field: str) -> str | None:
    value = event.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RealtimeSyncEventError("sync_event_id_invalid", "Realtime sync event id is invalid.")
    text = value.strip()
    _assert_public_safe_text(text)
    if not PUBLIC_ID_RE.fullmatch(text):
        raise RealtimeSyncEventError("sync_event_id_invalid", "Realtime sync event id is invalid.")
    return text


def _body_ref(value: object) -> dict[str, object]:
    if value is None:
        return {"kind": "none", "href": None, "body_included": False}
    if not isinstance(value, Mapping):
        raise RealtimeSyncEventError("sync_event_body_ref_invalid", "Realtime sync event body_ref is invalid.")
    kind = value.get("kind")
    if kind not in BODY_REF_KINDS:
        raise RealtimeSyncEventError("sync_event_body_ref_invalid", "Realtime sync event body_ref kind is invalid.")
    if value.get("body_included") is not False:
        raise RealtimeSyncEventError("sync_event_body_included_rejected", "Realtime sync event included message body.")
    href = value.get("href")
    if href is not None:
        if not isinstance(href, str) or not href.startswith("/v1/conversations/"):
            raise RealtimeSyncEventError("sync_event_body_ref_invalid", "Realtime sync event body_ref href is invalid.")
        _assert_public_safe_text(href)
        if any(marker in href for marker in ("..", "\\", "?", "#", "//")):
            raise RealtimeSyncEventError("sync_event_body_ref_invalid", "Realtime sync event body_ref href is invalid.")
    return {"kind": kind, "href": href, "body_included": False}


def _assert_public_safe_payload(value: object) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    forbidden = (
        '"message_body"',
        '"raw_body"',
        '"raw_prompt"',
        '"provider_output"',
        '"local_memory"',
        '"local_file"',
        '"file_bytes"',
        "access_token",
        "refresh_token",
        "id_token",
        "auth_code",
        "authorization_code",
        "google_token",
        "provider_key",
        "api_key",
        "client_secret",
        "secret_key",
        "arn:",
        "c:\\users",
        "\\\\",
        "/users/",
        "/home/",
        "/root/",
        "http://10.",
        "http://192.168.",
        "http://127.",
        "169.254.169.254",
    )
    if any(marker in serialized for marker in forbidden):
        raise RealtimeSyncEventError("sync_event_private_payload_rejected", "Realtime sync event contains private data.")


def _assert_public_safe_text(text: str) -> None:
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise RealtimeSyncEventError("sync_event_field_invalid", "Realtime sync event field is invalid.")
