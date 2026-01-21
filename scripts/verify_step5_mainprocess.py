import asyncio
import sys
import uuid
import json
import os
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add core to path
root = Path(__file__).parent.parent
sys.path.append(str(root / "core" / "src"))

async def test_main_process_tool_loop():
    print("Running MainProcess Tool Loop Verification...")
    
    # 1. Setup isolated DB
    TEST_DB = "test_main_process.db"
    if os.path.exists(TEST_DB): os.remove(TEST_DB)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"
    
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB}")
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    from ora_core.database.models import Base
    from ora_core.brain.process import MainProcess
    from ora_core.api.schemas.messages import MessageRequest
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Mock OmniEngine responses
    # Turn 1: Call google_search
    # Turn 2: Final response
    mock_turn1 = MagicMock()
    mock_turn1.message.content = "Let me search for that."
    
    gs_call = MagicMock()
    gs_call.id = "gs_123"
    gs_call.function.name = "google_search"
    gs_call.function.arguments = json.dumps({"query": "current status of ORA project"})
    mock_turn1.message.tool_calls = [gs_call]
    
    mock_turn2 = MagicMock()
    mock_turn2.message.content = "I found some information about ORA: it is a hardened AI system."
    mock_turn2.message.tool_calls = None
    
    # Setup the mock
    with patch("ora_core.engine.omni_engine.omni_engine.generate_response") as mock_gen:
        mock_gen.side_effect = [
            MagicMock(choices=[mock_turn1]),
            MagicMock(choices=[mock_turn2])
        ]
        
        # 3. Create Prerequisites (Conversation & Run)
        convo_id = str(uuid.uuid4())
        run_id = str(uuid.uuid4())
        user_id = "test_user_id_1"
        
        async with AsyncSessionLocal() as session:
            from ora_core.database.models import User, Conversation, Run, ConversationScope, RunStatus
            # Create User
            user = User(id=user_id)
            session.add(user)
            # Create Conversation
            convo = Conversation(id=convo_id, title="Test Tool Loop", user_id=user_id, scope=ConversationScope.personal)
            session.add(convo)
            # Create Run
            run = Run(id=run_id, conversation_id=convo_id, user_id=user_id, status=RunStatus.queued)
            session.add(run)
            await session.commit()

        # 4. Execute MainProcess
        async with AsyncSessionLocal() as session:
            request = MessageRequest(
                conversation_id=convo_id,
                content="Echo this",
                user_identity={"provider": "web", "id": "u1_tester", "display_name": "Tester"},
                idempotency_key="idempotency_key_final_123",
                stream=False,
                source="web"
            )
            
            process = MainProcess(run_id, request.conversation_id, request, session)
            
            print("Step: Execution...")
            await process.run()
            
            # 4. Verification
            from ora_core.database.repo import Repository, RunStatus
            repo = Repository(session)
            run = await repo.get_run(run_id)
            print(f"Run Status: {run.status}")
            
            # Check ToolCall record
            from ora_core.database.models import ToolCall
            from sqlalchemy import select
            res = await session.execute(select(ToolCall).where(ToolCall.run_id == run_id))
            calls = res.scalars().all()
            print(f"Tool Calls found: {len(calls)}")
            for c in calls:
                print(f"  - {c.tool_name}: {c.status} (Result: {c.result_json})")

            if run.status == RunStatus.completed and len(calls) == 1:
                print("\nSUCCESS: MainProcess successfully executed the tool loop.")
            else:
                print("\nFAILED: MainProcess loop failed.")

    await engine.dispose()
    if os.path.exists(TEST_DB): os.remove(TEST_DB)

if __name__ == "__main__":
    asyncio.run(test_main_process_tool_loop())
