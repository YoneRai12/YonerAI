import logging
import os
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

class CoreAPIClient:
    """
    Client for ORA Core API (/v1).
    Delegates message processing and memory management to the the central Brain.
    """
    def __init__(self, base_url: Optional[str] = None):
        # 1. Parameter Priority
        # 2. Env variable Priority (match ORA Core API default)
        # 3. Last fallback
        env_url = os.getenv("ORA_CORE_API_URL") or os.getenv("ORA_API_BASE_URL", "http://localhost:8001")
        self.base_url = (base_url or env_url).rstrip("/")

    async def send_message(self, 
                           content: str, 
                           provider_id: str, 
                           display_name: str, 
                           conversation_id: Optional[str] = None,
                           idempotency_key: Optional[str] = None,
                           attachments: list = None,
                           context_binding: Optional[dict] = None,
                           stream: bool = False,
                           client_history: list = None,
                           client_context: Optional[dict] = None,
                           available_tools: Optional[list] = None
                           ) -> Dict[str, Any]:
        """
        POST to /v1/messages
        """
        import uuid
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        # Normalize attachments (Defensive layer)
        normalized_atts = []
        for att in (attachments or []):
            if isinstance(att, dict) and "type" in att:
                normalized_atts.append(att)
            elif isinstance(att, str):
                normalized_atts.append({"type": "image_url", "url": att})
            else:
                logger.warning(f"Dropping invalid attachment: {att}")

        payload = {
            "conversation_id": conversation_id,
            "user_identity": {
                "provider": "discord", # Default for this client, can be tuned
                "id": str(provider_id),
                "display_name": display_name
            },
            "content": content,
            "attachments": normalized_atts,
            "idempotency_key": idempotency_key,
            "stream": stream,
            "context_binding": context_binding,
            "client_history": client_history or [],
            "client_context": client_context,
            "available_tools": available_tools # <--- Added
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.base_url}/v1/messages", json=payload) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        error_text = await resp.text()
                        logger.error(f"Core API Error ({resp.status}): {error_text}")
                        return {"error": error_text, "status": resp.status}
            except Exception as e:
                logger.error(f"Failed to connect to Core API: {e}")
                return {"error": str(e), "status": 500}

    async def stream_events(self, run_id: str, timeout: int = 300):
        """
        Yields events from the Core SSE stream for a specific run_id.
        """
        import json

        import aiohttp
        url = f"{self.base_url}/v1/runs/{run_id}/events"
        
        # Increase timeout for long-running tool executions
        timeout_cfg = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to connect to events: {await resp.text()}")
                        return
                    
                    async for line in resp.content:
                        if not line:
                            continue
                        
                        decoded_line = line.decode("utf-8").strip()
                        if not decoded_line:
                            continue
                        
                        if decoded_line.startswith("data: "):
                            try:
                                event_data = json.loads(decoded_line[6:])
                                yield event_data
                                
                                # Terminate on final or error
                                if event_data.get("event") in ["final", "error"]:
                                    break
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                logger.error(f"Error reading SSE stream: {e}")
                return

    async def get_final_response(self, run_id: str, timeout: int = 300) -> Optional[str]:
        """
        Convenience method to get just the final text.
        """
        async for event in self.stream_events(run_id, timeout):
            if event.get("event") == "final":
                return event.get("data", {}).get("text")
        return None

    async def poll_completion(self, run_id: str, timeout: int = 300) -> Optional[str]:
        return await self.get_final_response(run_id, timeout)

    async def submit_tool_output(self, run_id: str, tool_name: str, result: Any) -> bool:
        """
        POST tool results back to Core brain.
        """
        url = f"{self.base_url}/v1/runs/{run_id}/results"
        payload = {
            "tool": tool_name,
            "output": str(result)
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(f"✅ Successfully submitted output for {tool_name}")
                        return True
                    else:
                        text = await resp.text()
                        logger.error(f"❌ Failed to submit output ({resp.status}): {text}")
                        return False
            except Exception as e:
                logger.error(f"❌ Error submitting tool output: {e}")
                return False

core_client = CoreAPIClient()
