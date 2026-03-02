from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.datastructures import UploadFile

from src.web import endpoints
from src.web.files_store import (
    FILES_ROOT,
    cleanup_expired_files,
    create_file_record,
    create_share_token_record,
    get_file_record,
    get_file_record_by_share_token,
    issue_share_token,
)

router = APIRouter(tags=["files"])
logger = logging.getLogger(__name__)

_ACTOR_ID_RE = re.compile(r"^[A-Za-z0-9_.:@\-]{1,128}$")
_FILENAME_RE = re.compile(r"[\\/:*?\"<>|]+")
_DEFAULT_ALLOWED_MIME = {
    "application/json",
    "application/octet-stream",
    "application/pdf",
    "application/zip",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/csv",
    "text/plain",
}
_RATE_STATE: dict[str, list[float]] = {}


class ShareRequest(BaseModel):
    ttl_sec: int | None = None


def _bool_env(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _allowed_mime_set() -> set[str]:
    raw = (os.getenv("ORA_FILES_ALLOWED_MIME") or "").strip()
    if not raw:
        return set(_DEFAULT_ALLOWED_MIME)
    out = {part.strip().lower() for part in raw.split(",") if part.strip()}
    return out or set(_DEFAULT_ALLOWED_MIME)


def _max_file_bytes() -> int:
    raw = (os.getenv("ORA_FILES_MAX_BYTES") or "").strip()
    try:
        return max(1, int(raw)) if raw else 25 * 1024 * 1024
    except Exception:
        return 25 * 1024 * 1024


def _safe_filename(name: str) -> str:
    n = (name or "download.bin").strip()
    n = _FILENAME_RE.sub("_", n)
    n = re.sub(r"\s+", "_", n)
    return n[:180] or "download.bin"


def _detect_mime(data: bytes, *, filename: str, content_type_hint: str | None = None) -> str:
    if data.startswith(b"\xFF\xD8\xFF"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1A\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"PK\x03\x04"):
        return "application/zip"

    guessed = (mimetypes.guess_type(filename)[0] or "").lower()
    if guessed:
        return guessed
    hint = (content_type_hint or "").strip().lower()
    if hint:
        return hint
    return "application/octet-stream"


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _artifact_roots() -> list[Path]:
    from src.config import TEMP_DIR

    configured = (os.getenv("ORA_FILES_ARTIFACT_ROOTS") or "").strip()
    roots: list[Path] = [Path(TEMP_DIR)]
    if configured:
        roots = [Path(p.strip()) for p in configured.split(",") if p.strip()]
    return roots


def _clamp_ttl(ttl_sec: int | None) -> int:
    if ttl_sec is None:
        return 1800
    try:
        return max(1, min(int(ttl_sec), 1800))
    except Exception:
        return 1800


def _set_download_headers(resp: FileResponse) -> None:
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    resp.headers["X-Content-Type-Options"] = "nosniff"


def _check_rate_limit(*, key: str, limit: int, window_sec: int = 60) -> None:
    now = time.time()
    bucket = _RATE_STATE.setdefault(key, [])
    cutoff = now - float(window_sec)
    kept = [t for t in bucket if t >= cutoff]
    if len(kept) >= int(limit):
        raise HTTPException(status_code=429, detail="rate_limited")
    kept.append(now)
    _RATE_STATE[key] = kept


def _resolve_actor_id(request: Request, x_ora_user_id: str | None) -> str:
    actor = (x_ora_user_id or "").strip()
    if not actor:
        actor = (request.headers.get("x-user-id") or "").strip()
    if not actor:
        actor = (request.query_params.get("user_id") or "").strip()
    if not actor:
        actor = (request.cookies.get("ora_user_id") or "").strip()
    if not actor:
        raise HTTPException(status_code=401, detail="session_required")
    if not _ACTOR_ID_RE.match(actor):
        raise HTTPException(status_code=400, detail="invalid_actor_id")
    return actor


def _share_enabled() -> bool:
    return _bool_env("ORA_FILES_SHARE_ENABLED", default=False)


@router.post("/v1/files")
async def create_file(
    request: Request,
    _: None = Depends(endpoints.require_web_api),
    x_ora_user_id: str | None = Header(None),
):
    await cleanup_expired_files()
    actor_id = _resolve_actor_id(request, x_ora_user_id)
    _check_rate_limit(key=f"create:{actor_id}", limit=30)

    content_type = (request.headers.get("content-type") or "").lower()
    source_kind = "upload"
    artifact_path = ""
    expires_in_sec: int | None = None
    upload: UploadFile | None = None
    filename_hint: str | None = None
    hint_content_type: str | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        obj = form.get("file")
        if isinstance(obj, UploadFile):
            upload = obj
        source_kind = str(form.get("source_kind") or ("upload" if upload else "artifact")).strip().lower()
        artifact_path = str(form.get("artifact_path") or "").strip()
        filename_hint = str(form.get("filename") or "").strip() or None
        hint_content_type = str(form.get("content_type") or "").strip() or None
        ttl_raw = str(form.get("expires_in_sec") or "").strip()
        if ttl_raw:
            try:
                expires_in_sec = int(ttl_raw)
            except Exception:
                raise HTTPException(status_code=400, detail="invalid_expires_in_sec")
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_request_body")
        source_kind = str(body.get("source_kind") or "artifact").strip().lower()
        artifact_path = str(body.get("artifact_path") or "").strip()
        filename_hint = str(body.get("filename") or "").strip() or None
        hint_content_type = str(body.get("content_type") or "").strip() or None
        expires_in_sec = body.get("expires_in_sec")

    if source_kind not in {"upload", "artifact"}:
        raise HTTPException(status_code=400, detail="invalid_source_kind")

    max_bytes = _max_file_bytes()
    if source_kind == "upload":
        if upload is None:
            raise HTTPException(status_code=400, detail="file_required")
        raw = await upload.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise HTTPException(status_code=413, detail="file_too_large")
        if not raw:
            raise HTTPException(status_code=400, detail="empty_file")
        file_name = _safe_filename(filename_hint or upload.filename or "upload.bin")
        detected_mime = _detect_mime(raw, filename=file_name, content_type_hint=upload.content_type or hint_content_type)
    else:
        if not artifact_path:
            raise HTTPException(status_code=400, detail="artifact_path_required")
        p = Path(artifact_path).resolve()
        if not p.exists() or (not p.is_file()):
            raise HTTPException(status_code=404, detail="artifact_not_found")
        allowed = any(_is_within(p, root) for root in _artifact_roots())
        if not allowed:
            raise HTTPException(status_code=403, detail="artifact_path_forbidden")
        raw = p.read_bytes()
        if len(raw) > max_bytes:
            raise HTTPException(status_code=413, detail="file_too_large")
        if not raw:
            raise HTTPException(status_code=400, detail="empty_file")
        file_name = _safe_filename(filename_hint or p.name)
        detected_mime = _detect_mime(raw, filename=file_name, content_type_hint=hint_content_type)

    allowed_mimes = _allowed_mime_set()
    if detected_mime.lower() not in allowed_mimes:
        raise HTTPException(status_code=415, detail="unsupported_mime")

    now_ts = int(time.time())
    expires_at = now_ts + _clamp_ttl(expires_in_sec)
    file_id = uuid.uuid4().hex
    payload_hash = hashlib.sha256(raw).hexdigest()

    target_dir = FILES_ROOT / file_id
    target_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file_name).suffix
    payload_name = f"payload{ext}" if ext else "payload.bin"
    payload_path = target_dir / payload_name
    payload_path.write_bytes(raw)

    await create_file_record(
        file_id=file_id,
        owner_id=actor_id,
        source_kind=source_kind,
        original_name=file_name,
        mime_type=detected_mime.lower(),
        size_bytes=len(raw),
        sha256_hex=payload_hash,
        storage_path=str(payload_path),
        created_at=now_ts,
        expires_at=expires_at,
    )

    return {
        "ok": True,
        "file_id": file_id,
        "content_type": detected_mime.lower(),
        "bytes": len(raw),
        "sha256": payload_hash,
        "expires_at": expires_at,
    }


