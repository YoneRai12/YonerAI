from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from yonerai_cli.config import default_config_path


CONVERSATION_SYNC_POLICY_SCHEMA_VERSION = "yonerai-conversation-sync-policy/v0.1"
SYNC_POLICIES = ("local_only", "cloud_to_local", "bidirectional_explicit", "paused")
CONVERSATION_ORIGINS = ("local", "cloud", "web")
CONVERSATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")


class ConversationSyncPolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_safe_error(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "private_endpoint_printed": False,
            "local_path_printed": False,
            "token_printed": False,
            "raw_body_printed": False,
        }


def default_conversation_sync_policy_path(
    config_path: str | Path | None = None,
    *,
    env: Mapping[str, str | None] | None = None,
) -> Path:
    base = Path(config_path).expanduser() if config_path is not None else default_config_path(env)
    if config_path is None and not str((os.environ if env is None else env).get("YONERAI_CLI_CONFIG_PATH") or "").strip():
        return base.with_name("conversation-sync-policies.json")
    return base.with_name(f"{base.stem}.conversation-sync-policies.json")


def build_conversation_policy_status_report(
    *,
    store_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, object]:
    store = _load_store(store_path, config_path=config_path)
    records = _sorted_records(store)
    counts = {policy: 0 for policy in SYNC_POLICIES}
    origins = {origin: 0 for origin in CONVERSATION_ORIGINS}
    for record in records:
        counts[str(record["sync_policy"])] += 1
        origins[str(record["origin"])] += 1
    return _base_report(
        "conversation_policy_status",
        {
            "store_available": True,
            "conversation_count": len(records),
            "policy_counts": counts,
            "origin_counts": origins,
            "defaults": {
                "local_origin": "local_only",
                "cloud_origin": "cloud_to_local",
                "web_origin": "cloud_to_local",
            },
            "policy_definitions": _policy_definitions(),
        },
    )


def build_conversation_policy_list_report(
    *,
    store_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, object]:
    store = _load_store(store_path, config_path=config_path)
    conversations = [_public_record(record) for record in _sorted_records(store)]
    return _base_report(
        "conversation_policy_list",
        {
            "conversation_count": len(conversations),
            "conversations": conversations,
            "empty_state": "no local conversation sync policies have been recorded yet" if not conversations else None,
        },
    )


def build_conversation_policy_set_report(
    conversation_id: str,
    sync_policy: str,
    *,
    origin: str | None = None,
    confirm: bool = False,
    audit_reason: str = "public_cli_conversation_policy_set",
    store_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, object]:
    safe_conversation_id = _safe_conversation_id(conversation_id)
    normalized_policy = _normalize_policy(sync_policy)
    store = _load_store(store_path, config_path=config_path)
    existing = _records(store).get(safe_conversation_id)
    normalized_origin = _normalize_origin(
        origin or (str(existing.get("origin")) if isinstance(existing, Mapping) else _default_origin_for_policy(normalized_policy))
    )
    safe_audit_reason = _safe_public_text(audit_reason, fallback="public_cli_conversation_policy_set")

    if normalized_policy == "bidirectional_explicit" and not confirm:
        report = _base_report(
            "conversation_policy_set",
            {
                "ok": False,
                "conversation": _public_record(
                    _build_record(
                        conversation_id=safe_conversation_id,
                        origin=normalized_origin,
                        sync_policy=_default_policy_for_origin(normalized_origin),
                        audit_reason="not_written_confirmation_required",
                        existing=existing if isinstance(existing, Mapping) else None,
                    )
                ),
                "decision": {
                    "state": "approval_required",
                    "reason": "bidirectional_explicit_requires_confirm",
                    "requires_explicit_confirmation": True,
                    "written": False,
                },
            },
        )
        return report

    record = _build_record(
        conversation_id=safe_conversation_id,
        origin=normalized_origin,
        sync_policy=normalized_policy,
        audit_reason=safe_audit_reason,
        existing=existing if isinstance(existing, Mapping) else None,
    )
    _records(store)[safe_conversation_id] = record
    _save_store(store, store_path, config_path=config_path)
    return _base_report(
        "conversation_policy_set",
        {
            "conversation": _public_record(record),
            "decision": {
                "state": "written",
                "reason": safe_audit_reason,
                "requires_explicit_confirmation": normalized_policy == "bidirectional_explicit",
                "written": True,
            },
        },
    )


