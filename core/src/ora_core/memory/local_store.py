from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Mapping, Sequence


MEMORY_BOUNDARY_SCHEMA_VERSION = "yonerai-memory-boundary/v0.1"
LOCAL_MEMORY_SCHEMA_VERSION = MEMORY_BOUNDARY_SCHEMA_VERSION
MEMORY_SYNC_SCHEMA_VERSION = "yonerai-memory-sync-boundary/v0.1"
SELF_EVOLUTION_MEMORY_SCHEMA_VERSION = "yonerai-self-evolution-signal-memory/v0.1"

MemoryScope = Literal[
    "session",
    "local_private",
    "cloud_account",
    "shared_preference",
    "project",
    "procedural",
    "self_evolution_signal",
]
MemorySource = Literal[
    "user_explicit",
    "conversation_summary",
    "provider_result",
    "sync_import",
    "system_event",
    "synthetic_signal",
]
MemorySensitivity = Literal["public", "private", "local_only", "secret_like"]
SyncPolicy = Literal["never_sync", "cloud_to_local", "local_to_cloud_requires_approval", "shared_allowed"]
MemoryStatus = Literal["active", "archived", "forgotten", "pending_sync", "rejected"]
MemorySyncDirection = Literal["cloud_to_local", "local_to_cloud"]

VALID_SCOPES = {
    "session",
    "local_private",
    "cloud_account",
    "shared_preference",
    "project",
    "procedural",
    "self_evolution_signal",
}
VALID_SOURCES = {
    "user_explicit",
    "conversation_summary",
    "provider_result",
    "sync_import",
    "system_event",
    "synthetic_signal",
}
VALID_SENSITIVITIES = {"public", "private", "local_only", "secret_like"}
VALID_SYNC_POLICIES = {"never_sync", "cloud_to_local", "local_to_cloud_requires_approval", "shared_allowed"}
VALID_STATUSES = {"active", "archived", "forgotten", "pending_sync", "rejected"}
VALID_SYNC_DIRECTIONS = {"cloud_to_local", "local_to_cloud"}

LOCAL_PATH_PATTERNS = (
    re.compile(r"(?:(?<=^)|(?<=[\s\"'(<]))[A-Za-z]:[\\/][^\s\"'<>|]+", re.IGNORECASE),
    re.compile(r"(?:(?<=^)|(?<=[\s\"'(<]))/(?!/)[^\s\"'<>|]+", re.IGNORECASE),
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bAIzaSy[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b", re.IGNORECASE),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", re.IGNORECASE),
    re.compile(r"\bxox(?:b|p|a|r|s)-[A-Za-z0-9-]{10,}\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"\b[A-Za-z0-9_-]*(?:api[_-]?key|apikey|access[_-]?key|access[_-]?token|refresh[_-]?token|discord[_-]?token|private[_-]?key|client[_-]?secret|authorization|bearer|password|secret|token)[A-Za-z0-9_-]*\s*(?:=|:)\s*[^\s,;]+",
        re.IGNORECASE,
    ),
)


class MemoryStoreError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def to_public_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    created_at: str
    updated_at: str
    scope: MemoryScope
    source: MemorySource
    sensitivity: MemorySensitivity
    sync_policy: SyncPolicy
    status: MemoryStatus
    redacted_summary: str
    source_ref: str
    audit_reason: str
    tags: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def memory_id(self) -> str:
        return self.id

    @property
    def text(self) -> str:
        return self.redacted_summary

    @property
    def redacted(self) -> bool:
        return True

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["schema_version"] = MEMORY_BOUNDARY_SCHEMA_VERSION
        payload["memory_id"] = self.id
        payload["text"] = self.redacted_summary
        payload["tags"] = list(self.tags)
        payload["cloud_synced"] = False
        payload["raw_content_persisted"] = False
        payload["raw_prompt_persisted"] = False
        payload["provider_key_persisted"] = False
        payload["local_absolute_path_persisted"] = False
        payload["sync_up_approved"] = False
        return payload