@router.get("/v1/files/{file_id}/download")
async def download_file(
    file_id: str,
    request: Request,
    _: None = Depends(endpoints.require_web_api),
    x_ora_user_id: str | None = Header(None),
):
    await cleanup_expired_files()
    actor_id = _resolve_actor_id(request, x_ora_user_id)
    _check_rate_limit(key=f"download:{actor_id}", limit=120)

    rec = await get_file_record(file_id)
    if not rec:
        raise HTTPException(status_code=404, detail="file_not_found")
    if int(rec.get("expires_at") or 0) <= int(time.time()):
        await cleanup_expired_files()
        raise HTTPException(status_code=404, detail="file_expired")
    if str(rec.get("owner_id") or "") != actor_id:
        raise HTTPException(status_code=403, detail="owner_mismatch")

    fpath = Path(str(rec.get("storage_path") or ""))
    if not fpath.exists() or (not fpath.is_file()):
        raise HTTPException(status_code=404, detail="file_missing")

    resp = FileResponse(
        str(fpath),
        filename=str(rec.get("original_name") or "download.bin"),
        media_type=str(rec.get("mime_type") or "application/octet-stream"),
    )
    _set_download_headers(resp)
    return resp


@router.post("/v1/files/{file_id}/share")
async def issue_share_link(
    file_id: str,
    payload: ShareRequest,
    request: Request,
    _: None = Depends(endpoints.require_web_api),
    x_ora_user_id: str | None = Header(None),
):
    if not _share_enabled():
        raise HTTPException(status_code=404, detail="share_disabled")

    await cleanup_expired_files()
    actor_id = _resolve_actor_id(request, x_ora_user_id)
    _check_rate_limit(key=f"share:{actor_id}", limit=30)

    rec = await get_file_record(file_id)
    if not rec:
        raise HTTPException(status_code=404, detail="file_not_found")
    if str(rec.get("owner_id") or "") != actor_id:
        raise HTTPException(status_code=403, detail="owner_mismatch")

    now_ts = int(time.time())
    token, token_hash = issue_share_token()
    expires_at = now_ts + _clamp_ttl(payload.ttl_sec)
    await create_share_token_record(file_id=file_id, token_hash=token_hash, created_at=now_ts, expires_at=expires_at)

    logger.info(
        "files.share_issued file_id=%s owner=%s token_hash_prefix=%s expires_at=%s",
        file_id,
        actor_id,
        token_hash[:12],
        expires_at,
    )

    return {
        "ok": True,
        "share_token": token,
        "expires_at": expires_at,
        "path": f"/s/{token}",
    }


