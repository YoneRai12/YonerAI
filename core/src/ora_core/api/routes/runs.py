import json

from fastapi import APIRouter, Depends, HTTPException, Request
from ora_core.database.repo import Repository
from ora_core.database.session import get_db
from ora_core.engine.simple_worker import event_manager
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class ToolResultRequest(BaseModel):
    tool: str
    result: dict | str | list | int | float | bool | None = None
    tool_call_id: str | None = None

@router.get("/runs/{run_id}/events")
async def stream_run_events(run_id: str, request: Request):
    """
    SSE Endpoint for streaming run events.
    """
    async def event_generator():
        async for event in event_manager.listen(run_id):
            if await request.is_disconnected():
                break
            # Bundle event type into data payload for simple client parsing
            payload = {
                "event": event["event"],
                "data": event["data"]
            }
            yield {
                "data": json.dumps(payload)
            }

    return EventSourceResponse(event_generator())


@router.post("/runs/{run_id}/results")
async def submit_run_tool_result(
    run_id: str,
    body: ToolResultRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept external tool execution result and hand it to the active run loop.
    """
    repo = Repository(db)
    run = await repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = {
        "tool": body.tool,
        "result": body.result,
        "tool_call_id": body.tool_call_id,
    }

    if body.tool_call_id:
        await event_manager.submit_tool_result(run_id, body.tool_call_id, payload)
        await event_manager.emit(
            run_id,
            "tool_result_submit",
            {"tool": body.tool, "tool_call_id": body.tool_call_id},
        )
        return {"status": "ok", "accepted": True}

    # Backward-compatible accept for legacy clients that do not send tool_call_id.
    await event_manager.emit(
        run_id,
        "tool_result_submit",
        {"tool": body.tool, "tool_call_id": None, "note": "missing_tool_call_id"},
    )
    return {"status": "ok", "accepted": False, "note": "tool_call_id is required for run continuation"}
