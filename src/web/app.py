import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from src.storage import Store
from src.web import endpoints

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


@app.on_event("startup")
async def on_startup() -> None:
    global store
    store = Store(os.getenv("ORA_BOT_DB", "ora_bot.db"))
    await store.init()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global store
    # Store might not need explicit disconnect if using aiofiles/sqlite3 directly per request,
    # but good to have the hook.
    store = None
