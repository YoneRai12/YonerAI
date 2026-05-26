from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol


RUN_LEDGER_SCHEMA_VERSION = "yonerai-run-ledger/v1"
RUN_LEDGER_PATH_ENV = "YONERAI_RUN_LEDGER_PATH"
RunId = str
ExecutionStatus = Literal["created", "running", "completed", "failed", "blocked"]


_LOCAL_PATH_PATTERNS = (
    re.compile(r"(?:(?<=^)|(?<=[\s\"'(<]))[A-Za-z]:[\\/][^\s\"'<>|]+", re.IGNORECASE),
    re.compile(r"(?:(?<=^)|(?<=[\s\"'(<]))/(?:home|users|root|etc|var|tmp)/[^\s\"'<>|]+", re.IGNORECASE),
)
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|discord[_-]?token|private[_-]?key|client[_-]?secret)\s*(?:=|:)\s*[^\s,;]+",
        re.IGNORECASE,
    ),
    re.compile(r"authorization\s*:\s*bearer\s+[^\s,;]+", re.IGNORECASE),
    re.compile(r"authorization\s+bearer\s+[^\s,;]+", re.IGNORECASE),
)


@dataclass(frozen=True)
class ExecutionEvent:
    event_id: str
    run_id: RunId
    created_at: str
    name: str
    status: str
    summary: str

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ExecutionRun:
    run_id: RunId
    created_at: str
    updated_at: str
    task_summary: str
    classification: dict[str, object]
    route_decision: dict[str, object]
    provider_decision: dict[str, object]
    status: ExecutionStatus
    events: list[ExecutionEvent] = field(default_factory=list)
    approval_required: bool = False
    disabled_reason: str | None = None
    error_summary: str | None = None
    result_summary: str | None = None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": RUN_LEDGER_SCHEMA_VERSION,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "task_summary": self.task_summary,
            "classification": dict(self.classification),
            "route_decision": dict(self.route_decision),
            "provider_decision": dict(self.provider_decision),
            "status": self.status,
            "events": [event.to_public_dict() for event in self.events],
            "approval_required": self.approval_required,
            "disabled_reason": self.disabled_reason,
            "error_summary": self.error_summary,
            "result_summary": self.result_summary,
            "persistence": {
                "raw_prompt_persisted": False,
                "raw_completion_persisted": False,
                "provider_key_persisted": False,
                "memory_persisted": False,
            },
        }

    @classmethod
    def from_public_dict(cls, payload: dict[str, object]) -> "ExecutionRun":
        events = [
            ExecutionEvent(
                event_id=str(event.get("event_id") or ""),
                run_id=str(event.get("run_id") or payload.get("run_id") or ""),
                created_at=str(event.get("created_at") or ""),
                name=str(event.get("name") or ""),
                status=str(event.get("status") or ""),
                summary=str(event.get("summary") or ""),
            )
            for event in payload.get("events", [])
            if isinstance(event, dict)
        ]
        status = str(payload.get("status") or "failed")
        if status not in {"created", "running", "completed", "failed", "blocked"}:
            status = "failed"
        return cls(
            run_id=str(payload.get("run_id") or ""),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            task_summary=str(payload.get("task_summary") or ""),
            classification=dict(payload.get("classification") or {}),
            route_decision=dict(payload.get("route_decision") or {}),
            provider_decision=dict(payload.get("provider_decision") or {}),
            status=status,  # type: ignore[arg-type]
            events=events,
            approval_required=bool(payload.get("approval_required")),
            disabled_reason=_optional_text(payload.get("disabled_reason")),
            error_summary=_optional_text(payload.get("error_summary")),
            result_summary=_optional_text(payload.get("result_summary")),
        )


class RunLedger(Protocol):
    def create_run(
        self,
        *,
        task_text: str,
        classification: dict[str, object],
        route_decision: dict[str, object],
        provider_decision: dict[str, object],
        approval_required: bool,
        disabled_reason: str | None = None,
    ) -> ExecutionRun:
        ...

    def append_event(self, run_id: RunId, name: str, status: str, summary: str) -> ExecutionRun:
        ...

    def complete_run(self, run_id: RunId, *, result_summary: str | None = None) -> ExecutionRun:
        ...

    def fail_run(self, run_id: RunId, *, error_summary: str, blocked: bool = False) -> ExecutionRun:
        ...

    def list_runs(self, *, limit: int = 20) -> list[ExecutionRun]:
        ...

    def get_run(self, run_id: RunId) -> ExecutionRun | None:
        ...


