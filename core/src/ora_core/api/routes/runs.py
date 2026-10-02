import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from ora_core.api.dependencies.auth import get_current_user
from ora_core.database.models import User
from ora_core.database.repo import Repository
from ora_core.database.session import get_db
from ora_core.distribution.runtime import get_current_runtime
from ora_core.engine.simple_worker import event_manager, shape_reasoning_summary_data
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

_REASONING_SUMMARY_BLOCKED_KEYS = frozenset(
    {
        "raw_chain_of_thought",
        "raw_prompt",
        "raw_prompts",
        "hidden_route_rationale",
        "hidden_routing_rationale",
        "operator_only_diagnostics",
        "private_admin_state",
    }
)


def _sanitize_reasoning_summary_data(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in _REASONING_SUMMARY_BLOCKED_KEYS:
                continue
            sanitized[key_text] = _sanitize_reasoning_summary_data(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_reasoning_summary_data(item) for item in value]
    return value


def _build_sse_payload(event: dict[str, Any]) -> dict[str, Any]:
    event_type = event["event"]
    event_data = event["data"]
    if event_type == "reasoning_summary":
        event_data = shape_reasoning_summary_data(event_data)
    elif event_type == "meta":
        event_data = _sanitize_reasoning_summary_data(event_data)
    return {
        "event": event_type,
        "data": event_data,
    }


class ToolResultRequest(BaseModel):
    result_type: str = "continuation_tool_result"
    tool: str
    result: dict | str | list | int | float | bool | None = None
    tool_call_id: str | None = None

@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authenticated_user: User | None = Depends(get_current_user),
):
    """
    SSE Endpoint for streaming run events.
    """
    runtime = get_current_runtime()
    runtime.require_capability("run.read_events")
    repo = Repository(db)
    run = await repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Not Found")
    if runtime.enabled:
        if not authenticated_user:
            raise HTTPException(status_code=401, detail="Authenticated run owner is required.")
        if not run.user_id or run.user_id != authenticated_user.id:
            raise HTTPException(status_code=404, detail="Not Found")

    async def event_generator():
        async for event in event_manager.listen(run_id):
            if await request.is_disconnected():
                break
            payload = _build_sse_payload(event)
            yield {
                "data": json.dumps(payload)
            }

    return EventSourceResponse(event_generator())


@router.post("/runs/{run_id}/results")
async def submit_run_tool_result(
    run_id: str,
    body: ToolResultRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authenticated_user: User | None = Depends(get_current_user),
):
    """
    Accept external tool execution result and hand it to the active run loop.
    """
    get_current_runtime().require_capability("run.submit_continuation_results")
    if body.result_type != "continuation_tool_result":
        raise HTTPException(status_code=422, detail="Only continuation tool results are accepted.")
    if not body.tool_call_id:
        raise HTTPException(status_code=422, detail="tool_call_id is required for continuation.")

    repo = Repository(db)
    run = await repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Not Found")
    runtime = get_current_runtime()
    if runtime.enabled:
        if not authenticated_user:
            raise HTTPException(status_code=401, detail="Authenticated run owner is required.")
        if not run.user_id or run.user_id != authenticated_user.id:
            raise HTTPException(status_code=404, detail="Not Found")
    tool_call = await repo.get_tool_call(body.tool_call_id)
    if not tool_call or tool_call.run_id != run_id or tool_call.tool_name != body.tool:
        raise HTTPException(status_code=409, detail="Tool result does not match an active continuation tool call.")

    acceptance = await event_manager.accepts_tool_result(run_id, body.tool_call_id, body.tool)
    if acceptance == "unexpected":
        raise HTTPException(status_code=409, detail="Run is not awaiting this continuation tool result.")
    if acceptance == "mismatch":
        raise HTTPException(status_code=409, detail="Tool result does not match the expected continuation tool.")

    payload = {
        "tool": body.tool,
        "result": body.result,
        "tool_call_id": body.tool_call_id,
    }
    if acceptance == "duplicate":
        return {"status": "ok", "accepted": False, "duplicate": True}

    try:
        accepted = await event_manager.submit_tool_result(run_id, body.tool_call_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="Run is not awaiting this continuation tool result.") from exc

    await event_manager.emit(
        run_id,
        "tool_result_submit",
        {"tool": body.tool, "tool_call_id": body.tool_call_id},
    )
    return {
        "status": "ok",
        "accepted": bool(accepted),
        "continuation_only": True,
    }
