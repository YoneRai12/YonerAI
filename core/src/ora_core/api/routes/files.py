from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ora_core.api.dependencies.auth import get_current_user
from ora_core.api.schemas.messages import UserIdentity
from ora_core.database.models import User
from ora_core.database.repo import Repository
from ora_core.database.session import get_db
from ora_core.distribution.runtime import get_current_runtime

router = APIRouter()


class FileDownloadRequest(BaseModel):
    user_identity: Optional[UserIdentity] = None
    ttl_seconds: int = Field(default=300, ge=30, le=600)


@router.post("/files/{file_id}/download-url")
async def issue_distribution_file_download_url(
    file_id: str,
    body: FileDownloadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authenticated_user: Optional[User] = Depends(get_current_user),
):
    runtime = get_current_runtime()
    runtime.require_capability("files.issue_download_ticket")

    repo = Repository(db)
    file_record = await repo.get_distribution_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="Not Found")

    if runtime.enabled and not authenticated_user:
        raise HTTPException(status_code=401, detail="Authenticated owner is required.")

    if authenticated_user:
        user = authenticated_user
    else:
        if not body.user_identity:
            raise HTTPException(status_code=400, detail="user_identity is required.")
        user = await repo.get_or_create_user(
            provider=body.user_identity.provider,
            provider_id=body.user_identity.id,
            display_name=body.user_identity.display_name,
        )

    if file_record.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Not Found")

    expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=body.ttl_seconds)
    ticket = await repo.create_distribution_file_ticket(
        file_id=file_record.id,
        owner_user_id=user.id,
        expires_at=expires_at,
    )
    await repo.create_distribution_file_audit(
        file_id=file_record.id,
        owner_user_id=user.id,
        action="issue_download_ticket",
        ticket_id=ticket.id,
        remote_address=request.client.host if request.client else None,
    )

    download_url = str(request.url_for("download_distribution_file", ticket=ticket.id))
    return {
        "file_ref": {
            "file_id": file_record.id,
            "name": file_record.display_name,
            "media_type": file_record.media_type,
            "size_bytes": file_record.size_bytes,
            "sha256": file_record.sha256,
        },
        "download_url": download_url,
        "expires_at": expires_at.replace(microsecond=0).isoformat() + "Z",
    }


@router.get("/files/download/{ticket}", name="download_distribution_file")
async def download_distribution_file(
    ticket: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    runtime = get_current_runtime()
    runtime.require_capability("files.download")

    repo = Repository(db)
    ticket_record = await repo.consume_distribution_file_ticket(ticket)
    if not ticket_record:
        raise HTTPException(status_code=404, detail="Not Found")

    file_record = await repo.get_distribution_file(ticket_record.file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="Not Found")

    await repo.create_distribution_file_audit(
        file_id=file_record.id,
        owner_user_id=ticket_record.owner_user_id,
        action="download",
        ticket_id=ticket_record.id,
        remote_address=request.client.host if request.client else None,
    )

    file_path = Path(file_record.storage_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Not Found")

    response = FileResponse(
        path=file_path,
        media_type=file_record.media_type,
        filename=file_record.display_name,
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
