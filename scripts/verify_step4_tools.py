import asyncio
import sys
import uuid
import traceback
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add core to path
root = Path(__file__).parent.parent
sys.path.append(str(root / "core" / "src"))

async def test_phase6_mcp_hardened_final():
    print("Running Hardened Verification Final: Full Safety + Lease + Overwrite...")
    
    # Override DB environment for test
    TEST_DB_NAME = "test_ora_hardened_final.db"
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)
    
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_NAME}"
    
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, update as sqlalchemy_update
    engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB_NAME}")
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    from ora_core.database.models import Base, User, ToolCall
    from ora_core.database.repo import Repository
    from ora_core.mcp.registry import tool_registry, ToolDefinition
    from ora_core.mcp.runner import ToolRunner

    # Re-register tools for test (to ensure they exist in this session)
    async def gpu_handler(args):
        await asyncio.sleep(2.0)
        return {"msg": "gpu_done"}
    
    tool_registry.register_tool(
        ToolDefinition(name="gpu_slow", description="Slow GPU tool", parameters={}, gpu_required=True, timeout_sec=5),
        gpu_handler
    )

    try:
        summary = {}
        # Ensure tables exist for test
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Pre-create test user
        async with AsyncSessionLocal() as session:
            test_user = User(id="test_user_1")
            session.add(test_user)
            await session.commit()

        run_id = str(uuid.uuid4())
        user_id = "test_user_1"

        async def run_in_new_session(call_id, uid, tool="echo_tool", client="web", args=None):
            if args is None: args = {"text": "hello"}
            async with AsyncSessionLocal() as s:
                r = Repository(s)
                tr = ToolRunner(r)
                return await tr.run_tool(call_id, run_id, uid, tool, args, client)

        # --- CASE 1: Client Authorization ---
        print("\nCase 1: Client Authorization...")
        tool_registry.register_tool(
            ToolDefinition(name="admin_only", description="Admin only", parameters={}, allowed_clients=["api"]),
            lambda x: asyncio.sleep(0)
        )
        res1 = await run_in_new_session("call_auth_1", user_id, "admin_only", client="discord")
        if res1.get("status") == "failed" and "not authorized" in res1.get("error", ""):
            print("SUCCESS: Discord blocked from admin_only.")
            summary["case1_auth"] = "success"

        # --- CASE 2: Idempotency (Cached) ---
        print("\nCase 2: Idempotency (Cached)...")
        await run_in_new_session("idem_1", user_id, "echo_tool", args={"text": "first"})
        res2 = await run_in_new_session("idem_1", user_id, "echo_tool", args={"text": "second"})
        if res2.get("result", {}).get("msg") == "first": # Should return original
            print("SUCCESS: Cached result returned.")
            summary["case2_idempotency"] = "success"

        # --- CASE 4: GPU Concurrency ---
        print("\nCase 4: GPU Concurrency...")
        start = asyncio.get_event_loop().time()
        results = await asyncio.gather(
            run_in_new_session("gpu_1", user_id, "gpu_slow"),
            run_in_new_session("gpu_2", user_id, "gpu_slow")
        )
        duration = asyncio.get_event_loop().time() - start
        if duration >= 4.0:
            print(f"SUCCESS: GPU tasks ran sequentially ({duration:.1f}s).")
            summary["case4_gpu"] = "success"

        # --- CASE 5: In-Progress Polling ---
        print("\nCase 5: In-Progress Polling...")
        # Start A, then B starts immediately with same ID
        task_A = asyncio.create_task(run_in_new_session("poll_1", user_id, "gpu_slow"))
        await asyncio.sleep(0.5)
        res_B = await run_in_new_session("poll_1", user_id, "gpu_slow")
        res_A = await task_A
        if res_B == res_A:
            print("SUCCESS: Polling worker shared result.")
            summary["case5_polling"] = "success"

        # --- CASE 6: Zombie Recovery ---
        print("\nCase 6: Zombie Recovery...")
        async with AsyncSessionLocal() as s:
            zombie = ToolCall(id="zombie_1", run_id=run_id, user_id=user_id, tool_name="echo_tool", 
                              args_json={}, status="running", expires_at=datetime.utcnow() - timedelta(hours=1))
            s.add(zombie)
            await s.commit()
        res6 = await run_in_new_session("zombie_1", user_id, "echo_tool")
        if res6.get("status") == "completed":
            print("SUCCESS: Zombie recovered.")
            summary["case6_zombie"] = "success"

        # --- CASE 8: Ghost Overwrite Protection ---
        print("\nCase 8: Ghost Overwrite Protection...")
        ghost_call_id = "ghost_1"
        lease_A = "OLD_LEASE"
        async with AsyncSessionLocal() as s:
            # Manually seed a call claimed by OLD_LEASE
            c = ToolCall(id=ghost_call_id, run_id=run_id, user_id=user_id, tool_name="echo_tool", 
                         args_json={}, status="running", lease_token=lease_A, 
                         expires_at=datetime.utcnow() - timedelta(seconds=1)) # stale
            s.add(c)
            await s.commit()
        
        # New winner B claims it
        async with AsyncSessionLocal() as s:
            repo = Repository(s)
            lease_B = "NEW_LEASE"
            claimed_B = await repo.claim_tool_call(ghost_call_id, user_id, lease_B, datetime.utcnow() + timedelta(minutes=1))
            
            if claimed_B:
                # Old ghost A tries to update
                await repo.update_tool_call(ghost_call_id, user_id, "completed", lease_token=lease_A, result={"msg": "ghost"})
                
                # Verify DB - should still be running by lease_B
                stmt = select(ToolCall).where(ToolCall.id == ghost_call_id)
                res = await s.execute(stmt)
                rec = res.scalar_one()
                if rec.status == "running" and rec.lease_token == lease_B:
                    print("SUCCESS: Ghost overwrite blocked.")
                    summary["case8_ghost"] = "success"

        # Save Summary
        summary_path = root / "scripts" / "verify_summary_final.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f)
        print(f"\nFinal Summary: {summary}")

    except Exception:
        traceback.print_exc()
    finally:
        await engine.dispose()
        if os.path.exists(TEST_DB_NAME):
            os.remove(TEST_DB_NAME)

if __name__ == "__main__":
    asyncio.run(test_phase6_mcp_hardened_final())
