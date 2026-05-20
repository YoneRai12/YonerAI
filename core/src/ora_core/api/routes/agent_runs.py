from __future__ import annotations

from dataclasses import dataclass, field
import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ora_core.api.routes.public_messages import (
    PublicMessageError,
    build_public_message_response,
)
from ora_core.api.schemas.public_messages import (
    PUBLIC_MESSAGE_MAX_LENGTH,
    PublicMessageRequest,
)


router = APIRouter()

SURFACE_API_CONTRACT_VERSION = "surface-api-run-contract-0.1"
SUPPORTED_RUN_MODES = frozenset({"mock", "offline", "local"})
SURFACE_AGENT_RUN_STORE_MAX_ENTRIES = 128
SURFACE_AGENT_RUN_MAX_RESULTS_PER_RUN = 32
SURFACE_AGENT_RUN_RESULT_MAX_BYTES = 16 * 1024


class AgentRunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=PUBLIC_MESSAGE_MAX_LENGTH)
    mode: Literal["mock", "offline", "local"] = "mock"
    session_id: str | None = Field(default=None, max_length=120)
    conversation_id: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    local_provider: str | None = Field(default=None, max_length=64)
    local_base_url: str | None = Field(default=None, max_length=200)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=4096)


class AgentRunResultRequest(BaseModel):
    result_type: str = Field(default="surface_api_smoke_result", max_length=80)
    tool: str | None = Field(default=None, max_length=120)
    tool_call_id: str | None = Field(default=None, max_length=120)
    result: dict[str, Any] | list[Any] | str | int | float | bool | None = None


@dataclass
class AgentRunState:
    run_id: str
    status: str
    events: list[dict[str, Any]]
    created_at: str
    memory_persisted: bool = False
    accepted_results: list[dict[str, Any]] = field(default_factory=list)


_RUNS: dict[str, AgentRunState] = {}


def reset_surface_agent_run_store() -> None:
    _RUNS.clear()


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _public_error(status_code: int, code: str, message: str, metadata: dict[str, str] | None = None) -> HTTPException:
    detail = {"error": code, "message": message}
    if metadata:
        detail.update(metadata)
    return HTTPException(status_code=status_code, detail=detail)


def _get_run_or_404(run_id: str) -> AgentRunState:
    run = _RUNS.get(run_id)
    if not run:
        raise _public_error(404, "run_not_found", "Run not found.")
    return run


def _store_run(run: AgentRunState) -> None:
    while len(_RUNS) >= SURFACE_AGENT_RUN_STORE_MAX_ENTRIES:
        _RUNS.pop(next(iter(_RUNS)))
    _RUNS[run.run_id] = run




def _trim_oldest_tool_result_event(run: AgentRunState) -> None:
    for idx, event in enumerate(run.events):
        if event.get("event") == "tool_result_submit":
            run.events.pop(idx)
            break


def _result_payload_size_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

def _build_events(*, run_id: str, response_body: dict[str, Any]) -> list[dict[str, Any]]:
    meta = {
        "run_id": run_id,
        "status": "completed",
        "mode": response_body["mode"],
        "provider": response_body["provider"],
        "model": response_body.get("model"),
        "session_id": response_body["session_id"],
        "conversation_id": response_body["conversation_id"],
        "message_id": response_body["message_id"],
        "turn_index": response_body["turn_index"],
        "history_count": response_body["history_count"],
        "memory_persisted": False,
        "contract_version": SURFACE_API_CONTRACT_VERSION,
    }
    return [
        {"event": "meta", "data": meta},
        {
            "event": "final",
            "data": {
                "run_id": run_id,
                "reply": response_body["reply"],
                "mode": response_body["mode"],
                "provider": response_body["provider"],
                "model": response_body.get("model"),
                "memory_persisted": False,
                "requires_approval": response_body["requires_approval"],
            },
        },
    ]


@router.post("/run")
def create_agent_run(req: AgentRunRequest, request: Request) -> dict[str, Any]:
    prompt = req.prompt.strip()
    if not prompt:
        raise _public_error(400, "empty_prompt", "prompt must contain non-whitespace text.")

    public_req = PublicMessageRequest(
        message=prompt,
        mode=req.mode,
        session_id=req.session_id,
        conversation_id=req.conversation_id,
        model=req.model,
        local_provider=req.local_provider,
        local_base_url=req.local_base_url,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    try:
        public_response = build_public_message_response(public_req, request)
    except PublicMessageError as exc:
        raise _public_error(exc.status_code, exc.code, exc.message, exc.metadata) from exc

    response_body = public_response.model_dump()
    run_id = f"surface-run-{uuid4().hex}"
    events = _build_events(run_id=run_id, response_body=response_body)
    _store_run(
        AgentRunState(
            run_id=run_id,
            status="completed",
            events=events,
            created_at=_now_iso(),
        )
    )

    return {
        "ok": True,
        "run_id": run_id,
        "status": "completed",
        "mode": response_body["mode"],
        "provider": response_body["provider"],
        "model": response_body.get("model"),
        "session_id": response_body["session_id"],
        "conversation_id": response_body["conversation_id"],
        "message_id": response_body["message_id"],
        "memory_persisted": False,
        "reply": response_body["reply"],
        "events_url": f"/api/v1/agent/runs/{run_id}/events",
        "results_url": f"/api/v1/agent/runs/{run_id}/results",
        "contract_version": SURFACE_API_CONTRACT_VERSION,
    }


@router.get("/runs/{run_id}/events")
def get_agent_run_events(run_id: str) -> dict[str, Any]:
    run = _get_run_or_404(run_id)
    return {
        "ok": True,
        "run_id": run.run_id,
        "status": run.status,
        "events": run.events,
        "memory_persisted": run.memory_persisted,
        "contract_version": SURFACE_API_CONTRACT_VERSION,
    }


@router.post("/runs/{run_id}/results")
def submit_agent_run_result(run_id: str, req: AgentRunResultRequest) -> dict[str, Any]:
    run = _get_run_or_404(run_id)
    event = {
        "event": "tool_result_submit",
        "data": {
            "result_type": req.result_type,
            "tool": req.tool,
            "tool_call_id": req.tool_call_id,
            "accepted": True,
            "trusted": False,
            "memory_persisted": False,
        },
    }
    payload = req.model_dump()
    payload_size = _result_payload_size_bytes(payload)
    if payload_size > SURFACE_AGENT_RUN_RESULT_MAX_BYTES:
        raise _public_error(413, "result_too_large", "result payload exceeds size limit.")

    while len(run.accepted_results) >= SURFACE_AGENT_RUN_MAX_RESULTS_PER_RUN:
        run.accepted_results.pop(0)
        _trim_oldest_tool_result_event(run)

    run.accepted_results.append(payload)
    run.events.append(event)
    return {
        "ok": True,
        "run_id": run.run_id,
        "status": "accepted",
        "accepted": True,
        "trusted": False,
        "memory_persisted": False,
        "contract_version": SURFACE_API_CONTRACT_VERSION,
    }
