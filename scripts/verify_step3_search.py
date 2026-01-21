import asyncio
import sys
import uuid
import os
from pathlib import Path
from dotenv import load_dotenv

# Add core to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "core" / "src"))

# Load env before imports
load_dotenv()

from ora_core.database.session import AsyncSessionLocal
from ora_core.database.models import Base, RunStatus
from ora_core.database.repo import Repository
from ora_core.brain.process import MainProcess
from ora_core.api.schemas.messages import MessageRequest, UserIdentity
from ora_core.engine.simple_worker import event_manager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# USE TEST DB
TEST_DB = "sqlite+aiosqlite:///test_search.db"
test_engine = create_async_engine(TEST_DB)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

async def test_search_cycle():
    async with TestSession() as session:
        repo = Repository(session)
        
        # 1. Setup User & Conversation
        user = await repo.get_or_create_user("web", "search_user", "SearchTester")
        conv = await repo.get_or_create_conversation(None, user.id)
        
        # Create Run record
        from ora_core.database.models import Run
        run_id = str(uuid.uuid4())
        run_obj = Run(
            id=run_id,
            conversation_id=conv.id,
            user_id=user.id,
            status=RunStatus.queued,
            idempotency_key="test-idempotency-key-search"
        )
        session.add(run_obj)
        await session.commit()
        
        # 2. Mock OmniEngine to force tool usage
        from unittest.mock import AsyncMock, MagicMock
        from ora_core.engine import omni_engine as engine_module

        # Mock response object structure
        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.function.name = "google_search"
        mock_tc.function.arguments = '{"query": "Japan Prime Minister"}'

        mock_msg_tool = MagicMock()
        mock_msg_tool.content = None
        mock_msg_tool.tool_calls = [mock_tc]

        mock_msg_final = MagicMock()
        mock_msg_final.content = "日本の首相は石破茂氏です。"
        mock_msg_final.tool_calls = None

        mock_resp_tool = MagicMock()
        mock_resp_tool.choices = [MagicMock(message=mock_msg_tool)]

        mock_resp_final = MagicMock()
        mock_resp_final.choices = [MagicMock(message=mock_msg_final)]

        engine_module.omni_engine.generate = AsyncMock(side_effect=[mock_resp_tool, mock_resp_final])

        # 3. Mock SSE listener to see events
        async def listener():
            async for event in event_manager.listen(run_id):
                print(f"[SSE EVENT] {event['event']}: {event['data']}")
                if event['event'] == "final":
                    break

        listen_task = asyncio.create_task(listener())
        
        # 4. Request
        request = MessageRequest(
            conversation_id=conv.id,
            content="今の日本の首相は誰ですか？",
            user_identity=UserIdentity(provider="web", id="search_user"),
            source="web",
            stream=False,
            idempotency_key="test-idempotency-key-search"
        )
        
        print("\n--- Starting Cognitive Cycle ---\n")
        process = MainProcess(run_id, conv.id, request, session)
        await process.run()
        
        # Give some time for listener to finish
        await asyncio.sleep(2)
        listen_task.cancel()
        
        # 4. Verify DB Records
        run = await repo.get_run(run_id)
        assert run.status == RunStatus.completed
        
        from sqlalchemy import select
        from ora_core.database.models import ToolCall
        stmt = select(ToolCall).where(ToolCall.run_id == run_id)
        calls = (await session.execute(stmt)).scalars().all()
        
        print(f"\nTool Calls Found: {len(calls)}")
        for c in calls:
            print(f"- Tool: {c.tool_name}")
            print(f"  Status: {c.status}")
            print(f"  Latency: {c.latency_ms}ms")
            print(f"  Result Summary: {str(c.result_json)[:100]}...")

        if len(calls) > 0:
            print("\n--- SEARCH VERTICAL SLICE: PASS ---")
        else:
            print("\n--- SEARCH VERTICAL SLICE: NO TOOLS CALLED (Maybe LLM thought it knew?) ---")

if __name__ == "__main__":
    asyncio.run(setup_db())
    asyncio.run(test_search_cycle())
