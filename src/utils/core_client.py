import aiohttp
import logging
from typing import Optional, Any, Dict
from src.config import STATE_DIR # Using existing config style

logger = logging.getLogger(__name__)

class CoreAPIClient:
    """
    Client for ORA Core API (/v1).
    Delegates message processing and memory management to the the central Brain.
    """
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url.rstrip("/")

    async def send_message(self, 
                           content: str, 
                           provider_id: str, 
                           display_name: str, 
                           conversation_id: Optional[str] = None,
                           idempotency_key: Optional[str] = None,
                           attachments: list = None,
                           context_binding: Optional[dict] = None,
                           stream: bool = False
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
            "context_binding": context_binding
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

    async def get_final_response(self, run_id: str, timeout: int = 60) -> Optional[str]:
        """
        Listens to SSE events for a specific run_id and returns the final AI text.
        """
        import json
        url = f"{self.base_url}/v1/runs/{run_id}/events"
        
        timeout_cfg = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to connect to events: {await resp.text()}")
                        return None
                    
                    final_text = None
                    async for line in resp.content:
                        if not line:
                            continue
                        
                        l = line.decode("utf-8").strip()
                        if not l:
                            continue
                        
                        # SSE handling: event: ..., data: ...
                        if l.startswith("data: "):
                            try:
                                event_data = json.loads(l[6:])
                                event_type = event_data.get("event")
                                if event_type == "final":
                                    final_text = event_data.get("data", {}).get("text")
                                    return final_text
                                elif event_type == "error":
                                    logger.error(f"Core API Run Error: {event_data.get('data')}")
                                    return None
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                logger.error(f"Error reading SSE stream: {e}")
                return None
        return None

    async def poll_completion(self, run_id: str, timeout: int = 60) -> Optional[str]:
        """
        Wait for Run completion and return final response.
        """
        return await self.get_final_response(run_id, timeout)

core_client = CoreAPIClient()
