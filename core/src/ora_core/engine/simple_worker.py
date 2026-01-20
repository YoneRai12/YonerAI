import asyncio
from typing import Dict
from ora_core.database.models import RunStatus

class EventManager:
    def __init__(self):
        # run_id -> asyncio.Queue
        self.listeners: Dict[str, asyncio.Queue] = {}

    async def listen(self, run_id: str):
        queue = asyncio.Queue()
        self.listeners[run_id] = queue
        try:
            while True:
                event = await queue.get()
                yield event
                if event["event"] == "final" or event["event"] == "error":
                    break
        finally:
            if run_id in self.listeners:
                del self.listeners[run_id]

    async def dispatch_mock_stream(self, run_id: str, conversation_id: str):
        """
        Real AI Streaming Process via OmniEngine.
        """
        from ora_core.engine.omni_engine import omni_engine
        from ora_core.database.session import AsyncSessionLocal
        from ora_core.database.repo import Repository
        from ora_core.database.models import RunStatus, AuthorRole

        # 1. Fetch Context (Recent messages)
        # TODO: Ideally fetch from DB. For now, we'll just send the "latest" logic or minimal context.
        # Since 'simple_worker' is decoupled from the HTTP request context, we need to read from DB here.
        
        input_messages = [{"role": "system", "content": "You are ORA, an advanced AI system. Respond concisely and helpfully."}]
        
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
        try:
            async for token in omni_engine.generate_stream(input_messages):
                full_text += token
                await self.emit(run_id, "delta", {"text": token})
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
            # Update Run
            await repo.update_run_status(run_id, RunStatus.done)
            
        await self.emit(run_id, "final", {"text": full_text, "message_id": str(msg.id)})

    async def emit(self, run_id: str, event_type: str, data: dict):
        if run_id in self.listeners:
            await self.listeners[run_id].put({
                "event": event_type,
                "data": data
            })

event_manager = EventManager()
