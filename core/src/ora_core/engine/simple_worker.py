import asyncio
from typing import Any, Dict, List

from ora_core.database.models import RunStatus


def shape_reasoning_summary_data(value: Any) -> dict[str, str]:
    """Return the only public-safe reasoning_summary payload shape."""
    if not isinstance(value, dict):
        return {}
    summary = value.get("summary")
    if isinstance(summary, str):
        return {"summary": summary}
    return {}


class EventManager:
    def __init__(self):
        # run_id -> asyncio.Queue
        self.listeners: Dict[str, asyncio.Queue] = {}
        # Best-effort event buffer for late subscribers.
        # Without this, if the Brain finishes before the SSE client connects,
        # the client will hang forever waiting for events that were already emitted.
        self._event_buffer: Dict[str, List[dict[str, Any]]] = {}
        self._event_buffer_limit = 200
        self._event_buffer_timestamps: Dict[str, float] = {}
        self._event_buffer_ttl_sec = 300
        self._event_buffer_runs_limit = 1000
        self._event_lock = asyncio.Lock()
        self._terminal_events: Dict[str, dict[str, Any]] = {}
        # (run_id, tool_call_id) -> Future for external tool result handoff
        self._tool_result_waiters: Dict[tuple[str, str], asyncio.Future] = {}
        # Buffer early arrivals when submit lands before wait registration
        self._tool_result_buffer: Dict[tuple[str, str], dict[str, Any]] = {}
        self._expected_tool_results: Dict[tuple[str, str], str] = {}
        self._submitted_tool_results: set[tuple[str, str]] = set()
        self._tool_result_lock = asyncio.Lock()

    async def listen(self, run_id: str):
        queue = asyncio.Queue()
        # Register listener first so concurrent emits go to the queue, then flush any buffered events.
        async with self._event_lock:
            self.listeners[run_id] = queue
            self._evict_event_buffers_locked(asyncio.get_running_loop().time())
            buffered = self._event_buffer.pop(run_id, None) or []
            self._event_buffer_timestamps.pop(run_id, None)
            terminal = self._terminal_events.get(run_id)
            if terminal and not any(ev.get("event") in {"final", "error"} for ev in buffered):
                buffered.append(terminal)
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
                self._event_buffer_timestamps.pop(run_id, None)

    def _evict_event_buffers_locked(self, now: float) -> None:
        expired = [
            buffered_run_id
            for buffered_run_id, ts in self._event_buffer_timestamps.items()
            if now - ts > self._event_buffer_ttl_sec
        ]
        for buffered_run_id in expired:
            self._event_buffer.pop(buffered_run_id, None)
            self._event_buffer_timestamps.pop(buffered_run_id, None)

        overflow = len(self._event_buffer) - self._event_buffer_runs_limit
        if overflow > 0:
            oldest_run_ids = list(self._event_buffer.keys())[:overflow]
            for buffered_run_id in oldest_run_ids:
                self._event_buffer.pop(buffered_run_id, None)
                self._event_buffer_timestamps.pop(buffered_run_id, None)

    @staticmethod
    def _shape_event_data(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        if event_type == "reasoning_summary":
            return shape_reasoning_summary_data(data)
        return data

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
        event_type_text = str(event_type)
        event = {
            "event": event_type_text,
            "data": self._shape_event_data(event_type_text, data),
        }
        queue = None
        async with self._event_lock:
            if run_id in self._terminal_events:
                return
            if event_type_text in {"final", "error"}:
                self._terminal_events[run_id] = event
            queue = self.listeners.get(run_id)
            if queue is None:
                # Buffer events until the first listener attaches.
                now = asyncio.get_running_loop().time()
                self._evict_event_buffers_locked(now)
                buf = self._event_buffer.setdefault(run_id, [])
                buf.append(event)
                self._event_buffer_timestamps[run_id] = now
                # Keep buffer bounded to prevent unbounded growth if no clients connect.
                if len(buf) > self._event_buffer_limit:
                    del buf[: len(buf) - self._event_buffer_limit]
        if queue is not None:
            await queue.put(event)
        if event_type_text in {"final", "error"}:
            async with self._tool_result_lock:
                waiter_keys = [k for k in self._tool_result_waiters.keys() if k[0] == run_id]
                for key in waiter_keys:
                    fut = self._tool_result_waiters.pop(key, None)
                    if fut and not fut.done():
                        fut.cancel()
                buffer_keys = [k for k in self._tool_result_buffer.keys() if k[0] == run_id]
                for key in buffer_keys:
                    self._tool_result_buffer.pop(key, None)
                expected_keys = [k for k in self._expected_tool_results.keys() if k[0] == run_id]
                for key in expected_keys:
                    self._expected_tool_results.pop(key, None)
                    self._submitted_tool_results.discard(key)

    async def expect_tool_result(self, run_id: str, tool_call_id: str, tool_name: str) -> None:
        key = (run_id, tool_call_id)
        async with self._tool_result_lock:
            self._expected_tool_results[key] = tool_name

    async def accepts_tool_result(self, run_id: str, tool_call_id: str, tool_name: str | None = None) -> str:
        key = (run_id, tool_call_id)
        async with self._tool_result_lock:
            expected = self._expected_tool_results.get(key)
            if expected is None:
                return "unexpected"
            if tool_name and expected != tool_name:
                return "mismatch"
            if key in self._submitted_tool_results:
                return "duplicate"
            return "accepted"

    async def submit_tool_result(self, run_id: str, tool_call_id: str, payload: dict[str, Any]) -> bool:
        """
        Accept tool output from external clients (e.g., Discord ToolHandler).
        If a waiter is active, resolve it immediately; otherwise buffer it.
        """
        key = (run_id, tool_call_id)
        async with self._tool_result_lock:
            expected = self._expected_tool_results.get(key)
            if expected is None:
                raise KeyError("unexpected_tool_result")
            if key in self._submitted_tool_results:
                return False
            self._submitted_tool_results.add(key)
            waiter = self._tool_result_waiters.get(key)
            if waiter and not waiter.done():
                waiter.set_result(payload)
            else:
                self._tool_result_buffer[key] = payload
        return True

    async def wait_for_tool_result(self, run_id: str, tool_call_id: str, timeout_sec: int = 120) -> dict[str, Any]:
        """
        Wait for a previously dispatched external tool result.
        """
        key = (run_id, tool_call_id)

        async with self._tool_result_lock:
            buffered = self._tool_result_buffer.pop(key, None)
            if buffered is not None:
                self._expected_tool_results.pop(key, None)
                self._submitted_tool_results.discard(key)
                return buffered
            fut = asyncio.get_running_loop().create_future()
            self._tool_result_waiters[key] = fut

        try:
            return await asyncio.wait_for(fut, timeout=timeout_sec)
        finally:
            async with self._tool_result_lock:
                self._tool_result_waiters.pop(key, None)
                self._expected_tool_results.pop(key, None)
                self._submitted_tool_results.discard(key)

event_manager = EventManager()