class InMemoryRunLedger:
    def __init__(self) -> None:
        self._runs: dict[RunId, ExecutionRun] = {}

    def create_run(
        self,
        *,
        task_text: str,
        classification: dict[str, object],
        route_decision: dict[str, object],
        provider_decision: dict[str, object],
        approval_required: bool,
        disabled_reason: str | None = None,
    ) -> ExecutionRun:
        now = _now()
        run = ExecutionRun(
            run_id=new_run_id(),
            created_at=now,
            updated_at=now,
            task_summary=safe_summary(task_text),
            classification=_safe_json_dict(classification),
            route_decision=_safe_json_dict(route_decision),
            provider_decision=_safe_json_dict(provider_decision),
            status="created",
            approval_required=approval_required,
            disabled_reason=safe_summary(disabled_reason) if disabled_reason else None,
        )
        self._runs[run.run_id] = run
        return run

    def append_event(self, run_id: RunId, name: str, status: str, summary: str) -> ExecutionRun:
        run = self._require_run(run_id)
        run.events.append(
            ExecutionEvent(
                event_id=f"evt_{len(run.events) + 1:04d}",
                run_id=run.run_id,
                created_at=_now(),
                name=safe_summary(name, max_chars=80),
                status=safe_summary(status, max_chars=80),
                summary=safe_summary(summary),
            )
        )
        run.updated_at = _now()
        if run.status == "created":
            run.status = "running"
        self._persist()
        return run

    def complete_run(self, run_id: RunId, *, result_summary: str | None = None) -> ExecutionRun:
        run = self._require_run(run_id)
        run.status = "completed"
        run.updated_at = _now()
        run.result_summary = safe_summary(result_summary) if result_summary else None
        self._persist()
        return run

    def fail_run(self, run_id: RunId, *, error_summary: str, blocked: bool = False) -> ExecutionRun:
        run = self._require_run(run_id)
        run.status = "blocked" if blocked else "failed"
        run.updated_at = _now()
        run.error_summary = safe_summary(error_summary)
        self._persist()
        return run

    def list_runs(self, *, limit: int = 20) -> list[ExecutionRun]:
        ordered = sorted(self._runs.values(), key=lambda run: run.created_at, reverse=True)
        return ordered[: max(0, limit)]

    def get_run(self, run_id: RunId) -> ExecutionRun | None:
        return self._runs.get(run_id)

    def _require_run(self, run_id: RunId) -> ExecutionRun:
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(f"unknown run_id: {safe_summary(run_id, max_chars=80)}")
        return run

    def _persist(self) -> None:
        return None


class FileRunLedger(InMemoryRunLedger):
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        super().__init__()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            run = ExecutionRun.from_public_dict(payload)
            if run.run_id:
                self._runs[run.run_id] = run

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = "\n".join(json.dumps(run.to_public_dict(), ensure_ascii=False, sort_keys=True) for run in self.list_runs(limit=1000))
        _write_private_text(self.path, payload + ("\n" if payload else ""))


def _write_private_text(path: Path, text: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    opener_flags = flags | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, opener_flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            handle.write(text)
    finally:
        if fd != -1:
            os.close(fd)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def build_run_ledger_from_env(path: str | None = None) -> RunLedger:
    ledger_path = (path or os.getenv(RUN_LEDGER_PATH_ENV) or "").strip()
    if ledger_path:
        return FileRunLedger(ledger_path)
    return InMemoryRunLedger()


def new_run_id() -> RunId:
    return f"run_{uuid.uuid4().hex[:24]}"


def safe_summary(value: object, *, max_chars: int = 500) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    from .legacy_text import normalize_legacy_generated_text

    text = normalize_legacy_generated_text(text)
    try:
        from src.utils.redaction import redact_text

        text = redact_text(text)
    except Exception:
        pass
    for pattern in _LOCAL_PATH_PATTERNS:
        text = pattern.sub("[local_path_redacted]", text)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[secret_redacted]", text)
    return text[:max_chars]


def _safe_json_dict(value: dict[str, object]) -> dict[str, object]:
    try:
        from src.utils.redaction import redact_json

        redacted = redact_json(value)
    except Exception:
        redacted = value
    if not isinstance(redacted, dict):
        return {}
    return redacted


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = safe_summary(value)
    return text or None
