from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from ora_core.database.session import get_db
from ora_core.database.repo import Repository

router = APIRouter()

class LinkCodeRequest(BaseModel):
    provider: str
    provider_id: str

class LinkCodeResponse(BaseModel):
    code: str
    expires_at: str

class AccountLinkRequest(BaseModel):
    current_user_id: str # The Web user's internal UUID
    code: str

@router.post("/link-code", response_model=LinkCodeResponse)
async def create_link_code(req: LinkCodeRequest, fast_req: Request, db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    user = await repo.get_or_create_user(req.provider, req.provider_id)
    
    import random
    import string
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    # Pass IP for issuance audit
    request = await repo.create_link_request(user.id, code, ip=fast_req.client.host)
    await db.commit()
    
    return LinkCodeResponse(
        code=request.code,
        expires_at=request.expires_at.isoformat()
    )

@router.post("/link")
async def link_account(req: AccountLinkRequest, fast_req: Request, db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    ip = fast_req.client.host
    
    # 1. Check Lockout for the current web user
    user = await repo.get_user(req.current_user_id)
    if not user:
         raise HTTPException(status_code=404, detail="User not found")
         
    if user.link_locked_until and user.link_locked_until > datetime.utcnow():
        diff = user.link_locked_until - datetime.utcnow()
        raise HTTPException(
            status_code=429, 
            detail=f"Too many failed attempts. Try again in {int(diff.total_seconds() / 60)} minutes."
        )

    # 2. Verify Code
    link_req = await repo.get_link_request(req.code)
    
    if not link_req:
        await repo.update_user_link_failure(req.current_user_id, ip=ip)
        raise HTTPException(status_code=400, detail="Invalid or expired link code")
    
    # 3. Success -> Merge
    try:
        await repo.link_identities(req.current_user_id, link_req.user_id, ip=ip)
        await repo.reset_user_link_failure(link_req.user_id) # Reset for the now-merged user
        await repo.delete_link_request(req.code)
        await db.commit()
        return {"message": "Account linked successfully", "target_user_id": link_req.user_id}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
