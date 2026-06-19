from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from yonerai_cli.config import default_config_path


PROVIDER_SHARING_SCHEMA_VERSION = "yonerai-provider-sharing/v0.1"
PROVIDER_SHARING_CONSENT_VERSION = "yonerai-provider-sharing-consent/v0.1"
PROVIDER_DATA_POLICIES = ("none", "local_provider", "openai_shared_explicit")
CONVERSATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")


class ProviderSharingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_safe_error(self) -> dict[str, object]:
        return _safe_error(self.code, self.message)


def default_provider_sharing_path(
    config_path: str | Path | None = None,
    *,
    env: Mapping[str, str | None] | None = None,
) -> Path:
    base = Path(config_path).expanduser() if config_path is not None else default_config_path(env)
    source = os.environ if env is None else env
    if config_path is None and not str(source.get("YONERAI_CLI_CONFIG_PATH") or "").strip():
        return base.with_name("provider-sharing-consents.json")
    return base.with_name(f"{base.stem}.provider-sharing-consents.json")


def build_provider_sharing_status_report(
    *,
    conversation_id: str | None = None,
    store_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, object]:
    store = _load_store(store_path, config_path=config_path)
    records = _sorted_records(store)
    if conversation_id:
        safe_id = _safe_conversation_id(conversation_id)
        record = _records(store).get(safe_id)
        return _base_report(
            "provider_sharing_status",
            {
                "conversation_id": safe_id,
                "conversation": _public_record(record) if isinstance(record, Mapping) else _default_record(safe_id),
                "conversation_count": len(records),
            },
        )
    counts = {policy: 0 for policy in PROVIDER_DATA_POLICIES}
    for record in records:
        counts[str(record.get("provider_data_policy") or "none")] += 1
    return _base_report(
        "provider_sharing_status",
        {
            "conversation_count": len(records),
            "policy_counts": counts,
            "conversations": [_public_record(record) for record in records[:20]],
            "empty_state": "no provider-sharing consent has been recorded yet" if not records else None,
        },
    )


def build_provider_sharing_enable_report(
    conversation_id: str,
    *,
    sync_policy: str = "cloud_to_local",
    confirm: bool = False,
    store_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, object]:
    safe_id = _safe_conversation_id(conversation_id)
    safe_sync_policy = _safe_sync_policy(sync_policy)
    if safe_sync_policy == "local_only":
        return _base_report(
            "provider_sharing_enable",
            {
                "ok": False,
                "conversation_id": safe_id,
                "sync_policy": safe_sync_policy,
                "decision": _decision("rejected", "local_only_never_calls_openai", written=False),
                "error": _safe_error(
                    "local_only_provider_sharing_rejected",
                    "local_only conversations cannot enable OpenAI shared traffic.",
                ),
            },
        )
    consent_copy = _consent_copy()
    if not confirm:
        return _base_report(
            "provider_sharing_enable",
            {
                "ok": False,
                "conversation_id": safe_id,
                "sync_policy": safe_sync_policy,
                "provider_data_policy": "openai_shared_explicit",
                "consent_copy": consent_copy,
                "decision": _decision("approval_required", "provider_sharing_requires_explicit_confirm", written=False),
                "error": _safe_error(
                    "provider_sharing_consent_required",
                    "Explicit per-conversation confirmation is required before sending selected conversation context to OpenAI.",
                    next_safe_command=f"yonerai privacy provider-sharing enable {safe_id} --confirm",
                ),
            },
        )
    store = _load_store(store_path, config_path=config_path)
    now = _utc_now()
    record = {
        "conversation_id": safe_id,
        "provider_data_policy": "openai_shared_explicit",
        "sync_policy_at_consent": safe_sync_policy,
        "consent_state": "enabled",
        "consent_version": PROVIDER_SHARING_CONSENT_VERSION,
        "enabled_at": now,
        "updated_at": now,
        "revoked_at": None,
        "raw_body_stored": False,
        "provider_key_stored": False,
        "google_token_stored": False,
        "local_path_stored": False,
    }
    _records(store)[safe_id] = record
    _save_store(store, store_path, config_path=config_path)
    return _base_report(
        "provider_sharing_enable",
        {
            "conversation": _public_record(record),
            "conversation_id": safe_id,
            "sync_policy": safe_sync_policy,
            "provider_data_policy": "openai_shared_explicit",
            "consent_copy": consent_copy,
            "decision": _decision("written", "explicit_provider_sharing_consent_recorded", written=True),
        },
    )


