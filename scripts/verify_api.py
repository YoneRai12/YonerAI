import requests
import sys
import time

API_URL = "http://127.0.0.1:8001"

def check_api():
    print(f"Checking API at {API_URL}...")
    try:
        # 1. Health Check
        resp = requests.get(f"{API_URL}/docs")
        if resp.status_code == 200:
            print("✅ API is responding (Docs accessible)")
        else:
            print(f"❌ API responded with {resp.status_code}")
            return False

        # 2. Functional Check (Create Message)
        payload = {
            "conversation_id": "verify-script-conv",
            "content": "Is API working?",
            "idempotency_key": f"verify-{int(time.time())}"
        }
        # Use a new conversation scope if needed, or rely on auto-create default
        print("Sending test message...")
        resp = requests.post(f"{API_URL}/v1/messages", json=payload)
        
        if resp.status_code == 200:
            data = resp.json()
            print("✅ API Functional! Response:")
            print(data)
            return True
        else:
            print(f"❌ API Error: {resp.status_code}")
            print(resp.text)
            return False

    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return False

if __name__ == "__main__":
    success = check_api()
    if not success:
        sys.exit(1)
