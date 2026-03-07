import hmac
import os
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from ora_core.database.models import User
from ora_core.database.repo import Repository
from ora_core.database.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession


async def get_repo(db: AsyncSession = Depends(get_db)) -> Repository:
    return Repository(db)

async def get_current_user(
    request: Request,
    repo: Repository = Depends(get_repo)
) -> Optional[User]:
    """
    Default Auth Dependency.
    
    In 'local' mode: returns None (letting the route logic handle manual identity from body).
    In 'cloudflare' mode: Checks headers (via overridden logic or direct check).
    """
    # This function is intended to be OVERRIDDEN in main.py if Cloudflare is active.
    # Or we can put the logic here dynamically.
    
    if hasattr(request.app.state, "config"):
        config = request.app.state.config
        if config.auth_strategy == "cloudflare":
            from ora_core.api.middleware.cloudflare_auth import get_current_user_from_header
            return await get_current_user_from_header(request, repo)
            
    return None


def require_core_access(
    request: Request,
    authorization: str | None = Header(default=None),
    x_ora_core_token: str | None = Header(default=None),
) -> None:
    """
    Gate core APIs to trusted callers.

    - If ORA_CORE_API_TOKEN is set, clients must send it via
      `Authorization: Bearer <token>` or `X-ORA-Core-Token`.
    - If the token is not set, only loopback callers are allowed.
    """
    configured_token = (os.getenv("ORA_CORE_API_TOKEN") or "").strip()

    if configured_token:
        bearer_token = None
        if authorization and authorization.lower().startswith("bearer "):
            bearer_token = authorization.split(" ", 1)[1].strip()
        presented_token = x_ora_core_token or bearer_token

        if not presented_token or not hmac.compare_digest(presented_token, configured_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        return

    # Secure fallback when no API token is configured.
    client_host = request.client.host if request.client else None
    if client_host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Core API access is restricted to localhost unless ORA_CORE_API_TOKEN is configured.",
        )