LocalMemoryRecord = MemoryRecord


@dataclass(frozen=True)
class CloudMemoryRef:
    ref_id: str = "cloud-memory-fixture"
    selected_by_user: bool = False
    raw_body_included: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "ref_id": self.ref_id,
            "selected_by_user": self.selected_by_user,
            "raw_body_included": self.raw_body_included,
        }


@dataclass(frozen=True)
class LocalMemoryRef:
    memory_id: str
    scope: MemoryScope
    sensitivity: MemorySensitivity
    sync_policy: SyncPolicy
    status: MemoryStatus
    raw_body_included: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemorySyncDecision:
    direction: MemorySyncDirection
    state: Literal["preview_allowed", "approval_required", "blocked"]
    reason: str
    requires_explicit_approval: bool
    private_content_excluded: bool = True
    sync_performed: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemorySyncAudit:
    audit_reason: str
    actor: str = "local_user"
    dry_run: bool = True
    raw_private_content_logged: bool = False
    pii_logged: bool = False
    provider_keys_logged: bool = False
    local_absolute_paths_logged: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": MEMORY_SYNC_SCHEMA_VERSION,
            **asdict(self),
        }


@dataclass(frozen=True)
class MemorySyncEnvelope:
    direction: MemorySyncDirection
    decision: MemorySyncDecision
    cloud_ref: CloudMemoryRef
    local_refs: tuple[LocalMemoryRef, ...]
    audit: MemorySyncAudit
    official_backend_called: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": MEMORY_SYNC_SCHEMA_VERSION,
            "direction": self.direction,
            "decision": self.decision.to_public_dict(),
            "cloud_memory": self.cloud_ref.to_public_dict(),
            "local_memory": [ref.to_public_dict() for ref in self.local_refs],
            "audit": self.audit.to_public_dict(),
            "official_backend_called": self.official_backend_called,
            "sync_performed": False,
            "actions_not_performed": memory_sync_non_actions(),
        }


@dataclass(frozen=True)
class SelfEvolutionSignalMemory:
    feature_id: str
    surface: str
    mode: str
    outcome: str
    dropoff_stage: str
    complaint_class: str
    provider_class: str
    latency_bucket: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": SELF_EVOLUTION_MEMORY_SCHEMA_VERSION,
            "scope": "self_evolution_signal",
            "source": "synthetic_signal",
            "sensitivity": "public",
            "sync_policy": "never_sync",
            "proposal_only": True,
            "raw_prompt_included": False,
            "pii_included": False,
            "stable_user_tracking_included": False,
            **asdict(self),
        }


class LocalMemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def add(
        self,
        text: str,
        *,
        tags: tuple[str, ...] = (),
        scope: MemoryScope = "local_private",
        source: MemorySource = "user_explicit",
        sensitivity: MemorySensitivity | None = None,
        sync_policy: SyncPolicy | None = None,
        source_ref: str = "manual_cli",
        audit_reason: str = "explicit local memory add",
        metadata: Mapping[str, object] | None = None,
    ) -> MemoryRecord:
        scope = _normalize_scope(scope)
        source = _validate_member(source, VALID_SOURCES, "source")  # type: ignore[assignment]
        sensitivity = _default_sensitivity(scope) if sensitivity is None else sensitivity
        sensitivity = _validate_member(sensitivity, VALID_SENSITIVITIES, "sensitivity")  # type: ignore[assignment]
        sync_policy = _default_sync_policy(scope, sensitivity) if sync_policy is None else sync_policy
        sync_policy = _validate_member(sync_policy, VALID_SYNC_POLICIES, "sync_policy")  # type: ignore[assignment]
        cleaned = _redact_text(text)
        if not cleaned:
            raise MemoryStoreError("memory_text_required", "memory text must not be empty.")
        if _looks_secret_like(text):
            sensitivity = "secret_like"
            sync_policy = "never_sync"
        elif _looks_local_path_like(text):
            sensitivity = "local_only"
            sync_policy = "never_sync"
        now = _now()
        records = self.list(include_inactive=True)
        record = MemoryRecord(
            id=f"mem_{uuid.uuid4().hex[:24]}",
            created_at=now,
            updated_at=now,
            scope=scope,
            source=source,
            sensitivity=sensitivity,
            sync_policy=sync_policy,
            status="active",
            redacted_summary=cleaned,
            source_ref=_safe_source_ref(source_ref),
            audit_reason=_redact_text(audit_reason)[:240],
            tags=tuple(_safe_tag(tag) for tag in tags if _safe_tag(tag)),
            metadata=_safe_metadata(metadata or {}),
        )
        records.append(record)
        self._write(records)
        return record

    def list(
        self,
        *,
        scope: MemoryScope | str | None = None,
        include_inactive: bool = False,
    ) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        normalized_scope = _normalize_scope(scope) if scope else None
        records: list[MemoryRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            record = _record_from_payload(payload)
            if record is None:
                continue
            if normalized_scope and record.scope != normalized_scope:
                continue
            if not include_inactive and record.status != "active":
                continue
            records.append(record)
        return records

    def forget(self, memory_id: str) -> bool:
        target = str(memory_id or "").strip()
        found = False
        records: list[MemoryRecord] = []
        now = _now()
        for record in self.list(include_inactive=True):
            if record.id != target:
                records.append(record)
                continue
            found = True
            records.append(
                MemoryRecord(
                    id=record.id,
                    created_at=record.created_at,
                    updated_at=now,
                    scope=record.scope,
                    source=record.source,
                    sensitivity=record.sensitivity,
                    sync_policy="never_sync",
                    status="forgotten",
                    redacted_summary="[forgotten]",
                    source_ref=record.source_ref,
                    audit_reason="user requested local forget",
                    tags=record.tags,
                    metadata={},
                )
            )
        if found:
            self._write(records)
        return found

    def delete(self, memory_id: str) -> bool:
        target = str(memory_id or "").strip()
        records = self.list(include_inactive=True)
        kept = [record for record in records if record.id != target]
        if len(kept) == len(records):
            return False
        self._write(kept)
        return True

    def status(self) -> dict[str, object]:
        records = self.list(include_inactive=True)
        active = [record for record in records if record.status == "active"]
        counts_by_scope = {scope: sum(1 for record in active if record.scope == scope) for scope in sorted(VALID_SCOPES)}
        return {
            "schema_version": MEMORY_BOUNDARY_SCHEMA_VERSION,
            "ok": True,
            "operation": "status",
            "store_configured": True,
            "store_path_output": False,
            "record_count": len(active),
            "total_record_count": len(records),
            "counts_by_scope": counts_by_scope,
            "local_private_default": True,
            "cloud_sync_enabled": False,
            "local_to_cloud_enabled_by_default": False,
            "raw_prompt_persisted": False,
            "raw_secret_persisted": False,
            "local_absolute_path_persisted": False,
            "actions_not_performed": [
                "no production cloud runtime",
                "no automatic local-to-cloud memory sync",
                "no raw private memory upload",
                "no provider key storage",
                "no local absolute path output",
            ],
        }

    def export(self) -> dict[str, object]:
        records = [record.to_public_dict() for record in self.list()]
        return {
            "schema_version": MEMORY_BOUNDARY_SCHEMA_VERSION,
            "ok": True,
            "cloud_synced": False,
            "records": records,
            "count": len(records),
            "raw_prompt_persisted": False,
            "raw_secret_persisted": False,
            "local_absolute_path_persisted": False,
        }

    def _write(self, records: Sequence[MemoryRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = "\n".join(json.dumps(record.to_public_dict(), ensure_ascii=False, sort_keys=True) for record in records)
        _write_private_text(self.path, payload + ("\n" if payload else ""))


def default_memory_store_path(env: Mapping[str, str | None] | None = None) -> Path:
    source = os.environ if env is None else env
    override = str(source.get("YONERAI_MEMORY_STORE_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    appdata = str(source.get("APPDATA") or "").strip()
    if appdata:
        return Path(appdata) / "YonerAI" / "memory.jsonl"
    xdg_data = str(source.get("XDG_DATA_HOME") or "").strip()
    if xdg_data:
        return Path(xdg_data) / "yonerai" / "memory.jsonl"
    return Path.home() / ".local" / "share" / "yonerai" / "memory.jsonl"


def build_memory_sync_preview(
    records: Sequence[MemoryRecord] = (),
    *,
    direction: MemorySyncDirection = "cloud_to_local",
    explicit_approval: bool = False,
    selected_cloud_memory: bool = True,
) -> dict[str, object]:
    direction = _validate_member(direction, VALID_SYNC_DIRECTIONS, "direction")  # type: ignore[assignment]
    active_records = tuple(record for record in records if record.status == "active")
    decision = _memory_sync_decision(
        active_records,
        direction=direction,
        explicit_approval=explicit_approval,
        selected_cloud_memory=selected_cloud_memory,
    )
    envelope = MemorySyncEnvelope(
        direction=direction,
        decision=decision,
        cloud_ref=CloudMemoryRef(selected_by_user=selected_cloud_memory),
        local_refs=tuple(_local_ref(record) for record in active_records[:20]),
        audit=MemorySyncAudit(audit_reason=decision.reason),
    )
    report = envelope.to_public_dict()
    report.update(
        {
            "ok": True,
            "operation": "sync_preview",
            "preview_only": True,
            "sync_allowed": decision.state != "blocked",
            "explicit_approval_recorded": False,
            "local_to_cloud_enabled_by_default": False,
            "private_content_exclusion": {
                "local_private_excluded": True,
                "secret_like_excluded": True,
                "private_file_content_excluded": True,
                "local_node_payload_excluded": True,
                "raw_prompt_excluded": True,
            },
        }
    )
    return report


def select_allowed_memory_for_ask(records: Sequence[MemoryRecord], *, limit: int = 5) -> list[MemoryRecord]:
    allowed: list[MemoryRecord] = []
    for record in records:
        if record.status != "active":
            continue
        if record.scope not in {"procedural", "shared_preference"}:
            continue
        if record.sensitivity in {"secret_like", "local_only"}:
            continue
        allowed.append(record)
        if len(allowed) >= limit:
            break
    return allowed


def memory_context_event(records: Sequence[MemoryRecord]) -> dict[str, object]:
    ids = [record.id for record in records]
    return {
        "name": "memory_context_used",
        "status": "ok" if ids else "skipped",
        "summary": "memory_used_ids=" + ",".join(ids) if ids else "memory_used_ids=none",
        "memory_used": ids,
        "raw_memory_content_included": False,
    }


def build_memory_usage_report(records: Sequence[MemoryRecord], *, enabled: bool) -> dict[str, object]:
    ids = [record.id for record in records]
    return {
        "schema_version": MEMORY_BOUNDARY_SCHEMA_VERSION,
        "enabled": enabled,
        "used_ids": ids,
        "used_count": len(ids),
        "allowed_scopes": ["procedural", "shared_preference"],
        "raw_memory_content_in_ledger": False,
        "local_private_memory_used": False,
        "secret_like_memory_used": False,
        "content_sent_to_cloud_contract": False,
    }


def build_self_evolution_signal_memory(payload: Mapping[str, object]) -> SelfEvolutionSignalMemory:
    allowed = {
        "feature_id",
        "surface",
        "mode",
        "outcome",
        "dropoff_stage",
        "complaint_class",
        "provider_class",
        "latency_bucket",
    }
    forbidden = set(payload) - allowed
    if forbidden:
        raise MemoryStoreError("unsafe_self_evolution_signal", f"forbidden signal fields: {', '.join(sorted(forbidden))}")
    missing = allowed - set(payload)
    if missing:
        raise MemoryStoreError("incomplete_self_evolution_signal", f"missing signal fields: {', '.join(sorted(missing))}")
    values = {key: _safe_signal_value(payload[key], field=key) for key in allowed}
    return SelfEvolutionSignalMemory(**values)  # type: ignore[arg-type]


def memory_sync_non_actions() -> list[str]:
    return [
        "no network request",
        "no production cloud runtime",
        "no automatic local-to-cloud upload",
        "no private file content upload",
        "no local private memory upload",
        "no secret-like memory upload",
        "no provider key upload",
        "no OpenAI shared traffic",
    ]


def _memory_sync_decision(
    records: Sequence[MemoryRecord],
    *,
    direction: MemorySyncDirection,
    explicit_approval: bool,
    selected_cloud_memory: bool,
) -> MemorySyncDecision:
    if direction == "cloud_to_local":
        if not selected_cloud_memory:
            return MemorySyncDecision(
                direction=direction,
                state="blocked",
                reason="cloud_memory_not_selected",
                requires_explicit_approval=False,
            )
        return MemorySyncDecision(
            direction=direction,
            state="preview_allowed",
            reason="cloud_to_local_preview_only_selected_ref",
            requires_explicit_approval=False,
        )
    if not records:
        return MemorySyncDecision(
            direction=direction,
            state="approval_required",
            reason="local_to_cloud_disabled_by_default_no_records_selected",
            requires_explicit_approval=True,
        )
    if any(record.scope == "local_private" for record in records):
        return MemorySyncDecision(
            direction=direction,
            state="blocked",
            reason="local_private_memory_never_syncs",
            requires_explicit_approval=True,
        )
    if any(record.sensitivity in {"secret_like", "local_only"} for record in records):
        return MemorySyncDecision(
            direction=direction,
            state="blocked",
            reason="secret_like_or_local_only_memory_never_syncs",
            requires_explicit_approval=True,
        )
    if any(record.sync_policy not in {"local_to_cloud_requires_approval", "shared_allowed"} for record in records):
        return MemorySyncDecision(
            direction=direction,
            state="blocked",
            reason="record_sync_policy_does_not_allow_local_to_cloud",
            requires_explicit_approval=True,
        )
    if not explicit_approval:
        return MemorySyncDecision(
            direction=direction,
            state="approval_required",
            reason="local_to_cloud_requires_explicit_approval",
            requires_explicit_approval=True,
        )
    return MemorySyncDecision(
        direction=direction,
        state="preview_allowed",
        reason="explicit_approval_dry_run_preview_only",
        requires_explicit_approval=True,
    )


def _local_ref(record: MemoryRecord) -> LocalMemoryRef:
    return LocalMemoryRef(
        memory_id=record.id,
        scope=record.scope,
        sensitivity=record.sensitivity,
        sync_policy=record.sync_policy,
        status=record.status,
    )


def _record_from_payload(payload: dict[str, object]) -> MemoryRecord | None:
    memory_id = str(payload.get("id") or payload.get("memory_id") or "").strip()
    redacted_summary = _redact_text(payload.get("redacted_summary") or payload.get("text"))
    if not memory_id or not redacted_summary:
        return None
    try:
        scope = _normalize_scope(payload.get("scope") or "local_private")
        source = _validate_member(str(payload.get("source") or "user_explicit"), VALID_SOURCES, "source")
        sensitivity = _validate_member(
            str(payload.get("sensitivity") or _default_sensitivity(scope)),
            VALID_SENSITIVITIES,
            "sensitivity",
        )
        sync_policy = _validate_member(
            str(payload.get("sync_policy") or _default_sync_policy(scope, sensitivity)),
            VALID_SYNC_POLICIES,
            "sync_policy",
        )
        status = _validate_member(str(payload.get("status") or "active"), VALID_STATUSES, "status")
    except MemoryStoreError:
        return None
    tags_raw = payload.get("tags")
    tags = tuple(_safe_tag(tag) for tag in tags_raw if _safe_tag(tag)) if isinstance(tags_raw, list) else ()
    metadata_raw = payload.get("metadata")
    metadata = _safe_metadata(metadata_raw if isinstance(metadata_raw, Mapping) else {})
    created_at = str(payload.get("created_at") or _now())
    updated_at = str(payload.get("updated_at") or created_at)
    return MemoryRecord(
        id=memory_id,
        created_at=created_at,
        updated_at=updated_at,
        scope=scope,
        source=source,  # type: ignore[arg-type]
        sensitivity=sensitivity,  # type: ignore[arg-type]
        sync_policy=sync_policy,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        redacted_summary=redacted_summary,
        source_ref=_safe_source_ref(payload.get("source_ref") or "legacy_local_store"),
        audit_reason=_redact_text(payload.get("audit_reason") or "loaded from local store")[:240],
        tags=tags,
        metadata=metadata,
    )


def _normalize_scope(scope: object) -> MemoryScope:
    raw = str(scope or "").strip().lower().replace("-", "_")
    if raw == "local":
        raw = "local_private"
    return _validate_member(raw, VALID_SCOPES, "scope")  # type: ignore[return-value]


def _validate_member(value: str, allowed: set[str], field: str) -> str:
    if value not in allowed:
        raise MemoryStoreError(f"invalid_{field}", f"{field} is invalid.")
    return value


def _default_sensitivity(scope: MemoryScope) -> MemorySensitivity:
    if scope in {"local_private", "session"}:
        return "local_only"
    if scope == "cloud_account":
        return "private"
    return "private"


def _default_sync_policy(scope: MemoryScope, sensitivity: MemorySensitivity) -> SyncPolicy:
    if sensitivity in {"local_only", "secret_like"} or scope in {"local_private", "session", "self_evolution_signal"}:
        return "never_sync"
    if scope == "cloud_account":
        return "cloud_to_local"
    if scope in {"shared_preference", "project", "procedural"}:
        return "local_to_cloud_requires_approval"
    return "never_sync"


def _redact_text(value: object) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    try:
        from src.utils.redaction import redact_text

        text = redact_text(text)
    except Exception:
        pass
    for pattern in LOCAL_PATH_PATTERNS:
        text = pattern.sub("[local_path_redacted]", text)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[secret_redacted]", text)
    return text[:1000]


def _looks_secret_like(value: object) -> bool:
    text = str(value or "")
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _looks_local_path_like(value: object) -> bool:
    text = str(value or "")
    return any(pattern.search(text) for pattern in LOCAL_PATH_PATTERNS)


def _safe_tag(value: object) -> str:
    text = "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum() or ch in {"-", "_"})
    return text[:40]


def _safe_source_ref(value: object) -> str:
    text = _redact_text(value)
    if not text:
        return "none"
    if "[local_path_redacted]" in text or "[secret_redacted]" in text:
        return "redacted-source-ref"
    return re.sub(r"[^A-Za-z0-9_.:/@-]", "_", text)[:160]


def _safe_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in metadata.items():
        safe_key = re.sub(r"[^A-Za-z0-9_-]", "_", str(key or ""))[:40]
        if not safe_key:
            continue
        safe[safe_key] = _redact_text(value)[:200]
    return safe


def _safe_signal_value(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MemoryStoreError("invalid_self_evolution_signal", f"{field} must not be empty.")
    if any(pattern.search(text) for pattern in (*LOCAL_PATH_PATTERNS, *SECRET_PATTERNS)):
        raise MemoryStoreError("unsafe_self_evolution_signal", f"{field} contains private or secret-shaped content.")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", text):
        raise MemoryStoreError("invalid_self_evolution_signal", f"{field} must be a bounded low-resolution value.")
    return text


def _write_private_text(path: Path, text: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    opener_flags = flags | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, opener_flags, 0o600)
    try:
        if hasattr(os, "fchmod"):
            try:
                os.fchmod(fd, 0o600)
            except OSError:
                pass
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            handle.write(text)
    finally:
        if fd != -1:
            os.close(fd)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
