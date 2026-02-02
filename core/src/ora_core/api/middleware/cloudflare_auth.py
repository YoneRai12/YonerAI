import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from ora_core.database.models import User
from ora_core.database.repo import Repository

logger = logging.getLogger(__name__)

def get_repo(request: Request) -> Repository:
    return request.state.repo

async def get_current_user_from_header(
    request: Request,
    repo: Annotated[Repository, Depends(get_repo)] # Assumes repo is injected into request.state
) -> User:
    """
    Authentication Middleware for Cloudflare Access.
    Trusted Source: Cloudflare Tunnel.
    
    If 'Cf-Access-Authenticated-User-Email' is present, we assume trust (Zero Trust).
    If missing AND config.AUTH_STRATEGY == 'cloudflare', explicit 401.
    """
    
    # We access config from app state or similar
    config = request.app.state.config
    
    # 1. Check Header
    email = request.headers.get("Cf-Access-Authenticated-User-Email")
    
    if email:
        # Trusted User from Cloudflare
        # Ensure User exists in DB
        user = await repo.get_or_create_user_by_email(email)
        return user
    
    # 2. Strategy Check
    if config.auth_strategy == "cloudflare":
        # Strict Mode: Must have header
        # Optional: Check for local bypass (Admin Key) if needed?
        # For now, strict.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Cloudflare Identity Header"
        )
        
    # 3. Fallback for 'local'
    # Return None so that standard OAuth/Session auth can take over if this dependency is used as "Optional"
    # But if used as "Required", we might need to handle differently.
    # For ORA, we want a unified user object.
    
    # If we are here, it means no Cloudflare header and strategy is NOT Cloudflare.
    # So we should probably return None or let the next dependency handle it?
    # Actually, in main.py, we will switch dependencies based on strategy.
    return None