def build_provider_sharing_disable_report(
    conversation_id: str,
    *,
    store_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, object]:
    safe_id = _safe_conversation_id(conversation_id)
    store = _load_store(store_path, config_path=config_path)
    existing = _records(store).get(safe_id)
    now = _utc_now()
    record = dict(existing) if isinstance(existing, Mapping) else _default_record(safe_id)
    record.update(
        {
            "conversation_id": safe_id,
            "provider_data_policy": "none",
            "consent_state": "disabled",
            "updated_at": now,
            "revoked_at": now,
            "raw_body_stored": False,
            "provider_key_stored": False,
            "google_token_stored": False,
            "local_path_stored": False,
        }
    )
    _records(store)[safe_id] = record
    _save_store(store, store_path, config_path=config_path)
    return _base_report(
        "provider_sharing_disable",
        {
            "conversation": _public_record(record),
            "conversation_id": safe_id,
            "provider_data_policy": "none",
            "decision": _decision("written", "future_provider_sharing_disabled", written=True),
            "revocation_note": "Revocation stops future sharing. It does not recall data already submitted to OpenAI.",
        },
    )


def resolve_provider_data_policy(
    *,
    conversation_id: str | None,
    sync_policy: str | None,
    requested_policy: str | None = None,
    store_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, object]:
    normalized_sync = _safe_sync_policy(sync_policy or "cloud_to_local")
    if normalized_sync == "local_only":
        if requested_policy == "openai_shared_explicit":
            raise ProviderSharingError(
                "local_only_provider_sharing_rejected",
                "local_only conversations cannot use OpenAI shared traffic.",
            )
        return _policy_report(
            conversation_id=conversation_id,
            provider_data_policy="local_provider",
            consent_state="not_applicable",
            sync_policy=normalized_sync,
            consent_required=False,
        )
    requested = _safe_provider_data_policy(requested_policy or "none")
    if requested == "local_provider":
        return _policy_report(
            conversation_id=conversation_id,
            provider_data_policy="local_provider",
            consent_state="local_only",
            sync_policy=normalized_sync,
            consent_required=False,
        )
    if not conversation_id:
        if requested == "openai_shared_explicit":
            raise ProviderSharingError(
                "provider_sharing_consent_required",
                "OpenAI shared traffic requires a conversation id and explicit consent.",
            )
        return _policy_report(
            conversation_id=None,
            provider_data_policy="none",
            consent_state="not_enabled",
            sync_policy=normalized_sync,
            consent_required=False,
        )
    safe_id = _safe_conversation_id(conversation_id)
    store = _load_store(store_path, config_path=config_path)
    record = _records(store).get(safe_id)
    enabled = (
        isinstance(record, Mapping)
        and record.get("provider_data_policy") == "openai_shared_explicit"
        and record.get("consent_state") == "enabled"
    )
    if requested == "openai_shared_explicit" and not enabled:
        raise ProviderSharingError(
            "provider_sharing_consent_required",
            "This conversation has not recorded explicit OpenAI shared-traffic consent.",
        )
    if enabled:
        return _policy_report(
            conversation_id=safe_id,
            provider_data_policy="openai_shared_explicit",
            consent_state="enabled",
            sync_policy=normalized_sync,
            consent_required=False,
            consent_version=str(record.get("consent_version") or PROVIDER_SHARING_CONSENT_VERSION),
        )
    return _policy_report(
        conversation_id=safe_id,
        provider_data_policy="none",
        consent_state="not_enabled",
        sync_policy=normalized_sync,
        consent_required=False,
    )


def build_context_preview(
    *,
    prompt: str,
    provider_policy: Mapping[str, object],
    model_class: str = "staging_provider",
) -> dict[str, object]:
    text = str(prompt or "").strip()
    word_count = len([part for part in re.split(r"\s+", text) if part])
    estimated_tokens = max(1, min(2048, int(len(text) / 3.5) + word_count))
    provider_data_policy = str(provider_policy.get("provider_data_policy") or "none")
    return {
        "schema_version": "yonerai-context-preview/v0.1",
        "server_authoritative_context_policy": True,
        "current_message_included": provider_data_policy == "openai_shared_explicit",
        "prior_message_count": 0,
        "summary_included": False,
        "full_history_included": False,
        "estimated_tokens": estimated_tokens,
        "reserved_token_budget": max(512, min(4096, estimated_tokens + 512)),
        "model_class": model_class,
        "data_sharing_mode": provider_data_policy,
        "consent_version": provider_policy.get("consent_version"),
        "excluded_data_categories": [
            "local/workspace files",
            "attachments",
            "local private memory",
            "provider keys",
            "Google tokens",
            "raw chain-of-thought",
            "full conversation history by default",
        ],
    }


