import asyncio
from typing import Any, Dict, List

from ora_core.database.models import RunStatus


class EventManager:
    def __init__(self):
        # run_id -> asyncio.Queue
        self.listeners: Dict[str, asyncio.Queue] = {}
        # Best-effort event buffer for late subscribers.
        # Without this, if the Brain finishes before the SSE client connects,
        # the client will hang forever waiting for events that were already emitted.
        self._event_buffer: Dict[str, List[dict[str, Any]]] = {}
        self._event_buffer_limit = 200
        self._event_lock = asyncio.Lock()
        # (run_id, tool_call_id) -> Future for external tool result handoff
        self._tool_result_waiters: Dict[tuple[str, str], asyncio.Future] = {}
        # Buffer early arrivals when submit lands before wait registration
        self._tool_result_buffer: Dict[tuple[str, str], dict[str, Any]] = {}
        self._tool_result_lock = asyncio.Lock()

    async def listen(self, run_id: str):
        queue = asyncio.Queue()
        # Register listener first so concurrent emits go to the queue, then flush any buffered events.
        async with self._event_lock:
            self.listeners[run_id] = queue
            buffered = self._event_buffer.pop(run_id, None) or []
        try:
            for ev in buffered:
                yield ev
                if ev.get("event") in {"final", "error"}:
                    return
            while True:
                event = await queue.get()
                yield event
                if event["event"] == "final" or event["event"] == "error":
                    break
        finally:
            async with self._event_lock:
                self.listeners.pop(run_id, None)
                # Drop any leftover buffered events for this run to avoid leaks.
                self._event_buffer.pop(run_id, None)

    async def dispatch_mock_stream(self, run_id: str, conversation_id: str):
        """
        Real AI Streaming Process via OmniEngine.
        """
        from ora_core.database.models import AuthorRole
        from ora_core.database.repo import Repository
        from ora_core.database.session import AsyncSessionLocal
        from ora_core.engine.omni_engine import omni_engine

        # 1. Fetch Context (Recent messages)
        # TODO: Ideally fetch from DB. For now, we'll just send the "latest" logic or minimal context.
        # Since 'simple_worker' is decoupled from the HTTP request context, we need to read from DB here.

        input_messages = [{"role": "system", "content": "You are YonerAI (formerly ORA), an advanced AI system. Respond concisely and helpfully."}]

        async with AsyncSessionLocal() as db:
            repo = Repository(db)
            conv = await repo.get_conversation(conversation_id)
            if conv:
                # Naive history loading (last 10 messages)
                # Note: 'messages' relationship is loaded via selectinload in repo.get_conversation
                for m in conv.messages[-10:]:
                    role = "user" if m.author == AuthorRole.user else "assistant"
                    # Simple sanitization
                    if m.content:
                        input_messages.append({"role": role, "content": m.content})

        # 2. Stream from AI
        full_text = ""
        used_model = "ORA Universal Brain" # Default

        try:
            async for event_data in omni_engine.generate_stream(input_messages):
                # Handle String (Legacy/Error)
                if isinstance(event_data, str):
                     full_text += event_data
                     await self.emit(run_id, "delta", {"text": event_data})

                # Handle Structured Dict
                elif isinstance(event_data, dict):
                    evt_type = event_data.get("type")

                    if evt_type == "meta":
                        used_model = event_data.get("model", used_model)
                        await self.emit(run_id, "meta", {"model": used_model})

                    elif evt_type == "text":
                        content = event_data.get("content", "")
                        full_text += content
                        await self.emit(run_id, "delta", {"text": content})

                # await asyncio.sleep(0.01) # Optional: Smooth out if too fast
        except Exception as e:
            full_text += f"\n[Generation Error: {e}]"
            await self.emit(run_id, "error", {"text": str(e)})

        # 3. Final event & Save
        async with AsyncSessionLocal() as db:
            repo = Repository(db)
            # Create Assistant Message
            msg = await repo.create_message(
                conversation_id=conversation_id,
                role=AuthorRole.assistant,
                content=full_text
            )
            await repo.update_run_status(run_id, RunStatus.done)

        await self.emit(run_id, "final", {"text": full_text, "message_id": str(msg.id), "model": used_model})

    async def emit(self, run_id: str, event_type: str, data: dict):
        event = {"event": event_type, "data": data}
        queue = self.listeners.get(run_id)
        if queue is not None:
            await queue.put(event)
        else:
            # Buffer events until the first listener attaches.
            async with self._event_lock:
                buf = self._event_buffer.setdefault(run_id, [])
                buf.append(event)
                # Keep buffer bounded to prevent unbounded growth if no clients connect.
                if len(buf) > self._event_buffer_limit:
                    del buf[: len(buf) - self._event_buffer_limit]
        if event_type in {"final", "error"}:
            async with self._tool_result_lock:
                waiter_keys = [k for k in self._tool_result_waiters.keys() if k[0] == run_id]
                for key in waiter_keys:
                    fut = self._tool_result_waiters.pop(key, None)
                    if fut and not fut.done():
                        fut.cancel()
                buffer_keys = [k for k in self._tool_result_buffer.keys() if k[0] == run_id]
                for key in buffer_keys:
                    self._tool_result_buffer.pop(key, None)

    async def submit_tool_result(self, run_id: str, tool_call_id: str, payload: dict[str, Any]) -> None:
        """
        Accept tool output from external clients (e.g., Discord ToolHandler).
        If a waiter is active, resolve it immediately; otherwise buffer it.
        """
        key = (run_id, tool_call_id)
        async with self._tool_result_lock:
            waiter = self._tool_result_waiters.get(key)
            if waiter and not waiter.done():
                waiter.set_result(payload)
            else:
                self._tool_result_buffer[key] = payload

    async def wait_for_tool_result(self, run_id: str, tool_call_id: str, timeout_sec: int = 120) -> dict[str, Any]:
        """
        Wait for a previously dispatched external tool result.
        """
        key = (run_id, tool_call_id)

        async with self._tool_result_lock:
            buffered = self._tool_result_buffer.pop(key, None)
            if buffered is not None:
                return buffered
            fut = asyncio.get_running_loop().create_future()
            self._tool_result_waiters[key] = fut

        try:
            return await asyncio.wait_for(fut, timeout=timeout_sec)
        finally:
            async with self._tool_result_lock:
                self._tool_result_waiters.pop(key, None)

event_manager = EventManager()
