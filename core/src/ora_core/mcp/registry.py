from typing import Callable, Any, Awaitable, Dict, List, Literal
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict # JSON Schema
    gpu_required: bool = False
    vram_hint_mb: int = 0
    timeout_sec: int = 30
    allowed_clients: List[Literal["discord", "web", "api"]] = ["web", "api"]

class ToolResult(BaseModel):
    ok: bool
    content: List[Dict[str, Any]] # MCP compatible content[]
    structuredContent: Dict[str, Any] = {}
    error: Dict[str, Any] | None = None
    metrics: Dict[str, Any] = {
        "latency_ms": 0,
        "cache_hit": False
    }

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable[[dict, dict], Awaitable[Any]]] = {}

    def register_tool(
        self, 
        definition: ToolDefinition, 
        handler: Callable[[dict, dict], Awaitable[Any]]
    ):
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler
        logger.info(f"Tool registered: {definition.name}")

    def get_definition(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    async def execute_handler(self, name: str, args: dict, context: dict) -> Any:
        handler = self._handlers.get(name)
        if not handler:
            raise ValueError(f"No handler registered for tool: {name}")
        return await handler(args, context)

    def list_tools_for_client(self, client_type: str) -> List[ToolDefinition]:
        return [
            t for t in self._tools.values() 
            if client_type in t.allowed_clients
        ]

tool_registry = ToolRegistry()

# Register default tools
async def echo_handler(args: dict, context: dict):
    return {
        "ok": True,
        "content": [{"type": "text", "text": args.get("text", "echo")}],
        "metrics": {"latency_ms": 0, "cache_hit": False}
    }

tool_registry.register_tool(
    ToolDefinition(
        name="echo_tool", 
        description="Simple echo for testing", 
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"}
            },
            "required": ["text"]
        }, 
        allowed_clients=["discord", "web", "api"]
    ),
    echo_handler
)

# Phase 7: Real google_search implementation
async def google_search_handler(args: dict, context: dict):
    from ora_core.tools.search import execute_search
    query = args.get("query", "")
    user_id = context.get("user_id", "anonymous")
    
    # Selection of engine from environment
    import os
    provider = os.getenv("SEARCH_ENGINE", "google")
    
    return await execute_search(user_id, query, provider_name=provider)

tool_registry.register_tool(
    ToolDefinition(
        name="google_search",
        description="Search Google for the latest information.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."}
            },
            "required": ["query"]
        },
        timeout_sec=15,
        allowed_clients=["discord", "web", "api"]
    ),
    google_search_handler
)
