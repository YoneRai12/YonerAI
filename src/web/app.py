import os
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, Query, Header
from fastapi.responses import HTMLResponse

from src.config import resolve_bot_db_path
from src.storage import Store
from src.web import endpoints
from src.utils.temp_downloads import cleanup_expired_downloads
from src.web.files_store import cleanup_expired_files

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

# Files Router (MVP: local disk + sqlite metadata)
from src.web.routers import files
app.include_router(files.router)

# Mount Static Files
from fastapi.staticfiles import StaticFiles
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

PUBLIC_PAGES: dict[str, str] = {
    "about": "about.html",
    "architecture": "architecture.html",
    "clients": "clients.html",
    "contact": "contact.html",
    "desktop-discord": "desktop-discord.html",
    "developers": "developers.html",
    "linked": "linked.html",
    "platform-preview": "platform-preview.html",
    "privacy": "privacy.html",
    "relay-model": "relay-model.html",
    "roadmap": "roadmap.html",
    "security": "security.html",
    "security-model": "security-model.html",
    "terms": "terms.html",
    "trust-safety": "trust-safety.html",
    "web-mobile": "web-mobile.html",
}


def _normalize_lang(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw.startswith("ja") or raw == "jp":
        return "ja"
    return "en"


def _lang_prefix(lang: str) -> str:
    return "jp" if _normalize_lang(lang) == "ja" else "en"


def _detect_preferred_lang(request: Request) -> str:
    from_cookie = _normalize_lang(request.cookies.get("yonerai_lang"))
    if request.cookies.get("yonerai_lang"):
        return from_cookie
    accept = (request.headers.get("accept-language") or "").lower()
    if "ja" in accept:
        return "ja"
    return "en"


def _serve_public_page(filename: str) -> FileResponse:
    path = os.path.join(static_dir, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"{filename} is missing.")
    response = FileResponse(path)
    if filename in {"chat.html", "login.html"}:
        response.headers["Cache-Control"] = "no-store"
    return response


def _register_public_page_routes() -> None:
    for slug, filename in PUBLIC_PAGES.items():
        safe_name = slug.replace("/", "_")

        async def _redirect(request: Request, _slug: str = slug):
            lang = _detect_preferred_lang(request)
            qs = request.url.query
            target = f"/{_lang_prefix(lang)}/{_slug}"
            if qs:
                target = f"{target}?{qs}"
            return RedirectResponse(url=target, status_code=307)

        async def _serve_jp(_filename: str = filename):
            return _serve_public_page(_filename)

        async def _serve_en(_filename: str = filename):
            return _serve_public_page(_filename)

        if slug in {"terms", "privacy", "trust-safety"}:
            async def _serve_root(_filename: str = filename):
                return _serve_public_page(_filename)

            app.add_api_route(f"/{slug}", _serve_root, methods=["GET"], name=f"{safe_name}_root")
            app.add_api_route(f"/{slug}/", _serve_root, methods=["GET"], name=f"{safe_name}_root_slash")
        else:
            app.add_api_route(f"/{slug}", _redirect, methods=["GET"], name=f"redirect_{safe_name}")
            app.add_api_route(f"/{slug}/", _redirect, methods=["GET"], name=f"redirect_{safe_name}_slash")

        app.add_api_route(f"/jp/{slug}", _serve_jp, methods=["GET"], name=f"{safe_name}_jp")
        app.add_api_route(f"/jp/{slug}/", _serve_jp, methods=["GET"], name=f"{safe_name}_jp_slash")
        app.add_api_route(f"/en/{slug}", _serve_en, methods=["GET"], name=f"{safe_name}_en")
        app.add_api_route(f"/en/{slug}/", _serve_en, methods=["GET"], name=f"{safe_name}_en_slash")


@app.get("/")
async def read_index(request: Request):
    return _serve_public_page("index.html")


@app.get("/jp")
@app.get("/jp/")
async def read_index_jp():
    return _serve_public_page("index.html")


@app.get("/en")
@app.get("/en/")
async def read_index_en():
    return _serve_public_page("index.html")


@app.get("/chat")
@app.get("/chat/")
async def read_chat_redirect(request: Request):
    lang = _detect_preferred_lang(request)
    return RedirectResponse(url=f"/{_lang_prefix(lang)}/chat", status_code=307)


@app.get("/jp/chat")
@app.get("/jp/chat/")
async def read_chat_page_jp():
    return _serve_public_page("chat.html")


@app.get("/en/chat")
@app.get("/en/chat/")
async def read_chat_page_en():
    return _serve_public_page("chat.html")


@app.get("/auth/login")
async def auth_login(
    request: Request,
    return_to: str | None = Query(None, alias="returnTo"),
    next: str | None = Query(None),
):
    target = endpoints._normalize_next_path(return_to or next or "/chat")
    try:
        await endpoints.require_user_session(request)
        return RedirectResponse(url=target, status_code=302)
    except HTTPException:
        return _serve_public_page("login.html")


_register_public_page_routes()


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
    - Otherwise allow only intentional local/dev loopback bypass.
    """
    # Usability: allow local/dev loopback access to the setup page even when ORA_WEB_API_TOKEN is set.
    # The API endpoints still enforce require_web_api.
    if not endpoints.can_bypass_web_api_auth(request):
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
                    await cleanup_expired_files()
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
