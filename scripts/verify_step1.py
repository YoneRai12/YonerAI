import requests
import uuid
import json
import sys

BASE_URL = "http://localhost:8001/v1"

def print_result(name, passed, msg=""):
    icon = "✅" if passed else "❌"
    print(f"{icon} {name}: {msg}")

def test_schema_validation():
    print(f"\n--- Test 1: Schema Validation (422 Manual) ---")
    # Missing user_identity and idempotency_key
    payload = {"content": "Invalid Request"}
    try:
        res = requests.post(f"{BASE_URL}/messages", json=payload)
        if res.status_code == 422:
            data = res.json()
            if "manual" in data:
                print_result("422 Manual Check", True, "Received 'manual' with examples.")
                print(f"   Note: {data['manual']['notes']}")
                return True
            else:
                print_result("422 Manual Check", False, "Got 422 but missing 'manual' field.")
        else:
            print_result("422 Manual Check", False, f"Expected 422, got {res.status_code}")
    except Exception as e:
        print_result("422 Manual Check", False, f"Connection failed: {e}")
    return False

def test_idempotency():
    print(f"\n--- Test 2: Idempotency & Replay ---")
    
    idem_key = str(uuid.uuid4())
    user_id_data = {"provider": "web", "id": "verifier", "display_name": "Tester"}
    
    payload = {

        "conversation_id": None,
        "user_identity": user_id_data,
        "content": "First Try",
        "attachments": [],
        "idempotency_key": idem_key
    }
    
    # First Attempt
    try:
        res1 = requests.post(f"{BASE_URL}/messages", json=payload)
        if res1.status_code != 200:
            print(f"First request failed: {res1.text}")
            return False
            
        data1 = res1.json()
        run_id_1 = data1["run_id"]
        conv_id_1 = data1["conversation_id"]
        print(f"1st Run ID: {run_id_1}")
        
        # Second Attempt (Same Key)
        res2 = requests.post(f"{BASE_URL}/messages", json=payload)
        data2 = res2.json()
        run_id_2 = data2["run_id"]
        print(f"2nd Run ID: {run_id_2}")
        
        if run_id_1 == run_id_2:
            print_result("Idempotency", True, "Run IDs match (Replay worked).")
            return True
        else:
            print_result("Idempotency", False, "Run IDs DO NOT match (Dedup failed).")
            return False
            
    except Exception as e:
        print(f"Idempotency test failed: {e}")
        return False

if __name__ == "__main__":
    print("Verifying Step 1: Canonical Schema & Idempotency...")
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
        
    s1 = test_schema_validation()
    s2 = test_idempotency()
    
    if s1 and s2:
        print("\n✨ ALL TESTS PASSED! Step 1 is complete.")
    else:
        print("\n⚠️ SOME TESTS FAILED.")
