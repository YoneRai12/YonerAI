import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import aiohttp

try:
    from src.utils.origin_tags import build_origin_headers, node_id_from_env
except Exception:
    def node_id_from_env() -> str:
        node = (
            os.getenv("ORA_NODE_ID")
            or os.getenv("HOSTNAME")
            or os.getenv("COMPUTERNAME")
            or "local-node"
        )
        return str(node).strip() or "local-node"

    def build_origin_headers(
        *,
        origin: str,
        node_id: str,
        request_id: str,
        trace_id: str,
        signing_secret: str | None = None,
    ) -> dict[str, str]:
        del signing_secret
        return {
            "X-Origin": str(origin),
            "X-Node-ID": str(node_id),
            "X-Request-ID": str(request_id),
            "X-Trace-ID": str(trace_id),
        }

try:
    from src.utils.service_auth import build_service_auth_headers
except Exception:
    def build_service_auth_headers(*, method: str, path: str) -> dict[str, str]:
        del method, path
        return {}

logger = logging.getLogger(__name__)


def extract_text_from_core_data(data: Any) -> Optional[str]:
    """
    Core 'final' payload shape is not perfectly stable across versions/providers.
    Try a handful of common shapes without crashing.
    """
    if data is None:
        return None
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        parts: list[str] = []
        for item in data:
            t = extract_text_from_core_data(item)
            if isinstance(t, str) and t.strip():
                parts.append(t.strip())
        return "\n".join(parts).strip() if parts else None
    if not isinstance(data, dict):
        return None

    for k in ("text", "final", "answer", "content", "message"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v

    out = data.get("output")
    if isinstance(out, list):
        parts: list[str] = []
        for o in out:
            if not isinstance(o, dict):
                continue
            content = o.get("content")
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and isinstance(c.get("text"), str) and c["text"].strip():
                        parts.append(c["text"].strip())
        if parts:
            return "\n".join(parts).strip()

    for k in ("data", "result", "response"):
        t = extract_text_from_core_data(data.get(k))
        if isinstance(t, str) and t.strip():
            return t

    return None


class CoreAPIClient:
    """
    Client for ORA Core API (/v1).
    Delegates message processing and memory management to the central Brain.
    """

    def __init__(self, base_url: Optional[str] = None):
        env_url = os.getenv("ORA_CORE_API_URL") or os.getenv("ORA_API_BASE_URL", "http://localhost:8001")
        self.base_url = (base_url or env_url).rstrip("/")
        self._run_origin_ctx: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _request_path(url: str) -> str:
        try:
            return urlsplit(url).path or "/"
        except Exception:
            return "/"

    def _build_request_headers(
        self,
        *,
        method: str,
        url: str,
        correlation_id: str | None = None,
        origin_context: Optional[dict[str, Any]] = None,
        run_id: str | None = None,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        import uuid

        headers: dict[str, str] = {}
        if correlation_id:
            headers["X-Correlation-ID"] = str(correlation_id)

        path = self._request_path(url)
        headers.update(build_service_auth_headers(method=method, path=path))

        ctx: dict[str, Any] = {}
        if isinstance(origin_context, dict):
            ctx.update(origin_context)
        elif run_id and run_id in self._run_origin_ctx:
            ctx.update(self._run_origin_ctx[run_id])

        request_id = str(ctx.get("request_id") or "").strip() or str(uuid.uuid4())
        trace_id = str(ctx.get("trace_id") or "").strip() or (str(correlation_id or "").strip() or request_id)
        origin = str(ctx.get("origin") or "").strip() or "yonerai"
        node_id = str(ctx.get("node_id") or "").strip() or node_id_from_env()
        tampered = bool(ctx.get("tampered"))
        admin_verified = bool(ctx.get("admin_verified"))

        signing_secret = (os.getenv("ORA_ORIGIN_SIGNING_SECRET") or "").strip() or None
        headers.update(
            build_origin_headers(
                origin=origin,
                node_id=node_id,
                request_id=request_id,
                trace_id=trace_id,
                signing_secret=signing_secret,
            )
        )

        return headers, {
            "origin": origin,
            "node_id": node_id,
            "request_id": request_id,
            "trace_id": trace_id,
            "tampered": tampered,
            "admin_verified": admin_verified,
        }

    async def send_message(
        self,
        content: str,
        provider_id: str,
        display_name: str,
        identity_provider: str = "discord",
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
        route_hint: Optional[dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        origin_context: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST to /v1/messages."""
        import uuid

        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

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
                        logger.warning("Dropping invalid image_url attachment (missing url)")
                else:
                    normalized_atts.append(att)
            elif isinstance(att, str):
                normalized_atts.append({"type": "image_url", "url": att})
            else:
                logger.warning("Dropping invalid attachment")

        normalized_tools: list = available_tools if isinstance(available_tools, list) else []

        provider = (identity_provider or "").strip().lower() or "web"
        if provider not in {"discord", "web", "google", "apple"}:
            provider = "web"

        src = (source or "").strip().lower() or "web"
        if src not in {"discord", "web", "api"}:
            src = "web"

        url = f"{self.base_url}/v1/messages"
        headers, origin_ctx = self._build_request_headers(
            method="POST",
            url=url,
            correlation_id=correlation_id,
            origin_context=origin_context,
        )

        payload = {
            "conversation_id": conversation_id,
            "user_identity": {
                "provider": provider,
                "id": str(provider_id),
                "display_name": display_name,
            },
            "content": content,
            "attachments": normalized_atts,
            "idempotency_key": idempotency_key,
            "stream": stream,
            "source": src,
            "context_binding": context_binding,
            "client_history": client_history or [],
            "client_context": client_context,
            "available_tools": normalized_tools,
            "llm_preference": llm_preference,
            "route_hint": route_hint if isinstance(route_hint, dict) else None,
            "request_meta": {
                "request_id": origin_ctx.get("request_id"),
                "trace_id": origin_ctx.get("trace_id"),
                "origin": origin_ctx.get("origin"),
                "node_id": origin_ctx.get("node_id"),
                "tampered": bool(origin_ctx.get("tampered")),
                "admin_verified": bool(origin_ctx.get("admin_verified")),
            },
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        run_id = str(data.get("run_id") or "").strip()
                        if run_id:
                            self._run_origin_ctx[run_id] = origin_ctx
                        return data
                    error_text = await resp.text()
                    logger.error("Core API Error (%s)", resp.status)
                    return {"error": error_text, "status": resp.status}
            except Exception as e:
                logger.error("Failed to connect to Core API: %s", e)
                return {"error": str(e), "status": 500}

    async def stream_events(
        self,
        run_id: str,
        timeout: int = 300,
        *,
        origin_context: Optional[dict[str, Any]] = None,
    ):
        """Yield events from the Core SSE stream for a specific run_id."""
        import asyncio
        import json
        import time

        url = f"{self.base_url}/v1/runs/{run_id}/events"

        deadline = time.monotonic() + max(1, int(timeout))
        backoff = 0.5
        seen: set[str] = set()

        while time.monotonic() < deadline:
            remaining = max(1, int(deadline - time.monotonic()))
            timeout_cfg = aiohttp.ClientTimeout(total=remaining)
            try:
                headers, _ = self._build_request_headers(
                    method="GET",
                    url=url,
                    origin_context=origin_context,
                    run_id=run_id,
                )
                async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            logger.error("Failed to connect to events (%s)", resp.status)
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

                            try:
                                key = json.dumps(event_data, sort_keys=True, ensure_ascii=False)
                            except Exception:
                                key = str(event_data)
                            if key in seen:
                                continue
                            if len(seen) < 5000:
                                seen.add(key)

                            yield event_data

                            if event_data.get("event") in ["final", "error"]:
                                self._run_origin_ctx.pop(run_id, None)
                                return

                        raise aiohttp.ClientPayloadError("SSE ended without terminal event")

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning("SSE stream interrupted for run_id=%s; retrying: %s", run_id, e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 5.0)

        logger.error("SSE stream timeout for run_id=%s", run_id)
        self._run_origin_ctx.pop(run_id, None)
        return

    async def get_final_response(self, run_id: str, timeout: int = 300) -> Optional[str]:
        """Convenience method to get just the final text."""
        async for event in self.stream_events(run_id, timeout):
            if event.get("event") == "final":
                return extract_text_from_core_data(event.get("data"))
        return None

    async def poll_completion(self, run_id: str, timeout: int = 300) -> Optional[str]:
        return await self.get_final_response(run_id, timeout)

    async def submit_tool_output(
        self,
        run_id: str,
        tool_name: str,
        result: Any,
        tool_call_id: Optional[str] = None,
        *,
        origin_context: Optional[dict[str, Any]] = None,
    ) -> bool:
        """POST tool results back to Core brain."""
        url = f"{self.base_url}/v1/runs/{run_id}/results"
        payload = {
            "tool": tool_name,
            "result": result,
            "tool_call_id": tool_call_id,
        }
        headers, _ = self._build_request_headers(
            method="POST",
            url=url,
            origin_context=origin_context,
            run_id=run_id,
        )
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        logger.info("Successfully submitted output for %s", tool_name)
                        return True
                    text = await resp.text()
                    logger.error("Failed to submit output (%s): %s", resp.status, text)
                    return False
            except Exception as e:
                logger.error("Error submitting tool output: %s", e)
                return False


core_client = CoreAPIClient()


