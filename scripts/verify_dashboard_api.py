import requests
import sys

def verify_dashboard_api():
    url = "http://localhost:8000/api/dashboard/summary"
    try:
        print(f"Testing {url}...")
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print("Unknown Success: API returned 200 OK")
            print("Data keys:", data.keys())
            
            required_keys = ["total_runs", "tools", "recent_tool_calls"]
            missing_keys = [k for k in required_keys if k not in data]
            
            if not missing_keys:
                print("Validation Passed: All required keys present.")
                return True
            else:
                print(f"Validation Failed: Missing keys {missing_keys}")
                return False
        else:
            print(f"Validation Failed: Status code {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("Connection Error: Is the API server running on port 8000?")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    if verify_dashboard_api():
        sys.exit(0)
    else:
        sys.exit(1)
