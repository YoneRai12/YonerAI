import asyncio
import logging
from typing import Dict, Any
from .registry import tool_registry, ToolDefinition
from ora_core.database.repo import Repository

logger = logging.getLogger(__name__)

# Semaphores for GPU resource management
# Limit to 1 concurrent GPU tool call to ensure 25GB VRAM budget is respected safely.
gpu_semaphore = asyncio.Semaphore(1)

class ToolRunner:
    """
    Executes tool calls with safety fences:
    1. Permission Check (Client type)
    2. DB-level Idempotency (Atomic execution)
    3. Resource Management (GPU Semaphore)
    4. Error Handling & Persistence
    """
    def __init__(self, repo: Repository):
        self.repo = repo

    async def run_tool(
        self, 
        tool_call_id: str, 
        run_id: str, 
        user_id: str,
        tool_name: str, 
        args: dict, 
        client_type: str
    ) -> dict[str, Any]:
        
        # 1. Fetch Definition & Permission Check
        definition = tool_registry.get_definition(tool_name)
        if not definition:
            return {"status": "failed", "error": f"Tool '{tool_name}' not found."}
        
        if client_type not in definition.allowed_clients:
            logger.warning(f"Access denied: {client_type} tried to use {tool_name}")
            return {"status": "failed", "error": f"Client '{client_type}' is not authorized to use tool '{tool_name}'."}

        # 2. DB Idempotency Check (INSERT or Get)
        call_record, created = await self.repo.get_or_create_tool_call(
            tool_call_id, run_id, user_id, tool_name, args
        )
        
        from datetime import datetime, timedelta
        import uuid
        lease_token = str(uuid.uuid4())
        
        # Helper for polling logic
        async def poll_for_result():
            logger.info(f"Tool {tool_call_id} is running elsewhere, waiting for results...")
            for _ in range(30): # Up to 30 seconds
                await asyncio.sleep(1.0)
                await self.repo.db.rollback()
                from sqlalchemy import select
                from ora_core.database.models import ToolCall
                stmt = select(ToolCall).where(ToolCall.id == tool_call_id, ToolCall.user_id == user_id)
                r = await self.repo.db.execute(stmt)
                updated_record = r.scalar_one_or_none()
                if updated_record and updated_record.status in ["completed", "failed"]:
                    return {
                        "status": updated_record.status,
                        "result": updated_record.result_json,
                        "error": updated_record.error
                    }
            return {"status": "pending", "message": "Tool call is still being processed."}

        if not created:
            if call_record.status in ["completed", "failed"]:
                logger.info(f"Returning cached result for tool_call_id: {tool_call_id}")
                return {
                    "status": call_record.status,
                    "result": call_record.result_json,
                    "error": call_record.error
                }
            
            # If it's running and NOT stale, we poll
            if call_record.status == "running":
                is_stale = call_record.expires_at and datetime.utcnow() > call_record.expires_at
                if not is_stale:
                    return await poll_for_result()
                else:
                    logger.warning(f"Tool {tool_call_id} is stale. Attempting to reclaim...")

        # 3. Atomic Claim
        expires_at = datetime.utcnow() + timedelta(seconds=definition.timeout_sec + 60)
        claimed = await self.repo.claim_tool_call(tool_call_id, user_id, lease_token, expires_at)
        
        if not claimed:
            # We lost the race to claim it (someone else just started or recovered it)
            logger.info(f"Lost race to claim tool {tool_call_id}. Polling...")
            return await poll_for_result()

        # 4. Execution
        try:
            # Resource Management (GPU)
            if definition.gpu_required:
                logger.info(f"Tool {tool_name} requires GPU (Lease: {lease_token}). Waiting for semaphore...")
                async with gpu_semaphore:
                    result = await asyncio.wait_for(
                        tool_registry.execute_handler(tool_name, args, {"user_id": user_id}),
                        timeout=definition.timeout_sec
                    )
            else:
                result = await asyncio.wait_for(
                    tool_registry.execute_handler(tool_name, args, {"user_id": user_id}),
                    timeout=definition.timeout_sec
                )

            # Update Success (Verifying lease_token)
            await self.repo.update_tool_call(
                tool_call_id, user_id, "completed", 
                lease_token=lease_token, result=result
            )
            return {"status": "completed", "result": result}

        except asyncio.TimeoutError:
            error_res = {
                "ok": False,
                "content": [{"type": "text", "text": "Tool execution timed out."}],
                "error": {"code": "TIMEOUT", "message": f"Tool {tool_name} timed out after {definition.timeout_sec}s"},
                "metrics": {"latency_ms": definition.timeout_sec * 1000, "cache_hit": False}
            }
            await self.repo.update_tool_call(tool_call_id, user_id, "failed", lease_token=lease_token, error=json.dumps(error_res))
            return {"status": "failed", "error": error_res}
        except Exception as e:
            logger.error(f"Execution Error ({tool_name}): {e}", exc_info=True)
            error_res = {
                "ok": False,
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "error": {"code": "EXECUTION_ERROR", "message": str(e)},
                "metrics": {"latency_ms": 0, "cache_hit": False}
            }
            await self.repo.update_tool_call(tool_call_id, user_id, "failed", lease_token=lease_token, error=json.dumps(error_res))
            return {"status": "failed", "error": error_res}
