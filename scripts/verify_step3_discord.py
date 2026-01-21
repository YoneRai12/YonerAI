import asyncio
import aiohttp
import json
import uuid
import sys
from pathlib import Path

# Add core & project root to path
root = Path(__file__).parent.parent
sys.path.append(str(root / "core" / "src"))
sys.path.append(str(root))

async def test_discord_thin_client_flow():
    print("🚀 Testing Discord Thin Client Flow...")
    
    # 1. Simulate Discord Bot 'send_message' (delegation)
    base_url = "http://localhost:8001" # core_port
    
    payload = {
        "conversation_id": None,
        "user_identity": {
            "provider": "discord",
            "id": "123456789",
            "display_name": "TestUser"
        },
        "content": "Hello Core, this is Discord bot. Do you have my memory?",
        "idempotency_key": str(uuid.uuid4()),
        "stream": False
    }

    # Use the real CoreAPIClient to simulate the bot
    from src.utils.core_client import CoreAPIClient
    client = CoreAPIClient(base_url)

    print("\nStep 1: Sending message to Core...")
    resp_data = await client.send_message(
        content=payload["content"],
        provider_id=payload["user_identity"]["id"],
        display_name=payload["user_identity"]["display_name"],
        stream=False
    )
    
    if "error" in resp_data:
        print(f"❌ Failed to send message: {resp_data['error']}")
        return
        
    run_id = resp_data.get("run_id")
    print(f"✅ Message sent! Run ID: {run_id}")

    # 2. Simulate Discord Bot SSE Listener for final response
    print(f"\nStep 2: Listening for 'final' event on Run {run_id}...")
    final_text = await client.get_final_response(run_id)
    
    if final_text:
        print(f"\n✅ SUCCESS: Final AI Response received:")
        print(f"----------------------------------------")
        print(final_text)
        print(f"----------------------------------------")
    else:
        print("❌ Failed to receive final response.")

        # 3. Verify Memory Sync (Layer 4)
        print("\nStep 3: Verifying L:\ORA_Memory Sync...")
        # We check the memory file directly if accessible, or assume it worked if Core says so
        from ora_core.brain.memory import memory_store
        profile = await memory_store.read_user_profile("123456789")
        if profile and "layer4_raw_logs" in profile:
            logs = profile["layer4_raw_logs"]
            if any("Hello Core" in entry.get("user", "") for entry in logs):
                print(f"✅ Memory Sync Verified! Found 'Hello Core' in layer4_raw_logs.")
            else:
                print(f"⚠️ Memory Sync Check: Log entry not found in profile. (Logs: {len(logs)})")
        else:
            print(f"❌ Memory Profile or L4 logs missing for 123456789.")

if __name__ == "__main__":
    asyncio.run(test_discord_thin_client_flow())
