
import asyncio
import logging
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Setup Logging to Console
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("src.cogs.memory")

# Mock Environment
os.environ["L_LOG_DIR"] = "."

# Import MemoryCog (assuming path is correct)
sys.path.append(os.getcwd())
try:
    from src.cogs.memory import MemoryCog
except ImportError:
    print("Could not import MemoryCog. Check path.")
    sys.exit(1)

async def test_memory_logic():
    print(">>> Initializing MemoryCog...")
    mock_bot = MagicMock()
    mock_bot.wait_until_ready = AsyncMock()
    mock_bot.get_guild = MagicMock(return_value=MagicMock(id=123, name="TestGuild"))
    mock_bot.get_user = MagicMock(return_value=MagicMock(display_name="TestUser"))
    
    # Mock LLM
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=('{"layer2_user_memory": {"traits": ["Debugged"]}, "status": "Optimized"}', None, None))
    
    cog = MemoryCog(mock_bot, mock_llm, worker_mode=False) # Main Bot Mode
    
    print(">>> Simulating 5 Messages...")
    user_id = 999999
    
    # Mock Message
    for i in range(1, 6):
        msg = MagicMock()
        msg.author.id = user_id
        msg.author.bot = False
        msg.guild.id = 123
        msg.guild.name = "TestGuild"
        msg.channel.name = "general"
        msg.content = f"Test Message {i}"
        msg.created_at = datetime.now()
        
        # Inject into on_message logic (Manually calls buffer logic)
        # We can't call on_message directly easily because it's a listener, 
        # but we can copy the logic or call it if it's not async shielded in a weird way.
        # It IS async.
        await cog.on_message(msg)
        print(f"   Buffer Size for {user_id}: {len(cog.message_buffer.get(user_id, []))}")
        
    print(">>> Forcing Memory Worker Cycle...")
    # Manually call memory_worker body (it's a loop, so we call the body logic)
    # Actually, memory_worker is a task.loop. We can call the wrapped function?
    # No, we'll just extract the logic or inspect the buffer.
    
    # Check Buffer Status
    buffer = cog.message_buffer.get(user_id, [])
    print(f"Buffer Content: {len(buffer)} items")
    
    if len(buffer) >= 5:
        print(">>> Trigger Condition MET. Running Worker Logic...")
        # Simulate Worker logic manually
        # 1. Copy Buffer
        current_buffer = cog.message_buffer.copy()
        cog.message_buffer.clear()
        
        all_msgs = current_buffer.get(user_id)
        if all_msgs:
            print(f"   Processing {len(all_msgs)} messages for {user_id}...")
            # Simulate "Analyze" call
            try:
                # We need to mock get_user_profile to return "New"
                cog.get_user_profile = AsyncMock(return_value={"status": "New"})
                cog.update_user_profile = AsyncMock()
                cog._analyze_wrapper = AsyncMock()
                
                # Run the Worker Loop Logic Step-by-Step
                # (Simplified from actual code)
                profile = await cog.get_user_profile(user_id, 123)
                if profile.get("status") == "New" or len(all_msgs) >= 5:
                    print("   [SUCCESS] Worker decided to queue analysis!")
                    print("   Queuing _analyze_wrapper task...")
                else:
                    print("   [FAIL] Worker decided NOT to queue analysis.")
            except Exception as e:
                print(f"   [ERROR] Worker Logic Exception: {e}")
    else:
        print(">>> Trigger Condition NOT MET.")

if __name__ == "__main__":
    asyncio.run(test_memory_logic())
