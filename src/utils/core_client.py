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
                           available_tools: Optional[list] = None,
                           source: str = "discord",
                           llm_preference: Optional[str] = None,
                           correlation_id: Optional[str] = None
                           ) -> Dict[str, Any]:
        """
        POST to /v1/messages
        """
        import uuid
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        # Normalize attachments (Defensive layer)
        # Canonical schema for Core API:
        #   {"type":"image_url","url":"..."}
        # Accept legacy nested shape too:
        #   {"type":"image_url","image_url":{"url":"..."}}
        normalized_atts = []
        for att in (attachments or []):
            if isinstance(att, dict) and "type" in att:
                att_type = att.get("type")
                if att_type == "image_url":
                    url = att.get("url")
                    if not url and isinstance(att.get("image_url"), dict):
                        url = att["image_url"].get("url")
                    if url:
                        normalized_atts.append({"type": "image_url", "url": url})
                    else:
                        logger.warning(f"Dropping invalid image_url attachment (missing url): {att}")
                else:
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
            "source": source,
            "context_binding": context_binding,
            "client_history": client_history or [],
            "client_context": client_context,
            "available_tools": available_tools, # <--- Added
            "llm_preference": llm_preference,
        }

        headers = {}
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.base_url}/v1/messages", json=payload, headers=headers) as resp:
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
        url = f"{self.base_url}/v1/runs/{run_id}/events"

        # Robustness:
        # SSE streams can be interrupted (proxy resets, chunked transfer errors, etc.).
        # Retry within the timeout window and de-duplicate already-seen events.
        import asyncio
        import time

        deadline = time.monotonic() + max(1, int(timeout))
        backoff = 0.5
        seen: set[str] = set()

        while time.monotonic() < deadline:
            remaining = max(1, int(deadline - time.monotonic()))
            timeout_cfg = aiohttp.ClientTimeout(total=remaining)
            try:
                async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            logger.error(f"Failed to connect to events: {await resp.text()}")
                            return

                        async for line in resp.content:
                            if not line:
                                continue

                            decoded_line = line.decode("utf-8", errors="ignore").strip()
                            if not decoded_line:
                                continue

                            if not decoded_line.startswith("data: "):
                                continue

                            try:
                                event_data = json.loads(decoded_line[6:])
                            except json.JSONDecodeError:
                                continue

                            # De-dupe by stable JSON (best-effort).
                            try:
                                key = json.dumps(event_data, sort_keys=True, ensure_ascii=False)
                            except Exception:
                                key = str(event_data)
                            if key in seen:
                                continue
                            if len(seen) < 5000:
                                seen.add(key)

                            yield event_data

                            # Terminate on final or error
                            if event_data.get("event") in ["final", "error"]:
                                return

                        # If the stream ends without final/error, retry.
                        raise aiohttp.ClientPayloadError("SSE ended without terminal event")

            except asyncio.CancelledError:
                return
            except Exception as e:
                # Common transient: TransferEncodingError / ClientPayloadError ("not enough data ...")
                logger.warning(f"SSE stream interrupted for run_id={run_id}; retrying: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 5.0)

        logger.error(f"SSE stream timeout for run_id={run_id}")
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

    async def submit_tool_output(
        self,
        run_id: str,
        tool_name: str,
        result: Any,
        tool_call_id: Optional[str] = None,
    ) -> bool:
        """
        POST tool results back to Core brain.
        """
        url = f"{self.base_url}/v1/runs/{run_id}/results"
        # If result is a dict, send as is. If string/other, convert it.
        payload = {
            "tool": tool_name,
            "result": result,
            "tool_call_id": tool_call_id,
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
