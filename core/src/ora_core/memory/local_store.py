from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


LOCAL_MEMORY_SCHEMA_VERSION = "yonerai-local-memory/v0.1"


class MemoryStoreError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def to_public_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class LocalMemoryRecord:
    memory_id: str
    created_at: str
    text: str
    tags: tuple[str, ...]
    redacted: bool = True

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        payload["schema_version"] = LOCAL_MEMORY_SCHEMA_VERSION
        payload["cloud_synced"] = False
        return payload


class LocalMemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def add(self, text: str, *, tags: tuple[str, ...] = ()) -> LocalMemoryRecord:
        cleaned = _redact_text(text)
        if not cleaned:
            raise MemoryStoreError("memory_text_required", "memory text must not be empty.")
        records = self.list()
        record = LocalMemoryRecord(
            memory_id=f"mem_{uuid.uuid4().hex[:24]}",
            created_at=_now(),
            text=cleaned,
            tags=tuple(_safe_tag(tag) for tag in tags if _safe_tag(tag)),
        )
        records.append(record)
        self._write(records)
        return record

    def list(self) -> list[LocalMemoryRecord]:
        if not self.path.exists():
            return []
        records: list[LocalMemoryRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            memory_id = str(payload.get("memory_id") or "").strip()
            text = _redact_text(payload.get("text"))
            if not memory_id or not text:
                continue
            tags_raw = payload.get("tags")
            tags = tuple(_safe_tag(tag) for tag in tags_raw if _safe_tag(tag)) if isinstance(tags_raw, list) else ()
            records.append(
                LocalMemoryRecord(
                    memory_id=memory_id,
                    created_at=str(payload.get("created_at") or ""),
                    text=text,
                    tags=tags,
                    redacted=True,
                )
            )
        return records

    def delete(self, memory_id: str) -> bool:
        target = str(memory_id or "").strip()
        records = self.list()
        kept = [record for record in records if record.memory_id != target]
        if len(kept) == len(records):
            return False
        self._write(kept)
        return True

    def export(self) -> dict[str, object]:
        records = [record.to_public_dict() for record in self.list()]
        return {
            "schema_version": LOCAL_MEMORY_SCHEMA_VERSION,
            "ok": True,
            "cloud_synced": False,
            "records": records,
            "count": len(records),
        }

    def _write(self, records: Sequence[LocalMemoryRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(json.dumps(record.to_public_dict(), ensure_ascii=False, sort_keys=True) for record in records)
        self.path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


def _redact_text(value: object) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    try:
        from src.utils.redaction import redact_text

        text = redact_text(text)
    except Exception:
        text = re.sub(r"\bsk-[A-Za-z0-9_-]{20,}\b", "[REDACTED]", text)
        text = re.sub(r"\bAIzaSy[A-Za-z0-9_-]{20,}\b", "[REDACTED]", text)
        text = re.sub(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}\b", "[REDACTED]", text)
    return text[:1000]


def _safe_tag(value: object) -> str:
    text = "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum() or ch in {"-", "_"})
    return text[:40]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
