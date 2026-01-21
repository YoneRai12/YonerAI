from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

class ToolCallRequest(BaseModel):
    tool_name: str
    args: dict[str, Any]
    tool_call_id: str
    run_id: str
    client_type: Literal["discord", "web", "api"] = "web"
    auth_context: Optional[dict[str, Any]] = None

class ToolResultResponse(BaseModel):
    tool_call_id: str
    status: Literal["completed", "failed", "pending"]
    result: Optional[Any] = None
    error: Optional[str] = None
