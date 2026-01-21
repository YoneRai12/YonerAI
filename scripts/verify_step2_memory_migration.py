import asyncio
import sys
import uuid
import os
import json
from pathlib import Path
from datetime import datetime

# Add core to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "core" / "src"))

from ora_core.database.session import engine, AsyncSessionLocal
from ora_core.database.models import Base
from ora_core.database.repo import Repository
from ora_core.api.schemas.messages import MessageRequest, UserIdentity, ContextBinding
from ora_core.brain.context import ContextBuilder
from ora_core.brain.memory import memory_store, USER_MEMORY_DIR
from ora_core.brain.process import MainProcess

async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def test_memory_migration_and_assembly():
    discord_id = "test_discord_88"
    legacy_path = os.path.join(USER_MEMORY_DIR, f"{discord_id}.json")
    
    try:
        # 1. Setup Legacy Profile
        profile_data = {
            "id": discord_id,
            "name": "LegacyUser",
            "layer2_user_memory": {
                "facts": ["Likes Python"],
                "traits": ["Technical"],
                "impression": "Dev"
            },
            "layer3_recent_summaries": ["Discussed Step 1."],
            "layer4_raw_logs": []
        }
        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump(profile_data, f)

        async with AsyncSessionLocal() as session:
            repo = Repository(session)
            
            # 2. Setup DB State
            user = await repo.get_or_create_user("discord", discord_id, "LegacyUser")
            user_id = str(user.id)
            
            conv = await repo.get_or_create_conversation(None, user_id)
            conv_id = str(conv.id)
            
            await repo.create_user_message_and_run(conv_id, user_id, "L1 Test Message", [], "idem-l1")
            
            # 3. Test Context Assembly
            req = MessageRequest(
                user_identity=UserIdentity(provider="discord", id=discord_id, display_name="LegacyUser"),
                content="Current Question",
                idempotency_key="idem-curr",
                context_binding=None
            )
            
            print("Verifying Assembly...")
            messages = await ContextBuilder.build_context(req, user_id, conv_id, repo)
            
            # Basic checks
            sys_msg = messages[0]["content"]
            assert "LegacyUser" in sys_msg
            assert "Technical" in sys_msg
            
            history_contents = [m["content"] for m in messages if m["role"] == "user"]
            assert "L1 Test Message" in history_contents
            print("Assembly Check: PASS")

            # 4. Test L4 Update
            print("Verifying L4 Update...")
            bp = MainProcess("run-l4-test", conv_id, req, session)
            await bp._update_memory_on_completion(user_id, "User Message", "AI Response")
            
            # Check file
            with open(legacy_path, "r", encoding="utf-8") as f:
                updated = json.load(f)
                logs = updated.get("layer4_raw_logs", [])
                assert len(logs) > 0
                assert logs[0]["user"] == "User Message"
            print("L4 Update Check: PASS")

    finally:
        if os.path.exists(legacy_path):
            os.remove(legacy_path)

if __name__ == "__main__":
    asyncio.run(setup_db())
    asyncio.run(test_memory_migration_and_assembly())
    print("\n--- ALL TESTS PASSED ---")