def _policy_report(
    *,
    conversation_id: str | None,
    provider_data_policy: str,
    consent_state: str,
    sync_policy: str,
    consent_required: bool,
    consent_version: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": PROVIDER_SHARING_SCHEMA_VERSION,
        "conversation_id": conversation_id,
        "sync_policy": sync_policy,
        "provider_data_policy": provider_data_policy,
        "consent_state": consent_state,
        "consent_required": consent_required,
        "consent_version": consent_version,
        "openai_shared_traffic_enabled": provider_data_policy == "openai_shared_explicit",
        "local_only_excluded": sync_policy == "local_only",
        "raw_body_included": False,
        "provider_key_included": False,
        "google_token_included": False,
        "local_path_included": False,
    }


def _base_report(operation: str, extra: Mapping[str, object]) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": PROVIDER_SHARING_SCHEMA_VERSION,
        "ok": True,
        "operation": operation,
        "shared_traffic_default": False,
        "implicit_consent_allowed": False,
        "terms_checkbox_substitute_allowed": False,
        "sync_policy_is_separate": True,
        "provider_data_policy_is_separate": True,
        "local_only_openai_allowed": False,
        "raw_body_stored": False,
        "provider_key_stored": False,
        "google_token_stored": False,
        "refresh_token_stored": False,
        "local_path_stored": False,
        "actions_not_performed": [
            "no production Google login",
            "no production cloud claim",
            "no OpenAI key in Public CLI",
            "no shared traffic by default",
            "no implicit consent",
            "no local_only transmission",
            "no local/workspace files or attachments",
            "no private memory/secrets/provider keys",
            "no automatic paid overage",
        ],
    }
    report.update(dict(extra))
    return report


