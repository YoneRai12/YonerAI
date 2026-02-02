import asyncio
import os
import shutil
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.services.markdown_memory import MarkdownMemory


async def verify_markdown_memory():
    print("--- Verifying Markdown Memory ---")
    test_dir = "test_data/markdown_memories"
    
    # Clean prev test
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    mem = MarkdownMemory(root_dir=test_dir)
    session_id = "test-session-001"
    
    # Test Append
    print("Testing append_message...")
    await mem.append_message(session_id, "user", "Hello Clawdbot!")
    await mem.append_message(session_id, "assistant", "Hello User!")
    
    # Verify file existence
    files = os.listdir(test_dir)
    if not files:
        print("FAILED: No file created.")
        return
        
    filename = files[0]
    print(f"File created: {filename}")
    
    with open(os.path.join(test_dir, filename), "r", encoding="utf-8") as f:
        content = f.read()
        print(f"Content:\n{content}")
        
    if "Hello Clawdbot!" in content and "Hello User!" in content:
        print("SUCCESS: Content verification passed.")
    else:
        print("FAILED: Content mismatch.")

    # Cleanup
    shutil.rmtree(test_dir)

if __name__ == "__main__":
    asyncio.run(verify_markdown_memory())
