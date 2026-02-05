from fastapi import APIRouter, HTTPException, Body, Depends, Header
from fastapi.responses import StreamingResponse, Response, JSONResponse
from pydantic import BaseModel
from typing import Optional, Any, Dict, List
import io
import asyncio
import json
import logging
import os
import traceback
import uuid
from datetime import datetime, timezone

from src.utils.browser import browser_manager

router = APIRouter(tags=["browser"])
logger = logging.getLogger(__name__)


def _write_browser_api_error(endpoint: str, exc: Exception) -> str:
    """Persist browser API errors to a dedicated log file for post-mortem debugging."""
    error_id = uuid.uuid4().hex[:10]
    os.makedirs("logs", exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    payload = (
        f"[{ts}] endpoint={endpoint} error_id={error_id}\n"
        f"type={type(exc).__name__}\n"
        f"message={exc}\n"
        f"{traceback.format_exc()}\n"
    )
    with open(os.path.join("logs", "browser_api.log"), "a", encoding="utf-8", errors="ignore") as f:
        f.write(payload)
    return error_id

async def verify_token(x_auth_token: Optional[str] = Header(None)):
    # Do not call Config.load() here; browser API may run standalone without Discord env vars.
    # Token can be provided via env only.
    browser_token = (
        os.getenv("BROWSER_REMOTE_TOKEN")
        or os.getenv("ORA_BROWSER_REMOTE_TOKEN")
        or ""
    ).strip()
    if not browser_token:
        return

    if x_auth_token != browser_token:
        raise HTTPException(status_code=401, detail="Invalid Remote Control Token")

class ActionRequest(BaseModel):
    action: Dict[str, Any]

class ModeRequest(BaseModel):
    headless: bool
    scope: Optional[str] = "session"
    domain: Optional[str] = ""
    apply: Optional[bool] = True

@router.post("/launch", dependencies=[Depends(verify_token)])
async def launch_browser():
    """Starts the browser session."""
    try:
        await browser_manager.start()
        return {"status": "started", "headless": browser_manager.headless}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/action", dependencies=[Depends(verify_token)])
async def handle_action(req: ActionRequest = Body(...)):
    """
    Unified endpoint for browser actions, matching MeteoBOT's API.
    Expects payload: { "action": { "type": "...", ... } }
    """
    try:
        if not browser_manager.agent:
            # Auto-start if not running
            await browser_manager.ensure_active()

        # Use the agent's act method if available
        result = await browser_manager.agent.act(req.action)

        # In typical MeteoBOT fashion, some actions might return strict data
        # We need to ensure the response format matches what operator.html expects:
        # { "ok": bool, "result": ..., "observation": ... }

        # Get observation after action
        observation = await browser_manager.agent.observe()

        return {
            "ok": result.get("ok", False),
            "result": result,
            "observation": observation
        }
    except Exception as e:
        error_id = _write_browser_api_error("/action", e)
        logger.exception("Browser /action failed (error_id=%s)", error_id)
        # Match MeteoBOT error structure if possible: {"ok": False, "error": ...}
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "error_id": error_id, "result": {"error": str(e)}}
        )

@router.get("/state", dependencies=[Depends(verify_token)])
async def get_state():
    """
    Returns the current browser state including observation and headless status.
    Used by operator.html to update title, URL, etc.
    """
    try:
        await browser_manager.ensure_active()

        observation = await browser_manager.agent.observe()

        # Construct response
        return {
            "ok": True,
            "observation": observation,
            "headless": {
                "running": browser_manager.headless,
                "default": True, # config default
                "session": browser_manager.headless,
                "domain": None,
                "domain_name": ""
            }
        }
    except Exception as e:
         error_id = _write_browser_api_error("/state", e)
         logger.exception("Browser /state failed (error_id=%s)", error_id)
         return {"ok": False, "error": str(e), "error_id": error_id}

@router.get("/screenshot", dependencies=[Depends(verify_token)])
async def get_screenshot():
    """Returns a screenshot of the current page as a blob."""
    try:
        await browser_manager.ensure_active()
        data = await browser_manager.get_screenshot()
        if not data:
            raise RuntimeError("No screenshot bytes returned from browser manager.")
        return Response(content=data, media_type="image/jpeg")
    except Exception as e:
        # One hard restart retry helps recover from dead Playwright contexts.
        first_error_id = _write_browser_api_error("/screenshot", e)
        logger.exception("Browser /screenshot failed (first attempt, error_id=%s)", first_error_id)
        try:
            await browser_manager.close()
            await browser_manager.start()
            data = await browser_manager.get_screenshot()
            if not data:
                raise RuntimeError("No screenshot bytes returned after browser restart.")
            return Response(content=data, media_type="image/jpeg")
        except Exception as retry_exc:
            second_error_id = _write_browser_api_error("/screenshot(retry)", retry_exc)
            logger.exception("Browser /screenshot failed (retry, error_id=%s)", second_error_id)
            raise HTTPException(
                status_code=500,
                detail=f"Screenshot failed (error_id={second_error_id})",
            )

@router.post("/mode")
async def set_mode(req: ModeRequest):
    """
    Updates the browser mode (headless/headful).
    """
    try:
        if req.apply:
            # Restart browser with new headless setting
            # This requires browser_manager to support restarting with config
            await browser_manager.close()
            browser_manager.headless = req.headless
            await browser_manager.start()

        return {
            "ok": True,
            "running_headless": browser_manager.headless,
            "default_headless": True,
            "session_headless": browser_manager.headless
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

# Legacy endpoints support (optional, can keep for compatibility if needed)
@router.post("/navigate")
async def navigate_legacy(req: ActionRequest):
    # Dummy wrapper if something uses old endpoint, or just remove.
    # For now, let's stick to the new Operator API mainly.
    pass
