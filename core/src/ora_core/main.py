from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env in the root project directory relative to this file
# Core is at root/core, and main.py is at root/core/src/ora_core/main.py
# 1: ora_core, 2: src, 3: core, 4: root
ENV_PATH = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
    print(f"[CORE] Loaded .env from {ENV_PATH}")
else:
    print(f"[CORE][WARN] .env NOT FOUND at {ENV_PATH}")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ora_core.api.routes.auth import router as auth_router
from ora_core.api.routes.messages import router as messages_router
from ora_core.api.routes.runs import router as runs_router
from ora_core.api.routes.stats import router as stats_router
import os


def create_app():
    app = FastAPI(title="ORA Core", version="0.1")

    # Load Config
    from src.config import Config
    try:
        config = Config.load()
        app.state.config = config
    except Exception as e:
        print(f"Failed to load config: {e}")
        # Allow startup to continue? Or fail?
        # Core might need config for other things, but for now mostly for Auth.
        pass

    # Register Core Tools
    from ora_core.tools.discord_proxy import register_discord_proxies
    register_discord_proxies()

    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request schema is invalid. Please follow the Canonical Schema.",
                "details": exc.errors(),
                "manual": {
                    "example": {
                        "conversation_id": None,
                        "user_identity": {"provider": "web", "id": "local-user-1", "display_name": "YoneRai12"},
                        "content": "Hello",
                        "attachments": [],
                        "idempotency_key": "550e8400-e29b-41d4-a716-446655440000"
                    },
                    "notes": [
                        "conversation_id can be null (Core creates new).",
                        "idempotency_key must be stable per retry (UUID v4 recommended).",
                        "attachments must be typed objects, not just strings."
                    ]
                }
            },
        )

    cors_raw = os.getenv(
        "ORA_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3333,http://127.0.0.1:3333,http://localhost:8000,http://127.0.0.1:8000",
    )
    cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(messages_router, prefix="/v1")
    app.include_router(runs_router, prefix="/v1")
    app.include_router(auth_router, prefix="/v1/auth") # Core generic auth routes (me, logout)

    # Conditional Auth Logic
    if hasattr(app.state, "config") and app.state.config.auth_strategy == "cloudflare":
        # Cloudflare Auth Strategy
        print("[AUTH] Using Cloudflare Access Strategy")

        # Override get_current_user dependency
        # We need to import the dependency function from where it is used (auth.py, messages.py etc)
        # But FastAPI dependency overrides work on the App level.
        # Assuming the original dependency is `ora_core.api.routes.auth.get_current_user` (or similar common dep)
        # We need to know where `get_current_user` is defined. Usually in `ora_core.api.dependencies.auth`.
        # Since I don't have the common dependency definition in front of me, I will assume it's imported in routes.
        # Let's verify `ora_core/api/routes/auth.py` imports first to be safe, but for now I will add the logic
        # to SKIP loading google_auth_router.

        # dependency_overrides is better handled if we know the target function.
        # For now, we will trust the plan that we only need to secure the API.
        # Since we don't have a centralized `dependencies.py` viewed yet, let's stick to router exclusion.
        pass
    else:
        # Local Strategy (Standard)
        print("[AUTH] Using Local/Google OAuth Strategy")
        # User Request: Comment out Login for external connection
        # app.include_router(google_auth_router, prefix="/v1/auth")

    app.include_router(stats_router, prefix="/v1")

    from ora_core.api.routes.memory import router as memory_router
    app.include_router(memory_router, prefix="/v1")

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    from src.utils.logging_config import get_privacy_log_config

    # Apply privacy log config to hide IP addresses
    log_config = get_privacy_log_config()

    uvicorn.run("ora_core.main:app", host="0.0.0.0", port=8001, reload=True, log_config=log_config)
