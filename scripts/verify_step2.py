import requests
import uuid
import json
import sseclient # Requests can't handle SSE easily natively, but we can iterate lines

BASE_URL = "http://localhost:8001/v1"

def test_brain_stream():
    print(f"\n--- Test 3: Brain Integration (Streaming) ---")
    
    idem_key = str(uuid.uuid4())
    user_id = f"tester-{str(uuid.uuid4())[:8]}"
    
    payload = {
        "conversation_id": None,
        "user_identity": {"provider": "web", "id": user_id, "display_name": "BrainTester"},
        "content": "Hello Brain",
        "attachments": [],
        "idempotency_key": idem_key
    }
    
    
    # try removed
    
    res = requests.post(f"{BASE_URL}/messages", json=payload)
    if res.status_code != 200:
        print(f"❌ API Failed: {res.text}")
        return
        
    data = res.json()
    run_id = data["run_id"]
    print(f"Run ID: {run_id}")
    
    # Connect to SSE
    print("Connecting to Event Stream...")
    url = f"{BASE_URL}/runs/{run_id}/events"
    
    full_text = ""
    with requests.get(url, stream=True) as stream_response:
        for line in stream_response.iter_content(chunk_size=None):
            if line:
                decoded = line.decode('utf-8')
                print(f"[RAW]: {decoded}", end="")
                full_text += decoded
    
    if "I see you are BrainTester" in full_text:
        print("\n✅ ContextBuilder Logic Verified (Name injection).")
    else:
        print("\n❌ ContextBuilder Logic FAILED (Name missing).")

    if "read your memory file" in full_text:
            print("✅ Brain Mock Logic Verified.")



if __name__ == "__main__":
    test_brain_stream()
