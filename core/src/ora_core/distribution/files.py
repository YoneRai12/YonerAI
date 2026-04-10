from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class FileContractViolation(RuntimeError):
    pass


class FileRef(BaseModel):
    file_id: str
    name: str
    media_type: str
    size_bytes: int
    sha256: str


def assert_no_raw_file_bytes(payload: Any, *, path: str = "result") -> None:
    if isinstance(payload, (bytes, bytearray, memoryview)):
        raise FileContractViolation(f"Run payload contains raw bytes at {path}.")
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert_no_raw_file_bytes(value, path=f"{path}.{key}")
        return
    if isinstance(payload, list):
        for idx, value in enumerate(payload):
            assert_no_raw_file_bytes(value, path=f"{path}[{idx}]")


def _guess_media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


async def normalize_tool_result_for_run(
    repo,
    *,
    owner_user_id: str,
    run_id: str,
    tool_call_id: str,
    result: dict[str, Any],
) -> tuple[dict[str, Any], str | None, list[dict[str, Any]]]:
    assert_no_raw_file_bytes(result)

    if not isinstance(result, dict):
        raise FileContractViolation("Tool result must be a dict when Distribution Node MVP is enabled.")

    file_refs: list[dict[str, Any]] = []
    artifact_ref = result.get("artifact_ref")
    if artifact_ref is None:
        return result, None, file_refs

    artifact_text = str(artifact_ref).strip()
    if not artifact_text:
        raise FileContractViolation("artifact_ref cannot be empty.")
    if artifact_text.startswith("fileref:"):
        return result, artifact_text, file_refs

    artifact_path = Path(artifact_text)
    if not artifact_path.exists() or not artifact_path.is_file():
        raise FileContractViolation("artifact_ref must resolve to a local file before it can be exposed as a file ref.")

    created = await repo.create_distribution_file(
        owner_user_id=owner_user_id,
        run_id=run_id,
        tool_call_id=tool_call_id,
        storage_path=str(artifact_path.resolve()),
        display_name=artifact_path.name,
        media_type=_guess_media_type(artifact_path),
    )
    file_ref = FileRef(
        file_id=created.id,
        name=created.display_name,
        media_type=created.media_type,
        size_bytes=created.size_bytes,
        sha256=created.sha256,
    )
    file_refs.append(file_ref.model_dump())
    normalized = dict(result)
    normalized["artifact_ref"] = f"fileref:{created.id}"
    normalized["file_refs"] = file_refs
    return normalized, normalized["artifact_ref"], file_refs
