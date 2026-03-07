import logging
import os
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from ora_core.database.models import User
from ora_core.database.repo import Repository

try:
    import jwt
    from jwt import InvalidTokenError, PyJWKClient
except Exception:  # pragma: no cover - optional dependency is validated at runtime
    jwt = None
    InvalidTokenError = Exception
    PyJWKClient = None

logger = logging.getLogger(__name__)
_jwks_clients: dict[str, "PyJWKClient"] = {}

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
    
    if config.auth_strategy != "cloudflare":
        return None

    # 1. Check required Cloudflare Access headers
    email = request.headers.get("Cf-Access-Authenticated-User-Email")
    jwt_assertion = request.headers.get("Cf-Access-Jwt-Assertion")

    if not email or not jwt_assertion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Cloudflare Access headers"
        )

    if jwt is None or PyJWKClient is None:
        logger.error("cloudflare auth requested but PyJWT is not installed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloudflare auth is not available on this server"
        )

    team_domain = os.getenv("CF_ACCESS_TEAM_DOMAIN", "").strip()
    audience = os.getenv("CF_ACCESS_AUDIENCE", "").strip()

    if not team_domain or not audience:
        logger.error("cloudflare auth misconfigured: CF_ACCESS_TEAM_DOMAIN / CF_ACCESS_AUDIENCE")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloudflare auth is not configured"
        )

    jwks_url = f"https://{team_domain}/cdn-cgi/access/certs"
    jwks_client = _jwks_clients.get(jwks_url)
    if jwks_client is None:
        jwks_client = PyJWKClient(jwks_url)
        _jwks_clients[jwks_url] = jwks_client

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(jwt_assertion)
        claims = jwt.decode(
            jwt_assertion,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            options={"require": ["exp", "iat", "aud"]},
        )
    except InvalidTokenError:
        logger.warning("cloudflare auth rejected invalid jwt assertion")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Cloudflare Access token"
        )

    token_email = claims.get("email")
    if not token_email or token_email.lower() != email.lower():
        logger.warning("cloudflare auth email/header mismatch")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cloudflare identity mismatch"
        )

    return await repo.get_or_create_user_by_email(token_email)
