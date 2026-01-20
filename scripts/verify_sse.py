import requests
import sseclient
import json
import sys

API_URL = "http://127.0.0.1:8001"

def verify_sse():
    print(f"Creating message at {API_URL}...")
    
    # 1. Create Message
    payload = {
        "conversation_id": "verify-sse-conv",
        "content": "Hello via SSE",
        "idempotency_key": "sse-test-123"
    }
    
    try:
        resp = requests.post(f"{API_URL}/v1/messages", json=payload)
        resp.raise_for_status()
        data = resp.json()
        run_id = data["run_id"]
        print(f"✅ Message Created. Run ID: {run_id}")
        
    except Exception as e:
        print(f"❌ Failed to create message: {e}")
        return False

    # 2. Listen to SSE
    print(f"Connecting to SSE stream for run {run_id}...")
    stream_url = f"{API_URL}/v1/runs/{run_id}/events"
    
    try:
        with requests.get(stream_url, stream=True) as response:
            print("✅ SSE Connected. Waiting for events...")
            event_type = None
            full_text = ""
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("event:"):
                        event_type = decoded_line.split(":", 1)[1].strip()
                    elif decoded_line.startswith("data:"):
                        data_str = decoded_line.split(":", 1)[1].strip()
                        print(f"[{event_type}] {data_str}")
                        
                        try:
                            data = json.loads(data_str)
                            if event_type == "delta":
                                text = data.get("text", "")
                                full_text += text
                                # print(f"  Delta: {text}")
                            elif event_type == "final":
                                print(f"✅ FINAL RESPONSE: {data.get('text')}")
                                return True
                            elif event_type == "error":
                                print(f"❌ ERROR: {data.get('text')}")
                                return False
                        except json.JSONDecodeError:
                            pass
                            
        print("❌ Stream ended without 'final' event.")
        return False
            
    except Exception as e:
        print(f"❌ SSE Connection Failed: {e}")
        return False

if __name__ == "__main__":
    if not verify_sse():
        sys.exit(1)