def build_conversation_policy_pause_report(
    conversation_id: str,
    *,
    audit_reason: str = "public_cli_conversation_policy_pause",
    store_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, object]:
    safe_conversation_id = _safe_conversation_id(conversation_id)
    store = _load_store(store_path, config_path=config_path)
    existing = _records(store).get(safe_conversation_id)
    origin = str(existing.get("origin")) if isinstance(existing, Mapping) else "local"
    record = _build_record(
        conversation_id=safe_conversation_id,
        origin=_normalize_origin(origin),
        sync_policy="paused",
        audit_reason=_safe_public_text(audit_reason, fallback="public_cli_conversation_policy_pause"),
        existing=existing if isinstance(existing, Mapping) else None,
    )
    _records(store)[safe_conversation_id] = record
    _save_store(store, store_path, config_path=config_path)
    return _base_report(
        "conversation_policy_pause",
        {
            "conversation": _public_record(record),
            "decision": {
                "state": "written",
                "reason": "conversation_sync_paused",
                "written": True,
            },
        },
    )


def build_conversation_execution_policy(
    *,
    conversation_id: str,
    sync_policy: str,
    origin: str = "local",
) -> dict[str, object]:
    safe_conversation_id = _safe_conversation_id(conversation_id)
    normalized_policy = _normalize_policy(sync_policy)
    normalized_origin = _normalize_origin(origin)
    return {
        "conversation_id": safe_conversation_id,
        "origin": normalized_origin,
        "sync_policy": normalized_policy,
        "execution": _execution_boundary(normalized_policy, normalized_origin),
        "memory": _memory_boundary(normalized_policy, normalized_origin),
        "private_content_exclusion": _private_content_exclusion(),
    }


def _base_report(operation: str, extra: Mapping[str, object]) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": CONVERSATION_SYNC_POLICY_SCHEMA_VERSION,
        "ok": True,
        "operation": operation,
        "sync_performed": False,
        "local_to_cloud_upload_performed": False,
        "official_worker_dispatch_performed": False,
        "raw_body_stored": False,
        "raw_private_content_uploaded": False,
        "google_token_stored": False,
        "provider_key_stored": False,
        "local_absolute_path_stored": False,
        "private_content_exclusion": _private_content_exclusion(),
        "actions_not_performed": _non_actions(),
    }
    report.update(dict(extra))
    return report


