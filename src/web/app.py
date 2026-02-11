import os
import asyncio

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, Query, Header
from fastapi.responses import HTMLResponse

from src.config import resolve_bot_db_path
from src.storage import Store
from src.web import endpoints
from src.utils.temp_downloads import cleanup_expired_downloads

store: Store | None = None


def get_store() -> Store:
    assert store is not None, "Store is not initialized"
    return store


app = FastAPI(
    title="ORA Web API",
    version="0.1.0",
)

# CORS origins (comma-separated env)
cors_raw = os.getenv(
    "ORA_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3333,http://127.0.0.1:3333,http://localhost:8000,http://127.0.0.1:8000",
)
cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount router
app.include_router(endpoints.router, prefix="/api")

# Mount Browser Router
from src.web.routers import browser
app.include_router(browser.router, prefix="/api/browser")

# Temporary Download Router
from src.web.routers import downloads
app.include_router(downloads.router)

# Mount Static Files
from fastapi.staticfiles import StaticFiles
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def read_index():
    """Serve the Remote Loader at the root."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"detail": "ORA Web API is running, but index.html is missing."}


@app.get("/setup", response_class=HTMLResponse)
async def setup_ui(
    request: Request,
    x_ora_token: str | None = Header(None),
    authorization: str | None = Header(None),
    token: str | None = Query(None),
):
    """
    Local setup page.

    Guarded by the same policy as /api/*:
    - If ORA_WEB_API_TOKEN is set, require it.
    - Otherwise allow loopback.
    """
    # Usability: allow loopback access to the setup page even when ORA_WEB_API_TOKEN is set.
    # The API endpoints still enforce require_web_api.
    if not endpoints.is_loopback_request(request):
        await endpoints.require_web_api(
            request=request,
            x_ora_token=x_ora_token,
            authorization=authorization,
            token=token,
        )
    setup_path = os.path.join(static_dir, "setup.html")
    if os.path.exists(setup_path):
        return FileResponse(setup_path)
    return HTMLResponse("<h1>setup.html missing</h1>", status_code=404)


@app.on_event("startup")
async def on_startup() -> None:
    global store
    store = Store(resolve_bot_db_path())
    await store.init()

    # Background cleanup loop (optional).
    # In tests, disable to avoid flakiness with event-loop teardown.
    disable_bg = (os.getenv("ORA_DISABLE_WEB_BG_TASKS") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not disable_bg:
        # Ensure expired temporary downloads are eventually deleted even if nobody hits /download/* routes.
        async def _cleanup_loop() -> None:
            while True:
                try:
                    cleanup_expired_downloads()
                except Exception:
                    pass
                try:
                    if store:
                        await store.prune_audit_tables()
                except Exception:
                    pass
                await asyncio.sleep(600)  # 10 minutes

        app.state._temp_download_cleanup_task = asyncio.create_task(_cleanup_loop())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global store
    # Store might not need explicit disconnect if using aiofiles/sqlite3 directly per request,
    # but good to have the hook.
    store = None
    task = getattr(app.state, "_temp_download_cleanup_task", None)
    if task:
        task.cancel()
