from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from ora_core.engine.simple_worker import event_manager
import json

router = APIRouter()

@router.get("/runs/{run_id}/events")
async def stream_run_events(run_id: str, request: Request):
    """
    SSE Endpoint for streaming run events.
    """
    async def event_generator():
        async for event in event_manager.listen(run_id):
            if await request.is_disconnected():
                break
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"])
            }

    return EventSourceResponse(event_generator())