def _load_store(store_path: str | Path | None, *, config_path: str | Path | None) -> dict[str, object]:
    path = _store_path(store_path, config_path=config_path)
    if not path.exists():
        return {"schema_version": CONVERSATION_SYNC_POLICY_SCHEMA_VERSION, "conversations": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConversationSyncPolicyError("conversation_policy_store_invalid", "Conversation sync policy store is invalid.") from exc
    if not isinstance(raw, dict):
        raise ConversationSyncPolicyError("conversation_policy_store_invalid", "Conversation sync policy store is invalid.")
    conversations = raw.get("conversations")
    if not isinstance(conversations, dict):
        raw["conversations"] = {}
    sanitized: dict[str, object] = {"schema_version": CONVERSATION_SYNC_POLICY_SCHEMA_VERSION, "conversations": {}}
    for key, value in raw["conversations"].items():  # type: ignore[index]
        if not isinstance(value, Mapping):
            continue
        conversation_id = _safe_conversation_id(value.get("conversation_id", key))
        record = _build_record(
            conversation_id=conversation_id,
            origin=_normalize_origin(value.get("origin", "local")),
            sync_policy=_normalize_policy(value.get("sync_policy", _default_policy_for_origin(str(value.get("origin", "local"))))),
            audit_reason=_safe_public_text(value.get("audit_reason"), fallback="loaded_existing_policy"),
            existing=value,
        )
        _records(sanitized)[conversation_id] = record
    return sanitized


def _save_store(store: Mapping[str, object], store_path: str | Path | None, *, config_path: str | Path | None) -> None:
    path = _store_path(store_path, config_path=config_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ConversationSyncPolicyError("conversation_policy_store_write_failed", "Conversation sync policy store could not be written.") from exc


def _store_path(store_path: str | Path | None, *, config_path: str | Path | None) -> Path:
    if store_path is not None:
        return Path(store_path).expanduser()
    return default_conversation_sync_policy_path(config_path)


def _records(store: Mapping[str, object]) -> dict[str, object]:
    conversations = store.get("conversations")
    if isinstance(conversations, dict):
        return conversations
    raise ConversationSyncPolicyError("conversation_policy_store_invalid", "Conversation sync policy store is invalid.")


def _sorted_records(store: Mapping[str, object]) -> list[dict[str, object]]:
    return sorted(
        (_public_record(record) for record in _records(store).values() if isinstance(record, Mapping)),
        key=lambda item: (str(item.get("updated_at") or ""), str(item.get("conversation_id") or "")),
        reverse=True,
    )


def _build_record(
    *,
    conversation_id: str,
    origin: str,
    sync_policy: str,
    audit_reason: str,
    existing: Mapping[str, object] | None,
) -> dict[str, object]:
    now = _now_iso()
    created_at = _safe_public_text(existing.get("created_at") if existing else None, fallback=now)
    local_extended = bool(existing.get("local_extended", False)) if existing else False
    if sync_policy == "cloud_to_local" and origin in {"cloud", "web"}:
        local_extended = bool(existing.get("local_extended", False)) if existing else False
    return {
        "conversation_id": conversation_id,
        "origin": origin,
        "sync_policy": sync_policy,
        "created_at": created_at,
        "updated_at": now,
        "audit_reason": audit_reason,
        "local_extended": local_extended,
        "raw_body_stored": False,
        "local_absolute_path_stored": False,
        "provider_key_stored": False,
    }


def _public_record(record: Mapping[str, object]) -> dict[str, object]:
    policy = _normalize_policy(record.get("sync_policy", "local_only"))
    origin = _normalize_origin(record.get("origin", "local"))
    conversation_id = _safe_conversation_id(record.get("conversation_id", "conversation"))
    return {
        "conversation_id": conversation_id,
        "origin": origin,
        "sync_policy": policy,
        "created_at": _safe_public_text(record.get("created_at"), fallback=None),
        "updated_at": _safe_public_text(record.get("updated_at"), fallback=None),
        "audit_reason": _safe_public_text(record.get("audit_reason"), fallback="policy_record"),
        "local_extended": bool(record.get("local_extended", False)),
        "execution": _execution_boundary(policy, origin),
        "memory": _memory_boundary(policy, origin),
        "raw_body_stored": False,
        "local_absolute_path_stored": False,
        "provider_key_stored": False,
    }


def _execution_boundary(policy: str, origin: str) -> dict[str, object]:
    if policy == "paused":
        return {
            "execution_allowed": False,
            "official_worker_allowed": False,
            "local_loopback_required": True,
            "decision": "blocked_paused",
            "reason": "conversation_sync_paused",
        }
    if policy == "local_only":
        return {
            "execution_allowed": True,
            "official_worker_allowed": False,
            "local_loopback_required": True,
            "decision": "local_loopback_only",
            "reason": "local_only_conversation_must_not_dispatch_to_official_worker",
        }
    if policy == "cloud_to_local":
        allowed = origin in {"cloud", "web"}
        return {
            "execution_allowed": True,
            "official_worker_allowed": allowed,
            "local_loopback_required": not allowed,
            "decision": "cloud_origin_official_worker_allowed" if allowed else "local_origin_cloud_to_local_preview_only",
            "reason": "cloud_to_local_does_not_allow_silent_local_upload",
        }
    return {
        "execution_allowed": True,
        "official_worker_allowed": True,
        "local_loopback_required": False,
        "decision": "explicit_bidirectional_policy",
        "reason": "local_to_cloud_requires_existing_explicit_policy",
    }


def _memory_boundary(policy: str, origin: str) -> dict[str, object]:
    if policy == "local_only":
        return {
            "inherits_conversation_policy": True,
            "memory_scope": "local_private",
            "cloud_memory_index_allowed": False,
            "local_to_cloud_memory_sync": "disabled",
            "reason": "local_only_memory_stays_local",
        }
    if policy == "cloud_to_local":
        return {
            "inherits_conversation_policy": True,
            "memory_scope": "cloud_account_reference" if origin in {"cloud", "web"} else "local_private",
            "cloud_memory_index_allowed": origin in {"cloud", "web"},
            "local_to_cloud_memory_sync": "disabled",
            "reason": "cloud_memory_can_sync_down_only",
        }
    if policy == "bidirectional_explicit":
        return {
            "inherits_conversation_policy": True,
            "memory_scope": "shared_preference",
            "cloud_memory_index_allowed": True,
            "local_to_cloud_memory_sync": "explicit_policy_only",
            "reason": "bidirectional_memory_requires_explicit_policy",
        }
    return {
        "inherits_conversation_policy": True,
        "memory_scope": "paused",
        "cloud_memory_index_allowed": False,
        "local_to_cloud_memory_sync": "paused",
        "reason": "conversation_sync_paused",
    }


def _policy_definitions() -> dict[str, dict[str, object]]:
    return {
        "local_only": {
            "local_to_cloud_upload": False,
            "official_worker_dispatch": False,
            "default_for": ["local-origin conversation"],
        },
        "cloud_to_local": {
            "local_to_cloud_upload": False,
            "cloud_to_local_preview": True,
            "default_for": ["cloud-origin conversation", "web-origin conversation"],
        },
        "bidirectional_explicit": {
            "local_to_cloud_upload": "requires explicit confirmation",
            "cloud_to_local_preview": True,
            "default_for": [],
        },
        "paused": {
            "local_to_cloud_upload": False,
            "cloud_to_local_preview": False,
            "default_for": [],
        },
    }


def _private_content_exclusion() -> dict[str, bool]:
    return {
        "raw_body_excluded": True,
        "raw_prompt_excluded": True,
        "private_file_content_excluded": True,
        "local_private_memory_excluded": True,
        "local_node_payload_excluded": True,
        "provider_keys_excluded": True,
        "local_absolute_paths_excluded": True,
        "openai_shared_traffic_excluded": True,
    }


def _non_actions() -> list[str]:
    return [
        "no production Google login",
        "no Google token storage",
        "no refresh token storage",
        "no automatic local-to-cloud upload",
        "no private file content upload",
        "no local private memory upload",
        "no local node payload upload",
        "no provider key upload",
        "no OpenAI shared traffic",
        "no official worker dispatch for local_only conversations",
    ]


def _normalize_policy(value: object) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized not in SYNC_POLICIES:
        raise ConversationSyncPolicyError("conversation_policy_invalid", "Conversation sync policy is invalid.")
    return normalized


def _normalize_origin(value: object) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized not in CONVERSATION_ORIGINS:
        raise ConversationSyncPolicyError("conversation_origin_invalid", "Conversation origin is invalid.")
    return normalized


def _default_policy_for_origin(origin: str) -> str:
    normalized_origin = _normalize_origin(origin)
    return "local_only" if normalized_origin == "local" else "cloud_to_local"


def _default_origin_for_policy(policy: str) -> str:
    normalized_policy = _normalize_policy(policy)
    if normalized_policy == "cloud_to_local":
        return "cloud"
    return "local"


def _safe_conversation_id(value: object) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if any(marker in lowered for marker in _forbidden_markers()):
        raise ConversationSyncPolicyError("conversation_id_private_rejected", "Conversation id is not public-safe.")
    if not CONVERSATION_ID_RE.fullmatch(text):
        raise ConversationSyncPolicyError("conversation_id_invalid", "Conversation id is invalid.")
    return text


def _safe_public_text(value: object, *, fallback: str | None) -> str | None:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    lowered = text.lower()
    if any(marker in lowered for marker in _forbidden_markers()):
        return fallback
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return fallback
    return text[:180]


def _forbidden_markers() -> tuple[str, ...]:
    return (
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "authorization_code",
        "google_token",
        "staging_session_token",
        "api_key",
        "password",
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


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
