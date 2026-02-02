import asyncio
import json
import uuid

import aiohttp


async def test_proxy_dispatch():
    base_url = "http://localhost:8001"
    
    # 1. Send message that triggers a proxy tool (e.g. music_play)
    payload = {
        "user_identity": {
            "provider": "discord",
            "id": "test-user-123",
            "display_name": "Tester"
        },
        "content": "Play some lo-fi music",
        "attachments": [],
        "idempotency_key": str(uuid.uuid4()),
        "stream": True,
        "context_binding": {
            "provider": "discord",
            "kind": "dm",
            "external_id": "dm:test-user-123"
        }
    }
    
    print("--- Step 1: Sending Message to Core ---")
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{base_url}/v1/messages", json=payload) as resp:
            if resp.status != 200:
                print(f"Error: {await resp.text()}")
                return
            data = await resp.json()
            run_id = data["run_id"]
            print(f"Run ID: {run_id}")

    # 2. Listen to SSE for 'dispatch' event
    print("\n--- Step 2: Listening for SSE Events ---")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/v1/runs/{run_id}/events") as resp:
            async for line in resp.content:
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data: "):
                    event_data = json.loads(line_str[6:])
                    event_type = event_data.get("event")
                    print(f"Event: {event_type}")
                    
                    if event_type == "dispatch":
                        print("✅ FOUND DISPATCH EVENT!")
                        print(f"Action: {json.dumps(event_data.get('data'), indent=2)}")
                    
                    if event_type == "final":
                        print(f"Final Response: {event_data.get('data', {}).get('text')}")
                        break

if __name__ == "__main__":
    # We assume 'python -m ora_core.main' is running in another terminal
    print("Note: Ensure ORA Core is running on localhost:8001")
    asyncio.run(test_proxy_dispatch())
