import asyncio
import sys
import uuid
import os
from pathlib import Path

# Add core to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "core" / "src"))

from ora_core.database.session import engine, AsyncSessionLocal
from ora_core.database.models import Base, ConversationBinding, Conversation
from ora_core.database.repo import Repository
from ora_core.api.schemas.messages import MessageRequest, UserIdentity, ContextBinding

async def setup_db():
    async with engine.begin() as conn:
        # Create tables (ConversationBinding, etc.)
        await conn.run_sync(Base.metadata.create_all)

async def test_binding_resolution():
    async with AsyncSessionLocal() as session:
        repo = Repository(session)
        user_id = str(uuid.uuid4())
        
        # Identity
        identity = UserIdentity(provider="discord", id="123456", display_name="TestUser")
        user = await repo.get_or_create_user(identity.provider, identity.id, identity.display_name)
        
        # Test 1: DM Binding
        print("Testing DM Binding...")
        dm_binding = ContextBinding(provider="discord", kind="dm", external_id="dm:123456")
        req1 = MessageRequest(
            user_identity=identity,
            content="Hello DM",
            idempotency_key="idem-dm-1",
            context_binding=dm_binding
        )
        
        conv_id1 = await repo.resolve_conversation(user.id, None, dm_binding.model_dump())
        print(f"DM Conv ID: {conv_id1}")
        
        # Send again should return same
        conv_id1_replay = await repo.resolve_conversation(user.id, None, dm_binding.model_dump())
        assert conv_id1 == conv_id1_replay, "DM conversion must be stable"
        print("DM Binding: SUCCESS")

        # Test 2: Channel Binding
        print("Testing Channel Binding...")
        chan_binding = ContextBinding(provider="discord", kind="channel", external_id="guild:1:chan:A")
        conv_id_chan = await repo.resolve_conversation(user.id, None, chan_binding.model_dump())
        print(f"Channel Conv ID: {conv_id_chan}")
        assert conv_id1 != conv_id_chan, "Channel must have different conversation than DM"
        
        # Replay Channel
        conv_id_chan_replay = await repo.resolve_conversation(user.id, None, chan_binding.model_dump())
        assert conv_id_chan == conv_id_chan_replay, "Channel conversion must be stable"
        print("Channel Binding: SUCCESS")

        # Test 3: Idempotency re-verification via repo call
        print("Testing Idempotency Re-verification...")
        # Create a run first
        msg, run = await repo.create_user_message_and_run(
            conversation_id=conv_id1,
            user_id=user.id,
            content="Hello",
            attachments=[],
            idempotency_key="fixed-idempotency-key"
        )
        
        # Try to find by idempotency
        existing_run = await repo.get_run_by_idempotency(user.id, "fixed-idempotency-key")
        assert existing_run is not None
        assert existing_run.id == run.id
        print("Idempotency: SUCCESS")

if __name__ == "__main__":
    asyncio.run(setup_db())
    asyncio.run(test_binding_resolution())
    print("\n--- ALL TESTS PASSED ---")