def _load_store(store_path: str | Path | None, *, config_path: str | Path | None) -> dict[str, object]:
    path = _store_path(store_path, config_path=config_path)
    if not path.exists():
        return {"schema_version": PROVIDER_SHARING_SCHEMA_VERSION, "conversations": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderSharingError("provider_sharing_store_invalid", "Provider-sharing consent store is invalid.") from exc
    if not isinstance(raw, dict):
        raise ProviderSharingError("provider_sharing_store_invalid", "Provider-sharing consent store is invalid.")
    conversations = raw.get("conversations")
    if not isinstance(conversations, dict):
        conversations = {}
    sanitized: dict[str, object] = {"schema_version": PROVIDER_SHARING_SCHEMA_VERSION, "conversations": {}}
    for key, value in conversations.items():
        if not isinstance(value, Mapping):
            continue
        conversation_id = _safe_conversation_id(value.get("conversation_id", key))
        policy = _safe_provider_data_policy(value.get("provider_data_policy", "none"))
        record = _default_record(conversation_id)
        record.update(
            {
                "provider_data_policy": policy,
                "sync_policy_at_consent": _safe_sync_policy(value.get("sync_policy_at_consent", "cloud_to_local")),
                "consent_state": _safe_consent_state(value.get("consent_state", "disabled")),
                "consent_version": str(value.get("consent_version") or PROVIDER_SHARING_CONSENT_VERSION),
                "enabled_at": _safe_public_text(value.get("enabled_at"), fallback=None),
                "updated_at": _safe_public_text(value.get("updated_at"), fallback=None),
                "revoked_at": _safe_public_text(value.get("revoked_at"), fallback=None),
            }
        )
        _records(sanitized)[conversation_id] = record
    return sanitized


def _save_store(store: Mapping[str, object], store_path: str | Path | None, *, config_path: str | Path | None) -> None:
    path = _store_path(store_path, config_path=config_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ProviderSharingError("provider_sharing_store_write_failed", "Provider-sharing consent store could not be written.") from exc


def _store_path(store_path: str | Path | None, *, config_path: str | Path | None) -> Path:
    return Path(store_path).expanduser() if store_path is not None else default_provider_sharing_path(config_path)


def _records(store: Mapping[str, object]) -> dict[str, object]:
    records = store.get("conversations")
    if not isinstance(records, dict):
        raise ProviderSharingError("provider_sharing_store_invalid", "Provider-sharing consent store is invalid.")
    return records


def _sorted_records(store: Mapping[str, object]) -> list[Mapping[str, object]]:
    return [record for record in _records(store).values() if isinstance(record, Mapping)]


def _default_record(conversation_id: str) -> dict[str, object]:
    return {
        "conversation_id": conversation_id,
        "provider_data_policy": "none",
        "sync_policy_at_consent": "cloud_to_local",
        "consent_state": "disabled",
        "consent_version": PROVIDER_SHARING_CONSENT_VERSION,
        "enabled_at": None,
        "updated_at": None,
        "revoked_at": None,
        "raw_body_stored": False,
        "provider_key_stored": False,
        "google_token_stored": False,
        "local_path_stored": False,
    }


def _public_record(record: Mapping[str, object]) -> dict[str, object]:
    return {
        "conversation_id": _safe_conversation_id(record.get("conversation_id")),
        "provider_data_policy": _safe_provider_data_policy(record.get("provider_data_policy", "none")),
        "sync_policy_at_consent": _safe_sync_policy(record.get("sync_policy_at_consent", "cloud_to_local")),
        "consent_state": _safe_consent_state(record.get("consent_state", "disabled")),
        "consent_version": str(record.get("consent_version") or PROVIDER_SHARING_CONSENT_VERSION),
        "enabled_at": _safe_public_text(record.get("enabled_at"), fallback=None),
        "updated_at": _safe_public_text(record.get("updated_at"), fallback=None),
        "revoked_at": _safe_public_text(record.get("revoked_at"), fallback=None),
        "raw_body_stored": False,
        "provider_key_stored": False,
        "google_token_stored": False,
        "local_path_stored": False,
    }


def _consent_copy() -> dict[str, object]:
    return {
        "consent_version": PROVIDER_SHARING_CONSENT_VERSION,
        "selected_conversation_content_sent_to_openai": True,
        "inputs_and_outputs_shared_under_openai_data_sharing_settings": True,
        "may_be_used_for_evaluation_improvement_or_training": True,
        "context_package_may_include": [
            "current message",
            "small server-authoritative summary if present",
            "limited prior-message references",
            "metadata needed for quota and audit",
        ],
        "excluded": [
            "local/workspace files",
            "attachments",
            "local private memory",
            "local node payloads",
            "provider keys",
            "Google tokens",
        ],
        "revocation_stops_future_sharing": True,
        "already_submitted_data_recall_promised": False,
        "local_only_excluded": True,
        "general_terms_checkbox_is_not_substitute": True,
    }


def _decision(state: str, reason: str, *, written: bool) -> dict[str, object]:
    return {
        "state": state,
        "reason": reason,
        "written": written,
        "requires_explicit_confirmation": state == "approval_required",
    }


def _safe_error(code: str, message: str, *, next_safe_command: str | None = None) -> dict[str, object]:
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "private_endpoint_printed": False,
        "local_path_printed": False,
        "token_printed": False,
        "provider_key_printed": False,
        "raw_body_printed": False,
    }
    if next_safe_command:
        error["next_safe_command"] = next_safe_command
    return error


def _safe_conversation_id(value: object) -> str:
    text = str(value or "").strip()
    if not CONVERSATION_ID_RE.fullmatch(text):
        raise ProviderSharingError("provider_sharing_conversation_id_invalid", "Conversation id is invalid.")
    lowered = text.lower()
    if _looks_private(lowered):
        raise ProviderSharingError("provider_sharing_conversation_id_invalid", "Conversation id is invalid.")
    return text


def _safe_provider_data_policy(value: object) -> str:
    text = str(value or "none").strip()
    if text not in PROVIDER_DATA_POLICIES:
        raise ProviderSharingError("provider_data_policy_invalid", "Provider data policy is invalid.")
    return text


def _safe_sync_policy(value: object) -> str:
    text = str(value or "cloud_to_local").strip()
    if text not in {"local_only", "cloud_to_local", "bidirectional_explicit", "paused"}:
        raise ProviderSharingError("provider_sharing_sync_policy_invalid", "Sync policy is invalid.")
    return text


def _safe_consent_state(value: object) -> str:
    text = str(value or "disabled").strip()
    if text not in {"enabled", "disabled"}:
        return "disabled"
    return text


def _safe_public_text(value: object, *, fallback: object, max_length: int = 240) -> object:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if _looks_private(text.lower()) or any(ord(char) < 32 or ord(char) == 127 for char in text):
        return fallback
    return text[:max_length]


def _looks_private(lowered: str) -> bool:
    return any(
        marker in lowered
        for marker in (
            "access_token",
            "refresh_token",
            "client_secret",
            "authorization_code",
            "google_token",
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
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
