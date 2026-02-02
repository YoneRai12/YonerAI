from fastapi import APIRouter, HTTPException, Body, Depends, Header
from fastapi.responses import StreamingResponse, Response, JSONResponse
from pydantic import BaseModel
from typing import Optional, Any, Dict, List
import io
import asyncio
import json

from src.utils.browser import browser_manager
from src.config import Config

router = APIRouter(tags=["browser"])

async def verify_token(x_auth_token: Optional[str] = Header(None)):
    cfg = Config.load()
    if not cfg.browser_remote_token:
        # If no token configured, allow access (or warn? Default: Open if not set, strict if set)
        # For security audit, let's allow open ONLY if explicitly not set.
        return
    
    if x_auth_token != cfg.browser_remote_token:
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
        # Match MeteoBOT error structure if possible: {"ok": False, "error": ...}
        return JSONResponse(
            status_code=500, 
            content={"ok": False, "error": str(e), "result": {"error": str(e)}}
        )

@router.get("/state", dependencies=[Depends(verify_token)])
async def get_state():
    """
    Returns the current browser state including observation and headless status.
    Used by operator.html to update title, URL, etc.
    """
    try:
        if not browser_manager.agent:
             return {"ok": False, "error": "Browser not initialized"}

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
         return {"ok": False, "error": str(e)}

@router.get("/screenshot", dependencies=[Depends(verify_token)])
async def get_screenshot():
    """Returns a screenshot of the current page as a blob."""
    try:
        if not browser_manager.agent:
             raise HTTPException(status_code=400, detail="Browser not initialized")

        # Get screenshot bytes from agent
        # We might need to ensure the agent has a method for this or use the manager
        # browser_manager.get_screenshot() returns bytes
        data = await browser_manager.get_screenshot()
        return Response(content=data, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screenshot failed: {str(e)}")

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
