import os
import json
import urllib.request
import urllib.error

def load_env_manual(filepath=".env"):
    env_vars = {}
    if not os.path.exists(filepath):
        return env_vars
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    return env_vars

def test_webhook():
    print("Loading .env manually...")
    env = load_env_manual()
    
    url = env.get("PHOENIX_DISCORD_WEBHOOK_URL")
    if not url:
        print("ERROR: PHOENIX_DISCORD_WEBHOOK_URL is not set in .env")
        return

    print(f"URL found: {url[:10]}... (masked)")

    payload = {
        "content": "🔔 **Notifications Test**\nIf you see this, the system is working!"
    }
    
    print("Sending request...")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Phoenix/1.0"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            print(f"Success! Status Code: {res.status}")
            print(f"Response: {res.read().decode('utf-8')}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        print(f"Body: {e.read().decode('utf-8')}")
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
    except Exception as e:
        print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    test_webhook()
