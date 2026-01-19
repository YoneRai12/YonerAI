import os

from fastapi import FastAPI
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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount router
app.include_router(endpoints.router, prefix="/api")


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
