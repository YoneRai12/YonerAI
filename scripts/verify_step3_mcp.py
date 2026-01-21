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

from ora_core.database.session import create_async_engine, async_sessionmaker, AsyncSession
from ora_core.database.models import Base
from ora_core.database.repo import Repository
from ora_core.mcp.client import mcp_client_manager
from ora_core.mcp.runner import ToolRunner
from ora_core.mcp.registry import tool_registry

# USE TEST DB
TEST_DB = "sqlite+aiosqlite:///test_mcp.db"
test_engine = create_async_engine(TEST_DB)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

async def test_mcp_integration():
    # 1. Start MCP Client & Connect to mock artist
    mock_server_script = str(Path(__file__).resolve().parent / "mock_mcp_artist.py")
    
    # We use sys.executable to ensure we use the same python environment
    try:
        await mcp_client_manager.connect_stdio(
            "mcp-artist",
            sys.executable,
            [mock_server_script]
        )
        
        # 2. Check if tool is registered
        t_name = "mcp-artist_generate_artwork"
        definition = tool_registry.get_definition(t_name)
        if not definition:
            print(f"FAILED: Tool {t_name} not found in registry.")
            return

        print(f"SUCCESS: Tool {t_name} registered correctly.")
        
        # 3. Execute via ToolRunner
        async with TestSession() as session:
            repo = Repository(session)
            runner = ToolRunner(repo)
            
            run_id = str(uuid.uuid4())
            user_id = "test_user"
            tool_call_id = "call_mcp_123"
            
            print(f"Executing {t_name} via ToolRunner...")
            result = await runner.run_tool(
                tool_call_id=tool_call_id,
                run_id=run_id,
                user_id=user_id,
                tool_name=t_name,
                args={"prompt": "A futuristic city in space"},
                client_type="web"
            )
            
            print(f"Result Status: {result['status']}")
            
            # Check content
            tool_res = result.get("result", {})
            if tool_res.get("ok"):
                content = tool_res["content"][0]["text"]
                print(f"Tool Output Content: {content}")
                if "Artwork generated" in content:
                    print("\n--- MCP INTEGRATION (Trial): PASS ---")
                else:
                    print("\n--- MCP INTEGRATION (Trial): FAIL (Content mismatch) ---")
            else:
                print(f"\n--- MCP INTEGRATION (Trial): FAIL (Error: {tool_res.get('error')}) ---")

    finally:
        await mcp_client_manager.shutdown()

if __name__ == "__main__":
    asyncio.run(setup_db())
    asyncio.run(test_mcp_integration())