@router.get("/s/{share_token}")
async def shared_download(share_token: str, request: Request):
    if not _share_enabled():
        raise HTTPException(status_code=404, detail="share_disabled")

    await cleanup_expired_files()
    client_key = ((request.client.host if request.client else "") or "unknown").strip()
    _check_rate_limit(key=f"share_dl:{client_key}", limit=180)

    rec = await get_file_record_by_share_token(share_token)
    if not rec:
        raise HTTPException(status_code=404, detail="share_not_found")
    if int(rec.get("expires_at") or 0) <= int(time.time()):
        await cleanup_expired_files()
        raise HTTPException(status_code=404, detail="file_expired")

    fpath = Path(str(rec.get("storage_path") or ""))
    if not fpath.exists() or (not fpath.is_file()):
        raise HTTPException(status_code=404, detail="file_missing")

    resp = FileResponse(
        str(fpath),
        filename=str(rec.get("original_name") or "download.bin"),
        media_type=str(rec.get("mime_type") or "application/octet-stream"),
    )
    _set_download_headers(resp)
    # Explicit token redaction in any app-level log line we control.
    token_hash_prefix = hashlib.sha256(share_token.encode("utf-8")).hexdigest()[:12]
    logger.info("files.shared_download token_hash_prefix=%s status=200", token_hash_prefix)
    return resp
